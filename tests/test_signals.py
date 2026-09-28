from __future__ import annotations

import json
import unittest
from pathlib import Path

from investeval.signals import compare_signal_versions, evaluate_hot_context, load_signal_summary, summarize_feedback


ROOT = Path(__file__).resolve().parents[1]


class SignalGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = load_signal_summary(
            ROOT / "data" / "user-feedback.json",
            ROOT / "data" / "hot-context.json",
            ROOT / "data" / "user-feedback-candidate.json",
            ROOT / "data" / "hot-context-candidate.json",
        )

    def test_behavior_signals_create_an_investigation_queue(self) -> None:
        feedback = self.summary["baseline"]["feedback"]
        self.assertGreater(feedback["escalated_case_count"], 0)
        self.assertIn("never override", feedback["interpretation_boundary"])

    def test_helpful_feedback_does_not_clear_compliance_case(self) -> None:
        row = next(item for item in self.summary["baseline"]["feedback"]["cases"] if item["case_id"] == "compliance-guarantee")
        self.assertEqual(2, row["helpful"])
        self.assertEqual("observe", row["action"])

    def test_hot_context_detects_stale_future_and_mismatched_event_time(self) -> None:
        findings = {finding for result in self.summary["baseline"]["hot_context"]["results"] for finding in result["findings"]}
        self.assertEqual({"HOT_CONTEXT_STALE", "FUTURE_CONTEXT_LEAK", "EVENT_TIME_MISMATCH"}, findings)

    def test_candidate_signal_window_improves_without_deleting_baseline_failures(self) -> None:
        self.assertEqual(16, self.summary["pairing"]["feedback_observation_count"])
        self.assertEqual(4, self.summary["pairing"]["hot_context_check_count"])
        self.assertEqual(-50.0, self.summary["delta"]["negative_signal_rate_pp"])
        self.assertEqual(-3, self.summary["delta"]["hot_context_failed_count"])
        self.assertEqual(0, self.summary["candidate"]["hot_context"]["failed_count"])

    def test_unpaired_signal_windows_are_rejected(self) -> None:
        documents = []
        for name in ("user-feedback.json", "user-feedback-candidate.json", "hot-context.json", "hot-context-candidate.json"):
            documents.append(json.loads((ROOT / "data" / name).read_text(encoding="utf-8")))
        documents[1]["events"].pop()
        with self.assertRaisesRegex(ValueError, "identical pair IDs"):
            compare_signal_versions(*documents)

    def test_duplicate_feedback_event_is_rejected(self) -> None:
        event = {"event_id": "same", "case_id": "x", "signal": "helpful", "occurred_at": "2026-09-27T10:00:00Z"}
        with self.assertRaisesRegex(ValueError, "duplicate feedback"):
            summarize_feedback({"events": [event, event]})

    def test_unsupported_feedback_signal_is_rejected(self) -> None:
        event = {"event_id": "x", "case_id": "x", "signal": "buy_clicked", "occurred_at": "2026-09-27T10:00:00Z"}
        with self.assertRaisesRegex(ValueError, "unsupported feedback"):
            summarize_feedback({"events": [event]})


if __name__ == "__main__":
    unittest.main()
