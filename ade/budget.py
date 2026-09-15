from __future__ import annotations

import threading
from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Usage:
    model_calls: int = 0
    tokens: int = 0
    external_actions: int = 0


class BudgetLedger:
    """Admission-time reservations avoid concurrent overspend."""
    def __init__(self, limits: dict):
        self.limits = limits
        self._usage: dict[str, Usage] = {}
        self._lock = threading.RLock()

    def reserve(self, task_id: str, *, calls: int = 0, tokens: int = 0, actions: int = 0) -> Usage:
        with self._lock:
            current = self._usage.setdefault(task_id, Usage())
            proposed = Usage(current.model_calls + calls, current.tokens + tokens, current.external_actions + actions)
            call_limit = int(self.limits.get("task_model_calls", 0))
            token_limit = int(self.limits.get("task_tokens", 0))
            action_limit = int(self.limits.get("task_external_actions", 0))
            if proposed.model_calls > call_limit or proposed.tokens > token_limit or proposed.external_actions > action_limit:
                raise BudgetExceeded(f"Budget exceeded for task {task_id}")
            self._usage[task_id] = proposed
            return proposed

    def usage(self, task_id: str) -> Usage:
        with self._lock:
            return self._usage.get(task_id, Usage())
