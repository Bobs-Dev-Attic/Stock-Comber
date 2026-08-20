# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
