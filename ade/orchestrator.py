from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .agents import build_agents
from .approvals import ApprovalGate
from .budget import BudgetLedger
from .memory import MemoryStore
from .models import MockModelClient, OpenAICompatibleClient
from .planner import make_plan
from .security import sanitize_context
from .tools import ToolRegistry, default_registry
from .types import ActionProposal, Risk, TaskResult, TaskStatus
from .artifacts import inspect_artifact



def _safe_risk(value) -> Risk:
    try:
        return Risk(value)
    except ValueError:
        return Risk.EXTERNAL

class AdeOrchestrator:
    def __init__(self, *, runtime: dict, data_dir: Path, prompt_root: Path, mock: bool = False):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir
        self.memory = MemoryStore(data_dir / "ade.sqlite3")
        self.ledger = BudgetLedger(runtime["budgets"])
        self.gate = ApprovalGate(self.memory, runtime["approval"])
        client = MockModelClient(runtime, self.ledger) if mock else OpenAICompatibleClient(runtime, self.ledger)
        self.agents = build_agents(client, prompt_root)
        self.tools: ToolRegistry = default_registry()

    def run(self, objective: str, context: dict | None = None) -> TaskResult:
        task_id = uuid4().hex
        context = sanitize_context(context or {})
        attachment_reports = []
        for attachment in context.get("attachments", []):
            try:
                attachment_reports.append(inspect_artifact(attachment).to_dict())
            except (OSError, ValueError) as exc:
                attachment_reports.append({"path": str(attachment), "valid": False, "error": type(exc).__name__})
        if attachment_reports:
            context["attachment_reports"] = attachment_reports
        plan = make_plan(objective)
        self.memory.event(task_id, "plan", asdict(plan))
        trace = [{"agent": "ADE", "event": "plan", "domain": plan.domain, "items": [asdict(x) for x in plan.items]}]
        results = []
        for item in plan.items:
            result = self.agents[item.agent].run(task_id, item.objective, {"user_objective": objective, "input": context, "prior_results": results})
            results.append(result)
            self.memory.event(task_id, "agent_result", result)
            trace.append({"agent": result["agent"], "event": "completed"})
        final = self.agents["ade"].run(task_id, "Synthesize the work. Return a truthful executive result, unresolved risks, and proposed consequential actions.", {"objective": objective, "domain": plan.domain, "results": results})
        proposals = []
        for raw in final.get("proposals", []):
            proposal = ActionProposal(action=raw["action"], target=raw.get("target", ""), reason=raw.get("reason", ""), risk=_safe_risk(raw.get("risk", "external")), payload=raw.get("payload", {}))
            self.gate.submit(task_id, proposal)
            proposals.append(proposal)
        status = TaskStatus.WAITING_APPROVAL if proposals else TaskStatus.COMPLETE
        task_dir = self.data_dir / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        report_path = task_dir / "ADE-report.md"
        lines = ["# Rapporto ADE", "", final.get("summary", "Lavoro completato"), ""]
        if attachment_reports:
            lines += ["## Allegati verificati", ""]
            for report in attachment_reports:
                lines.append(f"- {Path(report['path']).name}: {report.get('kind', 'file')} — "
                             f"{'valido' if report.get('valid') else 'da controllare'}")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        artifact_paths = [str(report_path)]
        try:
            from .production import materialize_requests
            artifact_paths += materialize_requests(task_dir, final.get("documents", []))
        except Exception as exc:
            trace.append({"agent": "ADE", "event": "document_error", "error": str(exc)})
        return TaskResult(task_id, status, final.get("summary", "Work completed"), results, proposals, trace, artifact_paths)

    def propose(self, task_id: str, *, action: str, target: str, reason: str, risk: Risk = Risk.EXTERNAL, payload: dict | None = None) -> ActionProposal:
        proposal = ActionProposal(action, target, reason, risk, payload or {})
        self.gate.submit(task_id, proposal)
        return proposal
