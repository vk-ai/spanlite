from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class Case:
    id: str
    input: Any
    expect: Any = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Output:
    text: str = ""
    tools: tuple[str, ...] = ()
    args: dict[str, Any] = field(default_factory=dict)
    retrieved: tuple[str, ...] = ()
    loops: int = 1
    refused: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Score:
    name: str
    value: float
    passed: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "passed": self.passed,
            "detail": self.detail,
        }


class Judge(Protocol):
    """Strategy: one numeric score, one pass/fail."""

    name: str

    def score(self, case: Case, output: Output) -> Score: ...


@dataclass
class Row:
    case_id: str
    scores: list[Score]
    passed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "scores": [s.as_dict() for s in self.scores],
        }


class Suite:
    """Template method: run every case through every judge.

    The agent under test is a callable(case) -> Output. No framework required.
    """

    def __init__(self, name: str, judges: Sequence[Judge]) -> None:
        if not judges:
            raise ValueError("Suite needs at least one judge")
        self.name = name
        self.judges = list(judges)
        self.rows: list[Row] = []

    def run(self, cases: Sequence[Case], agent) -> list[Row]:
        self.rows = []
        for case in cases:
            output = agent(case)
            if not isinstance(output, Output):
                output = Output(text=str(output))
            scores = [j.score(case, output) for j in self.judges]
            self.rows.append(
                Row(
                    case_id=case.id,
                    scores=scores,
                    passed=all(s.passed for s in scores),
                )
            )
        return self.rows

    def pass_rate(self) -> float:
        if not self.rows:
            return 0.0
        return round(sum(1 for r in self.rows if r.passed) / len(self.rows), 4)

    def mean(self, judge_name: str) -> float:
        vals = [s.value for r in self.rows for s in r.scores if s.name == judge_name]
        if not vals:
            return 0.0
        return round(sum(vals) / len(vals), 4)
