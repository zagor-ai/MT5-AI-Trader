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
        self.assertEqual(digest["strategies"][0]["oos"]["profit_factor"], 1.4)
        self.assertEqual(digest["strategies"][0]["evidence"]["oos_source"], "test")

    def test_walk_forward_oos_is_used_when_final_test_metrics_are_missing(self):
        payload = [
            {
                "candidate": {"name": "WF_ONLY", "direction": "SELL"},
                "walk_forward_score": 13.68,
                "monte_carlo_robustness": 98.2,
                "sensitivity_robustness": 100.0,
                "regime_robustness": 73.1,
                "walk_forward": {
                    "window_count": 6,
                    "positive_windows": 4,
                    "positive_window_ratio": 4 / 6,
                    "oos_net_r_sum": 114.83,
                    "oos_net_r_mean": 19.138,
                    "oos_pf_mean": 1.0946,
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranked_strategies.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            digest, markdown = build_digest(path)

        strategy = digest["strategies"][0]
        self.assertEqual(strategy["evidence"]["oos_source"], "walk_forward")
        self.assertAlmostEqual(strategy["oos"]["profit_factor"], 1.0946, places=4)
        self.assertAlmostEqual(strategy["oos"]["net_r"], 114.83, places=2)
        self.assertAlmostEqual(strategy["oos"]["net_r_mean"], 19.138, places=3)
        self.assertEqual(digest["summary"]["oos_profit_factor"]["min"], 1.0946)
        self.assertEqual(digest["summary"]["oos_net_r"]["max"], 114.83)
        self.assertEqual(digest["quality"]["status"], "WARNING")
        self.assertIn("Walk-Forward OOS aggregates were used instead", markdown)
        self.assertNotIn("OOS PF: min `0.0`", markdown)
        self.assertNotIn("OOS Net R: min `0.0`", markdown)

    def test_missing_metrics_are_not_silently_converted_to_zero(self):
        payload = [{"candidate": {"name": "MISSING", "direction": "BUY"}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranked_strategies.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            digest, markdown = build_digest(path)

        strategy = digest["strategies"][0]
        self.assertIsNone(strategy["oos"]["profit_factor"])
        self.assertIsNone(strategy["oos"]["net_r"])
        self.assertEqual(digest["summary"]["oos_profit_factor"]["min"], None)
        self.assertEqual(digest["quality"]["status"], "WARNING")
        self.assertIn("No OOS metrics were found", markdown)


if __name__ == "__main__":
    unittest.main()
