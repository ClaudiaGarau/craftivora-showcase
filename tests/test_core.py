import json
import tempfile
import unittest
from pathlib import Path

from ade.approvals import ApprovalGate, PolicyDenied
from ade.budget import BudgetExceeded, BudgetLedger
from ade.memory import MemoryStore
from ade.orchestrator import AdeOrchestrator
from ade.planner import classify, make_plan
from ade.security import sanitize_context
from ade.types import ActionProposal, Risk


ROOT = Path(__file__).parents[1]


class CoreTests(unittest.TestCase):
    def runtime(self):
        return json.loads((ROOT / "config" / "runtime.mock.json").read_text(encoding="utf-8"))

    def test_domain_routing(self):
        self.assertEqual(classify("Ottimizza listing Etsy e PDF"), "commerce")
        self.assertEqual(classify("Costruisci un SaaS"), "software")
        self.assertEqual(make_plan("Etsy listing").items[0].agent, "poseidone")

    def test_atomic_budget(self):
        ledger = BudgetLedger({"task_model_calls": 1, "task_tokens": 100, "task_external_actions": 1})
        ledger.reserve("x", calls=1, tokens=50)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve("x", calls=1)

    def test_approval_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.sqlite")
            gate = ApprovalGate(memory, {"always_require": ["publish"], "deny_by_default": ["credential_export"]})
            proposal = ActionProposal("publish", "etsy:123", "ready", Risk.EXTERNAL)
            self.assertEqual(gate.submit("t", proposal), "pending")
            self.assertEqual(len(memory.pending("t")), 1)
            with self.assertRaises(PolicyDenied):
                gate.submit("t", ActionProposal("credential_export", "vault", "no", Risk.DESTRUCTIVE))

    def test_mock_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = AdeOrchestrator(runtime=self.runtime(), data_dir=Path(tmp), prompt_root=ROOT / "prompts", mock=True)
            result = engine.run("Analizza un prodotto Etsy")
            self.assertEqual(result.status.value, "complete")
            self.assertEqual([x["agent"] for x in result.outputs], ["POSEIDONE", "ARGO"])
            self.assertGreaterEqual(len(engine.memory.events(result.task_id)), 3)

    def test_context_redaction(self):
        clean = sanitize_context({"api_key": "abc", "nested": {"password": "x", "value": "ok"}})
        self.assertEqual(clean["api_key"], "[REDACTED]")
        self.assertEqual(clean["nested"]["password"], "[REDACTED]")
        self.assertEqual(clean["nested"]["value"], "ok")


if __name__ == "__main__":
    unittest.main()
