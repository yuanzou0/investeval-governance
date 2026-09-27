from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _arm_metrics(arm: dict[str, Any]) -> dict[str, Any]:
    outcomes = arm["outcomes"]
    count = len(outcomes)
    passed = sum(bool(item["passed"]) for item in outcomes)
    errors = Counter(code for item in outcomes for code in item.get("error_codes", []))
    covered = sum(int(item.get("checked_fact_count", 0)) > 0 for item in outcomes)
    return {
        "run_id": arm["run_id"],
        "label": arm["label"],
        "model_version": arm["model_version"],
        "prompt_version": arm["prompt_version"],
        "data_version": arm["data_version"],
        "sample_size": count,
        "passed_count": passed,
        "pass_rate": round(passed / count, 4) if count else 0.0,
        "average_score": round(sum(float(item["score"]) for item in outcomes) / count, 2) if count else 0.0,
        "evidence_coverage": round(covered / count, 4) if count else 0.0,
        "p95_latency_ms": int(arm["p95_latency_ms"]),
        "error_code_counts": dict(sorted(errors.items())),
    }


def compare_versions(document: dict[str, Any]) -> dict[str, Any]:
    baseline = _arm_metrics(document["baseline"])
    candidate = _arm_metrics(document["candidate"])
    policy = document["gate_policy"]
    baseline_ids = {item["case_id"] for item in document["baseline"]["outcomes"]}
    candidate_ids = {item["case_id"] for item in document["candidate"]["outcomes"]}
    if baseline_ids != candidate_ids:
        raise ValueError("baseline and candidate must contain identical case IDs")

    improvement_pp = round((candidate["pass_rate"] - baseline["pass_rate"]) * 100, 2)
    blocking_count = sum(candidate["error_code_counts"].get(code, 0) for code in policy["blocking_error_codes"])
    gates = [
        {"gate_id": "paired_sample_size", "label": "配对样本量", "passed": candidate["sample_size"] >= policy["minimum_sample_size"], "observed": candidate["sample_size"], "threshold": f">={policy['minimum_sample_size']}", "hard_blocker": True},
        {"gate_id": "pass_rate_improvement", "label": "通过率改善", "passed": improvement_pp >= policy["minimum_pass_rate_improvement_pp"], "observed": f"{improvement_pp:+.1f}pp", "threshold": f">={policy['minimum_pass_rate_improvement_pp']}pp", "hard_blocker": False},
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
            "summary": "样本量不足且延迟超过门槛，仅允许继续离线验证。" if hard_failures else "硬性门槛均通过，可进入受限灰度。"
        }
    }


def load_and_compare(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        document = json.load(handle)
    return compare_versions(document)

