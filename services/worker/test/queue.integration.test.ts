import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { randomUUID } from "node:crypto";
import { RedisJobQueue } from "../src/queue.js";

const url = process.env.ADE_TEST_REDIS_URL;
describe.skipIf(!url)("RedisJobQueue real integration", () => {
  const queue = new RedisJobQueue(url!, `ade:test:${randomUUID()}`);
  beforeAll(() => queue.connect());
  afterAll(() => queue.close());
  it("notifies, claims and prevents duplicate delivery", async () => {
    const id = randomUUID();
    expect(await queue.health()).toBe(true);
    await queue.notify(id);
    expect(await queue.claim()).toBe(id);
    expect(await queue.acquireDelivery(id, 10)).toBe(true);
    expect(await queue.acquireDelivery(id, 10)).toBe(false);
  });
});
