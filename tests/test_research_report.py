import json
import tempfile
import unittest
from pathlib import Path

from core.research_report import export_research_report


class ResearchReportSmokeTest(unittest.TestCase):
    def test_report_is_compact_and_machine_readable(self):
        item = {
            "candidate": {
                "name": "SELL_EMA_RSI_ATR_0166",
                "direction": "SELL",
                "indicators": {"ema_fast": 50, "ema_slow": 200, "rsi_period": 14, "atr_period": 14},
                "entry_rules": [],
                "exit_rules": [],
                "risk": {"atr_sl": 2.0, "rr": 2.0},
            },
            "validation_score": 4.2,
            "walk_forward_score": 72.0,
            "monte_carlo_robustness": 81.0,
            "sensitivity_robustness": 76.0,
            "regime_robustness": 68.0,
            "train": {"trade_count": 100, "profit_factor": 1.2, "net_r": 40.0},
            "test": {"trade_count": 30, "profit_factor": 1.1, "net_r": 12.0},
            "windows": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_research_report(
                Path(tmp),
                research_id="TEST-001",
                data_info={"symbol": "XAUUSD", "timeframe": "M5", "bars": 50000},
                config={"max_candidates": 300},
                pipeline={"candidates_generated": 300, "accepted_oos": 10, "final_ranked": 10},
                ranked=[item],
                code_version="test",
            )
            report = json.loads(Path(paths["report"]).read_text(encoding="utf-8"))
            self.assertEqual(report["run"]["research_id"], "TEST-001")
            self.assertEqual(report["ranking"]["top_strategies"][0]["candidate"]["name"], "SELL_EMA_RSI_ATR_0166")
            self.assertTrue(Path(paths["markdown"]).exists())
            self.assertTrue(Path(paths["manifest"]).exists())
            self.assertNotIn("trades", report["ranking"]["top_strategies"][0])


if __name__ == "__main__":
    unittest.main()
