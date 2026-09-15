import type { BrainClient } from "./brain.js";
import type { AttachmentService } from "./attachments.js";
import { signedDownload } from "./storage.js";
import type { GoogleCalendar, GoogleDrive, Gmail } from "./google-tools.js";
import { pcOpenApp, pcOpenPath, pcListFolder } from "./pc-control.js";
import type { Db } from "./db.js";

export interface ActionDeps {
  gcal: GoogleCalendar;
  gdrive: GoogleDrive;
  gmail: Gmail;
  brain?: BrainClient;
  attachments: AttachmentService;
  sessionSecret: string;
  apiBaseUrl: string;
}

export const DOCUMENT_MIME: Record<string, string> = {
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  pdf: "application/pdf",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

/** Tool per cui l'utente deve sempre confermare esplicitamente in modalità "balanced", indipendentemente
 * dal rischio stimato dal router: "gmail_send" perché un'email inviata non si può ritirare, "other" perché
 * è un'azione che il router non ha saputo classificare con precisione (prudenza per default),
 * "pc_*" perché toccano la macchina locale dell'utente — perimetro già stretto (solo app note e
 * cartelle personali, vedi pc-control.ts) ma comunque sempre confermato di default. */
const ALWAYS_APPROVE = new Set(["gmail_send", "other", "pc_open_app", "pc_open_path", "pc_list_folder"]);

const PC_TOOLS = new Set(["pc_open_app", "pc_open_path", "pc_list_folder"]);

export type ApprovalMode = "strict" | "balanced" | "full";

/** Rispecchia il selettore "Come approvare le azioni" delle Impostazioni (3 livelli, stile ChatGPT):
 * "strict" = Richiedi approvazione (mai automatico, nemmeno il rischio basso); "balanced" = Approva
 * per me (comportamento di default: automatico solo se rischio "low" e non nell'elenco sempre-da-confermare);
 * "full" = Accesso completo (mai un clic, nemmeno per gmail_send/pc_* — scelta esplicita dell'utente,
 * segnalata in rosso/arancio in UI). */
export function isAutoExecutable(tool: string, risk: string, mode: ApprovalMode = "balanced"): boolean {
  if (mode === "full") return true;
  if (mode === "strict") return false;
  return risk === "low" && !ALWAYS_APPROVE.has(tool);
}

/** Interruttori generali indipendenti dal livello di approvazione: se l'utente disattiva "Controllo
 * del PC" o "Browser" nelle Impostazioni, il relativo strumento non deve nemmeno essere proposto/eseguito,
 * a prescindere da cosa il router ha classificato. */
export function isToolAllowed(tool: string, settings: { computerUseEnabled: boolean; browserUseEnabled: boolean }): boolean {
  if (PC_TOOLS.has(tool)) return settings.computerUseEnabled;
  if (tool === "browser_task") return settings.browserUseEnabled;
  return true;
}

export interface UserToolSettings {
  approvalMode: ApprovalMode;
  computerUseEnabled: boolean;
  browserUseEnabled: boolean;
}

/** Punto unico da cui chat.ts e la decisione di approvazione in main.ts leggono le preferenze correnti —
 * lette ad ogni richiesta (non messe in cache) perché l'utente può cambiarle dalle Impostazioni in
 * qualunque momento e la modifica deve valere dal messaggio successivo, non dal prossimo riavvio. */
export async function getUserToolSettings(db: Db, userId: string): Promise<UserToolSettings> {
  const q = await db.query<{ approval_mode: ApprovalMode; computer_use_enabled: boolean; browser_use_enabled: boolean }>(
    "SELECT approval_mode,computer_use_enabled,browser_use_enabled FROM users WHERE id=$1",
    [userId],
  );
  const row = q.rows[0];
  return { approvalMode: row?.approval_mode ?? "balanced", computerUseEnabled: row?.computer_use_enabled ?? true, browserUseEnabled: row?.browser_use_enabled ?? true };
}

/** complex_task può produrre file di formati diversi da agenti diversi (rapporto .md, documenti,
 * immagini) — a differenza di image_generate/document_generate dove il formato è già noto, qui va
 * dedotto dall'estensione per scegliere un Content-Type ragionevole. */
export function guessMime(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return DOCUMENT_MIME[ext] ?? { png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", md: "text/markdown", txt: "text/plain", json: "application/json" }[ext] ?? "application/octet-stream";
}

export async function deliverGeneratedFile(deps: ActionDeps, userId: string, filename: string, mimeType: string, base64: string, label: string): Promise<string> {
  const item = await deps.attachments.saveGenerated(userId, filename, mimeType, Buffer.from(base64, "base64"));
  const signed = signedDownload(item.id, userId, deps.sessionSecret);
  const url = `${deps.apiBaseUrl.replace(/\/$/, "")}/v1/files/${item.id}?u=${userId}&expires=${signed.expires}&signature=${encodeURIComponent(signed.signature)}`;
  return `Ho generato ${label} "${filename}".\n\n[Scarica ${filename}](${url})`;
}

export async function executeAction(deps: ActionDeps, userId: string, tool: string, payload: Record<string, unknown>, summary: string, toolSettings: { computerUseEnabled: boolean; browserUseEnabled: boolean } = { computerUseEnabled: true, browserUseEnabled: true }): Promise<string> {
  if (!isToolAllowed(tool, toolSettings)) throw new Error(PC_TOOLS.has(tool) ? "controllo_pc_disattivato" : "controllo_browser_disattivato");
  const str = (v: unknown): string | undefined => (typeof v === "string" && v.trim() ? v : undefined);
  switch (tool) {
    case "calendar_create_event": {
      const title = str(payload.title) ?? summary, start = str(payload.start), end = str(payload.end);
      if (!start || !end) throw new Error("date_mancanti_nell_evento");
      const r = await deps.gcal.createEvent(userId, { title, start, end, description: str(payload.description) });
      return `Evento creato su Google Calendar: ${title}${r.htmlLink ? ` (${r.htmlLink})` : ""}`;
    }
    case "calendar_list_events": {
      const days = Number(payload.range_ ?? payload.rangeDays ?? payload.range ?? payload.range_days) || 7;
      const events = await deps.gcal.listEvents(userId, { rangeDays: days });
      if (!events.length) return `Nessun evento nei prossimi ${days} giorni.`;
      return `Prossimi eventi (${days} giorni):\n` + events.map((e) => `- ${e.title} (${e.start ?? "?"} → ${e.end ?? "?"})`).join("\n");
    }
    case "drive_save_file": {
      const name = str(payload.name) ?? "documento_ade.txt", content = str(payload.content_summary) ?? str(payload.content) ?? summary;
      const r = await deps.gdrive.saveFile(userId, { name, content });
      return `File salvato su Google Drive: ${name}${r.webViewLink ? ` (${r.webViewLink})` : ""}`;
    }
    case "drive_search_files": {
      const query = str(payload.query) ?? summary;
      const files = await deps.gdrive.searchFiles(userId, { query });
      if (!files.length) return `Nessun file trovato su Drive per "${query}".`;
      return `Trovati su Drive:\n` + files.map((f) => `- ${f.name}${f.webViewLink ? ` (${f.webViewLink})` : ""}`).join("\n");
    }
    case "gmail_send": {
      const to = str(payload.to), subject = str(payload.subject) ?? "", body = str(payload.body) ?? "";
      if (!to) throw new Error("destinatario_mancante");
      await deps.gmail.send(userId, { to, subject, body });
      return `Email inviata a ${to}.`;
    }
    case "gmail_read": {
      const query = str(payload.query);
      const messages = await deps.gmail.list(userId, { query });
      if (!messages.length) return "Nessuna email trovata.";
      return `Ultime email:\n` + messages.map((m) => `- ${m.from}: ${m.subject} — ${m.snippet}`).join("\n");
    }
    case "browser_task": {
      if (!deps.brain) throw new Error("controllo_browser_non_configurato");
      const objective = str(payload.objective) ?? str(payload.task) ?? summary;
      const result = await deps.brain.browserTask(objective);
      return result.ok ? result.summary : `Mi sono fermato: ${result.summary}`;
    }
    case "image_generate": {
      if (!deps.brain) throw new Error("generazione_immagini_non_configurata");
      const prompt = str(payload.prompt) ?? summary;
      const result = await deps.brain.imageGenerate(prompt);
      if (!result.ok || !result.base64) return `Non sono riuscita a generare un'immagine convincente: ${result.reason ?? "motivo sconosciuto"}.`;
      return deliverGeneratedFile(deps, userId, result.filename ?? "immagine.png", "image/png", result.base64, "l'immagine");
    }
    case "pc_open_app": {
      const name = str(payload.name) ?? str(payload.app) ?? summary;
      return pcOpenApp(name);
    }
    case "pc_open_path": {
      const target = str(payload.path) ?? str(payload.target);
      if (!target) throw new Error("percorso_mancante");
      return pcOpenPath(target);
    }
    case "pc_list_folder": {
      const target = str(payload.path) ?? str(payload.target);
      if (!target) throw new Error("percorso_mancante");
      return pcListFolder(target);
    }
    case "complex_task":
      // Gestito prima di arrivare qui (vedi complex-task-runtime.ts): è asincrono, non una singola
      // chiamata che può restare bloccata dietro il tetto dei 100s del proxy RunPod.
      throw new Error("complex_task_deve_passare_da_startComplexTaskJob");
    case "document_generate": {
      if (!deps.brain) throw new Error("generazione_documenti_non_configurata");
      const format = str(payload.format)?.toLowerCase();
      if (!format || !(format in DOCUMENT_MIME)) throw new Error("formato_documento_non_supportato");
      const request = str(payload.request) ?? summary;
      const result = await deps.brain.documentGenerate(format, request);
      if (!result.ok || !result.base64) return `Non sono riuscita a generare il documento: ${result.reason ?? "motivo sconosciuto"}.`;
      return deliverGeneratedFile(deps, userId, result.filename ?? `documento.${format}`, DOCUMENT_MIME[format]!, result.base64, "il documento");
    }
    default:
      throw new Error("azione_non_automatizzabile");
  }
}
