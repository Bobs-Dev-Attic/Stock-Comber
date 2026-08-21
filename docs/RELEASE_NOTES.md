# Release notes

## v0.21.0 — Saved custom jobs (2026-08-21)

Custom jobs can now be **saved to the database and re-run later**. In the
**Custom jobs** tab, give your builder a name and click **Save job** to persist
its criteria, tickers, and ticked strategies; pick one from the **Saved jobs**
dropdown and **Load** it to refill the builder, or **Delete** it. Jobs are stored
server-side (in the settings blob, under a new `jobs` config key) rather than in
the browser, so they survive reloads and are shared across devices.

- Reading the saved jobs is public (`GET /api/settings`); saving/deleting is
  gated by the same API key as other write endpoints (`POST /api/settings`), so
  the browser prompts for it once and remembers it for the session.
- Each job is validated on save — a unique, non-empty name, and (when present)
  valid custom criteria and strategy names.
- Implemented without adding a serverless function, keeping the Vercel Hobby
  12-function budget intact.

## v0.20.1 — Activity banner (2026-08-20)

A sticky banner now appears at the top of the dashboard while work is in
progress: **running** (a custom job, a manual screen, or a deep analysis — shown
in the accent color with a spinner) and **queued** (when tickers are added to the
~20-minute deep-analysis worker — shown in amber and auto-dismissing). It respects
the reduced-motion setting.

## v0.20.0 — Tabbed dashboard (2026-08-20)

The dashboard is now organized into three tabs, each with its own results and
status so they no longer overwrite each other:

- **📅 Scheduled report** — the latest nightly "hidden gems" shortlist (ranked by
  health), loaded automatically, with a Refresh button.
- **⚙️ Custom jobs** — build a reusable screen from your own `metric op value`
  rules over a set of tickers or an index template (Dow / Nasdaq-100 / S&P 500),
  then Run job. Templates now live here.
- **🔍 Manual searches** — the ticker search box, Analyze deep-dive, and strategy
  picker, with recent-searches-on-focus.

## v0.19.2 — Health score on the Analytics page (2026-08-20)

The **Analytics** page gains a **Health-score grades** chart: the composite
0–100 health of every passing company, bucketed into A–F bands (counted once per
ticker) and colored green (A/B) → amber (C) → red (D/F), with each band's average
score. It sits next to the news-sentiment chart. Backed by a new `health`
aggregation on `/api/analytics`.

## v0.19.1 — Nightly gems ranked by health (2026-08-20)

The nightly "hidden gems" shortlist is now **ranked by the composite health
score** (the blended 0–100 Value / Quality / Growth number). Every screen result
carries a `health_score`, the nightly job sorts by it by default, and it's a
default column on the dashboard and included in exports — so the strongest
businesses surface at the top instead of ties being broken arbitrarily. Set a
different `output.sort_by` to override.

## v0.19.0 — Investment thesis tracker (2026-08-20)

The feature almost nobody offers: the app doesn't just track the stock, it
tracks **why you bought it**.

On the new **Thesis Tracker** (`/thesis.html`, also a "🎯 track thesis" link in
the Analyze deep-dive) you write your reasons as **measurable conditions** —
e.g. `revenue_growth_5y_pct ≥ 20`, `net_margin_pct ≥ 15`, `debt_to_equity ≤ 0.5`
— plus a free-text note. Stock-Comber snapshots today's metrics as your
**baseline**, and the nightly job re-checks the live fundamentals and marks each
thesis:

- **intact** — every condition still holds,
- **weakening** — all still hold, but a metric has slipped ≥15% toward its limit,
- **broken** — one or more conditions no longer hold.

Each thesis shows a per-condition table: current value, baseline, **drift**, and
pass/fail — so you can see exactly what changed. Conditions reuse the same
metric vocabulary as custom criteria. Creating and deleting theses needs the
`STOCK_COMBER_API_KEY`; anyone can view them.

_Not investment advice — an educational tool for keeping yourself honest about
your original reasoning._

## v0.18.1 — Company snapshot header (2026-08-20)

The **Analyze** deep-dive now opens with a one-line **company snapshot** —
exchange, industry, market cap, IPO year, shares outstanding, and a link to the
company website (with its logo when available), from Finnhub's free `profile2`.
Also on the `profile` field of `/api/analyze`.

## v0.18.0 — Composite 0–100 scores (2026-08-20)

The **Analyze** deep-dive now opens with four at-a-glance scores:

