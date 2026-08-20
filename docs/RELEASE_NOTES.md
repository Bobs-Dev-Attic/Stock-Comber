# Release notes

## v0.7.0 — Analysis queue, news & sentiment (2026-08-20)

- **Queue for deeper analysis.** Screen a ticker and it's queued; a worker runs
  every ~20 min doing a full analysis — all strategies, Finnhub enrichment, and
  recent **news with an A–F sentiment grade** — and stores it as a run. Queue
  status shows on the History page.
- **News & sentiment** come from Finnhub's free company-news feed scored by a
  transparent local lexicon (no paid API). Stored with each analysis.
- `POST /api/queue` to enqueue, `GET /api/queue` to view.

_On Dataroma:_ superinvestor ownership is a strong gem signal, but there's no
free/official API and scraping is fragile — SEC 13F filings are the clean
free alternative (a possible future enrichment).

## v0.6.0 — Activity log & ticker autocomplete (2026-08-20)

- **History page** (`/history.html`) — a log of every stored nightly run (with
  per-run CSV/JSON export links) and every ad-hoc search. Backed by `/api/runs`.
- **Ticker autocomplete** in the dashboard search box, backed by `/api/tickers`
  (prefix/substring search over the SEC ticker list, with keyboard nav).

## v0.5.1 — Settings page (2026-08-20)

A browser **Settings page** (linked from the dashboard) to edit every parameter:
strategies, Graham/Buffett thresholds, the nightly universe filters (cap,
market-cap band, volume, sectors, countries, extra tickers), custom criteria and
output preferences. It shows which keys/DB are configured (never the secrets),
saves to your database, or lets you **Download as YAML** if you don't use a DB.

## v0.5.0 — Nightly "hidden gems" universe (2026-08-20)

The nightly job no longer re-screens every listed company. It now screens a
**capped, sector-diversified, rotating** pick designed to surface under-followed
long-term value:

- Filters by **market-cap band** (default $100M–$20B), **volume**, **sector**,
  and **country** (international included), with a **per-sector cap** so results
  stay diversified, and a **nightly count** (default 75) that **rotates** so
  coverage spreads across nights.
- Starts from a **curated seed** of diversified small/mid-cap + international
  names and **expands via Finnhub** (market cap / sector / country / volume),
  cached in the database.
- DB settings already override the file config; a settings page to edit it all
  ships next.

Run it with `stock-comber screen --nightly`; the scheduled workflow uses it by
default.

## v0.4.1 — Selectable columns & export button (2026-08-20)

The dashboard now has a **Columns** menu (toggle any metric on/off, remembered in
your browser) and an **Export** button to download the current results as CSV or
JSON. Programmatic export stays available via the key-protected `/api/export`.

## v0.4.0 — Persistence, Finnhub, and a key-protected export API (2026-08-20)

- **Storage (Postgres/Neon):** each screen run — results plus the raw retrieved
  fundamentals — is stored when a `DATABASE_URL` is configured. No-op without one.
- **Finnhub:** an extra price + metrics source, enabled with a `FINNHUB_API_KEY`.
- **Export API:** `GET /api/export?key=…&format=csv|json` returns stored runs,
  protected by the `STOCK_COMBER_API_KEY` env var.

### Setup (all optional; the app runs without them)
- **Neon:** create a free Postgres project, copy its connection string, and add it
  as `DATABASE_URL` in Vercel (Project → Settings → Environment Variables) and as
  a `DATABASE_URL` GitHub Actions secret (so scheduled runs persist).
- **Finnhub:** get a free key at finnhub.io and set `FINNHUB_API_KEY` in Vercel /
  GitHub secrets.
- **Export key:** set `STOCK_COMBER_API_KEY` in Vercel to any random string; pass
  it as `?key=` or the `X-API-Key` header.

## v0.3.2 — Reliable prices (Yahoo fallback) (2026-08-20)

