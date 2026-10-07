from __future__ import annotations

import json

import pytest

from spanlite import AgentCase, Output, Suite, TaskJudge
from spanlite.promote import (
    PromoteError,
    assert_no_worse,
    load_cases,
    load_regression,
    promote,
    replay,
)


def _failed_run():
    suite = Suite("agent", [TaskJudge()])
    cases = [
        AgentCase("ok", "capital", expect="Delhi"),
        AgentCase("bad", "capital", expect="Delhi"),
    ]
    outputs = {
        "ok": Output(text="Delhi"),
        "bad": Output(text="Mumbai"),
    }

    def agent(case):
        return outputs[case.id]

    suite.run(cases, agent)
    return suite, cases, outputs


def test_promote_writes_stable_pack_for_failures_only(tmp_path) -> None:
    suite, cases, outputs = _failed_run()
    path = promote(suite, cases, outputs, tmp_path / "regs", name="agent-bad")

    assert path.name == "agent-bad.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["kind"] == "suite_regression"
    assert raw["version"] == 1
    assert [c["id"] for c in raw["cases"]] == ["bad"]
    assert set(raw["outputs"]) == {"bad"}
    assert list(raw.keys()) == sorted(raw.keys())


def test_promote_refuses_passing_suite_without_force(tmp_path) -> None:
    suite = Suite("agent", [TaskJudge()])
    cases = [AgentCase("ok", "capital", expect="Delhi")]
    outputs = {"ok": Output(text="Delhi")}
    suite.run(cases, lambda c: outputs[c.id])

    with pytest.raises(PromoteError, match="force=True"):
        promote(suite, cases, outputs, tmp_path / "x.json")


def test_promote_force_all_pass(tmp_path) -> None:
    suite = Suite("agent", [TaskJudge()])
    cases = [AgentCase("ok", "capital", expect="Delhi")]
    outputs = {"ok": Output(text="Delhi")}
    suite.run(cases, lambda c: outputs[c.id])

    path = promote(suite, cases, outputs, tmp_path / "ok.json", force=True)
    pack = load_regression(path)
    assert [c.id for c in load_cases(pack)] == ["ok"]


def test_replay_and_assert_no_worse(tmp_path) -> None:
    suite, cases, outputs = _failed_run()
    path = promote(suite, cases, outputs, tmp_path / "pack.json", name="cap")
    pack = load_regression(path)

    replayed = replay(pack, [TaskJudge()])
    assert replayed.rows[0].case_id == "bad"
    assert not replayed.rows[0].passed

    # Same recorded failure is not "worse"
    assert_no_worse(replayed, pack)

    # Improved agent on the frozen case
    improved = Suite("agent", [TaskJudge()])
    improved.run(load_cases(pack), lambda _c: Output(text="Delhi"))
    assert improved.pass_rate() == 1.0
    assert_no_worse(improved, pack)


def test_assert_no_worse_detects_new_failure(tmp_path) -> None:
    suite = Suite("agent", [TaskJudge()])
    cases = [AgentCase("ok", "capital", expect="Delhi")]
    outputs = {"ok": Output(text="Delhi")}
    suite.run(cases, lambda c: outputs[c.id])
    path = promote(suite, cases, outputs, tmp_path / "base.json", force=True)
    pack = load_regression(path)

    worse = Suite("agent", [TaskJudge()])
    worse.run(cases, lambda _c: Output(text="Mumbai"))
    with pytest.raises(AssertionError, match="regressions"):
        assert_no_worse(worse, pack)


def test_cli_show_and_check(tmp_path) -> None:
    from spanlite.promote import _cli

    suite, cases, outputs = _failed_run()
    path = promote(suite, cases, outputs, tmp_path / "cli.json", name="cli")
    assert _cli(["check", str(path)]) == 0
    assert _cli(["show", str(path)]) == 0
