"""Promote failing suite runs into frozen regression packs for local CI replay.

Community pattern: capture a bad eval run → freeze cases + outputs → replay
through the same judges after prompt/agent changes. No cloud, no LLM-as-judge.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from spanlite.evals.agent import AgentCase
from spanlite.evals.base import Case, Output, Suite
from spanlite.evals.rag import RagCase
from spanlite.evals.skill import SkillCase

REGRESSION_VERSION = 1
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class PromoteError(ValueError):
    """Raised when a suite cannot be promoted or a pack is invalid."""


@dataclass(frozen=True)
class RegressionPack:
    """Frozen failing run: cases, recorded outputs, and baseline suite JSON."""

    version: int
    name: str
    suite: str
    judges: tuple[str, ...]
    cases: tuple[dict[str, Any], ...]
    outputs: dict[str, dict[str, Any]]
    baseline: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        """Stable on-disk shape (sorted keys at dump time)."""
        return {
            "baseline": self.baseline,
            "cases": list(self.cases),
            "judges": list(self.judges),
            "kind": "suite_regression",
            "name": self.name,
            "outputs": dict(sorted(self.outputs.items())),
            "suite": self.suite,
            "version": self.version,
        }


def _slug(name: str) -> str:
    cleaned = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return cleaned or "regression"


def _require_jsonable(value: Any, field: str) -> Any:
    if callable(value):
        raise PromoteError(f"{field} must be JSON-serializable; got a callable")
    try:
        json.dumps(value)
    except TypeError as exc:
        raise PromoteError(f"{field} must be JSON-serializable: {exc}") from exc
    return value


def case_to_dict(case: Case) -> dict[str, Any]:
    """Serialize a Case (and subclasses) for a regression pack."""
    base: dict[str, Any] = {
        "expect": _require_jsonable(case.expect, "case.expect"),
        "id": case.id,
        "input": _require_jsonable(case.input, "case.input"),
        "tags": list(case.tags),
    }
    if isinstance(case, RagCase):
        base["kind"] = "rag"
        base["gold_ids"] = list(case.gold_ids)
        base["k"] = case.k
        base["must_phrases"] = list(case.must_phrases)
    elif isinstance(case, SkillCase):
        base["kind"] = "skill"
        base["required_args"] = list(case.required_args)
        base["should_refuse"] = case.should_refuse
        base["tool"] = case.tool
    elif isinstance(case, AgentCase):
        base["kind"] = "agent"
        base["max_loops"] = case.max_loops
    else:
        base["kind"] = "case"
    return base


def case_from_dict(data: Mapping[str, Any]) -> Case:
    """Deserialize a Case from a regression pack entry."""
    kind = data.get("kind", "case")
    common = {
        "id": data["id"],
        "input": data["input"],
        "expect": data.get("expect"),
        "tags": tuple(data.get("tags") or ()),
    }
    if kind == "rag":
        return RagCase(
            **common,
            gold_ids=tuple(data.get("gold_ids") or ()),
            k=int(data.get("k", 5)),
            must_phrases=tuple(data.get("must_phrases") or ()),
        )
    if kind == "skill":
        return SkillCase(
            **common,
            tool=data.get("tool"),
            required_args=tuple(data.get("required_args") or ()),
            should_refuse=bool(data.get("should_refuse", False)),
        )
    if kind == "agent":
        return AgentCase(**common, max_loops=int(data.get("max_loops", 4)))
    return Case(**common)


def output_to_dict(output: Output) -> dict[str, Any]:
    return {
        "args": dict(output.args),
        "extra": dict(output.extra),
        "loops": output.loops,
        "refused": output.refused,
        "retrieved": list(output.retrieved),
        "text": output.text,
        "tools": list(output.tools),
    }


def output_from_dict(data: Mapping[str, Any]) -> Output:
    return Output(
        text=str(data.get("text") or ""),
        tools=tuple(data.get("tools") or ()),
        args=dict(data.get("args") or {}),
        retrieved=tuple(data.get("retrieved") or ()),
        loops=int(data.get("loops", 1)),
        refused=bool(data.get("refused", False)),
        extra=dict(data.get("extra") or {}),
    )


def _failed_case_ids(suite: Suite) -> list[str]:
    return [row.case_id for row in suite.rows if not row.passed]


def promote(
    suite: Suite,
    cases: Sequence[Case],
    outputs: Mapping[str, Output],
    path: str | Path,
    *,
    name: str | None = None,
    force: bool = False,
    failed_only: bool = True,
) -> Path:
    """Write a regression pack from a finished Suite run.

    By default only failing cases are stored (the usual promote-from-failure
    workflow). Pass ``force=True`` to allow promoting a fully passing suite,
    or ``failed_only=False`` to freeze every case.
    """
    if not suite.rows:
        raise PromoteError("suite has no rows; run Suite.run(...) before promote")

    failed = _failed_case_ids(suite)
    by_id = {c.id: c for c in cases}
    if failed_only:
        if failed:
            selected_ids = failed
        elif force:
            selected_ids = [c.id for c in cases]
        else:
            raise PromoteError(
                "suite has no failing rows; pass force=True to promote a passing run"
            )
    else:
        if not failed and not force:
            raise PromoteError(
                "refusing to promote a fully passing suite without force=True"
            )
        selected_ids = [c.id for c in cases]

    missing_cases = [cid for cid in selected_ids if cid not in by_id]
    if missing_cases:
        raise PromoteError(f"cases missing for ids: {missing_cases}")

    missing_outputs = [cid for cid in selected_ids if cid not in outputs]
    if missing_outputs:
        raise PromoteError(f"outputs missing for ids: {missing_outputs}")

    pack_name = name or f"{suite.name}-{'-'.join(selected_ids[:3])}"
    pack = RegressionPack(
        version=REGRESSION_VERSION,
        name=_slug(pack_name),
        suite=suite.name,
        judges=tuple(j.name for j in suite.judges),
        cases=tuple(case_to_dict(by_id[cid]) for cid in selected_ids),
        outputs={cid: output_to_dict(outputs[cid]) for cid in selected_ids},
        baseline=suite.to_json(),
    )

    dest = Path(path)
    if dest.suffix.lower() != ".json":
        dest = dest / f"{pack.name}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(pack.to_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dest


def load_regression(path: str | Path) -> RegressionPack:
    """Load a regression pack from disk."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PromoteError("regression pack must be a JSON object")
    if raw.get("kind") not in (None, "suite_regression"):
        raise PromoteError(f"unsupported kind: {raw.get('kind')!r}")
    version = int(raw.get("version", 0))
    if version != REGRESSION_VERSION:
        raise PromoteError(f"unsupported regression version: {version}")
    cases = raw.get("cases") or []
    outputs = raw.get("outputs") or {}
    if not cases or not outputs:
        raise PromoteError("regression pack needs non-empty cases and outputs")
    return RegressionPack(
        version=version,
        name=str(raw.get("name") or "regression"),
        suite=str(raw.get("suite") or ""),
        judges=tuple(raw.get("judges") or ()),
        cases=tuple(cases),
        outputs=dict(outputs),
        baseline=dict(raw.get("baseline") or {}),
    )


