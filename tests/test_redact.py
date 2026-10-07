"""Redaction tests. All secrets are synthetic and built at runtime so no
token-shaped literal lives in the repo."""

from __future__ import annotations

import json

import pytest

from spanlite import AgentCase, JsonlSink, MemorySink, Output, Suite, TaskJudge, Tracer, html_report
from spanlite.redact import (
    PII_RULES,
    SECRET_RULES,
    RedactingSink,
    Redactor,
    Rule,
    redact,
    rules_by_name,
)

OPENAI = "sk-" + "proj-" + "A1b2C3d4" * 4
ANTHROPIC = "sk-" + "ant-" + "api03-" + "Z9y8X7w6" * 4
GITHUB = "gh" + "p_" + "a" * 36
AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
SLACK = "xo" + "xb-" + "1234567890-abcdefghij"
GOOGLE = "AI" + "za" + "S" * 35
JWT = "ey" + "JhbGciOiJIUzI1NiJ9" + ".ey" + "JzdWIiOiIxMjM0NSJ9" + "." + "s1gn4tur3_abcdefgh"
PEM = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj\n-----END RSA PRIVATE KEY-----"
EMAIL = "ada" + "@" + "example.com"
CARD = "4111 1111 1111 1111"  # Luhn-valid test number


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        self.t += 0.01
        return self.t


def ids():
    n = iter(range(1, 10_000))
    return lambda: f"s{next(n)}"


@pytest.mark.parametrize(
    "secret,rule",
    [
        (OPENAI, "openai_key"),
        (ANTHROPIC, "anthropic_key"),
        (GITHUB, "github_token"),
        (AWS, "aws_access_key"),
        (SLACK, "slack_token"),
        (GOOGLE, "google_api_key"),
        (JWT, "jwt"),
        (PEM, "private_key"),
        ("Bearer " + "abcDEF123456ghiJKL789", "bearer"),
    ],
)
def test_default_rules_catch_secret_shapes(secret: str, rule: str) -> None:
    r = Redactor()
    out = r.text(f"calling api with {secret} now")
    assert secret not in out
    assert f"[REDACTED:{rule}]" in out
    assert r.counts.get(rule) == 1


def test_defaults_leave_ordinary_agent_text_and_pii_alone() -> None:
    text = (
        f"Paris is the capital. v1.2.3 took 1500 ms, task-skeleton-key, "
        f"see https://example.com/docs, contact {EMAIL}, 10.0.0.1"
    )
    assert Redactor().text(text) == text


def test_with_pii_masks_email_card_phone_ip_and_checks_luhn() -> None:
    r = Redactor.with_pii()
    out = r.text(f"mail {EMAIL}, card {CARD}, call +1 415-555-0100, host 10.0.0.1")
    assert EMAIL not in out and "[REDACTED:email]" in out
    assert "[REDACTED:card]" in out
    assert "[REDACTED:phone]" in out
    assert "[REDACTED:ipv4]" in out
    # A 16-digit number that fails Luhn is not treated as a card.
    assert "[REDACTED:card]" not in Redactor(rules=rules_by_name(["card"])).text("id 1234567812345678")


def test_deep_redaction_and_secret_keys() -> None:
    record = {
        "attrs": {
            "prompt": f"my key is {OPENAI}",
            "headers": {"Authorization": "Basic dXNlcjpwYXNz", "Accept": "json"},
            "password": "hunter2",
            "token": 42,  # non-string under a sensitive key is left alone
            "history": [f"jwt={JWT}", ("tuple", OPENAI)],
        },
        "tokens_in": 10,
    }
    out = redact(record)
    blob = json.dumps(out)
    for raw in (OPENAI, JWT, "hunter2", "dXNlcjpwYXNz"):
        assert raw not in blob
    assert out["attrs"]["headers"]["Accept"] == "json"
    assert out["attrs"]["token"] == 42
    assert isinstance(out["attrs"]["history"][1], tuple)
    assert record["attrs"]["password"] == "hunter2"  # input not mutated


