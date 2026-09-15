import { createHmac, timingSafeEqual } from "node:crypto";
export const PROTOCOL_VERSION = "1.0" as const;
export type BrowserAction = "snapshot"|"screenshot"|"click"|"fill"|"scroll"|"upload";
export interface BrowserRequest { version: typeof PROTOCOL_VERSION; requestId: string; origin: string; action: BrowserAction; params: Record<string,unknown>; risk: "read"|"write"|"external"; preview: string; approvalId?: string; expiresAt: string; sessionId: string; signature: string }
export interface BrowserResult { version: typeof PROTOCOL_VERSION; requestId: string; ok: boolean; result?: unknown; error?: {code:string;message:string}; completedAt: string }
const canonical=(r:Omit<BrowserRequest,"signature">)=>JSON.stringify(Object.keys(r).sort().reduce<Record<string,unknown>>((a,k)=>(a[k]=(r as unknown as Record<string,unknown>)[k],a),{}));
export function signRequest(request: Omit<BrowserRequest,"signature">, secret: string): BrowserRequest { return {...request,signature:createHmac("sha256",secret).update(canonical(request)).digest("base64url")}; }
export function verifyRequest(request: BrowserRequest, secret: string, now=Date.now()): boolean { if(request.version!==PROTOCOL_VERSION||Date.parse(request.expiresAt)<=now)return false; const {signature,...unsigned}=request; const expected=createHmac("sha256",secret).update(canonical(unsigned)).digest(); let actual:Buffer; try{actual=Buffer.from(signature,"base64url")}catch{return false} return actual.length===expected.length&&timingSafeEqual(actual,expected); }
export const requiresApproval=(action:BrowserAction)=>["click","fill","scroll","upload"].includes(action);
