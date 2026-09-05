from __future__ import annotations

import pytest

from spanlite.trace import MemorySink, Tracer


@pytest.fixture
def tracer() -> Tracer:
    """A tracer with a memory sink. Fake the clock in tests that care about time."""
    return Tracer("pytest", sinks=[MemorySink()])
