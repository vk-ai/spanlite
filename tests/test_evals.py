from __future__ import annotations

from spanlite import (
    AgentCase,
    LoopJudge,
    Output,
    RagCase,
    RecallJudge,
    RefusalJudge,
    SchemaJudge,
    SelectionJudge,
    SkillCase,
    Suite,
    TaskJudge,
    FaithfulnessJudge,
    MrrJudge,
    html_report,
    summary_table,
)


def test_agent_task_and_loops() -> None:
    suite = Suite("agent", [TaskJudge(), LoopJudge()])
    cases = [
        AgentCase("ok", "capital", expect="delhi", max_loops=3),
        AgentCase("spin", "capital", expect="delhi", max_loops=2),
    ]

    def agent(case):
        if case.id == "ok":
            return Output(text="New Delhi", loops=2)
        return Output(text="New Delhi", loops=9)

    rows = suite.run(cases, agent)
    assert rows[0].passed
    assert not rows[1].passed
    assert suite.pass_rate() == 0.5


def test_skill_selection_schema_refusal() -> None:
    suite = Suite("skill", [SelectionJudge(), SchemaJudge(), RefusalJudge()])
    cases = [
        SkillCase("search", "q", tool="web", required_args=("q",)),
        SkillCase("harm", "bomb", tool=None, should_refuse=True),
    ]

    def agent(case):
        if case.id == "search":
            return Output(tools=("web",), args={"q": "x"})
        return Output(refused=True)

    assert all(r.passed for r in suite.run(cases, agent))


def test_rag_recall_mrr_faith() -> None:
    suite = Suite("rag", [RecallJudge(), MrrJudge(), FaithfulnessJudge()])
    case = RagCase(
        "q1",
        "who",
        gold_ids=("d1",),
        k=3,
        must_phrases=("neem",),
    )

    def agent(_case):
        return Output(text="Neem is a tree.", retrieved=("d1", "d9"))

    rows = suite.run([case], agent)
    assert rows[0].passed
    table = summary_table(suite)
    assert "q1" in table
    html = html_report(suite)
    assert "q1" in html
    payload = suite.to_json()
    assert payload["pass_rate"] == 1.0
    assert payload["rows"][0]["case_id"] == "q1"
