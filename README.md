# InvestEval

InvestEval is a small, auditable quality-governance core for investment-agent answers. The first milestone provides frozen anonymous evaluation cases, typed data contracts, deterministic financial-fact checks, KYC and compliance rules, and reproducible tests.

## Current scope

- Four intents: market quote, financial analysis, news or announcement summary, and personalized explanation.
- Frozen synthetic fixtures with explicit `fixture://` provenance. They demonstrate the evaluation mechanics and are not represented as live market data.
- Deterministic checks for numeric mismatches, stale data, period mismatches, missing sources, unsupported claims, KYC mismatch, guaranteed-return language, privacy overreach, and facts changed by user profile.
- Per-case results with evidence references, reason codes, severity, and reproducible scores.

## Run

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m investeval.cli evaluate \
  --facts data/facts.json \
  --cases data/cases.json \
  --output artifacts/evaluation-results.json

# Start the dependency-free governance API
PYTHONPATH=src python -m investeval.cli serve --port 8000
```

## Governance API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Runtime health |
| `GET` | `/api/summary` | Quality and review summary |
| `GET` | `/api/cases` | Filterable case and Bad Case list |
| `GET` | `/api/cases/{case_id}` | Answer, findings, evidence lineage, and review detail |
| `POST` | `/api/evaluate` | Re-run deterministic evaluation |
| `POST` | `/api/cases/import` | Validate, persist, and evaluate anonymous QA logs |
| `POST` | `/api/cases/{case_id}/review` | Record a human review decision |

Example Bad Case query:

```text
/api/cases?outcome=bad_case&error_code=NUMERIC_MISMATCH&review_status=pending
```

The data is intentionally frozen so version comparisons use identical inputs. A future `FinancialDataProvider` adapter can replace the fixtures with Fuyao or iFinD MCP results without changing the evaluation result schema.
