import { randomUUID } from "node:crypto";
import type { Db } from "./db.js";

export type JobStatus = "queued"|"running"|"waiting_approval"|"succeeded"|"failed"|"cancelled";
export interface JobRecord { id:string; userId:string; kind:string; status:JobStatus; attempt:number; maxAttempts:number; input:unknown }

export class JobRepository {
  constructor(private readonly db:Db) {}

  async enqueue(userId:string,idempotencyKey:string,kind:string,input:unknown,maxAttempts=3):Promise<JobRecord>{
    const id=randomUUID();
    const outboxId=randomUUID();
    await this.db.query("BEGIN");
    try{
      const inserted=await this.db.query<{id:string,user_id:string,kind:string,status:JobStatus,attempt:number,max_attempts:number,input:unknown}>(
        `INSERT INTO jobs(id,user_id,idempotency_key,kind,input,status,max_attempts)
         VALUES($1,$2,$3,$4,$5,'queued',$6)
         ON CONFLICT(user_id,idempotency_key) DO NOTHING
         RETURNING id,user_id,kind,status,attempt,max_attempts,input`,[id,userId,idempotencyKey,kind,JSON.stringify(input),maxAttempts]);
      const row=inserted.rows[0]??(await this.db.query<{id:string,user_id:string,kind:string,status:JobStatus,attempt:number,max_attempts:number,input:unknown}>(
        "SELECT id,user_id,kind,status,attempt,max_attempts,input FROM jobs WHERE user_id=$1 AND idempotency_key=$2",[userId,idempotencyKey])).rows[0]!;
      if(inserted.rowCount){await this.db.query(
        "INSERT INTO outbox(id,aggregate_type,aggregate_id,event_type,payload) VALUES($1,'job',$2,'job.queued',$3)",
        [outboxId,row.id,JSON.stringify({jobId:row.id,kind})]);}
      await this.db.query("COMMIT");
      return this.map(row);
    }catch(error){await this.db.query("ROLLBACK");throw error}
  }

  async claim(workerId:string):Promise<JobRecord|undefined>{
    const q=await this.db.query<{id:string,user_id:string,kind:string,status:JobStatus,attempt:number,max_attempts:number,input:unknown}>(
      `UPDATE jobs SET status='running',attempt=attempt+1,locked_by=$1,heartbeat_at=now(),updated_at=now()
       WHERE id=(SELECT id FROM jobs WHERE status='queued' AND available_at<=now() ORDER BY priority DESC,created_at FOR UPDATE SKIP LOCKED LIMIT 1)
       RETURNING id,user_id,kind,status,attempt,max_attempts,input`,[workerId]);
    if(!q.rowCount)return undefined;
    const row=q.rows[0]!;await this.db.query(
      "INSERT INTO job_attempts(id,job_id,attempt,worker_id) VALUES($1,$2,$3,$4) ON CONFLICT(job_id,attempt) DO NOTHING",
      [randomUUID(),row.id,row.attempt,workerId]);return this.map(row)
  }

  /** Come claim(), ma per un job specifico invece del prossimo in coda — per chi crea e possiede
   * subito il proprio job nello stesso processo (es. l'hub locale che avvia un complex_task e lo
   * segue lui stesso via polling), senza passare da un worker separato che pesca dalla coda. */
  async claimById(jobId:string,workerId:string):Promise<JobRecord|undefined>{
    const q=await this.db.query<{id:string,user_id:string,kind:string,status:JobStatus,attempt:number,max_attempts:number,input:unknown}>(
      `UPDATE jobs SET status='running',attempt=attempt+1,locked_by=$1,heartbeat_at=now(),updated_at=now()
       WHERE id=$2 AND status='queued' RETURNING id,user_id,kind,status,attempt,max_attempts,input`,[workerId,jobId]);
    if(!q.rowCount)return undefined;
    const row=q.rows[0]!;await this.db.query(
      "INSERT INTO job_attempts(id,job_id,attempt,worker_id) VALUES($1,$2,$3,$4) ON CONFLICT(job_id,attempt) DO NOTHING",
      [randomUUID(),row.id,row.attempt,workerId]);return this.map(row)
  }

