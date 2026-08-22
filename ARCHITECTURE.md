# Architecture

A map of Stock-Comber for humans and AI agents. Read this first — it exists so a
session doesn't have to re-discover the codebase every time. When you change a
subsystem, update the relevant section here in the same PR.

## The shape of the thing

Stock-Comber is a Python package (`stock_comber/`) that screens public companies
against value-investing lenses, plus a **static single-page dashboard**
(`public/`) backed by **serverless functions** (`api/*.py`) on Vercel, plus a
**GitHub Actions** heartbeat that runs the nightly screen. State lives in a
**Neon Postgres** database (optional — the app degrades to a no-op backend
without one).

```
Browser (public/*.html, one SPA + 7 sub-pages)
   │  fetch()
   ▼
api/*.py  (12 Vercel serverless functions — see the cap below)
   │  import
   ▼
stock_comber/  (the library: screening, metrics, backtest, storage, schedule…)
   │
   ├── datasources/  → SEC EDGAR, Stooq, Yahoo, Finnhub (free, mostly key-less)
   └── storage.py    → Neon Postgres (or Null no-op backend)

GitHub Actions (screen.yml, */5 * * * *) → schedule.should_run_now() → nightly run
```

## The 12-function cap — the hard constraint

Vercel's **Hobby plan allows at most 12 Serverless Functions**. There are
**exactly 12** `api/*.py` files today (see `vercel.json`). **Do not add a 13th.**
New API surface must reuse an existing endpoint with a query parameter (e.g.
`api/runs.py?audit=1`, `api/universe.py?nightly=1`) or live as a *library* module
under `stock_comber/` (e.g. `apiguard.py`). Lifting the cap means upgrading to
Vercel Pro — a deliberate milestone, not an accident.

### The 12 endpoints
| File | Purpose |
|---|---|
| `api/screen.py` | Run a screen over a universe (1024 MB / 60 s) |
| `api/analyze.py` | Deep-dive one ticker; runs backtest when enabled (1024 MB / 60 s) |
| `api/backtest.py` | Backtest lenses for a ticker |
| `api/universe.py` | Nightly "hidden gems" preview (`?nightly=1&ordinal=&hour=`) |
| `api/runs.py` | Run history; audit log + rate-limit view (`?audit=1[&endpoint=]`) |
| `api/settings.py` | Read/write the settings JSONB singleton |
| `api/tickers.py` | Ticker catalog / lookups |
| `api/queue.py` | Manual analysis queue |
| `api/analytics.py` | Aggregate analytics for the dashboard |
| `api/signals.py` | Signal computations |
| `api/thesis.py` | Investment-thesis view |
| `api/export.py` | Export the latest report (CSV/MD/HTML) |

## Core library modules (`stock_comber/`)
- **`config.py`** — `DEFAULT_CONFIG` documents every knob; YAML/env loading and
  per-section validators (`_validate_api`, nightly, data). Config is a deep-merge
  of file/defaults ← DB-stored settings.
- **`models.py`** — dataclasses: `Company` (with `annuals` + `quarters`),
  `AnnualFacts`, `QuarterFacts` (latest 10-Q snapshot), `Quote` (incl. `volume`),
  `ScreenResult`.
- **`criteria/`** + **`scoring.py`** — the value lenses. `STRATEGIES` maps a key
  to an evaluate fn. Six ship: `graham`, `buffett`, `piotroski`, `greenblatt`,
  `lynch`, `netnet`, plus custom.
- **`metrics.py`** — `METRIC_KEYS` + `compute_metrics`; ratios plus liquidity
  metrics `avg_volume` / `dollar_volume`.
- **`screener.py`** — `Screener` orchestrates fetch → evaluate → rank;
  `resolve_universe` chooses list vs. nightly (nightly seeds rotation with
  `schedule.rotation_tick(utcnow)`). `run()` buffers + ranks + retains companies
  for persistence; `iter_results()` + `retain_companies=False` stream per-ticker
  results at O(1) company memory.
- **`report.py`** — string renderers (`to_json/csv/markdown/html`) plus
  `stream_csv`/`stream_html` that write row-by-row to a file handle;
  `write_reports` streams the dated file and `copyfile`s it to `latest`
  (report columns include `avg_volume` and `backtest_edge_pct`).
