from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class Risk(str, Enum):
    READ = "read"
    WRITE_LOCAL = "write_local"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class WorkItem:
    agent: str
    objective: str
    tools: list[str] = field(default_factory=list)
    model_tier: str = "general"
    requires: list[int] = field(default_factory=list)


@dataclass
class Plan:
    objective: str
    domain: str
    items: list[WorkItem]
    assumptions: list[str] = field(default_factory=list)


@dataclass
class ActionProposal:
    action: str
    target: str
    reason: str
    risk: Risk
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    summary: str
    outputs: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[ActionProposal] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
