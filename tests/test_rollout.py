from __future__ import annotations

import unittest
from pathlib import Path

from investeval.rollout import load_and_compare


ROOT = Path(__file__).resolve().parents[1]


class RolloutGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comparison = load_and_compare(ROOT / "data" / "version-runs.json")

    def test_comparison_is_paired(self) -> None:
        self.assertEqual(self.comparison["baseline"]["sample_size"], self.comparison["candidate"]["sample_size"])

    def test_candidate_improves_quality_without_claiming_rollout_readiness(self) -> None:
        self.assertGreater(self.comparison["delta"]["pass_rate_pp"], 0)
        self.assertEqual("HOLD", self.comparison["decision"]["status"])

    def test_hold_reasons_are_traceable_to_failed_hard_gates(self) -> None:
        failed_hard_gates = {gate["gate_id"] for gate in self.comparison["gates"] if gate["hard_blocker"] and not gate["passed"]}
        self.assertEqual(failed_hard_gates, set(self.comparison["decision"]["reason_codes"]))


if __name__ == "__main__":
    unittest.main()

