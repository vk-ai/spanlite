# Contributing to spanlite

Small library. Small PRs.

## First-time setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## What we take

- A new `Judge` with tests (strategy pattern, no network)
- Docs or example that show install in an existing pytest suite
- A bug with a failing test first

## What we do not take

- Vendor SDKs, OpenTelemetry exporters, LLM-as-judge in CI
- Drive-by dependency bumps
- Issues that only say "please add LangChain support" with no sketch

## PR shape

1. One idea.
2. Tests that do not sleep (inject `Clock`).
3. No new required dependencies.

Good first issues: extra RAG metrics that stay lexical, a JSONL pretty-printer, a pytest fixture that writes `suite.to_json()` on failure.
