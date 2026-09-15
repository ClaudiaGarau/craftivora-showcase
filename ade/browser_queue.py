from __future__ import annotations

from collections import deque
from threading import RLock
from uuid import uuid4


class BrowserQueue:
    def __init__(self):
        self._commands = deque()
        self._events = deque(maxlen=1000)
        self._lock = RLock()

    def submit(self, action: str, selector: str = "", value: str = "", approved: bool = False) -> dict:
        if action not in {"snapshot", "scroll", "click", "fill", "navigate"}:
            raise ValueError("Action is not allowlisted")
        if action in {"click", "fill", "navigate"} and not approved:
            raise PermissionError("Interactive browser actions require approval")
        command = {"type": "browser_action", "id": uuid4().hex, "action": action, "selector": selector, "value": value}
        with self._lock:
            self._commands.append(command)
        return command

    def next(self) -> dict:
        with self._lock:
            return self._commands.popleft() if self._commands else {"type": "idle"}

    def event(self, payload: dict) -> None:
        with self._lock:
            self._events.append(payload)

    def events(self) -> list[dict]:
        with self._lock:
            return list(self._events)