- **`universe.py`** — `build_nightly(config, store, finnhub, day_ordinal)`: the
  capped, sector-diversified, rotating "hidden gems" pool, with a
  `recently_screened` cooldown filter.
- **`backtest.py`** — `backtest_strategy` / `backtest_all` / `overall_edge`:
  point-in-time "did a PASS precede better forward returns?" (educational only).
- **`schedule.py`** — `should_run_now(config, now)` matches the stored 5-field
  cron against a 5-minute heartbeat (`HEARTBEAT_MINUTES`); `_match_field`
  supports `*/n`. `rotation_tick(now) = ordinal*24 + hour`.
- **`storage.py`** — Postgres backend + `Null` no-op; `save_run`, `latest_run`,
  `list_runs`, `get_run`, the `api_audit` table (`record_api_call` /
  `list_api_audit` / `count_api_calls`), and `recently_screened(days)`
  (scheduled runs only — excludes `meta.source` in `manual`/`queue`).
  `get_settings` is served from a DSN-keyed in-process TTL cache
  (`STOCK_COMBER_SETTINGS_TTL`, default 30s), refreshed on `save_settings`.
  `resolve_dsn` prefers `STOCK_COMBER_DATABASE_URL_POOLED` (Neon PgBouncer host)
  when set. Connections are per-operation (suits serverless).
- **`apiguard.py`** — **library, not an endpoint.** `guard(handler, endpoint)`
  audits + rate-limits every request; **fails open** on any error, but with a
  bounded per-instance in-memory limiter (`_MemoryLimiter`) as a floor when the
  DB count is unavailable (`degraded_count()` surfaces how often). Keys are
  bucketed only by a SHA-256 fingerprint (`_fingerprint`) — the raw key is never
  stored; keyless requests bucket by IP (`_client_ip`).
- **`validation.py`** — single source of truth for valid ticker symbols
  (`is_valid_ticker` / `normalize_ticker`, `^[A-Z][A-Z0-9.\-]{0,9}$`). Enforced
  in the screener and the Yahoo/SEC data sources before any URL is built
  (SSRF/path-injection guard), and mirrored by the API handlers at the boundary.
- **`cli.py`** — entry point (`stock-comber`); `cmd_screen`,
  `_attach_backtest_edge` (nightly edge injection, bounded-concurrency fetch).

## Frontend (`public/`)
- **`index.html`** — the SPA: tabs (Full list / Jobs / History / API), analysis &
  detail dialogs, `METRICS` / `DEFAULT_COLS`, `METRIC_INFO` tooltips, schedule
  editor (`cronToForm`/`formToCron`, next-runs preview), theming.
- **7 sub-pages** — settings, about, glossary, strategies, analytics, backtest,
  thesis. Each carries the pre-paint theme script + `[data-theme]` dark palette.
- **Theming contract:** light palette on bare `:root`; dark under
  `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` **and**
  `:root[data-theme="dark"]`. A `<head>` pre-paint script reads `localStorage.theme`
  to avoid a flash. Keep all three in sync when touching colors.

## Data & config model
- **Settings** are a single JSONB blob (the settings singleton) with sections:
  `strategies`, `schedule`, `universe` (+ `nightly`), `data`, `api`, `jobs`, and
  per-strategy blocks. Writes go through `config.py` validators.
- **Secrets** (API keys, `DATABASE_URL`) live in env / DB **write-only** and are
  **never returned to the browser**. The audit log stores only key fingerprints.
- **HTTP security headers** are set for every response in `vercel.json`: a hardened
  same-origin **CSP** (external script/connect/frame/object/base blocked; `img-src`
  allows `https:` for logos; `'unsafe-inline'` retained for the static inline-heavy
  SPA — no nonce is possible without an edge middleware), plus `nosniff`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS, and COOP.

## Testing
`pytest` (171 tests). The upstream data providers are blocked from this dev
environment's proxy, so live Yahoo/Google fetches can't be exercised locally —
tests stub them; browser checks use Playwright at
`/opt/pw-browsers/chromium` with route-stubbed APIs. Rely on hosted CI
(Actions + Vercel preview) to exercise real upstream calls.
