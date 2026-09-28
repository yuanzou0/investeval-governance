from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evaluator import evaluate_cases
from .models import EvaluationCase, Fact


def _digest(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_improvement_loop(document: dict[str, Any], facts: list[Fact]) -> dict[str, Any]:
    baseline_raw = document["baseline_case"]
    candidate_raw = document["candidate_case"]
    baseline_case = EvaluationCase.from_dict(baseline_raw)
    candidate_case = EvaluationCase.from_dict(candidate_raw)
    if baseline_case.case_id != candidate_case.case_id:
        raise ValueError("baseline and candidate improvement cases must share a case_id")
    if baseline_case.question != candidate_case.question:
        raise ValueError("baseline and candidate must answer the same question")

    baseline_result = evaluate_cases([baseline_case], facts)[0]
    candidate_result = evaluate_cases([candidate_case], facts)[0]
    verified = not baseline_result.passed and candidate_result.passed
    return {
        "schema_version": "1.0",
        "loop_id": document["loop_id"],
        "dataset_kind": document["dataset_kind"],
        "evidence_boundary": document["evidence_boundary"],
        "case_id": baseline_case.case_id,
        "question": baseline_case.question,
        "baseline": {
            "answer": baseline_case.answer,
            "model_version": baseline_case.model_version,
            "prompt_version": baseline_case.prompt_version,
            "data_version": baseline_case.data_version,
            "result": baseline_result.to_dict(),
            "input_sha256": _digest(baseline_raw),
        },
        "investigation": document["investigation"],
        "intervention": document["intervention"],
        "candidate": {
            "answer": candidate_case.answer,
            "model_version": candidate_case.model_version,
            "prompt_version": candidate_case.prompt_version,
            "data_version": candidate_case.data_version,
            "result": candidate_result.to_dict(),
            "input_sha256": _digest(candidate_raw),
        },
        "verification": {
            "status": "VERIFIED" if verified else "NOT_VERIFIED",
            "baseline_passed": baseline_result.passed,
            "candidate_passed": candidate_result.passed,
            "score_delta": candidate_result.score - baseline_result.score,
            "removed_error_codes": sorted(
                {item.code.value for item in baseline_result.findings}
                - {item.code.value for item in candidate_result.findings}
            ),
            "candidate_checked_fact_ids": candidate_result.checked_fact_ids,
            "candidate_answer_coverage": candidate_result.answer_coverage,
            "regression_scope": document["verification"]["regression_scope"],
            "rollout_decision": document["verification"]["rollout_decision"],
        },
    }


def load_and_run(path: str | Path, facts: list[Fact]) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        document = json.load(handle)
    return run_improvement_loop(document, facts)
