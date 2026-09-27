from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from investeval.governance import GovernanceService, QueryFilters


ROOT = Path(__file__).resolve().parents[1]


class GovernanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        directory = Path(self.temporary.name)
        self.facts = directory / "facts.json"
        self.cases = directory / "cases.json"
        self.reviews = directory / "reviews.json"
        shutil.copyfile(ROOT / "data" / "facts.json", self.facts)
        shutil.copyfile(ROOT / "data" / "cases.json", self.cases)
        self.service = GovernanceService(self.facts, self.cases, self.reviews)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_summary_and_bad_case_filter(self) -> None:
        summary = self.service.summary()
        bad_cases = self.service.list_cases(QueryFilters(outcome="bad_case"))
        self.assertEqual(summary["bad_case_count"], len(bad_cases))
        self.assertTrue(all(not item["passed"] for item in bad_cases))

    def test_case_detail_contains_lineage_and_findings(self) -> None:
        detail = self.service.get_case("quote-wrong-number")
        self.assertEqual("market-v1", detail["lineage"]["data_version"])
        self.assertEqual("NUMERIC_MISMATCH", detail["evaluation"]["findings"][0]["code"])
        self.assertEqual("pending", detail["review"]["status"])

    def test_human_review_is_persisted(self) -> None:
        review = self.service.review_case(
            "quote-wrong-number", "confirmed", "reviewer@example.test", "数字与冻结快照不一致"
        )
        self.assertEqual("confirmed", review["status"])
        reloaded = GovernanceService(self.facts, self.cases, self.reviews)
        self.assertEqual("confirmed", reloaded.get_case("quote-wrong-number")["review"]["status"])

    def test_completed_review_requires_reviewer(self) -> None:
        with self.assertRaisesRegex(ValueError, "reviewer is required"):
            self.service.review_case("quote-wrong-number", "confirmed", "")

    def test_import_validates_and_evaluates_new_log(self) -> None:
        base = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))["cases"][0]
        imported = dict(base)
        imported["case_id"] = "imported-quote-correct"
        response = self.service.import_cases({"cases": [imported]})
        self.assertEqual(1, response["imported_count"])
        self.assertTrue(self.service.get_case("imported-quote-correct")["evaluation"]["passed"])

    def test_duplicate_import_is_rejected_without_file_change(self) -> None:
        before = self.cases.read_text(encoding="utf-8")
        duplicate = json.loads(before)["cases"][0]
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.import_cases({"cases": [duplicate]})
        self.assertEqual(before, self.cases.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

