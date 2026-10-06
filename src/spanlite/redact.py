"""Redact secrets and PII before traces and CI artifacts reach disk.

spanlite writes JSONL traces and CI artifacts, and those files are exactly
where pasted API keys and customer emails end up living forever. A
``Redactor`` walks a record (dicts, lists, strings) and replaces matches with
``[REDACTED:<rule>]`` before any sink or artifact writer sees it.

Defaults are deliberately conservative:

- ``SECRET_RULES`` are **on by default**. They match high-confidence token
  shapes (provider key prefixes, JWTs, bearer headers, PEM private keys), so
  false positives on normal agent text are unlikely.
- ``PII_RULES`` (email, phone, IPv4, card numbers) are **opt-in** with
  ``Redactor.with_pii()`` because they can match ordinary data (version
  strings, ids, numbers) that you may want to keep.
- Values under sensitive keys (``password``, ``api_key``, ``authorization``,
  ...) are replaced whole, whatever they look like.

Regex redaction is best-effort defense in depth, not a guarantee. Keep
secrets out of prompts and attrs where you can.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class Rule:
    """A named regex. Matches become ``replacement.format(name=name)``."""

    name: str
    pattern: re.Pattern[str]

    @classmethod
    def compile(cls, name: str, pattern: str, flags: int = 0) -> "Rule":
        return cls(name, re.compile(pattern, flags))


# High-confidence secret shapes. Order matters: specific before generic.
SECRET_RULES: tuple[Rule, ...] = (
    Rule.compile(
        "private_key",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----",
    ),
    Rule.compile("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    Rule.compile("bearer", r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    Rule.compile("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    Rule.compile("openai_key", r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    Rule.compile("github_token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    Rule.compile("slack_token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    Rule.compile("aws_access_key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    Rule.compile("google_api_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    Rule.compile("stripe_key", r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,}"),
    Rule.compile("hf_token", r"\bhf_[A-Za-z0-9]{30,}"),
    Rule.compile("xai_key", r"\bxai-[A-Za-z0-9]{30,}"),
)

# Broader PII shapes; opt-in because they can match ordinary data.
PII_RULES: tuple[Rule, ...] = (
    Rule.compile("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    Rule.compile("card", r"\b(?:\d[ -]?){13,19}\b"),
    Rule.compile("phone", r"(?<![\w.])\+?\d{1,3}[ .-]?\(?\d{2,4}\)?[ .-]?\d{3,4}[ .-]?\d{3,4}(?![\w.])"),
    Rule.compile("ipv4", r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
)

DEFAULT_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "authorization",
        "client_secret",
        "cookie",
        "password",
        "passwd",
        "private_key",
        "refresh_token",
        "secret",
        "set-cookie",
        "token",
        "x-api-key",
    }
)


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


@dataclass(frozen=True)
class Redactor:
    """Deep-redacts strings inside JSON-like values.

    ``custom`` runs after the regex rules on every string (e.g. a project
    specific id format, or a call into a heavier PII detector you own).
    """

    rules: tuple[Rule, ...] = SECRET_RULES
    secret_keys: frozenset[str] = DEFAULT_SECRET_KEYS
    replacement: str = "[REDACTED:{name}]"
    custom: Callable[[str], str] | None = None
    _counts: dict[str, int] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def with_pii(cls, **kw: Any) -> "Redactor":
        """Secrets plus email / card (Luhn-checked) / phone / IPv4."""
        return cls(rules=SECRET_RULES + PII_RULES, **kw)

    def extend(self, *rules: Rule | tuple[str, str]) -> "Redactor":
        """Return a copy with extra rules, e.g. ``extend(("ticket", r"TCK-\\d+"))``."""
        extra = tuple(r if isinstance(r, Rule) else Rule.compile(*r) for r in rules)
        return Redactor(
            rules=self.rules + extra,
            secret_keys=self.secret_keys,
            replacement=self.replacement,
            custom=self.custom,
        )

    @property
    def counts(self) -> dict[str, int]:
        """How many replacements each rule made so far (for a CI summary)."""
        return dict(self._counts)

    def _bump(self, name: str, n: int = 1) -> None:
        self._counts[name] = self._counts.get(name, 0) + n

    def text(self, value: str) -> str:
        """Redact one string."""
        out = value
        for rule in self.rules:
            label = self.replacement.format(name=rule.name)
            if rule.name == "card":

                def card_sub(m: re.Match[str], _label: str = label) -> str:
                    if _luhn_ok(m.group(0)):
                        self._bump("card")
                        return _label
                    return m.group(0)

                out = rule.pattern.sub(card_sub, out)
                continue
            out, n = rule.pattern.subn(label, out)
            if n:
                self._bump(rule.name, n)
        if self.custom is not None:
            out = self.custom(out)
        return out

    def _is_secret_key(self, key: Any) -> bool:
        return isinstance(key, str) and key.strip().lower().replace(" ", "_") in self.secret_keys

    def redact(self, value: Any) -> Any:
        """Return a redacted deep copy of ``value`` (dict/list/tuple/str/scalars)."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, Mapping):
            out: dict[Any, Any] = {}
            for k, v in value.items():
                if self._is_secret_key(k) and isinstance(v, str) and v:
                    self._bump("secret_key")
                    out[k] = self.replacement.format(name="secret_key")
                else:
                    out[k] = self.redact(v)
            return out
        if isinstance(value, (list, tuple)):
            items = [self.redact(v) for v in value]
            return items if isinstance(value, list) else tuple(items)
        return value


def default_redactor() -> Redactor:
    """A fresh secrets-only redactor (the Tracer / artifact default)."""
    return Redactor()


def redact(value: Any, redactor: Redactor | None = None) -> Any:
    """Convenience: redact ``value`` with ``redactor`` (default: secrets only)."""
    return (redactor or default_redactor()).redact(value)


class RedactingSink:
    """Decorator sink: redact every record, then forward to ``inner``.

    Fails closed: if redaction raises, the record is dropped and counted in
    ``dropped`` instead of being written unredacted.
    """

    def __init__(self, inner: Any, redactor: Redactor | None = None) -> None:
        self.inner = inner
        self.redactor = redactor or default_redactor()
        self.dropped = 0

    def emit(self, record: Mapping[str, Any]) -> None:
        try:
            clean = self.redactor.redact(record)
        except Exception:
            self.dropped += 1
            return
        self.inner.emit(clean)


def rules_by_name(names: Iterable[str]) -> tuple[Rule, ...]:
    """Pick built-in rules by name, e.g. ``rules_by_name(["email", "openai_key"])``."""
    table = {r.name: r for r in SECRET_RULES + PII_RULES}
    missing = [n for n in names if n not in table]
    if missing:
        raise KeyError(f"unknown redaction rule(s): {', '.join(missing)}")
    return tuple(table[n] for n in names)
