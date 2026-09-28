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


def compare_signal_versions(
    baseline_feedback_document: dict[str, Any],
    candidate_feedback_document: dict[str, Any],
    baseline_hot_context_document: dict[str, Any],
    candidate_hot_context_document: dict[str, Any],
) -> dict[str, Any]:
    baseline_events = {item.get("pair_id"): item for item in baseline_feedback_document.get("events", [])}
    candidate_events = {item.get("pair_id"): item for item in candidate_feedback_document.get("events", [])}
    if (
        None in baseline_events
        or None in candidate_events
        or len(baseline_events) != len(baseline_feedback_document.get("events", []))
        or len(candidate_events) != len(candidate_feedback_document.get("events", []))
        or baseline_events.keys() != candidate_events.keys()
    ):
        raise ValueError("baseline and candidate feedback must contain identical pair IDs")
    for pair_id, baseline_event in baseline_events.items():
        if baseline_event["case_id"] != candidate_events[pair_id]["case_id"]:
            raise ValueError(f"feedback pair {pair_id} must use the same case ID")

    baseline_checks = {item["check_id"]: item for item in baseline_hot_context_document.get("checks", [])}
    candidate_checks = {item["check_id"]: item for item in candidate_hot_context_document.get("checks", [])}
    if (
        len(baseline_checks) != len(baseline_hot_context_document.get("checks", []))
        or len(candidate_checks) != len(candidate_hot_context_document.get("checks", []))
        or baseline_checks.keys() != candidate_checks.keys()
    ):
        raise ValueError("baseline and candidate hot-context checks must contain identical check IDs")
    for check_id, baseline_check in baseline_checks.items():
        if baseline_check["case_id"] != candidate_checks[check_id]["case_id"]:
            raise ValueError(f"hot-context pair {check_id} must use the same case ID")

    baseline = {
        "label": "Baseline",
        "feedback": summarize_feedback(baseline_feedback_document),
        "hot_context": evaluate_hot_context(baseline_hot_context_document),
    }
    candidate = {
        "label": "Candidate",
        "feedback": summarize_feedback(candidate_feedback_document),
        "hot_context": evaluate_hot_context(candidate_hot_context_document),
    }
    return {
        "schema_version": "2.0",
        "dataset_kind": "synthetic_paired_signal_governance_summary",
        "disclaimer": "Synthetic matched observation windows demonstrate the governance workflow; they are not causal or production evidence.",
        "pairing": {
            "feedback_observation_count": len(baseline_events),
            "hot_context_check_count": len(baseline_checks),
            "rule": "Feedback uses identical pair IDs and case IDs; hot-context uses identical check IDs and case IDs.",
        },
        "baseline": baseline,
        "candidate": candidate,
        "delta": {
            "negative_signal_rate_pp": round(
                (candidate["feedback"]["negative_signal_rate"] - baseline["feedback"]["negative_signal_rate"]) * 100, 2
            ),
            "negative_signal_count": candidate["feedback"]["negative_signal_count"] - baseline["feedback"]["negative_signal_count"],
            "escalated_case_count": candidate["feedback"]["escalated_case_count"] - baseline["feedback"]["escalated_case_count"],
            "hot_context_failed_count": candidate["hot_context"]["failed_count"] - baseline["hot_context"]["failed_count"],
        },
    }


def load_signal_summary(
    feedback_path: str | Path,
    hot_context_path: str | Path,
    candidate_feedback_path: str | Path | None = None,
    candidate_hot_context_path: str | Path | None = None,
) -> dict[str, Any]:
    with Path(feedback_path).open(encoding="utf-8") as handle:
        feedback = json.load(handle)
    with Path(hot_context_path).open(encoding="utf-8") as handle:
        hot_context = json.load(handle)
    if candidate_feedback_path is not None and candidate_hot_context_path is not None:
        with Path(candidate_feedback_path).open(encoding="utf-8") as handle:
            candidate_feedback = json.load(handle)
        with Path(candidate_hot_context_path).open(encoding="utf-8") as handle:
            candidate_hot_context = json.load(handle)
        return compare_signal_versions(feedback, candidate_feedback, hot_context, candidate_hot_context)
    return {
        "schema_version": "1.0",
        "dataset_kind": "synthetic_signal_governance_summary",
        "feedback": summarize_feedback(feedback),
        "hot_context": evaluate_hot_context(hot_context),
    }
