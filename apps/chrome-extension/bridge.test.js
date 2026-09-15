import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const manifest=JSON.parse(readFileSync(new URL("./manifest.json",import.meta.url),"utf8"));
const background=readFileSync(new URL("./background.js",import.meta.url),"utf8");

describe("secure Chrome bridge",()=>{
  it("uses Native Messaging and exposes no local HTTP bridge",()=>{
    expect(manifest.permissions).toContain("nativeMessaging");
    expect(manifest.host_permissions).toBeUndefined();
    expect(background).toContain("connectNative");
    expect(background).not.toMatch(/127\.0\.0\.1|localhost|fetch\s*\(/);
  });
  it("captures only after an explicit request and queues it for desktop review",()=>{
    expect(background).toContain('message?.type==="request"');
    expect(background).toContain("snapshotActiveTab");
    expect(background).toContain('type:"request"');
  });
});