- **Value** — how cheap (earnings yield, P/E, P/B)
- **Quality** — how good the business is (ROE, return on capital, margins, ROA,
  debt, liquidity)
- **Growth** — 5-year earnings & revenue trends
- **Overall** — a quality-tilted blend, with an A–F grade

Each is a 0–100 number with a colored meter. The math is fully transparent —
documented linear bands over the fundamentals Stock-Comber already computes, no
machine learning and no paid data. Metrics that aren't available are skipped and
the weights renormalise, so you never get a misleadingly low score just because
one input was missing. Also available programmatically as the `scores` field on
`/api/analyze`.

## v0.17.0 — Index universe templates (2026-08-20)

Screen a whole index — the **Dow 30**, **Nasdaq-100**, or **S&P 500** — filtered
by market-cap band, volume, **sector** and **industry**:

- **Templates menu** on the dashboard: pick an index and (optionally) a sector,
  and it loads the top-by-market-cap slice into the search box for a live
  side-by-side compare.
- **Nightly job:** choose an **Index template** in Settings (plus the new
  *Only industries* filter). The nightly "hidden gems" engine then draws its
  capped, sector-diversified, rotating pick from that index — so the full index
  is covered across successive nights.
- Backed by a new read-only `GET /api/universe`. Constituents are periodic
  snapshots bundled with the app (educational, not a live index feed).

## v0.16.0 — Store your Finnhub key from Settings (2026-08-20)

The Settings page now has a **key-entry field** that saves your **Finnhub API
key into the database** — a convenient alternative to setting it as an
environment variable. It powers news, sentiment, and enrichment.

Handled safely:

- **Write-only** — the key is never shown back; `GET /api/settings` redacts it.
- A **blank field never wipes** a stored key (blank = leave unchanged).
- Saving requires your **Export/API key** (`STOCK_COMBER_API_KEY`), the same gate
  as other settings; the status pill shows "Finnhub configured" from an env var
  **or** a stored key.

