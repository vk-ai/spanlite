from __future__ import annotations

from pathlib import Path

import pytest

from spanlite import JsonlSink, MemorySink, Tracer


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        self.t += 0.01
        return self.t


class SeqIds:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"s{self.n}"


def test_nested_spans_and_cost() -> None:
    sink = MemorySink()
    t = Tracer(
        "run",
        model="grok",
        usd_per_1k_in=1.0,
        usd_per_1k_out=2.0,
        clock=FakeClock(),
        ids=SeqIds(),
        sinks=[sink],
    )
    with t.span("answer", "llm") as span:
        t.tokens(span, 1000, 500)
        with t.span("search", "tool", tool="web"):
            pass
    s = t.summary()
    assert s["spans"] == 2
    assert s["tokens_in"] == 1000
    assert s["cost_usd"] == 2.0
    assert sink.records[0]["name"] == "search"
    assert sink.records[1]["parent_id"] is None


def test_error_recorded_and_reraised() -> None:
    t = Tracer("x", clock=FakeClock(), ids=SeqIds())
    with pytest.raises(RuntimeError):
        with t.span("boom"):
            raise RuntimeError("nope")
    assert t.spans[0].error == "RuntimeError: nope"


def test_jsonl_sink(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    t = Tracer("x", clock=FakeClock(), ids=SeqIds(), sinks=[JsonlSink(path)])
    with t.span("a"):
        pass
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert '"name": "a"' in lines[0]
