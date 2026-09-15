from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ModelClient


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    tier: str
    prompt_file: str


SPECS = {
    "ade": AgentSpec("ADE", "sovereign orchestrator", "orchestration", "ade.md"),
    "atena": AgentSpec("ATENA", "research and evidence", "research", "atena.md"),
    "apollo": AgentSpec("APOLLO", "creation and implementation", "creation", "apollo.md"),
    "argo": AgentSpec("ARGO", "quality, safety and release gate", "qa", "argo.md"),
    "poseidone": AgentSpec("POSEIDONE", "digital product and marketplace master", "general", "poseidone.md"),
}


class Agent:
    def __init__(self, spec: AgentSpec, client: ModelClient, prompt_root: Path):
        self.spec = spec
        self.client = client
        self.system = (prompt_root / spec.prompt_file).read_text(encoding="utf-8")

    def run(self, task_id: str, objective: str, context: dict[str, Any]) -> dict[str, Any]:
        prompt = json.dumps({"objective": objective, "context": context}, ensure_ascii=False)
        raw = self.client.complete(task_id=task_id, tier=self.spec.tier, system=self.system, prompt=prompt, json_mode=True)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"summary": raw, "findings": [], "recommendations": []}
        result["agent"] = self.spec.name
        return result


def build_agents(client: ModelClient, prompt_root: Path) -> dict[str, Agent]:
    return {key: Agent(spec, client, prompt_root) for key, spec in SPECS.items()}
