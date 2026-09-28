from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .evaluator import evaluate_cases
from .governance import GovernanceService
from .loader import load_cases, load_facts
from .rollout import load_and_compare
from .signals import load_signal_summary
from .web_api import serve


def _evaluate(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    facts = load_facts(args.facts)
    results = evaluate_cases(cases, facts)
    codes = Counter(finding.code.value for result in results for finding in result.findings)
    payload = {
        "schema_version": "1.0",
        "summary": {
            "case_count": len(results),
            "passed_count": sum(result.passed for result in results),
            "pass_rate": round(sum(result.passed for result in results) / len(results), 4),
            "error_code_counts": dict(sorted(codes.items())),
        },
        "results": [result.to_dict() for result in results],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


def _serve(args: argparse.Namespace) -> int:
    service = GovernanceService(args.facts, args.cases, args.reviews)
    serve(service, args.host, args.port)
    return 0


def _compare(args: argparse.Namespace) -> int:
    payload = load_and_compare(args.runs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "delta": payload["delta"]}, ensure_ascii=False, indent=2))
    return 0


def _signals(args: argparse.Namespace) -> int:
    payload = load_signal_summary(args.feedback, args.hot_context)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"feedback": payload["feedback"], "hot_context": {key: payload["hot_context"][key] for key in ("check_count", "passed_count", "failed_count")}}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="investeval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--facts", required=True)
    evaluate.add_argument("--cases", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.set_defaults(func=_evaluate)
    api = subparsers.add_parser("serve")
    api.add_argument("--facts", default="data/facts.json")
    api.add_argument("--cases", default="data/cases.json")
    api.add_argument("--reviews", default="runtime/reviews.json")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    api.set_defaults(func=_serve)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--runs", default="data/version-runs.json")
    compare.add_argument("--output", default="artifacts/version-comparison.json")
    compare.set_defaults(func=_compare)
    signals = subparsers.add_parser("signals")
    signals.add_argument("--feedback", default="data/user-feedback.json")
    signals.add_argument("--hot-context", default="data/hot-context.json")
    signals.add_argument("--output", default="artifacts/signals-context-summary.json")
    signals.set_defaults(func=_signals)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
