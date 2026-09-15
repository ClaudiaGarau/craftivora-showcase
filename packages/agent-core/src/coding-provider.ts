import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { relative, resolve } from "node:path";

export type CodingProviderName = "codex" | "claude";
export interface CodingRequest {
  provider: CodingProviderName;
  objective: string;
  workspace: string;
  allowedRoot: string;
  timeoutMs?: number;
  maxCostCents: number;
  approvedFingerprint?: string;
}
export interface CodingEstimate {
  provider: CodingProviderName;
  model: string;
  estimatedCostCents: number;
  estimatedSeconds: number;
  transmittedData: string[];
  fingerprint: string;
}
export interface CodingResult { provider:CodingProviderName; output:string; exitCode:number; elapsedMs:number }
export type ProcessRunner=(command:string,args:string[],cwd:string,timeoutMs:number)=>Promise<{stdout:string;stderr:string;exitCode:number}>;

const fingerprint=(request:CodingRequest)=>createHash("sha256").update(JSON.stringify({
  provider:request.provider,objective:request.objective,workspace:resolve(request.workspace),maxCostCents:request.maxCostCents
})).digest("base64url");

export class CodingProvider {
  constructor(private readonly runner:ProcessRunner=runProcess){}
  estimate(request:CodingRequest):CodingEstimate{
    validate(request);
    return {provider:request.provider,model:request.provider==="codex"?"configured Codex model":"configured Claude model",estimatedCostCents:request.maxCostCents,estimatedSeconds:Math.ceil((request.timeoutMs??900_000)/1000),transmittedData:["objective","selected workspace files and command output"],fingerprint:fingerprint(request)};
  }
  async execute(request:CodingRequest):Promise<CodingResult>{
    const estimate=this.estimate(request);
    if(request.approvedFingerprint!==estimate.fingerprint)throw new Error("coding_action_not_approved");
    const timeout=Math.min(request.timeoutMs??900_000,1_800_000),started=Date.now();
    const invocation=request.provider==="codex"
      ? {command:"codex",args:["exec","--json","--sandbox","workspace-write",request.objective]}
      : {command:"claude",args:["-p",request.objective,"--output-format","json","--permission-mode","acceptEdits"]};
    const result=await this.runner(invocation.command,invocation.args,resolve(request.workspace),timeout);
    if(result.exitCode!==0)throw new Error(`${request.provider}_failed_${result.exitCode}`);
    return {provider:request.provider,output:result.stdout.slice(0,2_000_000),exitCode:result.exitCode,elapsedMs:Date.now()-started};
  }
}

function validate(request:CodingRequest){
  if(!request.objective.trim()||request.objective.length>50_000)throw new Error("invalid_coding_objective");
  if(!Number.isInteger(request.maxCostCents)||request.maxCostCents<0)throw new Error("invalid_coding_budget");
  const root=resolve(request.allowedRoot),workspace=resolve(request.workspace),rel=relative(root,workspace);
  if(rel.startsWith("..")||rel.includes(":") )throw new Error("workspace_outside_allowed_root");
}

async function runProcess(command:string,args:string[],cwd:string,timeoutMs:number){
  return new Promise<{stdout:string;stderr:string;exitCode:number}>((resolveResult,reject)=>{
    const child=spawn(command,args,{cwd,shell:false,windowsHide:true,env:process.env}),stdout:string[]=[],stderr:string[]=[];
    const timer=setTimeout(()=>{child.kill();reject(new Error("coding_provider_timeout"))},timeoutMs);
    child.stdout.on("data",chunk=>{if(stdout.join("").length<2_000_000)stdout.push(String(chunk))});
    child.stderr.on("data",chunk=>{if(stderr.join("").length<200_000)stderr.push(String(chunk))});
    child.once("error",error=>{clearTimeout(timer);reject(error)});
    child.once("close",code=>{clearTimeout(timer);resolveResult({stdout:stdout.join(""),stderr:stderr.join(""),exitCode:code??-1})});
  });
}
