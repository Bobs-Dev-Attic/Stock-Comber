# TODO — Stock-Comber

A prioritized backlog from a multi-perspective review (senior engineering, security,
UX, marketing, founder, legal). Ordered so that the highest-risk, lowest-effort items
come first. Check items off as they ship; keep the ordering logical rather than strict.

Legend: **P0** ship first · **P1** reliability/cost · **P2** memory/scale · **P3** UX/quality · **P4** product/strategy.

## P0 — Security & correctness ✅ shipped in v0.38.0
- [x] **In-memory fallback rate limiter.** `apiguard.guard()` now falls back to a bounded
      per-warm-instance sliding-window limiter (`_MemoryLimiter`) when the DB count call
      fails, so a database outage can't turn rate limiting fully off. A `degraded_count()`
      counter + a warning log make the fallback visible.
- [x] **Bucket anonymous (no-key) requests.** `client_id` buckets keyless requests by IP
      under every scope (incl. `key`), so one anonymous flood can't exhaust a shared bucket.
      Covered by a regression test.
- [x] **Strict ticker validation.** New `stock_comber/validation.py` (`is_valid_ticker` /
      `normalize_ticker`, `^[A-Z][A-Z0-9.\-]{0,9}$`) is enforced in `Screener.screen_ticker`
      / `fetch_price` and defensively in the Yahoo + SEC-EDGAR fetchers before any URL is
      built — closing the SSRF/path-injection vector. API handlers already validated at the
      boundary.
- [x] **SQL parameterization audit + secret-leak test.** Audited `storage.py` — every query
      uses psycopg params (no f-string SQL). Added `tests/test_secrets_leak.py` asserting the
      settings endpoint's `_redact`/`_status` never return the Finnhub key, DB URL, or export
      key.
