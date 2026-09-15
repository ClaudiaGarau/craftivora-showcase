from __future__ import annotations

import platform
import shutil
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Capability:
    name: str
    status: str
    mode: str
    requirement: str
    limitation: str = ""


def environment_capabilities() -> dict:
    commands = ("browser-use", "ffmpeg", "ffprobe", "node", "npm", "pyinstaller", "nuitka")
    return {
        "platform": platform.platform(),
        "commands": {name: shutil.which(name) for name in commands},
    }


def capability_matrix() -> list[dict]:
    env = environment_capabilities()["commands"]
    rows = [
        Capability("orchestration", "verified", "deterministic+model", "Python runtime"),
        Capability("approval_budget_security", "verified", "deterministic", "SQLite"),
        Capability("browser_policy_adapter", "verified", "deterministic", "approved domains"),
        Capability("live_browser_session", "available" if env["browser-use"] else "not_configured", "external", "Browser Use + persistent profile", "A Codex/Chrome login is not automatically inherited."),
        Capability("image_fidelity_metrics", "verified", "deterministic", "Pillow", "Metrics do not replace semantic or human review."),
        Capability("video_generation", "available" if env["ffmpeg"] else "not_configured", "hybrid", "generation backend + FFmpeg"),
        Capability("presentation_generation", "adapter_ready", "hybrid", "python-pptx/LibreOffice + render QA"),
        Capability("windows_executable", "available" if env["pyinstaller"] and platform.system() == "Windows" else "builder_required", "build", "Windows builder or CI", "Linux RunPod cannot natively guarantee a Windows executable."),
        Capability("production_saas", "workflow_ready", "hybrid", "repo, tests, deployment credentials, human approvals", "Quality is project- and test-dependent, not automatic."),
    ]
    return [asdict(row) for row in rows]