  /** Riferimento esterno del job (es. il task_id del pod per un complex_task) — utile per
   * diagnostica/UI e per poter riprendere il polling se l'hub si riavvia mentre un job è in corso. */
  async setExternalRef(jobId:string,ref:string){await this.db.query("UPDATE jobs SET external_ref=$1,updated_at=now() WHERE id=$2",[ref,jobId])}

  async heartbeat(jobId:string,workerId:string){const q=await this.db.query(
    "UPDATE jobs SET heartbeat_at=now(),updated_at=now() WHERE id=$1 AND locked_by=$2 AND status='running'",[jobId,workerId]);
    if(!q.rowCount)throw new Error("job_lease_lost")}

  async complete(jobId:string,workerId:string){await this.finish(jobId,workerId,"succeeded")}
  async cancel(jobId:string,userId:string){const q=await this.db.query(
    "UPDATE jobs SET status='cancelled',finished_at=now(),updated_at=now() WHERE id=$1 AND user_id=$2 AND status IN ('queued','waiting_approval')",[jobId,userId]);
    if(!q.rowCount)throw new Error("job_not_cancellable")}

  async fail(jobId:string,workerId:string,errorCode:string,retryDelaySeconds=0){
    await this.db.query("BEGIN");try{
      const q=await this.db.query<{attempt:number,max_attempts:number}>("SELECT attempt,max_attempts FROM jobs WHERE id=$1 AND locked_by=$2 AND status='running' FOR UPDATE",[jobId,workerId]);
      if(!q.rowCount)throw new Error("job_lease_lost");const row=q.rows[0]!,retry=row.attempt<row.max_attempts;
      await this.db.query(`UPDATE jobs SET status=$3,locked_by=NULL,heartbeat_at=NULL,last_error=$4,
        available_at=now()+($5*interval '1 second'),updated_at=now(),finished_at=CASE WHEN $3='failed' THEN now() ELSE NULL END WHERE id=$1 AND locked_by=$2`,
        [jobId,workerId,retry?"queued":"failed",errorCode,retryDelaySeconds]);
      await this.db.query("UPDATE job_attempts SET finished_at=now(),outcome=$3,error_code=$4 WHERE job_id=$1 AND worker_id=$2 AND finished_at IS NULL",[jobId,workerId,retry?"retry":"failed",errorCode]);
      await this.db.query("COMMIT");
    }catch(error){await this.db.query("ROLLBACK");throw error}
  }

  async unpublished(limit=100){return (await this.db.query<{id:string;event_type:string;payload:unknown}>(
    "SELECT id,event_type,payload FROM outbox WHERE published_at IS NULL ORDER BY created_at LIMIT $1",[limit])).rows}
  async markPublished(id:string){await this.db.query("UPDATE outbox SET published_at=now(),attempts=attempts+1 WHERE id=$1 AND published_at IS NULL",[id])}

  private async finish(jobId:string,workerId:string,status:JobStatus){await this.db.query("BEGIN");try{
    const q=await this.db.query("UPDATE jobs SET status=$3,finished_at=now(),updated_at=now(),locked_by=NULL WHERE id=$1 AND locked_by=$2 AND status='running'",[jobId,workerId,status]);
    if(!q.rowCount)throw new Error("job_lease_lost");await this.db.query("UPDATE job_attempts SET finished_at=now(),outcome=$3 WHERE job_id=$1 AND worker_id=$2 AND finished_at IS NULL",[jobId,workerId,status]);
    await this.db.query("INSERT INTO outbox(id,aggregate_type,aggregate_id,event_type,payload) VALUES($1,'job',$2,$3,$4)",[randomUUID(),jobId,`job.${status}`,JSON.stringify({jobId})]);await this.db.query("COMMIT");
  }catch(error){await this.db.query("ROLLBACK");throw error}}
  private map(row:{id:string;user_id:string;kind:string;status:JobStatus;attempt:number;max_attempts:number;input:unknown}):JobRecord{return{id:row.id,userId:row.user_id,kind:row.kind,status:row.status,attempt:row.attempt,maxAttempts:row.max_attempts,input:row.input}}
}
