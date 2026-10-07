"""Promote a failing suite row, then replay it locally (no cloud)."""

from pathlib import Path

from spanlite import (
    AgentCase,
    Output,
    Suite,
    TaskJudge,
    assert_no_worse,
    load_regression,
    promote,
    replay,
)


def buggy_agent(case):
    return Output(text="Mumbai")


def fixed_agent(case):
    return Output(text="New Delhi")


def main() -> None:
    cases = [AgentCase("capital", "capital of India?", expect="Delhi")]
    outputs = {}

    def capturing(case):
        out = buggy_agent(case)
        outputs[case.id] = out
        return out

    suite = Suite("geo", [TaskJudge()])
    suite.run(cases, capturing)
    pack_path = promote(suite, cases, outputs, Path("/tmp/spanlite-regressions"))
    print("wrote", pack_path)

    pack = load_regression(pack_path)
    print("replay pass_rate", replay(pack, [TaskJudge()]).pass_rate())

    fixed = Suite("geo", [TaskJudge()])
    fixed.run(cases, fixed_agent)
    assert_no_worse(fixed, pack)
    print("fixed agent cleared the regression gate")


if __name__ == "__main__":
    main()