- [x] **Security headers** via `vercel.json`: `X-Content-Type-Options: nosniff`,
      `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, HSTS, and COOP.
      (A full CSP still needs script nonces/hashes given the inline-heavy SPA — see P3.)
- [x] **Surface the "not investment advice" disclaimer in the UI** — persistent page footer
      on the SPA + a disclaimer line in the analysis dialog (verified via Playwright).

### P0 follow-ups
- [x] **Content-Security-Policy** (v0.42.1). Shipped a hardened same-origin CSP in `vercel.json`:
      `default-src 'self'`, external script/connect/frame/object/base all blocked, `img-src`
      allows `https:` (external company logos) + `data:`. `script-src`/`style-src` retain
      `'unsafe-inline'` — unavoidable for a static, inline-heavy SPA on Vercel's CDN (no request
      passes through a server to mint a nonce). Validated with Playwright: 0 violations, 0 page
      errors, dialogs/theme/logo all work. **Nonce/hash-strict** (dropping `'unsafe-inline'`)
      remains a larger effort — see the deferred item below.
- [x] Disclaimer footer on the sub-pages (done in v0.41.0 — settings + thesis; others already had it).

### Deferred (larger efforts, not blocking)
- [ ] **Nonce/hash-strict CSP** (drop `'unsafe-inline'`). Needs either a Vercel Edge Middleware to
      inject a per-request nonce, or a build step that externalizes every inline `<script>`/`<style>`
      **and** removes all inline `style="…"` attributes (87) and the one inline `onerror=` handler.

## P1 — Reliability & cost ✅ shipped in v0.39.0
- [x] **Pooled connection preference.** `resolve_dsn` now prefers
      `STOCK_COMBER_DATABASE_URL_POOLED` (point it at Neon's PgBouncer `-pooler` host) so
      per-invocation connects don't exhaust direct connections under burst; falls back to the
      existing variables unchanged. (A module-level connection *reuse* refactor was deemed too
      risky against the per-op `with self._connect()` pattern — pooled endpoint is the
      recommended Neon fix and captures the win.)
- [x] **In-process settings cache.** `PostgresStorage.get_settings` serves the settings blob
      from a DSN-keyed TTL cache (`STOCK_COMBER_SETTINGS_TTL`, default 30s), refreshed on
      `save_settings`, returning a copy so callers can't corrupt it — removing a DB round-trip
      from the per-request hot path.
- [x] **Cooldown index.** Added a covering `idx_results_run_ticker (run_id, ticker)` so
      `recently_screened` and the Full-list DISTINCT ON stay off a full scan.
- [x] **Uniform timezone-aware datetimes.** `screener.resolve_universe` now uses
      `datetime.now(timezone.utc)` (the last remaining `utcnow()`).
- [x] **Degradation surfaced.** `apiguard.guard` already logs + counts fallbacks; the count is
      now exposed as `rate_limit_degraded` on `GET /api/runs?audit=1`, so a silent DB outage
      is visible rather than looking like "no limiting."

## P2 — Memory & scale ✅ shipped in v0.40.0
- [x] **Streaming path for the screen loop.** Correction from the original note: `build_nightly`
      returns only ticker *strings* — the peak-memory driver is `Screener.run` accumulating
      full `Company`/`AnnualFacts` in `last_companies` (needed by `save_run`). Added
      `Screener.iter_results()` + a `retain_companies` flag so a memory-conscious caller can
      stream per-ticker results with O(1) company memory; `run()` keeps the buffered, ranked,
      persistence-friendly default. `cmd_screen` now also releases `last_companies` right after
      persistence so report rendering doesn't hold it. (A full streaming-persistence rewrite of
      `save_run` was judged too risky for the current ~75-name nightly scale.)
- [x] **Bounded concurrency for per-ticker backtest history fetches.** `_attach_backtest_edge`
      now fetches Yahoo histories on a small bounded thread pool (`data.backtest_fetch_workers`,
      default 4, clamped 1–16; 1 = serial), cutting nightly wall-clock while staying polite;
      per-ticker failures stay isolated.
- [x] **Streaming report writers.** `report.py` gained `stream_csv` / `stream_html` that write
      row-by-row to a file handle; `write_reports` streams the stamped file and `shutil.copyfile`s
      it to `latest`, so a large universe is never held in memory twice. The string renderers
      (`to_csv`/`to_html`, used by the API) are now thin wrappers over the streamers.

## P3 — UX & quality ✅ shipped in v0.41.0
- [x] **First-run onboarding.** A dismissible welcome note on the dashboard explains what
      Stock-Comber is (a research shortlist, *not* advice) and links to About + Glossary;
      dismissal persists per browser (`localStorage.welcomeDismissed`).
- [x] **Accessibility pass.** Modal dialogs (analysis, job, nav drawer) now share a focus-trap
      layer: focus moves into the dialog on open, Tab/Shift-Tab cycle stays inside it,
      Escape closes the top-most dialog, and focus is restored to the trigger on close. The
      view tabs get arrow-key / Home / End navigation. Verified with Playwright (welcome
      show/dismiss, tab arrows, focus-in/ESC/restore, 0 page errors).
- [x] **Mobile layout check** at 375px — dashboard body overflow is 0; sub-pages verified too.
- [x] **Sub-page disclaimer footers** (the deferred P0 follow-up): added the "not investment
      advice" footer to `settings.html` and `thesis.html` (the two that lacked one; the rest
      already carried the caveat). Only the strict-CSP follow-up (see P0 follow-ups) remains.

## P4 — Product & strategy ✅ shipped in v0.42.0
- [x] **Data-provider ToS review.** `docs/DATASOURCES.md` now has a per-provider ToS-review
      summary table (permitted use, redistribution/caching, risk, action). Yahoo's unofficial
      endpoint is the one high-risk dependency (no SLA, discourages scraping).
- [x] **Licensed-source swap plan.** The swap procedure (behind the `datasources/` seam) and
      candidate licensed providers (FMP / Alpha Vantage / Tiingo / Polygon) are documented in
      `docs/DATASOURCES.md`.
- [x] **`LICENSE` + privacy stub.** `LICENSE` confirmed present (MIT). Added `PRIVACY.md`
      documenting that no personal data is collected, secrets are write-only, and the future-
      digest obligations (CAN-SPAM/GDPR) that would apply.
- [x] **Hobby→Pro tier trigger.** `docs/SCALING.md` documents the 12-function cap, the other
      Hobby limits, and the concrete triggers that justify a Pro upgrade — plus cheaper
      alternatives (Upstash, Neon pooling) to reach for first.
- [x] **CI hardening.** Added `pip-audit` (dependency CVE scan) and `mypy` (lenient,
      non-blocking) jobs to `ci.yml`, a lenient `[tool.mypy]` config, and `.github/dependabot.yml`
      for the pip + github-actions ecosystems.
- [x] **Marketing.** README gained a "Why Stock-Comber" section leading with the three
      differentiators (multi-lens consensus, backtested edge, nightly hidden gems).

### P4 follow-ups (deferred, not blocking)
- [ ] Actually migrate price data to a licensed provider (only needed for a public/commercial
      launch — the plan is documented; the code change is scoped but not done).
- [ ] Opt-in nightly digest (RSS/email) — would trigger the privacy/unsubscribe work noted in
      `PRIVACY.md`.
- [ ] Ratchet `mypy` from non-blocking → enforced, per-module.

## Cross-cutting
- [x] Content-Security-Policy — a hardened same-origin CSP ships in v0.42.1 (see P0 follow-ups).
      The remaining nonce/hash-strict variant is tracked under "Deferred (larger efforts)" above.
