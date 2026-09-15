import json
import os
import unittest
from unittest.mock import patch

from ade.budget import BudgetLedger
from ade.models import OpenAICompatibleClient, clean_model_output


class ModelOutputTests(unittest.TestCase):
    def test_removes_qwen_reasoning_block(self):
        raw = "Thinking Process:\n1. Analyze\n</think>\nCiao! Sono ADE."
        self.assertEqual(clean_model_output(raw), "Ciao! Sono ADE.")

    def test_keeps_normal_answer(self):
        self.assertEqual(clean_model_output("Risposta normale."), "Risposta normale.")

    def test_route_specific_model_override(self):
        runtime = {
            "routing": {"default": "general", "qa": "reasoning"},
            "models": {"reasoning": {"model": "auto", "max_output_tokens": 10}},
            "budgets": {"task_model_calls": 2, "task_tokens": 100, "task_external_actions": 0},
        }
        captured = {}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

        def fake_open(request, timeout=0):
            captured["body"] = json.loads(request.data)
            return Response()

        with patch.dict(os.environ, {"ADE_MODEL_REASONING_ID": "quality-model"}), patch(
            "urllib.request.urlopen", fake_open
        ):
            result = OpenAICompatibleClient(runtime, BudgetLedger(runtime["budgets"])).complete(
                task_id="t", tier="qa", system="s", prompt="p"
            )
        self.assertEqual(result, "ok")
        self.assertEqual(captured["body"]["model"], "quality-model")


if __name__ == "__main__":
    unittest.main()
