from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from spanlite.evals.base import Suite
from spanlite.trace import MemorySink, Tracer


@pytest.fixture
def tracer() -> Tracer:
    """A tracer with a memory sink. Fake the clock in tests that care about time."""
    return Tracer("pytest", sinks=[MemorySink()])


@pytest.fixture
def suite_artifact() -> Callable[[Suite, str | Path], Path | None]:
    """Write a readable Suite artifact only when one or more rows have failed."""

    def write(suite: Suite, path: str | Path) -> Path | None:
        if all(row.passed for row in suite.rows):
            return None
        artifact = Path(path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps(suite.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact

    return write
