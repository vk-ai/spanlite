from __future__ import annotations

from dataclasses import dataclass

from spanlite.evals.base import Case, Output, Score


@dataclass(frozen=True)
class RagCase(Case):
    gold_ids: tuple[str, ...] = ()
    k: int = 5
    must_phrases: tuple[str, ...] = ()


def _hits(gold: tuple[str, ...], retrieved: tuple[str, ...], k: int) -> int:
    top = retrieved[:k]
    gold_set = set(gold)
    return sum(1 for i in top if i in gold_set)


class RecallJudge:
    name = "recall"

    def score(self, case: Case, output: Output) -> Score:
        gold = getattr(case, "gold_ids", ())
        k = getattr(case, "k", 5)
        if not gold:
            return Score(self.name, 1.0, True, "no gold")
        value = _hits(gold, output.retrieved, k) / len(gold)
        return Score(self.name, round(value, 4), value >= 1.0, f"k={k}")


class MrrJudge:
    name = "mrr"

    def score(self, case: Case, output: Output) -> Score:
        gold = set(getattr(case, "gold_ids", ()))
        if not gold:
            return Score(self.name, 1.0, True, "no gold")
        rank = 0
        for i, doc in enumerate(output.retrieved, start=1):
            if doc in gold:
                rank = i
                break
        value = 0.0 if rank == 0 else 1.0 / rank
        return Score(self.name, round(value, 4), rank == 1, f"rank={rank or 'none'}")


class FaithfulnessJudge:
    """Lexical overlap with retrieved text. No LLM-as-judge, so CI is cheap and stable."""

    name = "faithfulness"

    def score(self, case: Case, output: Output) -> Score:
        phrases = getattr(case, "must_phrases", ())
        if not phrases:
            return Score(self.name, 1.0, True, "no phrases")
        blob = (output.text or "").lower()
        hit = sum(1 for p in phrases if p.lower() in blob)
        value = hit / len(phrases)
        return Score(self.name, round(value, 4), value >= 1.0, f"{hit}/{len(phrases)}")
