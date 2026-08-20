# Stock-Comber

**Find publicly traded companies that fit Benjamin Graham and Warren Buffett's
value-investing criteria — using only free, key-less online data sources.**

Stock-Comber combs SEC EDGAR (company fundamentals) and Stooq (prices),
computes the classic value ratios, and scores every company against two
well-known strategies. Every threshold is adjustable, and the whole thing runs
on a schedule so you get a fresh shortlist without lifting a finger.

> ⚠️ **Educational tool only — not investment advice.** Data from free sources
> can be delayed, incomplete, or wrong. Always do your own research.

---

## What it screens for

### Benjamin Graham — the "defensive investor" (from *The Intelligent Investor*)

| Criterion | Default |
|-----------|---------|
| Adequate size (revenue) | ≥ $700M |
| Strong current ratio | ≥ 2.0 |
| Long-term debt ≤ working capital | on |
| Positive earnings, N years running | 5 |
| Earnings growth over the window | ≥ 33% / 5y |
| Moderate P/E | ≤ 15 |
| Moderate P/B | ≤ 1.5 |
| Graham number (P/E × P/B) | ≤ 22.5 |
| Positive book value | on |
| Dividend record | off (optional) |

### Warren Buffett — durable, high-quality compounders

| Criterion | Default |
|-----------|---------|
| Return on equity | ≥ 15% |
| Consistent ROE, N years | 5 |
| Low leverage (total-liabilities / equity) | ≤ 0.5 |
| Net profit margin | ≥ 10% |
| Earnings growth over the window | ≥ 50% / 5y |
| Positive free cash flow, N years | 3 |

A company "passes" a strategy when it clears at least `pass_ratio` (default 80%)
of that strategy's criteria. **Every number above lives in
[`config/default.yaml`](config/default.yaml)** — copy it, tune it, and pass it
with `--config`.

### More investor lenses

Four additional, fully-adjustable strategies ship alongside Graham & Buffett
(all computed from the same free SEC fundamentals + price):

| Strategy | Key | The idea |
|---|---|---|
| **Piotroski F-Score** | `piotroski` | A 9-point test of *improving* financial strength (profitability, leverage/liquidity, efficiency). Passes at ≥ 7/9. |
| **Greenblatt Magic Formula** | `greenblatt` | Cheap **and** productive: high earnings yield + high return on capital. |
| **Peter Lynch (GARP)** | `lynch` | Growth at a reasonable price — PEG ≤ 1 with healthy, not-too-hot growth and sane debt. |
| **Graham Net-Net (NCAV)** | `netnet` | Deep value: price below (⅔ of) net current asset value. Rare — most large caps fail by design. |

Run any subset with `--strategy` (repeatable) or list them under `strategies:`
in config. The dashboard's **Analyze now** button scores a ticker against *all*
of them at once. A couple use free-data stand-ins (e.g. net margin for gross
margin, ROE-style return on capital) — noted in each rule's explanation.

### Custom criteria

Beyond the two built-in strategies you can define your own rules — each a simple
`metric op value` — and run them as a `custom` strategy. Set them in config:

```yaml
strategies: [graham, buffett, custom]
custom:
  pass_ratio: 1.0        # all rules must pass (lower it to allow misses)
  criteria:
    - {name: "Cheap earnings", metric: pe_ratio, op: "<=", value: 12}
    - {name: "High quality",   metric: roe_pct,  op: ">=", value: 20}
    - {metric: debt_to_equity, op: "<=", value: 0.5}
```

`op` is one of `<= < >= > == !=`. `metric` is any key of the computed metric
bundle: `price, revenue, net_income, eps, book_value_per_share, current_ratio,
working_capital, debt_to_equity, long_term_debt_to_equity, roe_pct,
net_margin_pct, free_cash_flow, graham_number, pe_ratio, pb_ratio,
earnings_growth_5y_pct, revenue_growth_5y_pct`. On the web dashboard there's a
**Custom criteria** builder that does the same thing interactively.

### Explaining a result

In the dashboard, **click any row** to open a detailed breakdown: every criterion
with its pass/fail, the actual value vs. the target, a plain-English note, the key
metrics, and links to the underlying **SEC EDGAR** filings and the exact
`companyfacts` data used, plus Stooq, Yahoo Finance, Finviz and Google Finance for
additional context.

---

## Install

```bash
pip install -e .            # core (requests + PyYAML)
pip install -e ".[schedule]"  # + APScheduler for `stock-comber schedule`
pip install -e ".[dev]"       # + pytest
```

Requires Python 3.9+.

## Usage

```bash
# Screen a few tickers you care about
stock-comber screen AAPL MSFT JNJ KO

# Comb the first 500 SEC filers with your own thresholds
stock-comber --config my-rules.yaml screen --limit 500 --verbose

# Only one strategy, only the passers, printed to the terminal
stock-comber screen --strategy graham --only-passing --no-write AAPL

# Inspect / validate configuration
stock-comber config
stock-comber validate --config my-rules.yaml

# List the tickers the SEC exposes
stock-comber tickers --limit 20
```

Reports are written to `reports/` as `screen-YYYYMMDD.{json,csv,md}` plus a
stable `latest.*` copy for dashboards. Choose formats in config
(`output.formats`: any of `json`, `csv`, `markdown`, `html`).

## Data sources (all free, no API key)

