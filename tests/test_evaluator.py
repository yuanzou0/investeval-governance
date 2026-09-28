from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from investeval.evaluator import evaluate_cases
from investeval.loader import load_cases, load_facts


ROOT = Path(__file__).resolve().parents[1]


class EvaluationFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts = load_facts(ROOT / "data" / "facts.json")
        cls.cases = load_cases(ROOT / "data" / "cases.json")
        cls.results = {result.case_id: result for result in evaluate_cases(cls.cases, cls.facts)}

    def test_frozen_fixture_has_four_intents(self) -> None:
        self.assertEqual(4, len({case.intent for case in self.cases}))

    def test_expected_error_codes_are_reproduced(self) -> None:
        for case in self.cases:
            with self.subTest(case=case.case_id):
                actual = {finding.code for finding in self.results[case.case_id].findings}
                self.assertEqual(set(case.expected_error_codes), actual)

    def test_correct_cases_pass_with_full_score(self) -> None:
        for case_id in ("quote-correct", "financial-correct"):
            result = self.results[case_id]
            self.assertTrue(result.passed)
            self.assertEqual(100.0, result.score)

    def test_invariant_change_is_detected_for_both_profiles(self) -> None:
        for case_id in ("invariant-conservative", "invariant-aggressive"):
            codes = {finding.code.value for finding in self.results[case_id].findings}
            self.assertIn("FACT_PERSONALIZED", codes)


class RepresentativeFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts = load_facts(ROOT / "data" / "facts.json")
        cls.cases = load_cases(ROOT / "data" / "representative-cases.json")
        cls.results = {result.case_id: result for result in evaluate_cases(cls.cases, cls.facts)}

    def test_stratified_design_has_six_cases_per_intent(self) -> None:
        counts = {intent: sum(case.intent == intent for case in self.cases) for intent in {case.intent for case in self.cases}}
        self.assertEqual(24, len(self.cases))
        self.assertEqual(4, len(counts))
        self.assertEqual({6}, set(counts.values()))

    def test_stratified_design_has_declared_pass_rate_and_labels(self) -> None:
        self.assertEqual(16, sum(result.passed for result in self.results.values()))
        for case in self.cases:
            with self.subTest(case=case.case_id):
                actual = {finding.code for finding in self.results[case.case_id].findings}
                self.assertEqual(set(case.expected_error_codes), actual)


class LoaderValidationTests(unittest.TestCase):
    def test_duplicate_fact_ids_are_rejected(self) -> None:
        payload = {"facts": [
            {
                "fact_id": "same", "entity_id": "X", "metric": "price", "value": 1,
                "as_of": "2026-01-01", "source_locator": "fixture://x",
                "source_title": "fixture", "data_version": "v1"
            },
            {
                "fact_id": "same", "entity_id": "Y", "metric": "price", "value": 2,
                "as_of": "2026-01-01", "source_locator": "fixture://y",
                "source_title": "fixture", "data_version": "v1"
            }
        ]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate fact_id"):
                load_facts(path)

    def test_untrusted_fact_source_scheme_is_rejected(self) -> None:
        payload = {"facts": [{
            "fact_id": "unsafe", "entity_id": "X", "metric": "price", "value": 1,
            "as_of": "2026-01-01", "source_locator": "javascript:alert(1)",
            "source_title": "unsafe", "data_version": "v1"
        }]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source_locator"):
                load_facts(path)


if __name__ == "__main__":
    unittest.main()
