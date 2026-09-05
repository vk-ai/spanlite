"""Drop spanlite into an existing pytest suite. No rewrite of the agent."""

from spanlite import Output, RagCase, RecallJudge, Suite


def my_retriever(query: str) -> list[str]:
    return ["doc-neem", "doc-other"] if "tree" in query else ["doc-other"]


def test_retriever_still_works():
    suite = Suite("rag", [RecallJudge()])
    case = RagCase("neem", "which tree", gold_ids=("doc-neem",), k=5)

    def agent(c):
        return Output(retrieved=tuple(my_retriever(str(c.input))))

    rows = suite.run([case], agent)
    assert rows[0].passed
