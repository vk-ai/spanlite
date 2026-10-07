from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from spanlite.evals.base import Suite
from spanlite.redact import Redactor, default_redactor
from spanlite.trace import MemorySink, Tracer

_DEFAULT: object = object()


@pytest.fixture
def tracer() -> Tracer:
    """A tracer with a memory sink. Fake the clock in tests that care about time."""
    return Tracer("pytest", sinks=[MemorySink()])


@pytest.fixture
def suite_artifact() -> Callable[..., Path | None]:
    """Write a readable Suite artifact only when one or more rows have failed.

    The artifact is redacted first (secrets by default; pass
    ``redactor=Redactor.with_pii()`` for PII too, or ``redactor=None`` to
    write it raw).
    """

    def write(
        suite: Suite,
        path: str | Path,
        *,
        redactor: Redactor | None | object = _DEFAULT,
    ) -> Path | None:
        if all(row.passed for row in suite.rows):
            return None
        data = suite.to_json()
        active = default_redactor() if redactor is _DEFAULT else redactor
        if isinstance(active, Redactor):
            data = active.redact(data)
        artifact = Path(path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact

    return write
