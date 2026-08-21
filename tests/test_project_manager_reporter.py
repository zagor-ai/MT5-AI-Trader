import unittest

from tools.project_manager_reporter import build_decision_package


class ProjectManagerReporterSmokeTest(unittest.TestCase):
    def _digest(self, *, validation=None):
        return {
            "schema_version": "1.1",
            "source": {"path": "results/ranked_strategies.json", "bytes": 123, "sha256": "abc123", "modified_utc": "2026-08-21T00:00:00+00:00"},
            "quality": {"status": "WARNING", "warnings": ["Validation score is unavailable"]},
            "record_count": 1,
            "summary": {},
            "strategies": [{
                "rank": 1,
                "name": "TEST_SELL",
                "direction": "SELL",
                "candidate": {"name": "TEST_SELL", "direction": "SELL", "indicators": {}, "risk": {}},
                "validation_score": validation,
                "walk_forward_score": 10.0,
                "monte_carlo_robustness": 95.0,
                "sensitivity_robustness": 100.0,
                "regime_robustness": 72.0,
                "oos": {"profit_factor": 1.08, "net_r": 120.0},
                "walk_forward": {"window_count": 6, "positive_windows": 4, "positive_window_ratio": 4 / 6},
                "monte_carlo": {"probability_positive": 0.91},
                "evidence": {"oos_source": "walk_forward"},
            }],
        }

    def test_package_is_machine_readable_and_safe(self):
        package = build_decision_package(self._digest())
        self.assertEqual(package["schema_version"], "1.0")
        self.assertEqual(package["source"]["sha256"], "abc123")
        self.assertEqual(package["decision"]["recommendation"], "REQUIRES_FURTHER_VALIDATION")
        self.assertTrue(package["audit_policy"]["raw_large_file_kept_local"])
        self.assertIn("OOS profit factor", " ".join(package["decision"]["risk_flags"]))

    def test_strong_result_can_be_forward_test_candidate(self):
        digest = self._digest(validation=2.0)
        row = digest["strategies"][0]
        row["oos"]["profit_factor"] = 1.35
        row["walk_forward"]["positive_window_ratio"] = 5 / 6
        row["walk_forward"]["positive_windows"] = 5
        row["monte_carlo"]["probability_positive"] = 0.93
        package = build_decision_package(digest)
        self.assertEqual(package["decision"]["recommendation"], "READY_FOR_FORWARD_TEST")


if __name__ == "__main__":
    unittest.main()
