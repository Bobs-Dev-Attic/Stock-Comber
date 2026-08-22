# Data sources

Stock-Comber combines four upstream providers, all free and mostly key-less. This
documents what each is used for, its endpoint shape, its terms-of-service posture,
and how to swap it out. Anything touching provider terms is a **legal**
consideration — treat the ToS column as a real obligation, not a footnote.

## The providers

| Source | Key? | Used for | Module |
|---|---|---|---|
| **SEC EDGAR** | No | Ticker→CIK map + XBRL `companyfacts` → annual fundamentals | `datasources/sec_edgar.py` |
| **Yahoo Finance** | No | Latest price + volume (primary price source) | `datasources/yahoo.py` |
| **Stooq** | No | Daily close (fallback price source) | `datasources/stooq.py` |
| **Finnhub** | Yes (free tier) | Real-time-ish quote + precomputed metrics; nightly market-cap/sector/country/volume enrichment | `datasources/finnhub.py` |

All fetches pass through a TTL **file cache** (`datasources/cache.py`) so scheduled
jobs don't hammer the free endpoints.

### SEC EDGAR
- Endpoints: `https://www.sec.gov/files/company_tickers.json`,
  `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`.
- **What we parse:** `extract_annuals` reduces the XBRL companyfacts to yearly
  (10-K) fundamentals used by the strategies; `extract_quarters` reduces the same
  document to the latest **quarterly (10-Q)** figures — the quarter's own 3-month
  revenue/net-income/EPS/operating-cash-flow plus the balance sheet as of quarter
  end. The quarterly read is surfaced as fresher `q_*` metrics and a
  `latest_quarter` date; it does **not** change the annual-based scoring.
- **ToS:** the SEC requires a descriptive `User-Agent` with a contact email
  (set `config.data.user_agent`) and rate-limits to ~10 req/s. Public-domain data;
  the main obligation is the honest User-Agent and the rate limit.

### Yahoo Finance
- Endpoint: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d`.
  `parse_chart` returns `(as_of, price, volume)`; `parse_history` yields year-end closes.
- **ToS risk (highest):** this is an **unofficial** endpoint with no SLA and terms
  that discourage scraping/redistribution. It can break without notice. This is the
  most likely provider to need replacing — see "Swapping a source".

### Stooq
- Endpoint: `https://stooq.com/q/d/l/?s={symbol}&i=d` (US tickers use a `.us` suffix).
- Used only as a price fallback when Yahoo fails. Free CSV; check current terms for
  automated/bulk use.

### Finnhub
- Endpoints: `/quote`, `/stock/metric`, plus catalog enrichment for the nightly pool.
- Enabled only when a key is present (`config.data.finnhub_api_key` or
  `FINNHUB_API_KEY`); skipped entirely otherwise. **The key is a secret** — env/DB
  write-only, never returned to the browser; the audit log stores only fingerprints.
- **ToS:** free tier has request-rate and redistribution limits. Review before
  caching/redistributing metrics.

## Terms-of-service review (summary)

A per-provider read of the compliance posture. **This is an engineering summary,
not legal advice** — confirm current terms before any public or commercial launch,
since these can change.

| Provider | Key? | Data | Redistribution / caching | Risk | Action |
|---|---|---|---|---|---|
| **SEC EDGAR** | No | Public-domain filings | Permitted; honest `User-Agent` + ~10 req/s required | **Low** | Keep the contact-email User-Agent and rate limit. Compliant. |
| **Yahoo Finance** | No | Prices/volume (unofficial endpoint) | Terms **discourage** scraping/redistribution; no SLA | **High** | Treat as best-effort; plan a licensed replacement for any public/commercial use. |
| **Stooq** | No | Daily closes (CSV) | Free; bulk/automated use should be verified | **Medium** | Fallback only; low volume. Verify terms before heavy use. |
| **Finnhub** | Yes (free tier) | Quote + metrics | Free tier limits request rate **and** redistribution | **Medium** | Key is secret; respect rate limit; don't redistribute raw metrics beyond the app. |

**Bottom line:** the only high-risk dependency is Yahoo's unofficial endpoint —
both for reliability (no SLA) and terms (discourages scraping). For a personal /
educational deployment the current setup is reasonable; for a public or commercial
launch, move price data to a **licensed** provider (see below) and re-check each
provider's terms.

## Swapping a source

The `datasources/` package is the seam. Each source is a small class with a narrow
interface (fetch a quote / history / fundamentals) consumed by `screener.Screener`.
To replace one (e.g. move price data to a **licensed** API — FMP, Alpha Vantage,
Tiingo, Polygon — for a real ToS and reliability):

1. Add a new module in `datasources/` exposing the same method(s) the current
   source does (e.g. `fetch_quote`, `fetch_history`).
2. Wire it in `screener.Screener.__init__` alongside/instead of the existing source
   (prices already use a **primary + fallback** list — add yours to that chain).
3. Keep the return shapes (`Quote`, the `{year: close}` history dict) identical so
   nothing downstream changes.
4. Route any API key through config/env as a **secret** (never hard-code; never
   return it to the client).
5. Add stub-based tests — the dev proxy blocks live provider calls, so tests must
   not depend on real network access.

## Environment gotcha
The development proxy **blocks Yahoo/Google/Finnhub**, so live fetches cannot be
exercised locally. Unit tests stub the providers; rely on hosted CI and the Vercel
preview to exercise real upstream calls.
