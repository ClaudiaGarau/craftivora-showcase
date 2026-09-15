import { createClient, type RedisClientType } from "redis";

export class RedisJobQueue {
  private client: RedisClientType;
  constructor(url: string, private queue = "ade:tasks") {
    this.client = createClient({ url });
  }
  async connect() { if (!this.client.isOpen) await this.client.connect(); }
  async close() { if (this.client.isOpen) await this.client.quit(); }
  async health() { return (await this.client.ping()) === "PONG"; }
  async notify(jobId: string) { await this.client.lPush(this.queue, JSON.stringify({ id: jobId })); }
  async claim(timeoutSeconds = 1) {
    const item = await this.client.brPop(this.queue, timeoutSeconds);
    if (!item) return null;
    const parsed = JSON.parse(item.element) as { id?: unknown };
    if (typeof parsed.id !== "string" || !parsed.id) throw new Error("invalid_queue_item");
    return parsed.id;
  }
  async acquireDelivery(jobId: string, ttlSeconds = 300) {
    return (await this.client.set(`ade:delivery:${jobId}`, "1", { NX: true, EX: ttlSeconds })) === "OK";
  }
}
