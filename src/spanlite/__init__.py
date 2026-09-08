"""spanlite — local-first traces and evals for LLM agents."""

from spanlite.trace import Clock, IdFactory, JsonlSink, MemorySink, Span, Tracer
from spanlite.evals.base import Case, Judge, Output, Score, Suite
from spanlite.evals.agent import AgentCase, LoopJudge, TaskJudge
from spanlite.evals.skill import SkillCase, SchemaJudge, SelectionJudge, RefusalJudge
from spanlite.evals.rag import RagCase, FaithfulnessJudge, MrrJudge, RecallJudge
from spanlite.report import html_report, summary_table
from spanlite.promote import (
    PromoteError,
    RegressionPack,
    assert_no_worse,
    load_regression,
    promote,
    replay,
)

__all__ = [
    "AgentCase",
    "Case",
    "Clock",
    "FaithfulnessJudge",
    "IdFactory",
    "JsonlSink",
    "Judge",
    "LoopJudge",
    "MemorySink",
    "MrrJudge",
    "Output",
    "PromoteError",
    "RagCase",
    "RecallJudge",
    "RefusalJudge",
    "RegressionPack",
    "SchemaJudge",
    "Score",
    "SelectionJudge",
    "SkillCase",
    "Span",
    "Suite",
    "TaskJudge",
    "Tracer",
    "assert_no_worse",
    "html_report",
    "load_regression",
    "promote",
    "replay",
    "summary_table",
]
__version__ = "0.1.0"