Only the Finnhub key is storable: `DATABASE_URL` is needed *to reach* the
database (so it can't live inside it), and `STOCK_COMBER_API_KEY` is the gate
that authorizes saving — both remain environment variables.

**Also:** live `/api/screen` and `/api/analyze` now merge your database-stored
settings over the defaults, so your tuned thresholds and stored key drive live
screens and deep-dives too — previously only the nightly job did.

## v0.15.4 — Settings page covers all six analysts (2026-08-20)

The **Settings page** (⚙️ from the dashboard) already let you set your keys'
status, pick strategies, tune Graham/Buffett thresholds, shape the nightly
"hidden gems" universe, define custom criteria, and set output preferences —
saving to your database or downloading as YAML. This release rounds it out for
the newer analysts:

- **Select and tune all six strategies** — Piotroski F-Score, Greenblatt Magic
  Formula, Lynch (GARP), and Graham Net-Net now have their own editable
  threshold cards, next to Graham and Buffett.
- **Custom criteria** gain the newer metrics (ROA, return-on-capital, earnings
  yield, NCAV per share, earnings CAGR).

Keys remain **read-only status pills** by design — `FINNHUB_API_KEY`,
`DATABASE_URL`, and `STOCK_COMBER_API_KEY` are secrets you set as environment
variables (Vercel / GitHub Actions), never typed into the browser.

## v0.15.3 — Recent searches on focus (2026-08-20)

Click into the ticker box (while it's empty) and your **recent searches** now
drop down — deduplicated and labelled by source (🕓 analyze / live) — so you can
re-run a prior ticker or comparison set with a single tap. Start typing and it
switches back to the usual ticker autocomplete. Backed by the existing
`/api/runs` search log.

## v0.15.2 — Analyze as a search icon in the ticker field (2026-08-20)

The Analyze button now lives **inside the ticker field**, on the same row —
embedded at the right edge as a 🔍 search icon (labelled "Analyze" for screen
readers, with the full tooltip on hover). This tightens the search row,
especially on mobile. It shows a ⏳ while working. Nothing about the behaviour
changed: enter one ticker for the full deep-dive, several to compare them in a
table using the ticked strategies.

## v0.15.1 — Mega-cap CIK override (2026-08-20)

Hardens SEC fundamentals resolution for the largest, most-searched tickers
(Apple, Microsoft, Exxon, Berkshire, and ~40 more). SEC's ticker→CIK file
occasionally points a big name at a newer registrant that has no 10-K XBRL data;
a curated override now supplies the correct filing CIK for those names.

It's a safety net, not the primary resolver: it only kicks in when the mapped
CIK returns no fundamentals (the same trigger as the existing EDGAR fallback),
and it's tried before the network lookup — so these names resolve instantly.
Because it fires only on an already-failing ticker, a wrong entry can never
regress a ticker that already resolves correctly.

## v0.15.0 — Backtest (2026-08-20)

The second half of the algo-trading thread: a **Backtest** page
(`/backtest.html`) that asks a simple, honest question — *did each lens's verdict
precede better returns for this company?*

- For every fiscal year, each lens is re-scored using only the fundamentals
  known **through that year** plus the year-end price, then compared to the
  **next year's** return.
- A ranked table shows each lens's **edge** (average forward return in its PASS
  years minus its FAIL years), pass hit-rate, and year counts; the best lens is
  highlighted.
- A per-year diverging bar chart shows the forward return each year, solid where
  the lens said PASS and faint where it said FAIL.
- Deep-linked from the **Analyze** deep-dive (a "🧪 backtest" link) and the
  dashboard footer. Backed by `GET /api/backtest?ticker=…`.

**Honesty note:** free data means annual fundamentals + Yahoo year-end prices,
one name at a time, with no dividends, costs, or survivorship control. It's
directional colour on a signal — **not a research backtest, not a track record,
and not investment advice.**

## v0.14.0 — Signals & alerts (2026-08-20)

The six value lenses now roll up into one plain-language call per company:

- **BUY / WATCH / AVOID** — a transparent, rules-based read of how many lenses
  clear the company and how strongly (blended into a 0–100 signal score). It
  shows as a colored banner at the top of the **Analyze** deep-dive, with the
  reasoning spelled out.
- **Alerts list** on the **History** page — the most recently analyzed tickers,
  actionable ones (BUY/WATCH) first, from the new `GET /api/signals`.

This is a summary of the checklists you can already see — **educational, not
investment advice** — and a user's ad-hoc "custom" lens is deliberately excluded
so it can't skew the consensus.

_Next up in this thread: a backtest view (strategy signal vs. forward return)._

## v0.13.0 — Similar companies in the same sector (2026-08-20)

The **Analyze** deep-dive now includes a **Similar companies (same sector)**
section. It pulls the company's peers from Finnhub's free `/stock/peers`
endpoint and lets you:

- **Tap a peer** to run a full deep-dive on it, or
- **Compare all in a table** — drops the whole peer group (plus the original
  ticker) into the batch screen so you see them scored side by side against the
  strategies you've ticked.

Peers need a `FINNHUB_API_KEY` (already configured on the hosted app); without
one the section shows a short note. Also available programmatically as the
`peers` field on `/api/analyze`.

## v0.12.1 — Mobile responsiveness (2026-08-20)

Fixes the **Strategies dropdown opening off-screen on phones** and makes every
page adapt to browser width:

- The Strategies / Columns / Export menus become a **viewport-pinned bottom
  sheet** on narrow screens, so they always fit no matter which button opened
  them.
- The dashboard search row **stacks** on phones and its buttons span the width.
- Dashboard, History, Settings and Analytics all get tighter phone padding, and
  the Analytics charts **scale by aspect ratio** instead of squishing.
- Verified: no horizontal page overflow at a 360px viewport.

## v0.12.0 — One "Analyze" button (2026-08-20)

Screen and Analyze now are merged into a **single Analyze button** that does the
right thing based on what you type:

- **One ticker** → the full deep-dive: all six analysts + Finnhub enrichment +
  recent news and a sentiment grade, in the detail view (and stored to history).
- **Several tickers** (up to 10) → compare them side by side in the sortable
  table, using the strategies you tick.
- **Empty box** → reloads the latest scheduled report.

Pressing Enter in the search box does the same. The ticked **Strategies** apply
to the multi-ticker table; a single-ticker deep-dive always runs every analyst.

## v0.11.1 — Multi-select strategies + clearer Screen vs. Analyze (2026-08-20)

- The strategy chooser under the search box is now a **Strategies ▾ dropdown with
  checkboxes** for all six lenses — tick any combination for the Screen table,
  and your choice is remembered (defaults to Graham + Buffett).
- **What does "Screen" do vs. "Analyze now"?** Both are useful:
  - **Screen** (renamed from "Screen live") compares **up to 10 tickers at once**
    as a sortable table, using the strategies you tick. Fast, no news/enrichment.
  - **Analyze now** takes **one** ticker and does the full deep-dive — all six
    analysts + Finnhub enrichment + recent news and a sentiment grade — in a
    detail view, and stores it to history.

  Tooltips and inline help now spell this out on the page.

## v0.11.0 — Four more investor lenses + fuller history (2026-08-20)

**Are there other analysts to consider?** Yes — four classics now ship alongside
Graham & Buffett, all computed from the same free SEC data:

- **Piotroski F-Score** — a 9-point test of *improving* financial strength
  (profitability, leverage/liquidity, operating efficiency); passes at ≥ 7/9.
- **Greenblatt Magic Formula** — cheap **and** productive: high earnings yield +
  high return on capital.
- **Peter Lynch (GARP)** — growth at a reasonable price: PEG ≤ 1 with healthy,
  not-overheated growth and manageable debt.
- **Graham Net-Net (NCAV)** — deep value: price below (two-thirds of) net current
  asset value. Rare, and most large caps fail by design.

The dashboard **Analyze now** button now scores a ticker against **all six**
lenses at once, each with its own pass/fail breakdown (tap a strategy for the
per-criterion actual-vs-target detail). They're also available via `--strategy`,
the `strategies:` config list, and `/api/screen?strategy=…`. A few use
free-data stand-ins (net margin for gross margin, an ROE-style return on
capital), noted in each rule.

**Fuller history.** Manual analyses are now logged to the History page's search
list (not just stored as runs), so every search — live screens and one-off
analyses — is recorded.

## v0.10.0 — Real data for "wrong-CIK" tickers + honest analysis states (2026-08-20)

**Why did XOM say "near miss" with a 0/0 score?** It wasn't a near miss — the
app couldn't get Exxon's fundamentals. SEC's ticker→CIK map pointed **XOM** at a
registrant (CIK 2115436) that has no XBRL 10-K financials, while Exxon's actual
filings live under CIK 34088. With no annual data, every criterion was skipped
and the empty result was mislabeled "near miss."

Two fixes:

- **CIK fallback.** When the mapped CIK returns no annual fundamentals, the app
  now asks EDGAR's company search which CIK actually files 10-Ks for that ticker
  and re-fetches that entity's `companyfacts`. So XOM (and any similarly
  misdirected ticker) gets a real Graham + Buffett breakdown. The fallback only
  fires when the primary lookup comes back empty.