Added a Yahoo Finance price source (keyless) as the primary price feed, with
Stooq as a fallback. Stooq rate-limits shared server IPs, which was leaving
price, P/E, P/B and the Graham number blank on the hosted app; Yahoo's chart
endpoint works reliably from servers, so price-based (Graham) screening now
computes.

## v0.3.1 — Live-screen production fix (2026-08-20)

The live screen was returning HTML instead of JSON in production. Fixed two
causes: Vercel Authentication was enabled (redirecting `/api/*` to a login page),
and the `builds`/`routes` config wasn't routing to the Python lambdas (404).
Switched to the standard `framework: null` + `outputDirectory: public` +
`functions` config so `/api/screen` and `/api/latest` serve JSON.

## v0.3.0 — Explanations, source links & custom criteria (2026-08-20)

Three new user-facing capabilities on the dashboard and API:

- **Click any result** to see a full breakdown — each criterion's pass/fail,
  actual vs. target, and a plain-English note, plus the key metrics.
- **Data-source & context links** on every company: SEC EDGAR filings and the
  exact `companyfacts` data used, plus Stooq, Yahoo Finance, Finviz and Google
  Finance.
- **Custom criteria** — define your own `metric op value` rules and run them as
  a `custom` strategy. Available in config, the CLI (`--strategy custom`), the
  API (`?custom=<json>`), and an interactive builder in the dashboard.

## v0.2.2 — Vercel build fix (explicit builds) (2026-08-20)

Vercel CLI 59's zero-config Python builder wants a single entrypoint and
rejected our two `/api` functions. Switched `vercel.json` to explicit legacy
`builds` + `routes` (one Python lambda per file, plus a static build for
`public/`), which bypasses framework auto-detection and restores the
static + serverless-functions layout. This supersedes the v0.2.1 approach.

## v0.2.1 — Vercel build fix (2026-08-20)

Fixes the Vercel deployment so the app actually builds and serves.

- Vercel CLI 59+ mistook the root `pyproject.toml` for a single-entrypoint
  Python backend and failed with "No python entrypoint found." Added
  `.vercelignore` to keep Vercel on the classic **static + `/api` serverless
  functions** model. Local install and CI still use `pyproject.toml` unchanged.

## v0.2.0 — Deployable web app (2026-08-20)

Stock-Comber is now a deployable web app, not just a CLI.

### Highlights
- **Dashboard** (`public/index.html`) — a clean, theme-aware page that shows the
  latest shortlist and lets you run a live screen on any tickers.
- **Serverless API** on Vercel:
  - `GET /api/screen?tickers=AAPL,MSFT&strategy=graham` — live screen (≤10 tickers).
  - `GET /api/latest` — the most recent scheduled report.
- **Auto-refresh** — the scheduled GitHub Actions job publishes each run to
  `public/data/latest.json`, so the deployed dashboard updates itself.

### Deploy
Import the repo on Vercel (zero config — `vercel.json` is included) and deploy.
The dashboard renders immediately from seed data; the scheduled job keeps it
current.

> Educational tool only — not investment advice.

## v0.1.0 — Initial release (2026-08-20)

Stock-Comber's first release: a value-investing stock screener that combs free
online data sources to surface companies fitting Graham and Buffett criteria.

### Highlights
- **Two strategies out of the box** — Benjamin Graham's defensive-investor
  checklist and a Warren Buffett quality/moat checklist.
- **Free data, no API keys** — SEC EDGAR fundamentals + Stooq prices, cached.
- **Everything is adjustable** — one YAML file drives every threshold.
- **Runs on a schedule** — GitHub Actions workflow commits a fresh shortlist;
  optional local scheduler included.
- **Reports** in JSON / CSV / Markdown / HTML.

### Getting started
```bash
pip install -e .
stock-comber screen AAPL MSFT JNJ KO
```

See the [README](../README.md) for full usage and the
[CHANGELOG](../CHANGELOG.md) for the complete list of changes.

> Educational tool only — not investment advice.
