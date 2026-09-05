from __future__ import annotations

from dataclasses import dataclass

from spanlite.evals.base import Case, Output, Score


@dataclass(frozen=True)
class SkillCase(Case):
    tool: str | None = None
    required_args: tuple[str, ...] = ()
    should_refuse: bool = False


class SelectionJudge:
    name = "selection"

    def score(self, case: Case, output: Output) -> Score:
        want = getattr(case, "tool", None)
        if want is None:
            ok = len(output.tools) == 0
            return Score(self.name, 1.0 if ok else 0.0, ok, "no tool")
        ok = want in output.tools
        return Score(self.name, 1.0 if ok else 0.0, ok, f"want {want}")


class SchemaJudge:
    name = "schema"

    def score(self, case: Case, output: Output) -> Score:
        required = getattr(case, "required_args", ())
        if not required:
            return Score(self.name, 1.0, True, "none required")
        missing = [k for k in required if k not in output.args]
        ok = not missing
        return Score(self.name, 1.0 if ok else 0.0, ok, f"missing {missing}")


class RefusalJudge:
    name = "refusal"

    def score(self, case: Case, output: Output) -> Score:
        should = bool(getattr(case, "should_refuse", False))
        ok = output.refused is should
        return Score(self.name, 1.0 if ok else 0.0, ok, f"should_refuse={should}")
