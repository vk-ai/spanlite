"""spanlite — local-first traces and evals for LLM agents."""

from spanlite.trace import Clock, IdFactory, JsonlSink, MemorySink, Span, Tracer
from spanlite.evals.base import Case, Judge, Output, Score, Suite
from spanlite.evals.agent import AgentCase, LoopJudge, TaskJudge
from spanlite.evals.skill import SkillCase, SchemaJudge, SelectionJudge, RefusalJudge
from spanlite.evals.rag import RagCase, FaithfulnessJudge, MrrJudge, RecallJudge
from spanlite.report import html_report, summary_table

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
    "RagCase",
    "RecallJudge",
    "RefusalJudge",
    "SchemaJudge",
    "Score",
    "SelectionJudge",
    "SkillCase",
    "Span",
    "Suite",
    "TaskJudge",
    "Tracer",
    "html_report",
    "summary_table",
]
__version__ = "0.1.0"
