from __future__ import annotations

import json
import time
from uuid import uuid4

from .browser_queue import BrowserQueue
from .budget import BudgetLedger
from .models import OpenAICompatibleClient

MAX_STEPS = 20
COMMAND_TIMEOUT_S = 30
POLL_INTERVAL_S = 0.5

SYSTEM_PROMPT = (
    "Sei ADE, un agente che controlla un vero browser Chrome attraverso un'estensione. "
    "Ad ogni turno ricevi l'obiettivo dell'utente, la cronologia delle azioni gia' fatte in questo "
    "compito, e un'istantanea della pagina attualmente aperta (titolo, url, testo visibile troncato, "
    "ed elenco di elementi interagibili con selettore CSS, tag, testo, tipo, nome, id). "
    "Rispondi SOLO con JSON valido nella forma esatta: "
    "{\"action\":\"navigate|click|fill|scroll|done\",\"url\":\"\",\"selector\":\"\",\"value\":\"\",\"reasoning\":\"\"}. "
    "Usa \"navigate\" con un url assoluto (https://...) per aprire una pagina. "
    "Usa \"click\", \"fill\" o \"scroll\" SOLO con un selettore preso esattamente dall'istantanea corrente, "
    "mai inventato: se l'elemento che ti serve non compare nell'istantanea, prova prima a fare scroll o naviga altrove. "
    "Per \"fill\" metti il testo da scrivere nel campo \"value\". "
    "Quando l'obiettivo e' raggiunto, o non puoi procedere in sicurezza, rispondi con action \"done\" e spiega "
    "in \"reasoning\" cosa hai fatto o perche' ti sei fermato. "
    "Non eseguire mai acquisti, pagamenti, invii di denaro, cancellazioni definitive, ne' inserire password o dati "
    "di pagamento: in quei casi fermati subito con \"done\" e spiega che serve l'intervento diretto dell'utente."
)


class BrowserTaskError(RuntimeError):
    pass


def _await_event(queue: BrowserQueue, command_id: str, timeout_s: float = COMMAND_TIMEOUT_S) -> dict:
    deadline = time.monotonic() + timeout_s
    seen = 0
    while time.monotonic() < deadline:
        events = queue.events()
        for event in events[seen:]:
            if event.get("commandId") == command_id:
                return event
        seen = len(events)
        time.sleep(POLL_INTERVAL_S)
    raise BrowserTaskError(
        "Timeout: l'estensione ADE non ha risposto. Verifica che Chrome sia aperto, "
        "l'estensione ADE collegata e il ponte locale attivo."
    )


def _snapshot(queue: BrowserQueue) -> dict:
    command = queue.submit("snapshot", approved=True)
    event = _await_event(queue, command["id"])
    return event.get("result") or {}


def run_browser_task(objective: str, runtime: dict, queue: BrowserQueue, max_steps: int = MAX_STEPS) -> dict:
    objective = (objective or "").strip()
    if not objective:
        return {"summary": "Obiettivo vuoto.", "steps": [], "ok": False}
    client = OpenAICompatibleClient(runtime, BudgetLedger(runtime["budgets"]))
    history: list[dict] = []
    steps: list[dict] = []
    try:
        snapshot = _snapshot(queue)
    except BrowserTaskError as exc:
        return {"summary": str(exc), "steps": [], "ok": False}
    for _ in range(max(1, max_steps)):
        prompt = json.dumps(
            {"objective": objective, "history": history[-8:], "snapshot": snapshot},
            ensure_ascii=False,
        )
        raw = client.complete(
            task_id=uuid4().hex,
            tier="classification",
            system=SYSTEM_PROMPT,
            prompt=prompt,
            json_mode=True,
        )
        try:
            decision = json.loads(raw)
            if not isinstance(decision, dict):
                raise ValueError("decision is not an object")
        except (TypeError, ValueError, json.JSONDecodeError):
            decision = {"action": "done", "reasoning": "Risposta del modello non valida; mi fermo per sicurezza."}
        action = str(decision.get("action", "done")).strip().lower()
        reasoning = str(decision.get("reasoning", ""))[:2000]
        if action not in {"navigate", "click", "fill", "scroll", "done"}:
            action = "done"
        if action == "done":
            steps.append({"action": "done", "reasoning": reasoning})
            return {"summary": reasoning or "Attivita' conclusa.", "steps": steps, "ok": True}
        selector = str(decision.get("selector", ""))[:500]
        value = str(decision.get("url", "") if action == "navigate" else decision.get("value", ""))[:5000]
        try:
            command = queue.submit(action, selector=selector, value=value, approved=True)
            result_event = _await_event(queue, command["id"])
        except (ValueError, PermissionError, BrowserTaskError) as exc:
            steps.append({"action": action, "selector": selector, "reasoning": reasoning, "error": str(exc)})
            return {"summary": f"Mi sono fermato: {exc}", "steps": steps, "ok": False}
        step_record = {
            "action": action,
            "selector": selector,
            "value": value,
            "reasoning": reasoning,
            "result": result_event.get("result"),
        }
        if not result_event.get("ok", True):
            step_record["error"] = result_event.get("error", "Azione non riuscita")
        steps.append(step_record)
        history.append({"action": action, "selector": selector, "reasoning": reasoning})
        try:
            snapshot = _snapshot(queue)
        except BrowserTaskError as exc:
            steps.append({"action": "snapshot", "error": str(exc)})
            return {"summary": str(exc), "steps": steps, "ok": False}
    return {
        "summary": f"Ho raggiunto il limite di {max_steps} passi senza completare l'obiettivo.",
        "steps": steps,
        "ok": False,
    }