| Source | What we pull | Endpoint |
|--------|--------------|----------|
| **SEC EDGAR** | Fundamentals (XBRL `companyfacts`) + ticker→CIK map | `data.sec.gov` |
| **Yahoo Finance** | Latest market price (primary) | `query1.finance.yahoo.com` |
| **Stooq** | Latest daily close price (fallback) | `stooq.com` |

SEC asks for a descriptive `User-Agent` containing a contact email — set it in
`config.data.user_agent`. Responses are cached under `data.cache_dir` with a
TTL so scheduled jobs stay polite. The data layer is pluggable: add a paid
source later by implementing the same small interface.

## Scheduling

**Hosted (recommended):** the included GitHub Actions workflow
[`.github/workflows/screen.yml`](.github/workflows/screen.yml) runs the screen
on a cron (weekdays 06:30 UTC by default) and commits fresh reports. Edit the
`cron:` line to change cadence, or trigger it by hand from the Actions tab.

**Local:** with APScheduler installed,

```bash
stock-comber schedule            # runs on config.schedule.cron
stock-comber schedule --once     # single cycle, then exit
```

## Deploy (Vercel)

The repo ships a deployable web app — a static dashboard plus a Python
serverless API — configured in [`vercel.json`](vercel.json).

1. Import the repository on [Vercel](https://vercel.com/new) (zero config).
2. Deploy. The dashboard renders immediately from seed data.

| Route | What it does |
|-------|--------------|
| `/` | Dashboard: latest shortlist + live-screen box |
| `/api/latest` | Most recent scheduled report (JSON) |
| `/api/screen?tickers=AAPL,MSFT&strategy=graham` | Live screen for ≤10 tickers |
| `/api/screen?tickers=AAPL&custom=[{"metric":"pe_ratio","op":"<=","value":12}]` | Live screen with custom criteria (URL-encode the JSON) |
| `/api/analyze?ticker=AAPL` | **Full analysis now** — all strategies + Finnhub enrichment + recent news scored into an A–F sentiment grade; stored as a run (powers the dashboard "Analyze now" button) |
| `/api/export?key=KEY&format=csv` | **Key-protected** export of the latest stored run (`format=json` also; `&run=<id>` for a specific run) |
| `/settings.html` · `/api/settings` | Settings page + API (edit parameters; `POST` needs `DATABASE_URL` + `STOCK_COMBER_API_KEY`) |
| `/history.html` · `/api/runs` | Activity log — stored runs + ad-hoc searches |
| `/api/tickers?q=AAP` | Ticker autocomplete (powers the dashboard search box) |
| `/analytics.html` · `/api/analytics` | Charts over stored history — runs over time, top passers, sectors, sentiment grades |
| `/api/signals[?action=BUY,WATCH]` | Plain BUY / WATCH / AVOID signal per recently-analyzed ticker, summarising the six value lenses (shown on History). Educational, not advice |
| `/backtest.html` · `/api/backtest?ticker=XOM` | Per-ticker signal backtest — did each lens's PASS years precede better forward returns? Point-in-time fundamentals + Yahoo year-end prices. Educational, not a track record |
| `/thesis.html` · `/api/thesis` | **Investment thesis tracker** — write why you'd buy as measurable conditions; the nightly job re-checks and flags **intact / weakening / broken** with per-condition drift from the baseline. `POST`/`DELETE` need `STOCK_COMBER_API_KEY` |

### Persistence, Finnhub & the export API (all optional)

Set these environment variables (in Vercel and as GitHub Actions secrets) to
turn on the extras — the app runs without any of them:

| Variable | Enables |
|----------|---------|
| `DATABASE_URL` | Store each run + raw data in Postgres (e.g. a free [Neon](https://neon.tech) database). |
| `FINNHUB_API_KEY` | Use [Finnhub](https://finnhub.io) as an extra price + metrics source. |
| `STOCK_COMBER_API_KEY` | Protect `/api/export`; pass it as `?key=` or the `X-API-Key` header. |

When `DATABASE_URL` is set, the scheduled job persists every run into the
`screen_runs`, `screen_results` and `raw_fundamentals` tables (schema created
automatically), and `/api/export` serves them.

The scheduled GitHub Actions job publishes each run to
`public/data/latest.json`, so the deployed dashboard refreshes automatically.
Live `/api/screen` calls reach SEC EDGAR + Stooq at request time and are capped
to keep within the serverless time budget; full-universe sweeps belong in the
scheduled job.

## Architecture

```
stock_comber/
  config.py         # adjustable parameters + validation
  models.py         # dataclasses (AnnualFacts, Company, ScreenResult, …)
  metrics.py        # derived ratios (P/E, P/B, ROE, Graham number, FCF, …)
  criteria/
    graham.py       # defensive-investor rules
    buffett.py      # quality/moat rules
  datasources/
    sec_edgar.py    # fundamentals + ticker map (+ companyfacts reducer)
    stooq.py        # prices
    cache.py        # TTL file cache
  screener.py       # fetch → evaluate → rank
  report.py         # json / csv / markdown / html
  cli.py            # command-line entry point
  scheduler.py      # optional local cron
api/
  screen.py         # serverless: live screen for given tickers
  latest.py         # serverless: serve latest committed report
public/
  index.html        # dashboard
  data/latest.json  # latest report (refreshed by the scheduled job)
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

CI runs the suite on Python 3.9 / 3.11 / 3.12 for every push and PR.

## Claude Code

This repo is configured (in [`.claude/settings.json`](.claude/settings.json))
to default to **Claude Opus 4.8** with **medium reasoning effort**.

## License

MIT — see [LICENSE](LICENSE).
