from __future__ import annotations

import json

from spanlite import AgentCase, Output, Suite, TaskJudge


def test_suite_artifact_writes_pretty_json_for_failed_rows(
    tmp_path, suite_artifact
) -> None:
    suite = Suite("agent", [TaskJudge()])
    suite.run(
        [AgentCase("capital", "capital", expect="Delhi")],
        lambda _case: Output(text="Mumbai"),
    )

    path = suite_artifact(suite, tmp_path / "agent.json")

    assert path == tmp_path / "agent.json"
    assert path.read_text(encoding="utf-8").startswith("{\n  \"cases\": 1,")
    assert json.loads(path.read_text(encoding="utf-8")) == suite.to_json()


def test_suite_artifact_skips_passing_rows(tmp_path, suite_artifact) -> None:
    suite = Suite("agent", [TaskJudge()])
    suite.run(
        [AgentCase("capital", "capital", expect="Delhi")],
        lambda _case: Output(text="Delhi"),
    )

    path = tmp_path / "agent.json"

    assert suite_artifact(suite, path) is None
    assert not path.exists()
