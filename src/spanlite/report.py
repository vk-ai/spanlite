from __future__ import annotations

from html import escape
from pathlib import Path

from spanlite.evals.base import Suite


def summary_table(suite: Suite) -> str:
    lines = [
        f"suite: {suite.name}",
        f"cases: {len(suite.rows)}  pass_rate: {suite.pass_rate():.0%}",
        "",
        f"{'case':<24} {'pass':<6} scores",
    ]
    for row in suite.rows:
        bits = "  ".join(f"{s.name}={s.value}" for s in row.scores)
        lines.append(f"{row.case_id:<24} {str(row.passed):<6} {bits}")
    return "\n".join(lines)


def html_report(suite: Suite, path: str | Path | None = None) -> str:
    rows = []
    for row in suite.rows:
        cells = "".join(
            f"<td class='{'ok' if s.passed else 'bad'}'>{escape(s.name)} {s.value}</td>"
            for s in row.scores
        )
        rows.append(
            f"<tr class='{'ok' if row.passed else 'bad'}'><td>{escape(row.case_id)}</td>"
            f"<td>{'pass' if row.passed else 'fail'}</td>{cells}</tr>"
        )
    html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>{escape(suite.name)}</title>
<style>
body{{font:14px/1.45 ui-sans-serif,system-ui;background:#0e1210;color:#e8ebe4;margin:32px}}
h1{{font-weight:500}} table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #2a322c;padding:8px 10px;text-align:left}}
.ok td.ok,.ok{{color:#7d9a6a}} .bad,.bad td.bad{{color:#c45c4a}}
.meta{{color:#8b9388}}
</style></head>
<body>
<h1>{escape(suite.name)}</h1>
<p class=\"meta\">{len(suite.rows)} cases · pass {suite.pass_rate():.0%}</p>
<table><thead><tr><th>case</th><th>result</th><th colspan=\"8\">scores</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    if path is not None:
        p = Path(path)
        p.write_text(html, encoding="utf-8")
    return html
