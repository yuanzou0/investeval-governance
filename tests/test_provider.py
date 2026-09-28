from __future__ import annotations

import unittest
from pathlib import Path

from investeval.provider import run_provider_drill


ROOT = Path(__file__).resolve().parents[1]


class ProviderFailureDrillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = run_provider_drill(ROOT / "data" / "provider-failure-scenarios.json")
        cls.results = {item["scenario_id"]: item for item in cls.payload["results"]}

    def test_healthy_provider_response_may_enter_fact_verification(self) -> None:
        result = self.results["provider-healthy"]
        self.assertEqual("PASS", result["status"])
        self.assertTrue(result["allow_fact_use"])
        self.assertEqual("CONTINUE_EVALUATION", result["rollout_decision"])

    def test_declared_provider_failures_are_fail_closed(self) -> None:
        failures = [item for item in self.payload["results"] if item["scenario_id"] != "provider-healthy"]
        self.assertEqual(7, len(failures))
        for result in failures:
            with self.subTest(scenario=result["scenario_id"]):
                self.assertEqual("FAIL_CLOSED", result["status"])
                self.assertFalse(result["allow_fact_use"])
                self.assertEqual("HOLD", result["rollout_decision"])

    def test_failure_drill_covers_required_error_classes(self) -> None:
        codes = {item["error_code"] for item in self.payload["results"] if item["error_code"]}
        self.assertEqual(
            {
                "PROVIDER_TIMEOUT",
                "PROVIDER_RATE_LIMITED",
                "PROVIDER_AUTH_FAILED",
                "PROVIDER_UPSTREAM_ERROR",
                "PROVIDER_SCHEMA_INVALID",
                "PROVIDER_UNAVAILABLE",
            },
            codes,
        )
        self.assertTrue(self.payload["summary"]["all_failures_block_fact_use"])


if __name__ == "__main__":
    unittest.main()
