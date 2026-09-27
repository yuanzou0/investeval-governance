from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evaluator import evaluate_cases
from .loader import load_cases, load_facts
from .models import EvaluationCase, EvaluationResult


REVIEW_DECISIONS = {"pending", "confirmed", "dismissed", "resolved"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@dataclass(frozen=True)
class QueryFilters:
    intent: str | None = None
    error_code: str | None = None
    review_status: str | None = None
    outcome: str | None = None


class GovernanceService:
    """Application service for import, evaluation, triage, and human review."""

    def __init__(self, facts_path: str | Path, cases_path: str | Path, reviews_path: str | Path):
        self.facts_path = Path(facts_path)
        self.cases_path = Path(cases_path)
        self.reviews_path = Path(reviews_path)
        self._raw_cases: dict[str, dict[str, Any]] = {}
        self._cases: dict[str, EvaluationCase] = {}
        self._results: dict[str, EvaluationResult] = {}
        self._reviews: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> dict[str, Any]:
        facts = load_facts(self.facts_path)
        cases = load_cases(self.cases_path)
        raw_document = json.loads(self.cases_path.read_text(encoding="utf-8"))
        self._raw_cases = {item["case_id"]: item for item in raw_document["cases"]}
        self._cases = {case.case_id: case for case in cases}
        self._results = {result.case_id: result for result in evaluate_cases(cases, facts)}
        if self.reviews_path.exists():
            review_document = json.loads(self.reviews_path.read_text(encoding="utf-8"))
            self._reviews = {item["case_id"]: item for item in review_document.get("reviews", [])}
        else:
            self._reviews = {}
        return self.summary()

    def _review_for(self, case_id: str) -> dict[str, Any]:
        return self._reviews.get(case_id, {
            "case_id": case_id,
            "status": "pending",
            "reviewer": None,
            "note": "",
            "updated_at": None,
        })

    def summary(self) -> dict[str, Any]:
        results = list(self._results.values())
        codes = Counter(finding.code.value for result in results for finding in result.findings)
        intents = Counter(result.intent.value for result in results)
        failed = [result for result in results if not result.passed]
        review_statuses = Counter(self._review_for(result.case_id)["status"] for result in failed)
        return {
            "case_count": len(results),
            "passed_count": sum(result.passed for result in results),
            "bad_case_count": len(failed),
            "pass_rate": round(sum(result.passed for result in results) / len(results), 4) if results else 0.0,
            "average_score": round(sum(result.score for result in results) / len(results), 2) if results else 0.0,
            "intent_counts": dict(sorted(intents.items())),
            "error_code_counts": dict(sorted(codes.items())),
            "review_status_counts": dict(sorted(review_statuses.items())),
        }

    def list_cases(self, filters: QueryFilters | None = None) -> list[dict[str, Any]]:
        filters = filters or QueryFilters()
        items: list[dict[str, Any]] = []
        for case_id, result in self._results.items():
            case = self._cases[case_id]
            review = self._review_for(case_id)
            codes = [finding.code.value for finding in result.findings]
            if filters.intent and case.intent.value != filters.intent:
                continue
            if filters.error_code and filters.error_code not in codes:
                continue
            if filters.review_status and review["status"] != filters.review_status:
                continue
            if filters.outcome == "passed" and not result.passed:
                continue
            if filters.outcome == "bad_case" and result.passed:
                continue
            items.append({
                "case_id": case_id,
                "intent": case.intent.value,
                "question": case.question,
                "answer_preview": case.answer[:120],
                "model_version": case.model_version,
                "prompt_version": case.prompt_version,
                "data_version": case.data_version,
                "passed": result.passed,
                "score": result.score,
                "error_codes": codes,
                "review": review,
            })
        return sorted(items, key=lambda item: (item["passed"], item["score"], item["case_id"]))

    def get_case(self, case_id: str) -> dict[str, Any]:
        if case_id not in self._cases:
            raise KeyError(case_id)
        case = self._cases[case_id]
        result = self._results[case_id]
        return {
            "case": self._raw_cases[case_id],
            "evaluation": result.to_dict(),
            "review": self._review_for(case_id),
            "lineage": {
                "model_version": case.model_version,
                "prompt_version": case.prompt_version,
                "data_version": case.data_version,
                "checked_fact_ids": result.checked_fact_ids,
            },
        }

    def review_case(self, case_id: str, status: str, reviewer: str, note: str = "") -> dict[str, Any]:
        if case_id not in self._cases:
            raise KeyError(case_id)
        if status not in REVIEW_DECISIONS:
            raise ValueError(f"status must be one of {sorted(REVIEW_DECISIONS)}")
        if status != "pending" and not reviewer.strip():
            raise ValueError("reviewer is required for a completed review action")
        review = {
            "case_id": case_id,
            "status": status,
            "reviewer": reviewer.strip() or None,
            "note": note.strip(),
            "updated_at": _utc_now(),
        }
        self._reviews[case_id] = review
        _atomic_write_json(self.reviews_path, {
            "schema_version": "1.0",
            "reviews": sorted(self._reviews.values(), key=lambda item: item["case_id"]),
        })
        return review

    def import_cases(self, payload: dict[str, Any]) -> dict[str, Any]:
        incoming = payload.get("cases")
        if not isinstance(incoming, list) or not incoming:
            raise ValueError("payload must contain a non-empty cases array")
        parsed = [EvaluationCase.from_dict(item) for item in incoming]
        incoming_ids = [case.case_id for case in parsed]
        if len(incoming_ids) != len(set(incoming_ids)):
            raise ValueError("import contains duplicate case_id")
        existing = set(self._cases)
        duplicates = sorted(existing.intersection(incoming_ids))
        if duplicates:
            raise ValueError(f"case_id already exists: {', '.join(duplicates)}")
        document = json.loads(self.cases_path.read_text(encoding="utf-8"))
        document["cases"].extend(incoming)
        _atomic_write_json(self.cases_path, document)
        self.reload()
        return {"imported_count": len(incoming), "case_ids": incoming_ids, "summary": self.summary()}

