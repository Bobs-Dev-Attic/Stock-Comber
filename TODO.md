# TODO — Stock-Comber

A prioritized backlog from a multi-perspective review (senior engineering, security,
UX, marketing, founder, legal). Ordered so that the highest-risk, lowest-effort items
come first. Check items off as they ship; keep the ordering logical rather than strict.

Legend: **P0** ship first · **P1** reliability/cost · **P2** memory/scale · **P3** UX/quality · **P4** product/strategy.

## P0 — Security & correctness
- [ ] **In-memory fallback rate limiter.** `apiguard.guard()` fails open when the DB is
      unreachable (correct for availability), but that leaves *no* limit during an outage.
      Add a per-warm-instance token bucket so a floor of protection survives DB failure.
- [ ] **Bucket anonymous (no-key) requests.** Requests with no API key should be limited
      by a coarse client signal (`apiguard._client_ip` already exists) so one anonymous
      flood can't exhaust a shared bucket for everyone.
- [ ] **Strict ticker validation** (`^[A-Z.\-]{1,10}$`) before any ticker is interpolated
      into an upstream URL (Yahoo/Finnhub/SEC) — closes an SSRF/redirect vector.
- [ ] **SQL parameterization audit + secret-leak test.** Confirm every `storage.py` query
      uses psycopg params (never f-string SQL). Add a test asserting no `/api/*` response
      body contains a known secret-shaped substring.
- [ ] **Security headers** via `vercel.json`: `X-Content-Type-Options: nosniff`,
      `Referrer-Policy`, `X-Frame-Options: DENY` (or CSP `frame-ancestors 'none'`).
      A full CSP needs script nonces/hashes given the inline-heavy SPA — stage that later.
- [ ] **Surface the "not investment advice" disclaimer in the UI** (page footer + the
      analysis dialog), not only in generated reports — it must be visible at the point of
      decision.

## P1 — Reliability & cost
- [ ] **Neon pooled connection string** + a module-level lazy connection reused across warm
      invocations, so bursts don't exhaust Postgres connections.
- [ ] **Cache the settings singleton in-process** with a short TTL and write-invalidation, to
      drop a DB round-trip from the hot path (settings are read on nearly every request).
- [ ] **Index the `recently_screened` lookup** (runs by finished/created time) so cooldown
      filtering doesn't degrade linearly with history.
- [ ] **Uniform timezone-aware datetimes.** Migrate remaining `datetime.utcnow()` (e.g.
      `screener.resolve_universe`) to `datetime.now(timezone.utc)` — `report.py` already does.
- [ ] **Structured logging + degradation counter.** Emit a JSON log/counter when `guard`
      fails open, so a silent DB outage is visible rather than looking like "no limiting."

## P2 — Memory & scale
- [ ] **Stream the nightly build.** `build_nightly` + `_attach_backtest_edge` hold every
      `Company`/`AnnualFacts` in memory at once. Yield `ScreenResult` per ticker and discard
      the source object before the next — peak memory O(1) instead of O(universe).
- [ ] **Bounded concurrency for per-ticker backtest history fetches** (small thread pool,
      respecting upstream rate limits) to cut nightly wall-clock.
- [ ] **Stream report writers** to the file handle instead of `"".join(body)` for large
      universes (CSV/HTML).

## P3 — UX & quality
- [ ] **First-run onboarding / empty states** pointing new users to About + Glossary.
- [ ] **Accessibility pass** (axe): dialog focus traps, ESC-to-close, keyboard tab nav,
      and contrast validated in *both* themes (see the dataviz color rules for any charts).
- [ ] **Mobile layout check** at 375px for the dense tables and dialogs.

## P4 — Product & strategy
- [ ] **Review each data provider's ToS** (Yahoo unofficial endpoints, Finnhub free tier,
      SEC EDGAR, Stooq) for permitted use, caching/redistribution limits, and attribution.
      See `docs/DATASOURCES.md`.
- [ ] **Plan a licensed market-data source swap** (FMP / Alpha Vantage / Tiingo / Polygon)
      behind the existing `datasources/` abstraction — Yahoo's unofficial API has no SLA.
- [ ] **`LICENSE` presence check + privacy-policy stub** (pre-req for any future email digest,
      which adds CAN-SPAM/GDPR obligations).
- [ ] **Decide the Hobby→Pro tier trigger.** The 12-serverless-function cap is a growth wall;
      document the milestone at which lifting it is worth $20/mo.
- [ ] **CI hardening:** add `pip-audit` and Dependabot for dependency CVEs; add `mypy`
      (non-blocking first, then ratchet).
- [ ] **Marketing:** lead with the differentiators — multi-lens value consensus + backtested
      edge + "hidden gems" surfacing. Consider an opt-in nightly digest (RSS/email).
