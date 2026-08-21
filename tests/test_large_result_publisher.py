import json
import tempfile
import unittest
from pathlib import Path

from tools.large_result_publisher import build_digest


class LargeResultPublisherSmokeTest(unittest.TestCase):
    def test_digest_strips_bulky_trade_and_equity_data(self):
        payload = [
            {
                "candidate": {"name": "TEST", "direction": "BUY", "indicators": {"ema_fast": 20}},
                "validation_score": 12.3,
                "walk_forward_score": 8.5,
                "monte_carlo_robustness": 91.0,
                "sensitivity_robustness": 80.0,
                "regime_robustness": 75.0,
                "test": {"trade_count": 20, "profit_factor": 1.4, "net_r": 12.0},
                "walk_forward": {"window_count": 6, "positive_windows": 5, "positive_window_ratio": 5 / 6},
                "trades": [{"pnl": 999999} for _ in range(100)],
                "equity_curve": list(range(1000)),
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranked_strategies.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            digest, markdown = build_digest(path)

        self.assertEqual(digest["record_count"], 1)
        self.assertEqual(digest["strategies"][0]["name"], "TEST")
        self.assertNotIn("trades", digest["strategies"][0])
        self.assertNotIn("equity_curve", digest["strategies"][0])
        self.assertIn("TEST", markdown)
        self.assertEqual(len(digest["source"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
