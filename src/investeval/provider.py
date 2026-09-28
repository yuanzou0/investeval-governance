from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderCheck:
    scenario_id: str
    status: str
    error_code: str | None
    allow_fact_use: bool
    rollout_decision: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "error_code": self.error_code,
            "allow_fact_use": self.allow_fact_use,
            "rollout_decision": self.rollout_decision,
            "reason": self.reason,
        }


def assess_provider_response(raw: dict[str, Any]) -> ProviderCheck:
    scenario_id = str(raw["scenario_id"])
    status_code = int(raw.get("status_code", 0))
    payload = raw.get("payload")
    required_fields = tuple(raw.get("required_fields", ("value", "as_of", "source")))

    failure: tuple[str, str] | None = None
    if raw.get("timed_out"):
        failure = ("PROVIDER_TIMEOUT", "data provider request timed out")
    elif not raw.get("available", True):
        failure = ("PROVIDER_UNAVAILABLE", "data provider is unavailable")
    elif status_code == 429:
        failure = ("PROVIDER_RATE_LIMITED", "data provider returned HTTP 429")
    elif status_code in (401, 403):
        failure = ("PROVIDER_AUTH_FAILED", f"data provider returned HTTP {status_code}")
    elif 500 <= status_code <= 599:
        failure = ("PROVIDER_UPSTREAM_ERROR", f"data provider returned HTTP {status_code}")
    elif status_code != 200:
        failure = ("PROVIDER_HTTP_ERROR", f"data provider returned HTTP {status_code}")
    elif not isinstance(payload, dict):
        failure = ("PROVIDER_SCHEMA_INVALID", "data provider payload is not an object")
    else:
        missing = [field for field in required_fields if field not in payload]
        if missing:
            failure = ("PROVIDER_SCHEMA_INVALID", f"data provider payload missing fields: {missing}")

    if failure:
        return ProviderCheck(
            scenario_id=scenario_id,
            status="FAIL_CLOSED",
            error_code=failure[0],
            allow_fact_use=False,
            rollout_decision="HOLD",
            reason=failure[1],
        )
    return ProviderCheck(
        scenario_id=scenario_id,
        status="PASS",
        error_code=None,
        allow_fact_use=True,
        rollout_decision="CONTINUE_EVALUATION",
        reason="provider response is complete and may enter fact verification",
    )


def run_provider_drill(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        raw = json.load(handle)
    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("provider drill must contain a non-empty scenarios array")
    results = [assess_provider_response(item) for item in scenarios]
    return {
        "schema_version": "1.0",
        "provider_mode": "simulated_failure_drill",
        "summary": {
            "scenario_count": len(results),
            "passed_count": sum(result.status == "PASS" for result in results),
            "fail_closed_count": sum(result.status == "FAIL_CLOSED" for result in results),
            "all_failures_block_fact_use": all(
                not result.allow_fact_use for result in results if result.status == "FAIL_CLOSED"
            ),
        },
        "results": [result.to_dict() for result in results],
        "evidence_boundary": (
            "Synthetic provider-failure evidence only; this does not prove a live Fuyao or iFinD integration."
        ),
    }
