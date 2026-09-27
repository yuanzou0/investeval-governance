from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Intent(str, Enum):
    MARKET_QUOTE = "market_quote"
    FINANCIAL_ANALYSIS = "financial_analysis"
    NEWS_SUMMARY = "news_summary"
    PERSONALIZED_EXPLANATION = "personalized_explanation"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCode(str, Enum):
    NUMERIC_MISMATCH = "NUMERIC_MISMATCH"
    STALE_DATA = "STALE_DATA"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    MISSING_SOURCE = "MISSING_SOURCE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    KYC_MISMATCH = "KYC_MISMATCH"
    FACT_PERSONALIZED = "FACT_PERSONALIZED"
    GUARANTEED_RETURN = "GUARANTEED_RETURN"
    PRIVACY_OVERREACH = "PRIVACY_OVERREACH"


@dataclass(frozen=True)
class Fact:
    fact_id: str
    entity_id: str
    metric: str
    value: Any
    unit: str | None
    as_of: date
    period: str | None
    source_locator: str
    source_title: str
    data_version: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Fact":
        required = {
            "fact_id", "entity_id", "metric", "value", "as_of",
            "source_locator", "source_title", "data_version",
        }
        missing = required - raw.keys()
        if missing:
            raise ValueError(f"fact missing fields: {sorted(missing)}")
        if not str(raw["source_locator"]).startswith(("fixture://", "https://")):
            raise ValueError("source_locator must use fixture:// or https://")
        return cls(
            fact_id=str(raw["fact_id"]),
            entity_id=str(raw["entity_id"]),
            metric=str(raw["metric"]),
            value=raw["value"],
            unit=raw.get("unit"),
            as_of=date.fromisoformat(raw["as_of"]),
            period=raw.get("period"),
            source_locator=str(raw["source_locator"]),
            source_title=str(raw["source_title"]),
            data_version=str(raw["data_version"]),
        )


@dataclass(frozen=True)
class Claim:
    claim_id: str
    entity_id: str
    metric: str
    asserted_value: Any
    unit: str | None
    asserted_as_of: date
    asserted_period: str | None
    cited_fact_id: str | None
    tolerance: float = 0.0

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Claim":
        return cls(
            claim_id=str(raw["claim_id"]),
            entity_id=str(raw["entity_id"]),
            metric=str(raw["metric"]),
            asserted_value=raw["asserted_value"],
            unit=raw.get("unit"),
            asserted_as_of=date.fromisoformat(raw["asserted_as_of"]),
            asserted_period=raw.get("asserted_period"),
            cited_fact_id=raw.get("cited_fact_id"),
            tolerance=float(raw.get("tolerance", 0.0)),
        )


@dataclass(frozen=True)
class KYCProfile:
    profile_id: str
    risk_level: str
    horizon: str
    experience: str
    consented_fields: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "KYCProfile":
        return cls(
            profile_id=str(raw["profile_id"]),
            risk_level=str(raw["risk_level"]),
            horizon=str(raw["horizon"]),
            experience=str(raw["experience"]),
            consented_fields=tuple(raw.get("consented_fields", [])),
        )


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    invariant_group_id: str | None
    intent: Intent
    question: str
    answer: str
    evaluation_date: date
    max_age_days: int
    model_version: str
    prompt_version: str
    data_version: str
    kyc: KYCProfile | None
    claims: tuple[Claim, ...]
    recommendation_risk: str | None = None
    used_profile_fields: tuple[str, ...] = ()
    expected_error_codes: tuple[ErrorCode, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EvaluationCase":
        return cls(
            case_id=str(raw["case_id"]),
            invariant_group_id=raw.get("invariant_group_id"),
            intent=Intent(raw["intent"]),
            question=str(raw["question"]),
            answer=str(raw["answer"]),
            evaluation_date=date.fromisoformat(raw["evaluation_date"]),
            max_age_days=int(raw["max_age_days"]),
            model_version=str(raw["model_version"]),
            prompt_version=str(raw["prompt_version"]),
            data_version=str(raw["data_version"]),
            kyc=KYCProfile.from_dict(raw["kyc"]) if raw.get("kyc") else None,
            claims=tuple(Claim.from_dict(item) for item in raw.get("claims", [])),
            recommendation_risk=raw.get("recommendation_risk"),
            used_profile_fields=tuple(raw.get("used_profile_fields", [])),
            expected_error_codes=tuple(ErrorCode(code) for code in raw.get("expected_error_codes", [])),
        )


@dataclass(frozen=True)
class Finding:
    code: ErrorCode
    severity: Severity
    message: str
    claim_id: str | None = None
    fact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "claim_id": self.claim_id,
            "fact_id": self.fact_id,
        }


@dataclass
class EvaluationResult:
    case_id: str
    intent: Intent
    passed: bool
    score: float
    findings: list[Finding] = field(default_factory=list)
    checked_fact_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "intent": self.intent.value,
            "passed": self.passed,
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
            "checked_fact_ids": self.checked_fact_ids,
        }