- **Honest states + explanations.** Even when a stock *doesn't fit*, you now get
  the full per-criterion breakdown (actual vs. target, pass/fail, plain-English
  note). The modal distinguishes **PASS** / **did not pass** ("met N of M
  criteria") from **not analyzed**, and when fundamentals genuinely can't be
  retrieved it says so plainly instead of showing a blank score. News sentiment
  still runs either way.

## v0.9.1 — Fix: autocomplete blocked the action buttons (2026-08-20)

The ticker autocomplete opened as an overlay that could sit on top of the
wrapped **Analyze now** / **Screen live** buttons, so a click hit a suggestion
instead of the button and the Graham/Buffett analysis never ran. The suggestion
list now renders **in-flow below the controls** (it can't cover the buttons) and
closes the moment you start an action. Enter XOM, click **Analyze now**, and it
runs.

## v0.9.0 — Manual "Analyze now" button (2026-08-20)

The dashboard now has an **Analyze now** button beside "Screen live". Enter a
ticker and it runs the *full* analysis on demand — all strategies, Finnhub
enrichment, and recent company news scored into an **A–F sentiment grade** —
without waiting for the ~20-minute queue worker.

- Results open in a modal: each strategy's pass/fail (tap for the full
  criterion breakdown), a sentiment summary (grade, net score, headline count),
  and the recent news headlines.
- When a database is configured the analysis is **stored as its own run**, so it
  also shows up on the History and Analytics pages.
- Backed by a new `GET /api/analyze?ticker=…` endpoint. News + sentiment need a
  `FINNHUB_API_KEY`; without one the screen still runs, just without news.

## v0.8.0 — Analytics & charts (2026-08-20)

A new **Analytics** page (`/analytics.html`, linked from the dashboard and
History) visualises your stored screening history:

- **Screened vs. passing per run** — grouped bars over time, oldest to newest.
- **Most frequently passing tickers** — which names clear a strategy most often.
- **Passing by sector** — where the matches cluster, joined to the universe catalog.
- **News-sentiment grades** — the A–F distribution from queued full analyses.

Powered by a new read-only `GET /api/analytics` endpoint that aggregates runs,
results, the universe catalog and stored sentiment. Charts are self-contained
inline SVG (no external libraries), theme-aware, and use a colorblind-validated
palette with direct value labels. Everything degrades gracefully to empty
states when no database is configured.

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
