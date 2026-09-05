from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Protocol

_PARENT: ContextVar[str | None] = ContextVar("spanlite_parent", default=None)


class Clock(Protocol):
    def now(self) -> float: ...


class IdFactory(Protocol):
    def __call__(self) -> str: ...


class Sink(Protocol):
    def emit(self, record: Mapping[str, Any]) -> None: ...


class WallClock:
    def now(self) -> float:
        return time.perf_counter()


class UuidFactory:
    def __call__(self) -> str:
        return uuid.uuid4().hex[:12]


class MemorySink:
    """Strategy: keep records in process for tests and summaries."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def emit(self, record: Mapping[str, Any]) -> None:
        self.records.append(dict(record))


class JsonlSink:
    """Strategy: append-only JSONL. Safe for local CI. No daemon."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: Mapping[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


@dataclass
class Span:
    id: str
    name: str
    kind: str
    parent_id: str | None
    t0: float
    t1: float | None = None
    tool: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def ms(self) -> float:
        end = self.t1 if self.t1 is not None else self.t0
        return round((end - self.t0) * 1000, 3)


class Tracer:
    """Facade over nested spans.

    Inject Clock and IdFactory in tests. Never sleeps. Never talks to a vendor.
    """

    def __init__(
        self,
        run_id: str,
        *,
        model: str = "unknown",
        usd_per_1k_in: float = 0.0,
        usd_per_1k_out: float = 0.0,
        clock: Clock | None = None,
        ids: IdFactory | None = None,
        sinks: list[Sink] | None = None,
    ) -> None:
        self.run_id = run_id
        self.model = model
        self.usd_per_1k_in = usd_per_1k_in
        self.usd_per_1k_out = usd_per_1k_out
        self._clock = clock or WallClock()
        self._ids = ids or UuidFactory()
        self._sinks = sinks or [MemorySink()]
        self.spans: list[Span] = []

    def _emit(self, record: Mapping[str, Any]) -> None:
        for sink in self._sinks:
            sink.emit(record)

    @contextmanager
    def span(
        self,
        name: str,
        kind: str = "llm",
        *,
        tool: str | None = None,
        **attrs: Any,
    ) -> Iterator[Span]:
        parent = _PARENT.get()
        item = Span(
            id=self._ids(),
            name=name,
            kind=kind,
            parent_id=parent,
            t0=self._clock.now(),
            tool=tool,
            attrs=dict(attrs),
        )
        self.spans.append(item)
        token = _PARENT.set(item.id)
        try:
            yield item
        except Exception as exc:
            item.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            item.t1 = self._clock.now()
            _PARENT.reset(token)
            self._emit(self._record(item))

    def tokens(self, span: Span, tokens_in: int, tokens_out: int = 0) -> None:
        span.tokens_in += tokens_in
        span.tokens_out += tokens_out

    def _record(self, span: Span) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "span_id": span.id,
            "parent_id": span.parent_id,
            "name": span.name,
            "kind": span.kind,
            "tool": span.tool,
            "ms": span.ms,
            "tokens_in": span.tokens_in,
            "tokens_out": span.tokens_out,
            "cost_usd": self._cost(span),
            "error": span.error,
            "attrs": span.attrs,
        }

    def _cost(self, span: Span) -> float:
        return round(
            (span.tokens_in / 1000) * self.usd_per_1k_in
            + (span.tokens_out / 1000) * self.usd_per_1k_out,
            6,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model": self.model,
            "spans": len(self.spans),
            "errors": sum(1 for s in self.spans if s.error),
            "tokens_in": sum(s.tokens_in for s in self.spans),
            "tokens_out": sum(s.tokens_out for s in self.spans),
            "cost_usd": round(sum(self._cost(s) for s in self.spans), 6),
            "latency_ms": round(sum(s.ms for s in self.spans), 3),
        }
