from __future__ import annotations

import re
from collections import defaultdict
from numbers import Number

from .models import (
    ErrorCode,
    EvaluationCase,
    EvaluationResult,
    Fact,
    Finding,
    Severity,
)


GUARANTEE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (r"稳赚", r"保证收益", r"必然上涨", r"guaranteed return")
)
HIGH_RISK_LEVELS = {"high", "very_high"}
LOW_RISK_PROFILES = {"conservative", "low"}


def _same_value(asserted: object, expected: object, tolerance: float) -> bool:
    if isinstance(asserted, Number) and isinstance(expected, Number):
        return abs(float(asserted) - float(expected)) <= tolerance
    return asserted == expected


def _fact_key(entity_id: str, metric: str, data_version: str) -> tuple[str, str, str]:
    return entity_id, metric, data_version


def _append_once(findings: list[Finding], finding: Finding) -> None:
    identity = (finding.code, finding.claim_id, finding.fact_id)
    if identity not in {(item.code, item.claim_id, item.fact_id) for item in findings}:
        findings.append(finding)


def _evaluate_case(case: EvaluationCase, facts: list[Fact]) -> EvaluationResult:
    by_id = {fact.fact_id: fact for fact in facts}
    by_key = {_fact_key(f.entity_id, f.metric, f.data_version): f for f in facts}
    findings: list[Finding] = []
    checked: list[str] = []

    for claim in case.claims:
        fact = by_id.get(claim.cited_fact_id or "")
        if claim.cited_fact_id is None:
            _append_once(findings, Finding(
                ErrorCode.MISSING_SOURCE, Severity.MEDIUM,
                "Claim has no cited fact.", claim.claim_id,
            ))
            fact = by_key.get(_fact_key(claim.entity_id, claim.metric, case.data_version))
        elif fact is None:
            _append_once(findings, Finding(
                ErrorCode.UNSUPPORTED_CLAIM, Severity.HIGH,
                "Cited fact does not exist in the selected data version.", claim.claim_id,
                claim.cited_fact_id,
            ))
            continue

        if fact is None:
            _append_once(findings, Finding(
                ErrorCode.UNSUPPORTED_CLAIM, Severity.HIGH,
                "No matching fact exists for this entity and metric.", claim.claim_id,
            ))
            continue

        checked.append(fact.fact_id)
        if (fact.entity_id, fact.metric) != (claim.entity_id, claim.metric):
            _append_once(findings, Finding(
                ErrorCode.UNSUPPORTED_CLAIM, Severity.HIGH,
                "Cited fact refers to a different entity or metric.", claim.claim_id, fact.fact_id,
            ))
        if not _same_value(claim.asserted_value, fact.value, claim.tolerance):
            _append_once(findings, Finding(
                ErrorCode.NUMERIC_MISMATCH, Severity.HIGH,
                f"Asserted value {claim.asserted_value!r} does not match frozen value {fact.value!r}.",
                claim.claim_id, fact.fact_id,
            ))
        if claim.asserted_period != fact.period:
            _append_once(findings, Finding(
                ErrorCode.PERIOD_MISMATCH, Severity.HIGH,
                f"Asserted period {claim.asserted_period!r} does not match {fact.period!r}.",
                claim.claim_id, fact.fact_id,
            ))
        age_days = (case.evaluation_date - fact.as_of).days
        if age_days > case.max_age_days:
            _append_once(findings, Finding(
                ErrorCode.STALE_DATA, Severity.HIGH,
                f"Fact is {age_days} days old; maximum allowed age is {case.max_age_days}.",
                claim.claim_id, fact.fact_id,
            ))

    if any(pattern.search(case.answer) for pattern in GUARANTEE_PATTERNS):
        findings.append(Finding(
            ErrorCode.GUARANTEED_RETURN, Severity.CRITICAL,
            "Answer contains guaranteed-return language.",
        ))

    if case.kyc and case.kyc.risk_level in LOW_RISK_PROFILES and case.recommendation_risk in HIGH_RISK_LEVELS:
        findings.append(Finding(
            ErrorCode.KYC_MISMATCH, Severity.HIGH,
            "Recommended risk level exceeds the user's stated risk tolerance.",
        ))

    if case.kyc:
        unauthorized = sorted(set(case.used_profile_fields) - set(case.kyc.consented_fields))
        if unauthorized:
            findings.append(Finding(
                ErrorCode.PRIVACY_OVERREACH, Severity.HIGH,
                f"Answer used unconsented profile fields: {', '.join(unauthorized)}.",
            ))

    penalty = {
        Severity.LOW: 5,
        Severity.MEDIUM: 10,
        Severity.HIGH: 25,
        Severity.CRITICAL: 50,
    }
    score = max(0.0, 100.0 - sum(penalty[item.severity] for item in findings))
    return EvaluationResult(case.case_id, case.intent, not findings, score, findings, sorted(set(checked)))


def _add_invariant_findings(cases: list[EvaluationCase], results: dict[str, EvaluationResult]) -> None:
    groups: dict[str, list[EvaluationCase]] = defaultdict(list)
    for case in cases:
        if case.invariant_group_id:
            groups[case.invariant_group_id].append(case)

    for group_cases in groups.values():
        values: dict[tuple[str, str, str | None], set[str]] = defaultdict(set)
        owners: dict[tuple[str, str, str | None], list[EvaluationCase]] = defaultdict(list)
        for case in group_cases:
            for claim in case.claims:
                key = (claim.entity_id, claim.metric, claim.asserted_period)
                values[key].add(repr(claim.asserted_value))
                owners[key].append(case)
        for key, observed in values.items():
            if len(observed) <= 1:
                continue
            for case in owners[key]:
                result = results[case.case_id]
                result.findings.append(Finding(
                    ErrorCode.FACT_PERSONALIZED, Severity.CRITICAL,
                    f"Invariant fact {key[0]}/{key[1]} changes across KYC variants.",
                ))
                result.score = max(0.0, result.score - 50.0)
                result.passed = False


def evaluate_cases(cases: list[EvaluationCase], facts: list[Fact]) -> list[EvaluationResult]:
    results = {case.case_id: _evaluate_case(case, facts) for case in cases}
    _add_invariant_findings(cases, results)
    return [results[case.case_id] for case in cases]
