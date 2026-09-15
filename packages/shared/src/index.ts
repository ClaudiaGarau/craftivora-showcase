export type Channel = "desktop" | "web" | "telegram" | "chrome";
export type Risk = "read_local" | "write_local" | "account_access" | "external_change" | "publish" | "send_message" | "spend" | "delete" | "irreversible";
export type ApprovalMode = "strict" | "balanced" | "full";
export interface UserProfile { id: string; email: string; name: string; avatarUrl?: string; approvalMode?: ApprovalMode; computerUseEnabled?: boolean; browserUseEnabled?: boolean }
export interface Attachment { id: string; name: string; mimeType: string; size: number; status: "pending"|"ready"|"rejected"; downloadUrl?: string; extractedText?: string }
export interface Message { id: string; conversationId: string; role: "user"|"assistant"|"system"; content: string; channel: Channel; attachments: Attachment[]; createdAt: string }
export interface Conversation { id: string; title: string; updatedAt: string; messages?: Message[] }
export interface Approval { id: string; userId: string; action: string; target: string; risk: Risk; dataSummary: string; consequences: string; estimatedCostCents: number; status: "pending"|"approved"|"rejected"|"expired"; expiresAt: string }
export interface CostEstimate { provider: string; model: string; estimatedCostCents: number; estimatedSeconds: number; transmittedData: string[]; configured: boolean }

export const allowedUploadTypes = new Set(["image/png","image/jpeg","image/webp","application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","text/csv","application/vnd.openxmlformats-officedocument.presentationml.presentation","application/zip","text/plain","application/json","audio/mpeg","audio/wav","video/mp4","video/webm"]);
export const shortNaturalReply = (text: string): string | undefined => ({ciao:"Ciao!",buongiorno:"Buongiorno!",buonasera:"Buonasera!",grazie:"Prego!"} as Record<string,string>)[text.trim().toLocaleLowerCase("it")];
