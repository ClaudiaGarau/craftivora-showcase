from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .budget import BudgetLedger

MAX_IMAGES = 4
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _encode_image(path: str) -> dict[str, Any] | None:
    """Legge un'immagine da disco e la incapsula come blocco data URI per la chat completions API.
    Ritorna None (invece di sollevare un'eccezione) se il file manca o è troppo grande: un allegato
    illeggibile non deve far fallire l'intera risposta, solo essere ignorato silenziosamente qui —
    il report di ade/artifacts.py segnala già il problema nel contesto testuale."""
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError:
        return None
    if size > MAX_IMAGE_BYTES:
        return None
    mime = mimetypes.guess_type(source.name)[0] or "image/png"
    try:
        data = base64.b64encode(source.read_bytes()).decode()
    except OSError:
        return None
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def clean_model_output(text: str) -> str:
    """Remove reasoning traces that some local Qwen servers place in content."""
    value = (text or "").strip()
    if "</think>" in value:
        value = value.rsplit("</think>", 1)[1].strip()
    while "<think>" in value and "</think>" in value:
        before, rest = value.split("<think>", 1)
        _, after = rest.split("</think>", 1)
        value = (before + after).strip()
    return value


class ModelClient(Protocol):
    def complete(self, *, task_id: str, tier: str, system: str, prompt: str, json_mode: bool = False, image_paths: list[str] | None = None) -> str: ...


@dataclass
class OpenAICompatibleClient:
    runtime: dict[str, Any]
    ledger: BudgetLedger

    def complete(self, *, task_id: str, tier: str, system: str, prompt: str, json_mode: bool = False, image_paths: list[str] | None = None) -> str:
        # Qwen3.5 è un modello "ibrido pensante": pensa sempre, non esiste modo di disattivarlo con
        # questa versione di llama-cpp-python (chat_template_kwargs non è supportato dal server: un
        # campo extra silenziosamente ignorato — non aggiungerlo di nuovo pensando sia la soluzione).
        # L'unico modo verificato per evitare il "leak" del pensiero è dare margine sufficiente di
        # max_output_tokens perché il modello raggiunga davvero il tag "</think>" di chiusura, che
        # clean_model_output() sa già rimuovere in modo affidabile.
        route = self.runtime["routing"].get(tier, self.runtime["routing"]["default"])
        cfg = self.runtime["models"][route]
        max_tokens = int(cfg.get("max_output_tokens", 4000))
        self.ledger.reserve(task_id, calls=1, tokens=max_tokens)
        base = os.getenv(cfg.get("base_url_env", "ADE_MODEL_BASE_URL"), "http://127.0.0.1:8001/v1").rstrip("/")
        key = os.getenv(cfg.get("api_key_env", "ADE_MODEL_API_KEY"), "EMPTY")
        # A route-specific override keeps economy, reasoning and vision genuinely
        # distinct while preserving ADE_MODEL_ID as a backwards-compatible default.
        route_env = "ADE_MODEL_" + route.upper().replace("-", "_") + "_ID"
        model = os.getenv(route_env, os.getenv("ADE_MODEL_ID", cfg["model"]))
        if model.lower() == "auto":
            models_req = urllib.request.Request(base + "/models", headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(models_req, timeout=30) as response:
                available = json.loads(response.read()).get("data", [])
            if not available:
                raise RuntimeError("No model is loaded in the configured model server")
            ids = [str(item.get("id", "")) for item in available if item.get("id")]
            preferred = [str(value).lower() for value in cfg.get("prefer", [])]
            model = next(
                (candidate for hint in preferred for candidate in ids if hint in candidate.lower()),
                ids[0],
            )
        user_content: Any = prompt
        blocks = [_encode_image(p) for p in (image_paths or [])[:MAX_IMAGES]]
        blocks = [b for b in blocks if b is not None]
        if blocks:
            user_content = [{"type": "text", "text": prompt}, *blocks]
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=180) as response:
            payload = json.loads(response.read())
        return clean_model_output(payload["choices"][0]["message"]["content"])


@dataclass
class MockModelClient:
    runtime: dict[str, Any]
    ledger: BudgetLedger

    def complete(self, *, task_id: str, tier: str, system: str, prompt: str, json_mode: bool = False, image_paths: list[str] | None = None) -> str:
        self.ledger.reserve(task_id, calls=1, tokens=200)
        if json_mode:
            return json.dumps({"summary": "Mock analysis completed", "findings": [], "recommendations": []})
        return f"Mock result for {tier}: {prompt[:120]}"
