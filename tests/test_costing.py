import unittest

from ade.costing import estimate


RUNTIME = {
    "infrastructure": {"gpu_hourly_usd": 0.45},
    "approval": {"confirm_gpu_minutes": 2},
    "cost_profiles": {
        "reasoning": {"route": "reasoning", "gpu_minutes": [1, 4]},
        "image": {"route": "image", "gpu_minutes": [1, 6]},
        "video": {"route": "video", "gpu_minutes": [8, 25], "operator_cost_usd": [0.5, 5.0]},
        "document": {"route": "reasoning", "gpu_minutes": [2, 8]},
        "software": {"route": "reasoning", "gpu_minutes": [3, 20]},
    },
}


class CostingTests(unittest.TestCase):
    def test_video_is_high_and_confirmed(self):
        quote = estimate("crea un video pubblicitario", RUNTIME)
        self.assertEqual(quote.model_route, "video")
        self.assertTrue(quote.requires_confirmation)
        self.assertGreater(quote.cost_usd_high, quote.cost_usd_low)

    def test_estimate_never_claims_exact_cost(self):
        quote = estimate("analizza", RUNTIME)
        self.assertIn("Stima", quote.notes[-1])


if __name__ == "__main__":
    unittest.main()
