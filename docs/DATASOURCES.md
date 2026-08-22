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
