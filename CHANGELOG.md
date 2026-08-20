# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-08-20

### Added
- **Manual analysis button.** An **"Analyze now"** button on the dashboard runs
  the full, deep analysis on the first entered ticker immediately — all
  strategies, Finnhub enrichment, and recent news scored into an A–F sentiment
  grade — instead of waiting for the ~20-min queue worker. Results open in a
  modal (per-strategy pass/fail, sentiment summary, and news headlines) and,
  when a database is configured, the analysis is stored as its own run so it
  also appears in History and Analytics. Backed by a new `GET /api/analyze?ticker=…`
  endpoint (`run_analysis`, reusing `analysis.analyze_ticker`).

[0.9.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.9.0

## [0.8.0] - 2026-08-20

### Added
- **Analytics view** (`/analytics.html`) — a charts page over the stored
  history: screened-vs-passing per run (grouped bars, oldest→newest), the
  most-frequently-passing tickers, passing results by sector, and the news
  sentiment-grade distribution. Backed by a new read-only `GET /api/analytics`
  endpoint (`PostgresStorage.analytics`) that aggregates runs, results, the
  universe catalog and stored sentiment. Self-contained inline SVG, theme-aware,
  no external dependencies; linked from the dashboard and History page. Charts
  use the validated categorical palette with direct value labels.

[0.8.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.8.0

## [0.7.1] - 2026-08-20

### Added
- **On-demand analysis** — `stock-comber analyze-queue --seed AAPL,MSFT` enqueues
  and immediately analyses specific tickers; the `analyze` workflow gains a
  matching `seed` dispatch input. Handy for deep-analysing a name now instead of
  waiting for the queue.

[0.7.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.7.1

## [0.7.0] - 2026-08-20

### Added
- **Analysis queue.** Tickers a user screens are enqueued (`analysis_queue`
  table, `POST /api/queue`) and processed out-of-band by a new
  `analyze` GitHub Actions worker (every ~20 min) that runs a full analysis:
  all strategies, Finnhub metric enrichment, and recent **news + a sentiment
  grade**. Each processed ticker is stored as its own run. CLI:
  `stock-comber analyze-queue`. Queue status shows on the History page.
- **News & sentiment.** `FinnhubSource.fetch_news` pulls recent company news
  (free tier); `stock_comber/sentiment.py` scores headlines with a transparent
  finance lexicon into an A–F **sentiment grade** (no paid API, no ML dep),
  stored alongside the analysis.
- `GET /api/queue` (view) / `POST /api/queue` (enqueue, capped + de-duplicated).

### Notes
- Dataroma-style superinvestor ownership is a useful gem signal but has no free
  official API (scraping is fragile / against ToS); SEC 13F filings are the
  free, official alternative and a candidate for a future enrichment.

[0.7.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.7.0

## [0.6.0] - 2026-08-20

### Added
- **Activity log** — a **History page** (`public/history.html`, linked from the
  dashboard) listing stored nightly runs (date, strategies, counts, per-run
  CSV/JSON export links) and the ad-hoc **search log**. Backed by
  `GET /api/runs`. Live `/api/screen` queries are now recorded to a new
  `searches` table (query + counts) when a database is configured.
- **Ticker autocomplete** — the dashboard search box suggests tickers as you
  type (prefix/substring over the SEC ticker list), with keyboard navigation.
  Backed by `GET /api/tickers?q=` (`match_tickers` in `sec_edgar.py`).

[0.6.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.6.0

## [0.5.2] - 2026-08-20

### Fixed
- **Finnhub free-tier rate limiting (429s).** The first nightly run made ~200
  Finnhub calls and hit the ~60/min limit. Now Finnhub's budget is reserved for
  universe enrichment: it's dropped to **last** in the price chain (Yahoo/Stooq
  cover prices), per-ticker metric enrichment is **off by default**
  (`data.finnhub_enrich_results`), `fetch_profile` is a **single call** (volume
  is opt-in), calls are **throttled** (`data.finnhub_min_interval`, ~1.1s), and a
  circuit breaker stops calling Finnhub after repeated 429s in a run. A nightly
  run now uses ~1 Finnhub call per enriched name, within the free tier.

[0.5.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.5.2

## [0.5.1] - 2026-08-20

### Added
- **Settings page** (`public/settings.html`) — edit strategies, Graham/Buffett
  thresholds, the nightly universe filters (cap, market-cap band, volume,
  sectors, countries, extra tickers), custom criteria, and output preferences in
  the browser. Shows **key/DB status** (configured or not) without ever
  revealing secrets. Saves to the database, or **Download as YAML** when no DB is
  configured. Linked from the dashboard.
- **Settings API** (`api/settings.py`) — `GET /api/settings` returns the
  effective config + key status; `POST /api/settings?key=…` validates and merges
  changes into the stored settings (requires `DATABASE_URL` +
  `STOCK_COMBER_API_KEY`).

[0.5.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.5.1

## [0.5.0] - 2026-08-20

### Added
- **Nightly "hidden gems" universe** (`stock_comber/universe.py`) — instead of
  re-screening every listed company, the nightly job now screens a **capped,
  sector-diversified, rotating** pick tuned to find under-followed long-term
  value. Configurable filters: market-cap band (default $100M–$20B), minimum
  average volume, sectors, excluded sectors, countries (international included),
  per-sector cap, and nightly count (default 75).
- **Curated seed universe** (`seed_universe.py`) of ~65 diversified small/mid-cap
  and international names, expanded over time by a **Finnhub-backed catalog**
  (`universe`, `screen_state` tables): each night enriches a rotating batch with
  market cap / sector / country / volume (`FinnhubSource.fetch_profile`).
- **DB-stored settings** (`settings` table) deep-merged over the file/default
  config via `effective_config`, so a settings page can drive runs.
- `stock-comber screen --nightly` and a `universe.mode: nightly` config switch;
  the scheduled workflow now runs `--nightly` by default (with a `nightly=false`
  dispatch option for the old SEC-list mode).

### Notes
- New tickers beyond the seed come from `universe.extra_tickers` (settings) and
  the accumulating catalog; broad auto-discovery of the full symbol list is a
  planned follow-up (kept off by default to respect Finnhub's free-tier limits).

[0.5.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.5.0

## [0.4.2] - 2026-08-20

### Fixed
- **Scheduled run failed / didn't persist.** The workflow passed `--verbose`
  after the `screen` subcommand (argparse rejected it) and installed the package
  without `psycopg`, so persistence would have no-op'd even with `DATABASE_URL`
  set. The `screen` subcommand now accepts `--verbose` in either position, a
  `storage` extra provides `psycopg`, and the workflow installs `.[storage]`.

[0.4.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.4.2

## [0.4.1] - 2026-08-20

### Added
- **Selectable columns** in the dashboard — a Columns menu to toggle any of the
  17 metrics (plus strategy/pass/score) on or off; the choice persists in
  `localStorage`. Sorting works on whichever columns are shown.
- **Export button** — download the current results as CSV or JSON (client-side),
  with a pointer to the key-protected `/api/export` endpoint for programmatic use.

[0.4.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.4.1

## [0.4.0] - 2026-08-20

### Added
- **Persistence (Postgres / Neon).** New `stock_comber/storage.py` stores each
  screen run, its per-company results, and the raw retrieved fundamentals in a
  Postgres database. Activated when `DATABASE_URL` / `POSTGRES_URL` (or
  `config.storage.dsn`) is set; a no-op backend keeps the app working otherwise.
  The scheduled job persists runs when `DATABASE_URL` is configured.
- **Finnhub source** (`stock_comber/datasources/finnhub.py`), an extra source
  alongside SEC/Yahoo: added to the price chain and used to enrich each company
  with Finnhub's precomputed metrics (stored as raw data). Enabled via
  `FINNHUB_API_KEY` / `config.data.finnhub_api_key`; skipped without a key.
- **Key-protected export API** — `GET /api/export?key=…&format=csv|json[&run=<id>]`
  serves stored runs, guarded by the `STOCK_COMBER_API_KEY` env var
  (query `key` or `X-API-Key` header). Falls back to the committed report when no
  database is configured.
- `Company.extra` field for supplementary source data.

### Notes
- On a large universe, Finnhub's free-tier rate limit (~60 req/min) will throttle
  per-ticker metric calls; failures are caught and the screen continues.

[0.4.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.4.0

## [0.3.2] - 2026-08-20

### Added
- **Yahoo Finance price source** (`stock_comber/datasources/yahoo.py`), used as
  the primary price feed with Stooq as a fallback. Stooq rate-limits shared
  server IPs (e.g. Vercel), which left `price`, P/E, P/B and the Graham number
  empty; Yahoo's keyless chart endpoint is reliable from servers.
- A price-source chain in the screener (`fetch_price`) that tries each source in
  order and tolerates failures.

[0.3.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.3.2

## [0.3.1] - 2026-08-20

### Fixed
- **Live screen returned HTML instead of JSON in production.** Two causes:
  (1) the project had Vercel Authentication (SSO) enabled, which 302-redirected
  `/api/*` to a login page — disabled it so the public dashboard and API work;
  (2) the `builds`/`routes` config built the Python lambdas but didn't route to
  them (404). Replaced it with the standard `framework: null` +
  `outputDirectory: public` + `functions` config so `api/*.py` are served as
  regular serverless functions at `/api/*` and `public/` is the static root.

[0.3.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.3.1

## [0.3.0] - 2026-08-20

### Added
- **Click-through result explanations.** Clicking a row in the dashboard opens a
  detail panel: every criterion with pass/fail, actual vs. target, a plain-English
  note, the key metrics, and any data notes.
- **Data-source & context links** per company: SEC EDGAR filings, the exact
  `companyfacts` JSON used, Stooq, Yahoo Finance, Finviz, and Google Finance.
- **Custom criteria.** A new `custom` strategy evaluates user-defined
  `metric op value` rules (`stock_comber/criteria/custom.py`), configurable via
  `config.custom.criteria`, the `--strategy custom` CLI flag, the
  `/api/screen?...&custom=<json>` parameter, and an interactive builder in the
  dashboard. Validated in `validate_config`.
- Two new metrics in the bundle: `earnings_growth_5y_pct`, `revenue_growth_5y_pct`.
- `cik` is now included on every result (drives the SEC links).

[0.3.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.3.0

## [0.2.2] - 2026-08-20

### Fixed
- **Vercel build still failed** under CLI 59's zero-config Python builder, which
  demands a single entrypoint and rejects our two `/api` functions
  ("No python entrypoint found"). Switched `vercel.json` to explicit legacy
  `builds` (one `@vercel/python` lambda per `api/*.py` plus a `@vercel/static`
  build for `public/`) with `routes`, which bypasses framework auto-detection
  and restores per-file serverless functions. `includeFiles` bundles the
  `stock_comber` package into the screen function and the seed report into the
  latest function.

[0.2.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.2.2

## [0.2.1] - 2026-08-20

### Fixed
- **Vercel build failure** ("No python entrypoint found"). Vercel CLI 59+
  classified the repo as a single-entrypoint Python backend because of the root
  `pyproject.toml`, which conflicts with our two independent `/api` serverless
  functions. Added `.vercelignore` to hide the Python packaging files from the
  Vercel build, restoring the classic static + `/api` functions model. Local
  install and CI are unaffected (they still use `pyproject.toml`).

[0.2.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.2.1

## [0.2.0] - 2026-08-20

### Added
- **Deployable web app on Vercel.**
  - Static dashboard (`public/index.html`): theme-aware, responsive, sortable
    results table; loads the latest scheduled report and runs live screens.
  - Serverless API `GET /api/screen?tickers=…&strategy=…` runs a live screen for
    up to 10 tickers against SEC EDGAR + Stooq.
  - Serverless API `GET /api/latest` serves the most recent committed report.
  - `vercel.json` wiring (`public` output, Python functions with bundled
    package, root rewrite).
- Scheduled workflow now publishes `reports/latest.json` to
  `public/data/latest.json` so the deployed dashboard refreshes automatically.
- Seed `public/data/latest.json` so the dashboard renders on first deploy.

[0.2.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.2.0

## [0.1.0] - 2026-08-20

### Added
- Initial release of **Stock-Comber**, a value-investing stock screener.
- **Benjamin Graham** "defensive investor" strategy (`stock_comber/criteria/graham.py`):
  adequate size, current ratio, debt vs. working capital, earnings stability and
  growth, moderate P/E and P/B, Graham number, positive book value, optional
  dividend record.
- **Warren Buffett** quality strategy (`stock_comber/criteria/buffett.py`):
  high and consistent ROE, low leverage, strong net margin, earnings growth,
  positive free cash flow.
- Free, key-less **data sources**: SEC EDGAR (`companyfacts` fundamentals +
  ticker→CIK map) and Stooq (prices), with a TTL file cache.
- Fully **adjustable parameters** via `config/default.yaml` with deep-merge over
  built-in defaults and config validation.
- **Metrics** engine: current ratio, working capital, debt/equity, ROE, net
  margin, EPS, book value per share, free cash flow, Graham number, P/E, P/B,
  cumulative earnings growth.
- **Reports** in JSON, CSV, Markdown and HTML, plus a stable `latest.*` copy.
- **CLI** (`stock-comber`): `screen`, `config`, `validate`, `tickers`,
  `schedule`.
- **Scheduling**: GitHub Actions workflow for hosted cron runs that commit fresh
  reports, plus an optional local APScheduler runner.
- **CI** workflow running the test suite on Python 3.9 / 3.11 / 3.12.
- Test suite (27 tests) covering config, extraction, metrics, criteria, report
  rendering and the screener orchestrator.
- Claude Code project settings defaulting to Opus 4.8 with medium effort.

[0.1.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.1.0
