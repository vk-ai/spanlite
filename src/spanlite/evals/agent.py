from __future__ import annotations

from dataclasses import dataclass

from spanlite.evals.base import Case, Output, Score


@dataclass(frozen=True)
class AgentCase(Case):
    """A task the agent must finish. expect is a substring or callable."""

    max_loops: int = 4


class TaskJudge:
    """Did the final text contain the expected answer?"""

    name = "task"

    def score(self, case: Case, output: Output) -> Score:
        expect = case.expect
        text = output.text or ""
        if callable(expect):
            ok = bool(expect(text, output))
            detail = "predicate"
        elif expect is None:
            ok = bool(text.strip())
            detail = "non-empty"
        else:
            needle = str(expect).lower()
            ok = needle in text.lower()
            detail = f"look for {expect!r}"
        return Score(self.name, 1.0 if ok else 0.0, ok, detail)


class LoopJudge:
    """Agents that spin are a cost leak. Fail if loops exceed the case cap."""

    name = "loops"

    def score(self, case: Case, output: Output) -> Score:
        cap = getattr(case, "max_loops", 4)
        ok = output.loops <= cap
        return Score(self.name, float(output.loops), ok, f"cap {cap}")
