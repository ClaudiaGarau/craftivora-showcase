export type AgentName="ADE"|"Atena"|"Apollo"|"Argo"|"Poseidone";
export interface AgentDefinition { name:AgentName; responsibility:string; allowedTools:string[]; maxCostCents:number; timeoutMs:number; retries:number; qualityCriteria:string[] }
export const agents:Record<AgentName,AgentDefinition>={
 ADE:{name:"ADE",responsibility:"Orchestrazione, routing, memoria e sintesi",allowedTools:["delegate","memory.read","memory.write"],maxCostCents:100,timeoutMs:120000,retries:1,qualityCriteria:["risposta verificabile","nessuna azione implicita"]},
 Atena:{name:"Atena",responsibility:"Ricerca e analisi basate su fonti",allowedTools:["web.read","document.read"],maxCostCents:50,timeoutMs:90000,retries:2,qualityCriteria:["fonti citate","incertezza esplicita"]},
 Apollo:{name:"Apollo",responsibility:"Creazione di codice e contenuti",allowedTools:["artifact.create","code.test"],maxCostCents:200,timeoutMs:300000,retries:1,qualityCriteria:["output apribile","test superati"]},
 Argo:{name:"Argo",responsibility:"Qualità, sicurezza e rilascio",allowedTools:["artifact.inspect","code.test","security.scan"],maxCostCents:30,timeoutMs:180000,retries:0,qualityCriteria:["evidenza riproducibile","fail closed"]},
 Poseidone:{name:"Poseidone",responsibility:"Prodotti digitali, media, SEO e marketplace",allowedTools:["artifact.create","image.generate","marketplace.read"],maxCostCents:300,timeoutMs:600000,retries:1,qualityCriteria:["file integro","vincoli commerciali verificati"]}
};
export interface Tool<I,O>{name:string;schema:unknown;permissions:string[];execute(input:I):Promise<O>}
export class ToolRegistry { private tools=new Map<string,Tool<unknown,unknown>>(); register<I,O>(t:Tool<I,O>){if(this.tools.has(t.name))throw new Error(`Duplicate tool: ${t.name}`);this.tools.set(t.name,t as Tool<unknown,unknown>)} get(name:string){const t=this.tools.get(name);if(!t)throw new Error(`Unknown tool: ${name}`);return t} describe(){return [...this.tools.values()].map(({name,schema,permissions})=>({name,schema,permissions}))} }
export * from "./coding-provider.js";
