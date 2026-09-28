from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ALLOWED_SIGNALS = {"helpful", "not_helpful", "retry", "report"}
NEGATIVE_SIGNALS = {"not_helpful", "retry", "report"}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def summarize_feedback(document: dict[str, Any]) -> dict[str, Any]:
    events = document.get("events", [])
    ids = [event["event_id"] for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate feedback event_id")
    if any(event.get("signal") not in ALLOWED_SIGNALS for event in events):
        raise ValueError("unsupported feedback signal")

    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    totals = Counter()
    for event in events:
        _parse_time(event["occurred_at"])
        grouped[event["case_id"]][event["signal"]] += 1
        totals[event["signal"]] += 1

    rows = []
    for case_id, counts in sorted(grouped.items()):
        negative = sum(counts[signal] for signal in NEGATIVE_SIGNALS)
        escalated = counts["report"] > 0 or negative >= 2
        rows.append({
            "case_id": case_id,
            "helpful": counts["helpful"],
            "not_helpful": counts["not_helpful"],
            "retry": counts["retry"],
            "report": counts["report"],
            "negative_signal_count": negative,
            "escalated": escalated,
            "action": "human_review" if counts["report"] else "quality_investigation" if escalated else "observe",
        })

    negative_total = sum(totals[signal] for signal in NEGATIVE_SIGNALS)
    return {
        "event_count": len(events),
        "helpful_count": totals["helpful"],
        "negative_signal_count": negative_total,
        "negative_signal_rate": round(negative_total / len(events), 4) if events else 0.0,
        "report_count": totals["report"],
        "escalated_case_count": sum(row["escalated"] for row in rows),
        "cases": rows,
        "interpretation_boundary": "Behavior signals prioritize investigation; they never override factual or compliance findings.",
    }


def evaluate_hot_context(document: dict[str, Any]) -> dict[str, Any]:
    results = []
    for item in document.get("checks", []):
        question_time = _parse_time(item["question_time"])
        published_at = _parse_time(item["source_published_at"])
        age_hours = round((question_time - published_at).total_seconds() / 3600, 2)
        findings = []
        if published_at > question_time:
            findings.append("FUTURE_CONTEXT_LEAK")
        elif age_hours > float(item["maximum_age_hours"]):
            findings.append("HOT_CONTEXT_STALE")
        if item.get("answer_event_date") != item.get("reference_event_date"):
            findings.append("EVENT_TIME_MISMATCH")
        results.append({
            "check_id": item["check_id"],
            "case_id": item["case_id"],
            "question_time": item["question_time"],
            "source_published_at": item["source_published_at"],
            "age_hours": age_hours,
            "maximum_age_hours": item["maximum_age_hours"],
            "passed": not findings,
            "findings": findings,
        })
    return {
        "check_count": len(results),
        "passed_count": sum(item["passed"] for item in results),
        "failed_count": sum(not item["passed"] for item in results),
        "results": results,
    }


def load_signal_summary(feedback_path: str | Path, hot_context_path: str | Path) -> dict[str, Any]:
    with Path(feedback_path).open(encoding="utf-8") as handle:
        feedback = json.load(handle)
    with Path(hot_context_path).open(encoding="utf-8") as handle:
        hot_context = json.load(handle)
    return {
        "schema_version": "1.0",
        "dataset_kind": "synthetic_signal_governance_summary",
        "feedback": summarize_feedback(feedback),
        "hot_context": evaluate_hot_context(hot_context),
    }

