from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _outcome_metrics(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(outcomes)
    passed = sum(bool(item["passed"]) for item in outcomes)
    errors = Counter(code for item in outcomes for code in item.get("error_codes", []))
    covered = sum(int(item.get("checked_fact_count", 0)) > 0 for item in outcomes)
    return {
        "sample_size": count,
        "passed_count": passed,
        "pass_rate": round(passed / count, 4) if count else 0.0,
        "average_score": round(sum(float(item["score"]) for item in outcomes) / count, 2) if count else 0.0,
        "evidence_coverage": round(covered / count, 4) if count else 0.0,
        "error_code_counts": dict(sorted(errors.items())),
    }


def _arm_metrics(arm: dict[str, Any]) -> dict[str, Any]:
    outcomes = arm["outcomes"]
    return {
        "run_id": arm["run_id"],
        "label": arm["label"],
        "model_version": arm["model_version"],
        "prompt_version": arm["prompt_version"],
        "data_version": arm["data_version"],
        **_outcome_metrics(outcomes),
        "p95_latency_ms": int(arm["p95_latency_ms"]),
    }


def _index_outcomes(arm: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outcomes = arm["outcomes"]
    indexed = {item["case_id"]: item for item in outcomes}
    if len(indexed) != len(outcomes):
        raise ValueError(f"{arm['label']} contains duplicate case IDs")
    return indexed


def compare_versions(document: dict[str, Any]) -> dict[str, Any]:
    baseline = _arm_metrics(document["baseline"])
    candidate = _arm_metrics(document["candidate"])
    policy = document["gate_policy"]
    baseline_index = _index_outcomes(document["baseline"])
    candidate_index = _index_outcomes(document["candidate"])
    if baseline_index.keys() != candidate_index.keys():
        raise ValueError("baseline and candidate must contain identical case IDs")
    for case_id, baseline_item in baseline_index.items():
        if not baseline_item.get("intent"):
            raise ValueError(f"paired outcome {case_id} is missing an intent")
        if baseline_item["intent"] != candidate_index[case_id].get("intent"):
            raise ValueError(f"paired outcome {case_id} must use the same intent")

    intent_breakdown = []
    for intent in sorted({item["intent"] for item in baseline_index.values()}):
        case_ids = [case_id for case_id, item in baseline_index.items() if item["intent"] == intent]
        baseline_intent = _outcome_metrics([baseline_index[case_id] for case_id in case_ids])
        candidate_intent = _outcome_metrics([candidate_index[case_id] for case_id in case_ids])
        regressed = sum(
            bool(baseline_index[case_id]["passed"]) and not bool(candidate_index[case_id]["passed"])
            for case_id in case_ids
        )
        improved = sum(
            not bool(baseline_index[case_id]["passed"]) and bool(candidate_index[case_id]["passed"])
            for case_id in case_ids
        )
        intent_breakdown.append({
            "intent": intent,
            "sample_size": len(case_ids),
            "baseline": baseline_intent,
            "candidate": candidate_intent,
            "delta": {
                "pass_rate_pp": round((candidate_intent["pass_rate"] - baseline_intent["pass_rate"]) * 100, 2),
                "average_score": round(candidate_intent["average_score"] - baseline_intent["average_score"], 2),
                "evidence_coverage_pp": round((candidate_intent["evidence_coverage"] - baseline_intent["evidence_coverage"]) * 100, 2),
            },
            "improved_case_count": improved,
            "regressed_case_count": regressed,
        })

    improvement_pp = round((candidate["pass_rate"] - baseline["pass_rate"]) * 100, 2)
    blocking_count = sum(candidate["error_code_counts"].get(code, 0) for code in policy["blocking_error_codes"])
    maximum_intent_regression = float(policy.get("maximum_intent_pass_rate_regression_pp", 0))
    regressed_intents = [
        item for item in intent_breakdown
        if item["delta"]["pass_rate_pp"] < -maximum_intent_regression or item["regressed_case_count"] > 0
    ]
    gates = [
        {"gate_id": "paired_sample_size", "label": "配对样本量", "passed": candidate["sample_size"] >= policy["minimum_sample_size"], "observed": candidate["sample_size"], "threshold": f">={policy['minimum_sample_size']}", "hard_blocker": True},
        {"gate_id": "pass_rate_improvement", "label": "通过率改善", "passed": improvement_pp >= policy["minimum_pass_rate_improvement_pp"], "observed": f"{improvement_pp:+.1f}pp", "threshold": f">={policy['minimum_pass_rate_improvement_pp']}pp", "hard_blocker": False},
        {"gate_id": "intent_regression", "label": "意图级回归", "passed": not regressed_intents, "observed": f"{len(regressed_intents)}个意图退化", "threshold": "=0", "hard_blocker": True},
        {"gate_id": "evidence_coverage", "label": "证据核验覆盖", "passed": candidate["evidence_coverage"] >= policy["minimum_evidence_coverage"], "observed": f"{candidate['evidence_coverage'] * 100:.1f}%", "threshold": f">={policy['minimum_evidence_coverage'] * 100:.0f}%", "hard_blocker": True},
        {"gate_id": "blocking_errors", "label": "阻断类错误", "passed": blocking_count == 0, "observed": blocking_count, "threshold": "=0", "hard_blocker": True},
        {"gate_id": "p95_latency", "label": "P95 延迟", "passed": candidate["p95_latency_ms"] <= policy["maximum_p95_latency_ms"], "observed": f"{candidate['p95_latency_ms']}ms", "threshold": f"<={policy['maximum_p95_latency_ms']}ms", "hard_blocker": True}
    ]
    hard_failures = [gate for gate in gates if gate["hard_blocker"] and not gate["passed"]]
    return {
        "schema_version": "1.0",
        "dataset_kind": document.get("dataset_kind"),
        "disclaimer": document.get("disclaimer"),
        "policy_version": policy["policy_version"],
        "baseline": baseline,
        "candidate": candidate,
        "intent_breakdown": intent_breakdown,
        "delta": {
            "pass_rate_pp": improvement_pp,
            "average_score": round(candidate["average_score"] - baseline["average_score"], 2),
            "evidence_coverage_pp": round((candidate["evidence_coverage"] - baseline["evidence_coverage"]) * 100, 2),
            "p95_latency_ms": candidate["p95_latency_ms"] - baseline["p95_latency_ms"]
        },
        "gates": gates,
        "decision": {
            "status": "HOLD" if hard_failures else "CONSERVATIVE_ROLLOUT",
            "reason_codes": [gate["gate_id"] for gate in hard_failures],
            "summary": (
                f"{'、'.join(gate['label'] for gate in hard_failures)}未通过，仅允许继续离线验证。"
                if hard_failures else "硬性门槛均通过，可进入受限灰度。"
            )
        }
    }


def load_and_compare(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        document = json.load(handle)
    return compare_versions(document)
