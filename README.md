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
| **Stooq** | Latest daily close price | `stooq.com` |

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
