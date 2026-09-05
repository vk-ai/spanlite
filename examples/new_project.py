"""Start a new agent project with spanlite in five lines."""

from spanlite import MemorySink, Output, Suite, TaskJudge, Tracer, AgentCase


def fake_agent(case):
    return Output(text="boiled water is safer than untreated water")


def main() -> None:
    t = Tracer("demo", model="grok", usd_per_1k_in=0.003, usd_per_1k_out=0.015, sinks=[MemorySink()])
    with t.span("answer") as span:
        t.tokens(span, 80, 40)
    print("trace", t.summary())

    suite = Suite("water", [TaskJudge()])
    suite.run([AgentCase("q1", "How to drink safer water?", expect="boiled")], fake_agent)
    print("eval pass_rate", suite.pass_rate())


if __name__ == "__main__":
    main()
