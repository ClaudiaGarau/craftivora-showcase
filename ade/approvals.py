from __future__ import annotations

from dataclasses import asdict

from .memory import MemoryStore
from .types import ActionProposal, Risk


class PolicyDenied(RuntimeError):
    pass


class ApprovalGate:
    def __init__(self, memory: MemoryStore, policy: dict):
        self.memory = memory
        self.always = set(policy.get("always_require", []))
        self.denied = set(policy.get("deny_by_default", []))

    def submit(self, task_id: str, proposal: ActionProposal) -> str:
        if proposal.action in self.denied:
            raise PolicyDenied(f"Action denied by policy: {proposal.action}")
        needs_approval = proposal.action in self.always or proposal.risk in {Risk.EXTERNAL, Risk.DESTRUCTIVE}
        if needs_approval:
            self.memory.create_approval(task_id, asdict(proposal))
            return "pending"
        return "allowed"
