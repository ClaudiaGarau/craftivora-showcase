from __future__ import annotations

import json
from uuid import uuid4

from .budget import BudgetLedger
from .memory import MemoryStore
from .models import OpenAICompatibleClient
from .artifacts import inspect_artifact


SHORT_REPLIES = {
    "ciao": "Ciao!",
    "buongiorno": "Buongiorno!",
    "buonasera": "Buonasera!",
    "grazie": "Prego!",
    "come stai": "Bene, grazie. E tu?",
}


class ConversationService:
    def __init__(self, runtime: dict, memory: MemoryStore):
        self.runtime = runtime
        self.memory = memory

    def reply(self, conversation_id: str, text: str, attachments: list[str] | None = None) -> str:
        normalized = " ".join(text.lower().strip().split()).rstrip("?!.,;: ")
        history = self.memory.conversation(conversation_id, 16)
        attachments = attachments or []
        reports = []
        for path in attachments:
            try:
                reports.append(inspect_artifact(path).to_dict())
            except (OSError, ValueError):
                reports.append({"path": path, "valid": False, "error": "unreadable"})
        image_paths = [r["path"] for r in reports if r.get("kind") == "image" and r.get("valid")]
        if normalized in SHORT_REPLIES and not reports:
            answer = SHORT_REPLIES[normalized]
        else:
            client = OpenAICompatibleClient(self.runtime, BudgetLedger(self.runtime["budgets"]))
            answer = client.complete(
                task_id=uuid4().hex,
                tier="vision" if image_paths else "default",
                system=(
                    "Sei ADE, il braccio destro personale dell'utente. Rispondi in italiano con naturalezza e "
                    "misura: saluti e domande semplici richiedono una frase breve; approfondisci soltanto quando "
                    "serve. Non ripresentarti se la conversazione è già iniziata. Ricorda le informazioni presenti "
                    "nella cronologia, non ripetere istruzioni già comprese e non mostrare codice o comandi se non "
                    "richiesti. Non fingere azioni o capacità non verificate. Se sono allegate immagini, descrivi "
                    "davvero cosa vedi (non limitarti a formato/dimensioni) e usalo per rispondere alla richiesta."
                ),
                prompt=json.dumps({"conversation": history, "message": text, "attachments": reports}, ensure_ascii=False),
                image_paths=image_paths,
            ).strip()
        stored = text if not reports else text + "\n[Allegati: " + ", ".join(str(x.get("path", "file")) for x in reports) + "]"
        self.memory.remember_message(conversation_id, "user", stored)
        self.memory.remember_message(conversation_id, "assistant", answer)
        return answer