def test_tracer_redacts_before_jsonl_sink(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    mem = MemorySink()
    t = Tracer("r1", clock=Clock(), ids=ids(), sinks=[JsonlSink(path), mem])
    with t.span("answer", "llm", prompt=f"use {OPENAI} and {GITHUB}", user=EMAIL):
        pass
    disk = path.read_text(encoding="utf-8")
    assert OPENAI not in disk and GITHUB not in disk
    assert "[REDACTED:openai_key]" in disk
    assert EMAIL in disk  # PII is opt-in
    assert mem.records[0]["attrs"]["prompt"] == "use [REDACTED:openai_key] and [REDACTED:github_token]"
    assert t.spans[0].attrs["prompt"].startswith("use sk-")  # in-memory span untouched


def test_tracer_pii_opt_in_custom_rule_and_opt_out(tmp_path) -> None:
    mem = MemorySink()
    r = Redactor.with_pii().extend(("ticket", r"TCK-\d+"))
    t = Tracer("r2", clock=Clock(), ids=ids(), sinks=[mem], redactor=r)
    with t.span("tool", "tool", tool="crm", q=f"{EMAIL} TCK-123"):
        pass
    assert mem.records[0]["attrs"]["q"] == "[REDACTED:email] [REDACTED:ticket]"

    raw = MemorySink()
    t2 = Tracer("r3", clock=Clock(), ids=ids(), sinks=[raw], redactor=None)
    with t2.span("x", prompt=OPENAI):
        pass
    assert raw.records[0]["attrs"]["prompt"] == OPENAI


def test_tracer_fails_closed_when_redaction_raises() -> None:
    def boom(_s: str) -> str:
        raise RuntimeError("detector down")

    mem = MemorySink()
    t = Tracer("r4", clock=Clock(), ids=ids(), sinks=[mem], redactor=Redactor(custom=boom))
    with t.span("x", prompt="hello"):
        pass
    assert mem.records == []
    assert t.dropped_records == 1


def test_redacting_sink_wrapper_fails_closed() -> None:
    inner = MemorySink()
    sink = RedactingSink(inner)
    sink.emit({"prompt": OPENAI})
    assert inner.records == [{"prompt": "[REDACTED:openai_key]"}]
    bad = RedactingSink(inner, Redactor(custom=lambda s: 1 / 0))  # type: ignore[arg-type,return-value]
    bad.emit({"prompt": "x"})
    assert bad.dropped == 1 and len(inner.records) == 1


def _failing_suite(case_id: str) -> Suite:
    suite = Suite("agent", [TaskJudge()])
    suite.run([AgentCase(case_id, "capital", expect="Delhi")], lambda _c: Output(text="Mumbai"))
    return suite


def test_suite_artifact_is_redacted_by_default(tmp_path, suite_artifact) -> None:
    suite = _failing_suite(f"leak-{OPENAI}")
    path = suite_artifact(suite, tmp_path / "a.json")
    text = path.read_text(encoding="utf-8")
    assert OPENAI not in text and "[REDACTED:openai_key]" in text
    raw = suite_artifact(suite, tmp_path / "raw.json", redactor=None)
    assert OPENAI in raw.read_text(encoding="utf-8")


def test_html_report_redacts_case_ids(tmp_path) -> None:
    suite = _failing_suite(f"user-{EMAIL}-{OPENAI}")
    html = html_report(suite, tmp_path / "r.html", redactor=Redactor.with_pii())
    on_disk = (tmp_path / "r.html").read_text(encoding="utf-8")
    for doc in (html, on_disk):
        assert OPENAI not in doc and EMAIL not in doc


def test_rule_helpers() -> None:
    assert {r.name for r in rules_by_name(["email", "jwt"])} == {"email", "jwt"}
    with pytest.raises(KeyError):
        rules_by_name(["nope"])
    assert not {r.name for r in SECRET_RULES} & {r.name for r in PII_RULES}
    custom = Redactor(rules=(Rule.compile("order", r"ORD\d{4}"),), replacement="***")
    assert custom.text("ORD1234 shipped") == "*** shipped"
