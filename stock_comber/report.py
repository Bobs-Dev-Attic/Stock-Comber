"""Render screening results to JSON, CSV, Markdown and HTML."""

from __future__ import annotations

import csv
import html
import io
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Optional, TextIO

from .models import ScreenResult


def _esc(v: Any) -> str:
    """HTML-escape a value for safe interpolation into the report markup.

    Company names and (defensively) tickers/strategies come from upstream data —
    'AT&T', 'Procter & Gamble', or any '<'/'>' would otherwise break the markup
    or inject live HTML into the served report."""
    return html.escape("" if v is None else str(v))


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


def stream_csv(results: list[ScreenResult], cfg: dict[str, Any], fh: TextIO) -> None:
    """Write the CSV report directly to a file handle, one row at a time, so a
    large universe never materialises the whole rendered string in memory."""
    rows = _filtered(results, cfg)
    writer = csv.writer(fh)
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


def to_csv(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    buf = io.StringIO()
    stream_csv(results, cfg, buf)
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


_HTML_HEAD = """<!doctype html>
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
<div class='meta'>Generated {generated} · strategies: {strategies}</div>
<table><thead><tr><th>Ticker</th><th>Company</th><th>Strategy</th><th>Pass</th>
<th>Score</th><th>Price</th><th>P/E</th><th>P/B</th><th>ROE%</th><th>Vol</th><th>Edge%</th></tr></thead>
<tbody>"""

_HTML_TAIL = """</tbody></table>
<footer>Educational tool only — not investment advice.</footer>
</body></html>"""


def stream_html(results: list[ScreenResult], cfg: dict[str, Any], fh: TextIO) -> None:
    """Write the HTML report to a file handle, one row at a time (bounded memory)."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fh.write(_HTML_HEAD.format(
        generated=_esc(generated),
        strategies=_esc(", ".join(cfg.get("strategies", [])))))
    for r in _filtered(results, cfg):
        m = r.metrics
        cls = "pass" if r.passed else "near"
        fh.write(
            f"<tr class='{cls}'><td>{_esc(r.ticker)}</td><td>{_esc(r.name or '')}</td>"
            f"<td>{_esc(r.strategy)}</td><td>{'✔' if r.passed else '·'}</td>"
            f"<td>{r.score_pct:.0f}%</td><td>{_fmt(m.get('price'))}</td>"
            f"<td>{_fmt(m.get('pe_ratio'))}</td><td>{_fmt(m.get('pb_ratio'))}</td>"
            f"<td>{_fmt(m.get('roe_pct'))}</td><td>{_fmt(m.get('avg_volume'))}</td>"
            f"<td>{_fmt(m.get('backtest_edge_pct'))}</td></tr>"
        )
    fh.write(_HTML_TAIL)


def to_html(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    buf = io.StringIO()
    stream_html(results, cfg, buf)
    return buf.getvalue()


def _rss_date(dt: datetime) -> str:
    """RFC 822 date (what RSS 2.0 pubDate/lastBuildDate expect)."""
    from email.utils import format_datetime
    return format_datetime(dt)


def _digest_rows(results: list[ScreenResult], cfg: dict[str, Any]) -> list[ScreenResult]:
    """The nightly digest is the shortlist: passing matches only, capped by
    ``output.top_n``. Ranking order is preserved from the caller."""
    rows = [r for r in results if r.passed]
    top_n = cfg.get("output", {}).get("top_n")
    if top_n:
        rows = rows[:top_n]
    return rows


def stream_rss(results: list[ScreenResult], cfg: dict[str, Any], fh: TextIO) -> None:
    """Write an RSS 2.0 feed of the nightly "hidden gems" (passing matches).

    Streamed item-by-item so a large universe never materialises the whole feed
    in memory. Every interpolated value is XML-escaped. No personal data is
    involved — this is a static feed of public screening results, so it carries
    none of the subscriber/unsubscribe obligations an email digest would.
    """
    out = cfg.get("output", {})
    site = str(out.get("site_url") or "https://github.com/Bobs-Dev-Attic/Stock-Comber")
    now = datetime.now(timezone.utc)
    built = _rss_date(now)
    strategies = ", ".join(cfg.get("strategies", [])) or "value strategies"
    rows = _digest_rows(results, cfg)
    fh.write("<?xml version='1.0' encoding='UTF-8'?>\n")
    fh.write("<rss version='2.0' xmlns:atom='http://www.w3.org/2005/Atom'>\n<channel>\n")
    fh.write(f"<title>Stock-Comber — Nightly Hidden Gems</title>\n")
    fh.write(f"<link>{_esc(site)}</link>\n")
    fh.write(f"<atom:link href='{_esc(site.rstrip('/'))}/feed.xml' rel='self' "
             "type='application/rss+xml'/>\n")
    fh.write("<description>Value stocks that passed Stock-Comber's Graham &amp; "
             "Buffett screens in the latest nightly run. Educational research "
             "shortlist — not investment advice.</description>\n")
    fh.write("<language>en-us</language>\n")
    fh.write(f"<lastBuildDate>{built}</lastBuildDate>\n")
    fh.write(f"<generator>Stock-Comber</generator>\n")
    for r in rows:
        m = r.metrics
        title = f"{r.ticker} — {(r.name or r.ticker)} ({r.strategy}) · {r.score_pct:.0f}%"
        bits = [f"Passed the {_esc(r.strategy)} screen with a "
                f"{r.score_pct:.0f}% score."]
        if m.get("price") is not None:
            bits.append(f"Price {_fmt(m.get('price'))}.")
        if m.get("pe_ratio") is not None:
            bits.append(f"P/E {_fmt(m.get('pe_ratio'))}.")
        if m.get("backtest_edge_pct") is not None:
            bits.append(f"Backtest edge {_fmt(m.get('backtest_edge_pct'))}%.")
        desc = " ".join(bits) + " Educational only — not investment advice."
        # Stable-per-day guid so a reader dedupes within a run but shows a fresh
        # item each night; not a resolvable URL (isPermaLink=false).
        guid = f"stock-comber:{r.ticker}:{r.strategy}:{now.strftime('%Y-%m-%d')}"
        fh.write("<item>\n")
        fh.write(f"<title>{_esc(title)}</title>\n")
        fh.write(f"<link>{_esc(site)}</link>\n")
        fh.write(f"<guid isPermaLink='false'>{_esc(guid)}</guid>\n")
        fh.write(f"<pubDate>{built}</pubDate>\n")
        fh.write(f"<description>{_esc(desc)}</description>\n")
        fh.write("</item>\n")
    fh.write("</channel>\n</rss>\n")


def to_rss(results: list[ScreenResult], cfg: dict[str, Any]) -> str:
    buf = io.StringIO()
    stream_rss(results, cfg, buf)
    return buf.getvalue()


RENDERERS = {
    "json": (to_json, "json"),
    "csv": (to_csv, "csv"),
    "markdown": (to_markdown, "md"),
    "html": (to_html, "html"),
    "rss": (to_rss, "xml"),
}

# Streaming writers write directly to a file handle. csv/html stream row-by-row
# (bounded memory for large universes); json/markdown wrap the string renderers
# (their payloads are already compact). Same output as RENDERERS, less peak RAM.
STREAMERS = {
    "json": (lambda r, c, fh: fh.write(to_json(r, c)), "json"),
    "csv": (stream_csv, "csv"),
    "markdown": (lambda r, c, fh: fh.write(to_markdown(r, c)), "md"),
    "html": (stream_html, "html"),
    "rss": (stream_rss, "xml"),
}


def write_reports(results: list[ScreenResult], cfg: dict[str, Any]) -> list[str]:
    """Write all configured report formats; return the list of file paths.

    The stamped file is streamed to disk; the stable ``latest`` copy is a
    filesystem copy of it, so the rendered report is never held in memory twice.
    """
    out = cfg.get("output", {})
    out_dir = out.get("dir", "reports")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    written: list[str] = []
    for fmt in out.get("formats", ["json"]):
        stream_fn, ext = STREAMERS[fmt]
        path = os.path.join(out_dir, f"screen-{stamp}.{ext}")
        tmp = path + ".tmp"
        # Stream to a temp file, then atomically move it into place — so a
        # mid-stream render error can't leave a truncated report or a "latest"
        # that's out of sync with the stamped file. Still bounded memory.
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                stream_fn(results, cfg, fh)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        written.append(path)
        # Keep a stable "latest" copy for dashboards — copy the file, don't
        # re-render or buffer the whole report again.
        latest = os.path.join(out_dir, f"latest.{ext}")
        shutil.copyfile(path, latest)
        written.append(latest)
    return written
