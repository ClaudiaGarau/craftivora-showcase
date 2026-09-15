from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse


class BrowserPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserRequest:
    operation: str
    url: str
    mutating: bool = False


class BrowserUseAdapter:
    """Policy boundary for a persistent Browser Use session.

    Mutating operations are rejected until an external approval gate supplies an
    approval id. Commands use argument arrays and never invoke a shell.
    """

    def __init__(self, allowed_domains: set[str], runner=subprocess.run):
        self.allowed_domains = {d.lower() for d in allowed_domains}
        self.runner = runner

    def validate(self, request: BrowserRequest, approval_id: str | None = None) -> None:
        host = (urlparse(request.url).hostname or "").lower()
        if not host or not any(host == d or host.endswith("." + d) for d in self.allowed_domains):
            raise BrowserPolicyError(f"domain_not_allowed:{host}")
        if request.mutating and not approval_id:
            raise BrowserPolicyError("explicit_approval_required")

    def command(self, request: BrowserRequest, approval_id: str | None = None) -> list[str]:
        self.validate(request, approval_id)
        return ["browser-use", request.operation, request.url, "--json"]

    def execute(self, request: BrowserRequest, approval_id: str | None = None) -> dict:
        command = self.command(request, approval_id)
        result = self.runner(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
