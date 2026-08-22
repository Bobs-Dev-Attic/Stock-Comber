"""Render screening results to JSON, CSV, Markdown and HTML."""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .models import ScreenResult


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:,.0f}M"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def _filtered(results: list[ScreenResult], cfg: dict[str, Any]) -> list[ScreenResult]:
    out = cfg.get("output", {})
    rows = results
    if out.get("only_passing", False):
        rows = [r for r in rows if r.passed]
    top_n = out.get("top_n")
    if top_n:
        rows = rows[:top_n]
    return rows


def to_json(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": cfg.get("strategies", []),
        "count": len(results),
        "passing": sum(1 for r in results if r.passed),
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(payload, indent=2, default=str)


def to_csv(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    rows = _filtered(results, cfg)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ticker", "name", "strategy", "passed", "score", "max_score",
        "score_pct", "price", "pe_ratio", "pb_ratio", "roe_pct",
        "current_ratio", "debt_to_equity", "graham_number", "avg_volume",
        "backtest_edge_pct",
    ])
    for r in rows:
        m = r.metrics
        writer.writerow([
            r.ticker, r.name or "", r.strategy, r.passed,
            f"{r.score:g}", f"{r.max_score:g}", f"{r.score_pct:.1f}",
            _fmt(m.get("price")), _fmt(m.get("pe_ratio")), _fmt(m.get("pb_ratio")),
            _fmt(m.get("roe_pct")), _fmt(m.get("current_ratio")),
            _fmt(m.get("debt_to_equity")), _fmt(m.get("graham_number")),
            _fmt(m.get("avg_volume")), _fmt(m.get("backtest_edge_pct")),
        ])
    return buf.getvalue()


def to_markdown(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    rows = _filtered(results, cfg)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    passing = sum(1 for r in results if r.passed)
    lines = [
        "# Stock-Comber screening report",
        "",
        f"_Generated {generated}_ · strategies: "
        f"**{', '.join(cfg.get('strategies', []))}**",
        "",
        f"Screened **{len({r.ticker for r in results})}** companies · "
        f"**{passing}** strategy matches passed.",
        "",
        "| Ticker | Company | Strategy | Pass | Score | Price | P/E | P/B | ROE% | Curr | D/E | Vol | Edge% |",
        "|--------|---------|----------|:----:|------:|------:|----:|----:|-----:|-----:|----:|----:|------:|",
    ]
    for r in rows:
        m = r.metrics
        mark = "✅" if r.passed else "▫️"
        lines.append(
            f"| {r.ticker} | {(r.name or '')[:28]} | {r.strategy} | {mark} | "
            f"{r.score_pct:.0f}% | {_fmt(m.get('price'))} | {_fmt(m.get('pe_ratio'))} | "
            f"{_fmt(m.get('pb_ratio'))} | {_fmt(m.get('roe_pct'))} | "
            f"{_fmt(m.get('current_ratio'))} | {_fmt(m.get('debt_to_equity'))} | "
            f"{_fmt(m.get('avg_volume'))} | {_fmt(m.get('backtest_edge_pct'))} |"
        )
    lines.append("")
    lines.append(
        "> Educational tool only — not investment advice. Data from SEC EDGAR "
        "and Stooq may be delayed or incomplete."
    )
    return "\n".join(lines)


def to_html(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    rows = _filtered(results, cfg)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = []
    for r in rows:
        m = r.metrics
        cls = "pass" if r.passed else "near"
        body.append(
            f"<tr class='{cls}'><td>{r.ticker}</td><td>{(r.name or '')}</td>"
            f"<td>{r.strategy}</td><td>{'✔' if r.passed else '·'}</td>"
            f"<td>{r.score_pct:.0f}%</td><td>{_fmt(m.get('price'))}</td>"
            f"<td>{_fmt(m.get('pe_ratio'))}</td><td>{_fmt(m.get('pb_ratio'))}</td>"
            f"<td>{_fmt(m.get('roe_pct'))}</td><td>{_fmt(m.get('avg_volume'))}</td>"
            f"<td>{_fmt(m.get('backtest_edge_pct'))}</td></tr>"
        )
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Stock-Comber report</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:2rem;background:#0f1115;color:#e6e6e6}}
 h1{{margin-bottom:.2rem}} .meta{{color:#9aa;margin-bottom:1rem}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{padding:.4rem .6rem;border-bottom:1px solid #2a2f3a;text-align:right}}
 th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
 tr.pass{{background:#12321e}} tr.near{{opacity:.7}}
 footer{{margin-top:1rem;color:#889;font-size:.85rem}}
</style></head><body>
<h1>Stock-Comber screening report</h1>
<div class='meta'>Generated {generated} · strategies: {', '.join(cfg.get('strategies', []))}</div>
<table><thead><tr><th>Ticker</th><th>Company</th><th>Strategy</th><th>Pass</th>
<th>Score</th><th>Price</th><th>P/E</th><th>P/B</th><th>ROE%</th><th>Vol</th><th>Edge%</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<footer>Educational tool only — not investment advice.</footer>
</body></html>"""


RENDERERS = {
    "json": (to_json, "json"),
    "csv": (to_csv, "csv"),
    "markdown": (to_markdown, "md"),
    "html": (to_html, "html"),
}


def write_reports(results: list[ScreenResult], cfg: dict[str, Any]) -> list[str]:
    """Write all configured report formats; return the list of file paths."""
    out = cfg.get("output", {})
    out_dir = out.get("dir", "reports")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    written: list[str] = []
    for fmt in out.get("formats", ["json"]):
        renderer, ext = RENDERERS[fmt]
        content = renderer(results, cfg)
        path = os.path.join(out_dir, f"screen-{stamp}.{ext}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)
        # Also keep a stable "latest" copy for dashboards.
        latest = os.path.join(out_dir, f"latest.{ext}")
        with open(latest, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(latest)
    return written