def load_cases(pack: RegressionPack) -> list[Case]:
    return [case_from_dict(item) for item in pack.cases]


def frozen_agent(pack: RegressionPack):
    """Return an agent callable that replays recorded Outputs (no network)."""

    recorded = {cid: output_from_dict(payload) for cid, payload in pack.outputs.items()}

    def agent(case: Case) -> Output:
        try:
            return recorded[case.id]
        except KeyError as exc:
            raise PromoteError(f"no recorded output for case {case.id!r}") from exc

    return agent


def replay(pack: RegressionPack, judges: Sequence[Any]) -> Suite:
    """Re-score recorded outputs with the given judges (deterministic)."""
    cases = load_cases(pack)
    suite = Suite(pack.suite or pack.name, judges)
    suite.run(cases, frozen_agent(pack))
    return suite


def assert_no_worse(suite: Suite, pack: RegressionPack) -> None:
    """Fail if the new suite is worse than the frozen baseline on shared cases.

    A case that passed in the baseline must still pass. Extra cases in the new
    suite are ignored. Missing baseline cases are ignored (partial replays).
    """
    baseline_rows = {
        row["case_id"]: row
        for row in (pack.baseline.get("rows") or [])
        if isinstance(row, dict) and "case_id" in row
    }
    current = {row.case_id: row for row in suite.rows}

    regressions: list[str] = []
    for case_id, old in baseline_rows.items():
        if case_id not in current:
            continue
        if old.get("passed") and not current[case_id].passed:
            regressions.append(case_id)

    if regressions:
        raise AssertionError(f"regressions vs baseline: {regressions}")


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m spanlite",
        description=(
            "Validate or inspect a suite regression pack "
            "(create packs with spanlite.promote(...) in Python)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    show = sub.add_parser("show", help="Print a short summary of a pack")
    show.add_argument("path", type=Path)

    check = sub.add_parser(
        "check",
        help="Load a pack and exit 0 if the file is a valid regression pack",
    )
    check.add_argument("path", type=Path)

    args = parser.parse_args(list(argv) if argv is not None else None)
    pack = load_regression(args.path)
    if args.cmd == "show":
        failed = [
            row.get("case_id")
            for row in (pack.baseline.get("rows") or [])
            if isinstance(row, dict) and not row.get("passed")
        ]
        print(
            json.dumps(
                {
                    "name": pack.name,
                    "suite": pack.suite,
                    "cases": len(pack.cases),
                    "judges": list(pack.judges),
                    "baseline_pass_rate": pack.baseline.get("pass_rate"),
                    "failed_case_ids": failed,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.cmd == "check":
        print(f"ok {pack.name} ({len(pack.cases)} cases)")
        return 0
    return 1


def main() -> None:
    raise SystemExit(_cli())


if __name__ == "__main__":
    main()
