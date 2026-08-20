# Release notes

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
