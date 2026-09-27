from __future__ import annotations

import json
from pathlib import Path

from .models import EvaluationCase, Fact


def _read_json(path: str | Path) -> object:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_facts(path: str | Path) -> list[Fact]:
    raw = _read_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("facts"), list):
        raise ValueError("facts file must contain a facts array")
    facts = [Fact.from_dict(item) for item in raw["facts"]]
    ids = [fact.fact_id for fact in facts]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate fact_id")
    return facts


def load_cases(path: str | Path) -> list[EvaluationCase]:
    raw = _read_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError("cases file must contain a cases array")
    cases = [EvaluationCase.from_dict(item) for item in raw["cases"]]
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case_id")
    return cases

