# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.49.1] - 2026-08-23

### Fixed
- **Grouping the Full list by Ticker no longer looks blank (real fix).** The Full list is deduped per
  **(ticker, strategy)**, so a ticker has several rows (one per strategy) — grouping by Ticker
  therefore makes multi-member groups, and those were rendering **collapsed by default**, hiding
  every data row. Groups now render **expanded by default** (data always visible); clicking a group
  header collapses it, and a single-row group shows its row with no toggle. Supersedes the v0.45.2
  singleton-only fix, which wrongly assumed one row per ticker.

[0.49.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.49.1

## [0.49.0] - 2026-08-23

### Added
- **Illustrative "value entry zone" in the deep-dive analysis.** A new `stock_comber/entry.py`
  (`suggest_entry_zone`) computes a transparent reference entry range for a full analysis: it anchors
  on the Graham fair value, applies a base margin of safety (default 25%), then nudges that discount —
  in percentage points — by the **backtest edge** (more historical edge → less discount), **news
  sentiment** (positive tone → less discount), and **volume velocity** (heavy recent volume vs.
  average → more discount and a wider band). Returns a low/mid/high zone, the final margin of safety,
  a confidence label (from how many signals were available), whether the current price sits
  below/within/above the zone, and a full per-factor breakdown so the number is auditable. Surfaced
  as a "Value entry zone" card in the analysis dialog (`/api/analyze` gains an `entry_zone` field).
  Knobs live under `config.entry`.

### Notes
- This is explicitly **not a price target and not investment advice** — it's a deterministic
  margin-of-safety reference over public fundamentals, carrying the same educational caveat as the
  rest of the app, and it degrades gracefully (no Graham fair value → no zone, with the reason shown).
  Scoped to the deep-dive analysis only; the Full list is unchanged.

[0.49.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.49.0

## [0.48.0] - 2026-08-22

### Added
- **Opt-in nightly digest as an RSS feed.** A new `rss` output format (`report.stream_rss`) emits an
  RSS 2.0 feed of the passing "hidden gems" from the latest nightly run. The scheduled workflow
  publishes it at **`/feed.xml`**, and the dashboard links it (a `<link rel="alternate">` in the head
  plus a footer link) so any reader can subscribe. Each item carries the ticker, company, strategy,
  score, and key metrics (price, P/E, backtest edge) with the standard "not investment advice"
  caveat. Feed links use a configurable `output.site_url` (defaults to the project homepage). Chosen
  over an email digest deliberately: RSS is a **static, no-PII** feed — no subscriber list, no
  unsubscribe flow, no mail-provider secret, and no new serverless function (we stay at the 12-cap).
  Streamed item-by-item and fully XML-escaped.

[0.48.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.48.0

## [0.47.0] - 2026-08-22

### Changed
- **Backtest price history now routes through Tiingo when a key is configured.** New
  `datasources.make_history_source(cfg, …)` returns a `TiingoSource` (dividend/split-**adjusted**
  closes) when `data.tiingo_api_key` / `TIINGO_API_KEY` is set, else the free `YahooSource` — both
  expose an identical `fetch_history(ticker, years) → {year: close}`. Wired into all three history
  call sites: the nightly per-name backtest edge (`cli._attach_backtest_edge`, per-worker-thread),
  the deep-dive analysis backtest (`api/analyze.py`), and the `/api/backtest` endpoint. With no key,
  history stays on Yahoo exactly as before. This completes the licensed-provider migration started in
  v0.46.0 (quotes) — Tiingo now serves both quotes and backtest history.

[0.47.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.47.0

## [0.46.0] - 2026-08-22

### Added
- **Tiingo licensed price provider.** New `datasources/tiingo.py` (`TiingoSource`) fetches the latest
  end-of-day price + volume and year-end **dividend/split-adjusted** history from
  [Tiingo](https://www.tiingo.com/), a licensed provider with a real terms-of-service and SLA — unlike
  the unofficial Yahoo endpoint. Enabled only when a key is configured (`config.data.tiingo_api_key`
  or the `TIINGO_API_KEY` env var); when present it becomes the **primary** price source ahead of the
  free Yahoo → Stooq → Finnhub chain, so screening quotes come from a licensed feed while the free
  sources stay as resilient fallbacks. With no key, the chain is byte-for-byte unchanged.
- **Store the Tiingo key in Settings.** The Settings page gained a write-only Tiingo key field and a
  "Tiingo" chip in Keys & status, mirroring the Finnhub key handling.

### Security
- The Tiingo key is a **secret**: it travels only in the request `Authorization` header (never the
  URL, the cache key, or a log line), is redacted by the settings API (`_SECRET_PATHS`), and is
  reported to the browser only as a boolean. Covered by `tests/test_secrets_leak.py` and
  `tests/test_tiingo.py` (asserts the key never appears in the request URL/params).

### Notes
- Scope is the **price/quote chain** (what screening and the Full list use). `TiingoSource` also
  implements `fetch_history`; routing the nightly/deep-dive backtest through it (currently Yahoo) is
  a scoped follow-up so the threaded history path stays untouched here.

[0.46.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.46.0

## [0.45.2] - 2026-08-22

### Fixed
- **Grouping the Full list by Ticker no longer shows a blank table.** The Full list is deduped to
  one row per name, so grouping by Ticker (or any all-unique column) produced only single-member
  groups — all collapsed by default, hiding the one row each. Single-member groups now always
  render their row and drop the expand toggle, so the data is never hidden behind a click.
  Multi-member groups (e.g. by Strategy or Passing) still collapse by default as before.

[0.45.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.45.2

## [0.45.1] - 2026-08-22

### Changed
- **`mypy` is now an enforced (blocking) CI gate** for the `stock_comber` package. The package
  type-checks clean and the `typecheck` job no longer swallows failures, so any *new* type error
  fails CI. Cleared the existing findings with real fixes (implicit-`Optional` defaults on
  `apiguard.guard`/`_MemoryLimiter.hit`, a `None`-narrowing list comp in the Buffett FCF check
  and the news-sentiment call, an explicit `Optional[Company]` in `screen_ticker`, and clearer
  tuple unpacking in the nightly backtest loop). The config stays lenient (untyped bodies
  allowed), so this gates regressions without a full annotation sweep; `api/` handlers and
  `tests/` remain out of scope. `mypy` added to the `dev` extra. No runtime behavior change.

[0.45.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.45.1

## [0.45.0] - 2026-08-22

### Added
- **Trailing-twelve-month (TTM) figures.** `sec_edgar.extract_ttm` rolls a full fiscal year
  forward by the latest interim results — **last full fiscal year + current year-to-date −
  prior-year same year-to-date** — for revenue, net income, and operating cash flow. All periods
  are matched by their actual **dates** (not calendar-year labels), so companies with off-calendar
  fiscal years roll forward correctly. Attached to `Company.ttm` and surfaced as optional
  **TTM revenue / TTM net income** columns; `None` when the roll-forward components aren't all
  present. Annual-based strategy scoring is unchanged.
- **Group the Full list by Ticker.** Added a *Ticker* option to the Group-by dropdown, so a
  company's per-strategy rows collapse under one expandable group.

[0.45.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.45.0

## [0.44.0] - 2026-08-22

### Added
- **Group the Full list by any column.** A new **Group by** dropdown groups the table by a chosen
  column (Strategy, Pass, Last analyzed, any metric, …). Grouped rows collapse under a header
  showing the group value and member count; click a group's **▸ / ▾** to expand or collapse it.
  Groups appear in the current sort order and members sort within each group. The choice is
  remembered across refreshes (`sc_group`). Frontend-only.

[0.44.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.44.0

## [0.43.0] - 2026-08-22

### Added
- **SEC 10-Q quarterly fundamentals.** `extract_quarters` reduces the same EDGAR companyfacts
  document to the latest reported quarter — the quarter's own 3-month revenue, net income, and
  diluted EPS, plus the balance sheet as of quarter end — attached to `Company.quarters`
  (`QuarterFacts`). Surfaced as fresher, pickable columns **Qtr revenue / Qtr net income /
  Qtr EPS / Qtr current ratio** (`q_*` metrics) and a **"latest 10-Q &lt;date&gt;"** line in the
  deep-dive dialog. The annual-based strategy scoring is **unchanged** — this is a fresher read,
  not a new pass/fail input. (TTM roll-forward remains a documented follow-up.)

[0.43.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.43.0

## [0.42.3] - 2026-08-22

### Added
- **"Last analyzed" column on the Full list.** Shows the date of the most recent screening run
  that produced each row (from the stored run's timestamp), sortable like any other column and
  included in the CSV/JSON export. Rows not drawn from a stored run show "—". On by default;
  toggle it from the Columns menu. Frontend-only.

[0.42.3]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.42.3

## [0.42.2] - 2026-08-22

### Added
- **The active dashboard tab is remembered across page refreshes.** `showTab` persists the
  current tab (Full list / Jobs / History / API) to `localStorage` (`sc_tab`), and the page
  restores it on load — falling back to the Full-list landing when nothing (or an unrecognized
  value) is stored. Frontend-only.

[0.42.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.42.2

## [0.42.1] - 2026-08-22

### Security
- **Content-Security-Policy.** Every response now carries a hardened, same-origin CSP
  (`vercel.json`): `default-src 'self'` with external script/connect/frame/object/base-uri all
  blocked, `form-action 'self'`, `frame-ancestors 'none'`, and `img-src 'self' data: https:` so
  external company logos still load. `script-src`/`style-src` keep `'unsafe-inline'` — required
  for a static, inline-heavy SPA served from the CDN (no request passes through a server to mint
  a per-request nonce); no `'unsafe-eval'` is granted. Validated with Playwright (0 violations,
  0 page errors; dialogs, theme toggle, and the logo path all work). A nonce/hash-strict policy
  that drops `'unsafe-inline'` is tracked in `TODO.md` as a larger follow-up (edge middleware or
  a build-step externalization of all inline JS/CSS + inline `style=`/`onerror`).

[0.42.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.42.1

## [0.42.0] - 2026-08-22

### Added
- **`PRIVACY.md`** — documents that the app collects no personal data, that secrets are
  write-only (only key fingerprints and coarse IPs are logged, for rate limiting), and the
  obligations any future email-digest feature would carry.
- **`docs/SCALING.md`** — the 12-serverless-function Hobby cap, the other Hobby limits, and the
  concrete triggers that justify a Vercel Pro upgrade (plus cheaper alternatives to try first).
- **README "Why Stock-Comber"** section leading with the three differentiators: multi-lens
  value consensus, a backtested edge per pick, and the nightly "hidden gems" engine.
- **`docs/DATASOURCES.md`** ToS-review summary table (per-provider permitted use, redistribution
  limits, risk, and action) alongside the existing source-swap procedure.

### CI / tooling
- Added a **`pip-audit`** dependency-vulnerability job and a lenient, non-blocking **`mypy`**
  type-check job to `ci.yml`, a `[tool.mypy]` config, and **`.github/dependabot.yml`** for the
  pip and github-actions ecosystems. Both new CI jobs are informational for now (`|| true`),
  to be ratcheted stricter over time.

### Fixed (post-update review)
- **HTML reports now escape** ticker/company/strategy values, so names like "AT&T" or any
  stray angle bracket can't break the markup or inject content into the served report.
- **`write_reports` is now atomic** — it streams to a temp file and `os.replace`s it into place,
  so a mid-render error can't leave a truncated report or a `latest.*` out of sync.
- **Nightly backtest fetches use a per-thread `YahooSource`** (thread-local), since
  `requests.Session` isn't guaranteed thread-safe under the bounded worker pool.
- **`Screener.iter_results` resets `last_companies`** per call (matching `run()`), preventing
  stale-company accumulation across successive streaming calls.
- **Rate-limiter `remaining`** is consistent between the DB and in-memory-fallback paths (the
  in-flight request is no longer double-counted in the degraded path).

[0.42.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.42.0

## [0.41.0] - 2026-08-22

### Added
- **First-run welcome.** A dismissible note on the dashboard explains what Stock-Comber is
  (a research shortlist, not investment advice) and links to the About and Glossary pages;
  the dismissal is remembered per browser.
- **"Not investment advice" footers** added to the Settings and Thesis sub-pages (the two that
  lacked the caveat the other pages already carried).

### Accessibility
- **Modal focus management.** The analysis dialog, job dialog, and nav drawer now share a
  focus-trap layer: focus moves into the dialog on open, Tab / Shift-Tab cycle within it,
  **Escape** closes the top-most dialog, and focus returns to the element that opened it.
- **Keyboard tab navigation.** The view tabs (Full list / Jobs / History / API) respond to
  ←/→/↑/↓ and Home/End.
- Verified at 375px width — the dashboard and sub-pages have no horizontal body overflow.

[0.41.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.41.0

## [0.40.0] - 2026-08-22

### Performance
- **Concurrent nightly backtest fetches.** The nightly "hidden gems" backtest-edge step now
  fetches per-name price histories on a small bounded thread pool
  (`data.backtest_fetch_workers`, default 4, clamped 1–16; set 1 for the old serial behaviour),
  cutting wall-clock while staying polite to the free price endpoint. Per-ticker failures stay
  isolated.
- **Streaming report writers.** CSV and HTML reports are now written row-by-row straight to the
  file (`stream_csv` / `stream_html`); `write_reports` streams the dated file and copies it to
  `latest` at the filesystem level, so a large universe's report is never buffered in memory
  twice. The string renderers (`to_csv` / `to_html`) are unchanged wrappers over the streamers.
- **Bounded-memory screen streaming.** New `Screener.iter_results()` + a `retain_companies`
  flag let a caller stream per-ticker results without accumulating every `Company`/`AnnualFacts`
  (peak memory O(1) in universe size); `run()` keeps the buffered, ranked, persistence-friendly
  default. The CLI screen releases the retained companies right after persistence so report
  rendering doesn't hold them.

[0.40.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.40.0

## [0.39.0] - 2026-08-22

### Changed
- **In-process settings cache.** The settings singleton — read on nearly every request — is
  now served from a short-lived (default 30s, `STOCK_COMBER_SETTINGS_TTL`) in-process cache
  keyed by DSN, refreshed immediately on save and returned as a copy so callers can't corrupt
  it. Removes a database round-trip from the per-request hot path on warm serverless instances.
- **Pooled connection preference.** `resolve_dsn` now prefers `STOCK_COMBER_DATABASE_URL_POOLED`
  when set (point it at Neon's PgBouncer `-pooler` host) so per-invocation connects don't
  exhaust direct connections under burst; falls back to the existing variables unchanged.
- **Timezone-aware datetimes.** The last `datetime.utcnow()` (`screener.resolve_universe`) is
  now `datetime.now(timezone.utc)`.

### Performance
- Added a covering index `idx_results_run_ticker (run_id, ticker)` so the nightly cooldown
  lookup (`recently_screened`) and the Full-list DISTINCT ON stay off a full table scan.

### Observability
- `GET /api/runs?audit=1` now returns `rate_limit_degraded` — how often the rate limiter has
  fallen back to its in-memory floor — so a degrading database audit path is visible rather
  than looking like "no rate limiting."

[0.39.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.39.0

## [0.38.0] - 2026-08-22

### Security
- **In-memory fallback rate limiter.** The shared API guard (`apiguard.guard`) now falls back
  to a bounded, per-warm-instance sliding-window limiter when the database rate-limit count is
  unavailable, so a DB outage can no longer disable rate limiting entirely (it fails open only
  down to a floor, not off). A `degraded_count()` and a warning log make the degradation
  visible. Keyless (anonymous) requests are bucketed by client IP under every scope so one
  flood can't exhaust a shared bucket.
- **Strict ticker validation (SSRF/path-injection guard).** New `stock_comber/validation.py`
  is the single source of truth for valid symbols (`^[A-Z][A-Z0-9.\-]{0,9}$`) and is enforced
  in the screener and defensively in the Yahoo and SEC-EDGAR data sources *before* any ticker
  is interpolated into an upstream URL.
- **Security headers** are now sent for every response via `vercel.json`:
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, `Strict-Transport-Security`, and `Cross-Origin-Opener-Policy`.
- **Secret-leak regression test** (`tests/test_secrets_leak.py`) locks in that the settings
  endpoint returns only booleans for configured keys — never the Finnhub key, database URL,
  or export key.

### Added
- **"Not investment advice" disclaimer in the UI** — a persistent page footer on the dashboard
  and a disclaimer line at the foot of the stock-analysis dialog, so the caveat is visible at
  the point of decision (previously only in generated reports).

[0.38.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.38.0

## [0.37.2] - 2026-08-22

### Added
- **Project documentation for contributors and AI agents.** New `ARCHITECTURE.md` (codebase
  map, the 12-serverless-function cap, module index, theming/config/secrets contracts),
  `AGENTS.md` (the standing per-feature release process, hard constraints, and hard-won
  gotchas), `docs/DATASOURCES.md` (each upstream provider, its endpoints, terms-of-service
  posture, and the source-swap procedure), and a prioritized `TODO.md` distilled from a
  multi-perspective review (security, reliability, memory/scale, UX, product). Documentation
  only — no code or behavior changes.

[0.37.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.37.2

## [0.37.1] - 2026-08-22

### Added
- **Explanatory tooltips on every metric.** Hovering a results-table column header (now
  dotted-underlined) or any value cell shows a plain-language explanation of what the metric
  measures and why it matters as an indicator — for all columns (P/E, ROE, margins,
  liquidity, health score, backtest edge, etc.). The deep-dive detail modal's Key-metrics
  tiles get the same tooltips. Frontend-only.

[0.37.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.37.1

## [0.37.0] - 2026-08-22

### Added
- **Backtest edge in the nightly report.** The nightly "hidden gems" run now computes a
  per-name **backtest edge** — the mean, across value lenses, of each lens's edge (avg
  next-year return after a PASS minus after a fail) — and attaches it as `backtest_edge_pct`.
  It shows as a default **"Backtest edge %"** column in the dashboard's Full list and in the
  generated CSV/Markdown/HTML reports. On by default; toggle at **Settings → Analysis →
  "Show a backtest edge in the nightly report"** (`data.backtest_in_nightly`). One extra
  year-end price-history fetch per name; failures are skipped and never sink the run.
  (Existing saved column layouts are unchanged — reset columns to pick up the new default.)

[0.37.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.37.0

## [0.36.0] - 2026-08-22

### Added
- **Backtest folded into the analysis report (on by default).** A full deep-dive analysis
  now also runs a per-strategy backtest and shows it inline in the report — for each value
  lens: PASS-years, average next-year return after a PASS, the **edge** (avg return after a
  PASS minus after a fail, colored), and the PASS hit-rate — with a link to the full
  backtest. `GET /api/analyze` returns a new `backtest` object.
- **Settings toggle.** A new **Settings → Analysis → “Run a backtest in each analysis”**
  switch (`data.backtest_on_analysis`, default on) turns it off to skip the extra
  price-history fetch. The backtest never blocks or fails the analysis.

[0.36.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.36.0

## [0.35.1] - 2026-08-22

### Added
- **"Next runs" list in the schedule dialog.** The Scheduled report dialog now shows the
  next five fire times for the schedule you're editing (with a relative countdown for each),
  updating live as you change the frequency, interval, time, or days — so a sub-daily cadence
  is easy to sanity-check before saving. Client-side only (reuses the cron matcher).

[0.35.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.35.1

## [0.35.0] - 2026-08-22

### Added
- **Sub-daily schedules ("every N hours").** The Scheduled report dialog now has a
  **Frequency** control: *Once a day* (as before) or *Every N hours* (1/2/3/4/6/8/12h),
  which saves an `M */N * * DOW` cron. The hosted 5-minute heartbeat already honors full
  cron, so these fire down to 5-minute resolution.
- **Per-run universe rotation.** The nightly rotation seed now advances **every hour**
  (`schedule.rotation_tick`), so a shorter-than-daily schedule screens *fresh* names on each
  run instead of repeating the same day's pool. The "what the next run will screen" preview
  passes the next run's hour (`/api/universe?nightly=1&hour=…`) so it matches what will
  actually run. Combined with the 90-day cooldown, frequent runs now spread coverage rather
  than churn.

[0.35.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.35.0

## [0.34.1] - 2026-08-22

### Added
- **Cooldown status in the next-run preview.** The Scheduled report dialog's "what the next
  run will screen" preview now shows the active re-analysis cooldown — the window in days
  and how many recently-screened stocks are being held back (hover to see the tickers), with
  a reminder that manual analyses are exempt. `GET /api/universe?nightly=1` now returns
  `cooldown_days`, `on_cooldown_count`, and a capped `on_cooldown` sample.

[0.34.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.34.1

## [0.34.0] - 2026-08-22

### Added
- **Nightly re-analysis cooldown.** The scheduled "hidden gems" run now skips any stock it
  already screened within a configurable window (default **90 days**), so the same names
  aren't re-analyzed every few nights and coverage spreads to fresh candidates. Manual
  analyses are exempt — they can be run anytime and never count toward the cooldown.
  Backed by `PostgresStorage.recently_screened(days)` (scheduled runs only — `manual`/`queue`
  runs are excluded) and applied in `build_nightly`; the "what the next run will screen"
  preview reflects it too. New setting `universe.nightly.reanalyze_cooldown_days` (0 = off),
  editable under **Settings → nightly universe**. If every eligible name is on cooldown, the
  run falls back to the unfiltered pool rather than producing an empty report.

[0.34.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.34.0

## [0.33.2] - 2026-08-22

### Added
- **Theme toggle on every sub-page.** Each sub-page (Settings, About, Definitions,
  Strategies, Analytics, Backtest, Theses) now has a small floating theme button
  (top-right) that cycles **System → Light → Dark**, sharing the same saved preference as
  the dashboard — so you can switch themes from anywhere, not just the dashboard menu.

[0.33.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.33.2

## [0.33.1] - 2026-08-22

### Fixed
- **Activity banner really closes now.** The banner's `.banner { display:flex }` class rule
  was overriding the `[hidden]` attribute, so `hideBanner()` set `hidden` but the banner
  stayed visible — it never actually closed (and briefly showed on load). Added
  `.banner[hidden] { display:none }`, so tap-to-dismiss, the auto-hide, and dialog-open all
  hide it as intended.

### Changed
- **Theme preference carries across pages.** The dark/light choice from the dashboard menu
  now applies to every sub-page too (Settings, About, Definitions, Strategies, Analytics,
  Backtest, Theses): each honors the saved `data-theme` (applied before first paint) while
  "System" still follows the OS.

[0.33.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.33.1

## [0.33.0] - 2026-08-22

### Added
- **Dark / light theme toggle in the menu.** The ☰ menu now has a theme control that
  cycles **System → Light → Dark**; the choice is saved (localStorage) and applied before
  first paint on reload, so there's no flash. "System" follows the OS preference. Built on
  a `data-theme` override layered over the existing `prefers-color-scheme` palette.

### Fixed
- **Activity banner could look "stuck analyzing."** The top banner now always auto-hides
  (a 45s safety ceiling for in-flight work, 4.5s for queued toasts) and can be dismissed by
  tapping it, so a slow or hung request can never leave it showing indefinitely.

[0.33.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.33.0

## [0.32.3] - 2026-08-22

### Fixed
- **Analysis dialog close button hidden behind the banner.** The "Analyzing…" activity
  banner could overlap the ✕ that closes the stock-analysis dialog (notably on mobile).
  The banner is now dismissed the moment the dialog opens, and the dialog overlay renders
  above the banner (raised z-index) as a safety net, so the ✕ is always visible and
  tappable.

[0.32.3]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.32.3

## [0.32.2] - 2026-08-22

### Changed
- **Responsive History tab.** The History cards (Queued & running, Past runs, Searches)
  now flow into multiple columns on wide screens and collapse to a single column on
  narrow ones (`auto-fit` grid), so the tab uses the available width instead of three
  stacked full-width cards. No horizontal overflow at any width.

[0.32.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.32.2

## [0.32.1] - 2026-08-22

### Added
- **Rate-limit indicator on the API tab.** The API tab now shows a live indicator of the
  caller's current standing against the configured rate limit — used / limit, a colored
  usage meter (green → amber → red), requests remaining in the window, and the bucket
  scope. It also clearly reflects the "limiting off" and "no database" states.
  `GET /api/runs?audit=1` now returns a `rate_limit` block (limit / remaining / scope /
  retry_after) for the requesting client.

[0.32.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.32.1

## [0.32.0] - 2026-08-22

### Added
- **API access / audit log.** Every API request is now recorded in a new `api_audit`
  table — endpoint, method, resulting status, timestamp, and a **non-secret** client id
  (IP, or a short SHA-256 fingerprint of the API key; the key itself is never stored). A
  shared `stock_comber/apiguard.py` guard is wired into all 12 serverless handlers. View
  it on the dashboard's **API tab** (filterable by endpoint) or via
  `GET /api/runs?audit=1[&endpoint=…]`.
- **Configurable rate limit.** A per-client sliding-window rate limit (default 120
  requests / 60s, bucketed by IP) returns HTTP `429` when exceeded and logs the rejection.
  Tune it under **Settings → API access & rate limit**: toggle enforcement, set
  max-requests/window, and choose the bucket (`ip` / `key` / `global`). New config block
  `config.api` with validation.

### Notes
- Both features are backed by Postgres and are active only when a database is configured;
  the guard **fails open** (never blocks or errors the API) if logging/limiting hits a
  problem. No new serverless function — the audit view reuses `/api/runs` and the guard is
  a shared library, so the deployment stays within the 12-function cap.

[0.32.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.32.0

## [0.31.0] - 2026-08-21

### Added
- **Click a History row to open its full analysis.** In the History tab, rows in the
  **Queued & running** list (and single-ticker rows in **Searches**) are now clickable —
  clicking one opens that ticker's full deep-dive dialog (all six lenses + news &
  sentiment), fetched via `/api/analyze`. Multi-ticker searches and run summaries stay
  non-clickable.

### Changed
- **History list is more responsive.** Clickable rows get a clear hover/underline
  affordance and active (queued/processing) rows are dimmed, and the queue now
  auto-refreshes every ~12s while anything is still queued or running (stopping on its own
  once idle or when you leave the tab), so finished analyses appear without a manual refresh.

[0.31.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.31.0

## [0.30.3] - 2026-08-21

### Added
- **`avg_volume` in the generated nightly reports.** The CSV, Markdown and HTML report
  renderers now include an average-daily-volume column, so the nightly "hidden gems"
  report shows each pick's liquidity. (The JSON report already carried every metric.)

[0.30.3]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.30.3

## [0.30.2] - 2026-08-21

### Changed
- **`dollar_volume` is now a default results column.** The average-daily-dollar-volume
  liquidity metric joins `avg_volume` in the out-of-the-box results table. (Existing saved
  column layouts are unchanged; reset columns to pick up the new default.)

[0.30.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.30.2

## [0.30.1] - 2026-08-21

### Changed
- **`avg_volume` is now a default results column.** The average-daily-volume metric
  (added in 0.30.0) is shown out of the box in the results table, so liquidity is visible
  without opening the column picker. (Existing saved column layouts are unchanged; reset
  columns to pick up the new default.)

[0.30.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.30.1

## [0.30.0] - 2026-08-21

### Added
- **Volume / liquidity custom metrics.** Two new metrics are now computed for every
  screened company and available as custom-criterion targets:
  - `avg_volume` — average daily share volume (Finnhub's smoothed 3-month/10-day figure
    on enriched analyses, otherwise the latest day's volume from the price quote).
  - `dollar_volume` — average daily **dollar** volume (price × average share volume), the
    standard liquidity gauge. Screen out thinly-traded names with e.g.
    `dollar_volume >= 5000000`.
  Volume is parsed from the existing Yahoo price fetch (`Quote.volume`), so the live
  screen picks it up with no new API calls or serverless functions. Both metrics appear
  in the custom-criteria builders (dashboard, Settings, Thesis), the results-table column
  picker, and the glossary.

[0.30.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.30.0

## [0.29.2] - 2026-08-21

### Added
- **Screen the whole next-run pool at once.** The Scheduled report dialog's next-run
  preview now has a **"▶ Screen all N"** button that runs a live fundamentals screen
  over the entire (capped) nightly pool in one shot, using the nightly run's own
  configured strategies, and drops the results into the Jobs-tab results table. Tapping
  a single ticker still opens its full deep-dive. Capped at 40 tickers per batch to stay
  under the serverless time limit; no new function (still 12).

[0.29.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.29.2

## [0.29.1] - 2026-08-21

### Added
- **Deep-dive preview from the next-run list.** In the Scheduled report dialog's
  "what the next run will screen" preview, each ticker is now clickable — tapping one
  closes the dialog and opens that stock's full deep-dive analysis (all six lenses +
  news &amp; sentiment), so you can preview any candidate before the nightly run.

[0.29.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.29.1

## [0.29.0] - 2026-08-21

### Added
- **Preview what the next scheduled run will analyze.** The Scheduled report dialog
  now shows the capped, sector-diversified, rotated ticker pool the next nightly run
  will screen (for the next run's date), as a scrollable list of tickers with their
  sector on hover. Backed by `GET /api/universe?nightly=1[&ordinal=N]` (reuses the
  existing function — still 12), which runs the real nightly universe selection with
  no Finnhub calls.
- **"Why it didn't pass" in the expanded stock view.** The detail modal now leads
  with a dedicated section listing only the failed criteria, each with a plain
  explanation — the rule plus its actual-vs-target values (e.g. "Return on equity
  above 15.0% — actual 12 vs target 15"). The full criteria list still follows.

[0.29.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.29.0

## [0.28.0] - 2026-08-21

### Added
- **See & fine-tune the scheduled report's strategies.** The Scheduled report
  card/dialog (Jobs tab) now shows which strategies the nightly run uses; the
  overview summary lists them, and the schedule dialog renders them as chips that
  deep-link to their threshold editors in Settings (e.g. Buffett's min ROE,
  Graham's max P/E), plus an "edit all in Settings" link. Settings' strategy cards
  gained anchor ids (`#sec-graham`, `#sec-buffett`, …) for the deep links.

### Notes
- The full parameter editor already lived on the **Settings** page (☰ menu →
  Settings): the strategies checklist, every Graham/Buffett/Piotroski/Greenblatt/
  Lynch/Net-Net threshold, the nightly-universe knobs, and custom criteria — all
  saved to the database that drives the nightly screen. This change makes it
  discoverable and editable straight from the Scheduled report.

[0.28.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.28.0

## [0.27.1] - 2026-08-21

### Added
- **In-dialog job results preview.** Running a custom job with **▶ Run now** now
  shows a compact results preview inside the dialog (top rows by health, with a
  result/passing summary) instead of closing it, plus an **Open full results →**
  button that switches to the full table. Running a saved job from its card still
  goes straight to the table.

[0.27.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.27.1

## [0.27.0] - 2026-08-21

### Changed
- **Redesigned the Jobs tab.** It's now a clean overview of the three job types —
  Scheduled report, Custom jobs, Manual search — each a card with an action button.
  Job parameters have moved into **dialog windows**: **Configure** opens the schedule
  dialog, **+ Add job** opens the custom-job builder (criteria, tickers, templates,
  strategies), and **Analyze…** opens the manual-search dialog. Configured custom
  jobs are listed on the overview (name + summary) with **▶ Run / Edit / Delete**;
  Edit reopens a job in the dialog. The scheduled-report card shows a live summary
  (enabled · time · days).
- **Countdown shown on the Jobs tab too.** The next-scheduled-run countdown now
  appears on both the Full list and the Jobs tab.

[0.27.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.27.0

## [0.26.0] - 2026-08-21

### Added
- **Countdown to the next scheduled run.** The Full list tab shows a live countdown
  (updating every second) to the next hosted run, computed from the stored schedule
  — e.g. "Next scheduled run in 2h 14m 03s · Fri 06:30 UTC". Shows an off state when
  the nightly run is disabled, and refreshes when you save a new schedule.
- **Index filter on the Full list.** A dropdown (All indexes / Dow 30 / Nasdaq-100 /
  S&P 500, from `/api/universe`) filters the full list to a chosen index's
  constituents, composable with the text filter and "passing only". The status line
  shows "showing N of M".

[0.26.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.26.0

## [0.25.2] - 2026-08-21

### Changed
- **History tab surfaces queued & running jobs.** The analysis-queue card is now
  "Queued & running": rows are ordered running → queued → done/error with
  color-coded status badges (running/queued highlighted), and an active count
  shows in both the card header and the tab's status line.

[0.25.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.25.2

## [0.25.1] - 2026-08-21

### Changed
- **Saved jobs are now shown as a list on the Jobs tab.** Each configured job
  appears as a card with its name and a summary (tickers · rule count ·
  strategies) and its own **▶ Run / Load / Delete** buttons, replacing the
  saved-jobs dropdown. Saving or deleting updates the list in place.

[0.25.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.25.1

## [0.25.0] - 2026-08-21

### Added
- **Persistent sort.** The results table now remembers the column you sorted by and
  the direction across reloads (in `localStorage` under `sc_sort`), instead of
  resetting to Score ▼ every time.
- **Drag-to-reorder columns.** Drag any column header to reorder the table; the
  order is saved (`sc_cols`) and restored on reload. The Ticker column stays pinned
  first. `orderedCols()` now follows the saved column order rather than a fixed one.

[0.25.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.25.0

## [0.24.0] - 2026-08-21

### Added
- **API tab.** A new 🔌 API tab on the dashboard documents every endpoint (public
  reads and key-gated writes) with method, path, and a short description —
  replacing the small API list that used to live in the footer.

### Changed
- **The nightly schedule now honours the minute.** The hosted heartbeat runs every
  5 minutes (`*/5 * * * *`) and `schedule-gate` matches the configured minute to
  that slot, so a run set for 06:15 fires at 06:15 — not the top of the hour. Five
  minutes is GitHub Actions' finest schedule resolution; the time picker now steps
  in 5-minute increments and `HEARTBEAT_MINUTES` keeps the gate and the workflow in
  sync.
- **Removed the dashboard footer.** Navigation lives in the ☰ menu, the API
  reference in the new API tab, and the disclaimer/data-sources on the About page.

[0.24.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.24.0

## [0.23.0] - 2026-08-21

### Added
- **The stored schedule now drives the hosted nightly run.** The GitHub Actions
  workflow runs on an hourly heartbeat and a new `schedule-gate` step consults the
  schedule saved from the dashboard (Jobs tab → Scheduled report, in the database)
  to decide whether *this* hour should run. So changing the time/days in the UI and
  saving actually changes when the hosted run fires — no YAML edits. New
  `stock_comber/schedule.py` (`should_run_now`) + `stock-comber schedule-gate` CLI
  command. When no schedule is stored (or no `DATABASE_URL`), it defaults to
  06:xx UTC on weekdays — the previous behaviour. Because the heartbeat is hourly,
  the run fires at the top of the configured hour (minute is approximate). A manual
  `workflow_dispatch` always runs.
- `GET /api/settings` now returns `schedule_configured` so the dashboard shows the
  true hosted default when a schedule hasn't been saved yet.

### Changed
- **Header menu is now a slide-in side drawer.** The ☰ menu opens as a panel that
  slides in from the right with a backdrop (closable via ×, the backdrop, or Esc),
  instead of a popover that fell back to a bottom sheet on narrow screens.

[0.23.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.23.0

## [0.22.0] - 2026-08-21

### Added
- **Reorganized dashboard around three tabs.** The landing view is now a **📋 Full
  list** — every company screened across all stored runs, deduped to each name's
  most recent result, with a live ticker/name filter and a "passing only" toggle.
  A **⚙️ Jobs** tab gathers the different job types in one place: the nightly
  scheduled report (enable/disable + time-of-day + days), the custom-job builder
  with saved jobs, and manual search. A **🕓 History** tab shows the analysis
  queue plus every past run and search.
- **Run a saved job in one click.** Saved custom jobs now have a **▶ Run** button
  (alongside Load / Delete) that loads the job into the builder and runs it
  immediately.
- **Nightly schedule preference.** The Jobs tab persists `schedule.enabled` and a
  derived cron (time + days) to the settings blob (key-gated). The hosted nightly
  run is still triggered by GitHub Actions; this records the preferred cadence and
  drives the optional local scheduler.
- **Navigation menu.** A ☰ menu in the header links to Settings, About, Definition
  of terms, and Strategies (plus Analytics / Backtest / Theses).
- **New reference pages** (static, no serverless functions): `about.html`,
  `glossary.html` (searchable definition of terms), and `strategies.html` (the six
  value/quality lenses + custom criteria).
- **`GET /api/runs?results=all`** returns a deduped per-company roll-up
  (`{results: [...]}`) across all stored runs, backed by a new
  `storage.list_all_results()`. No new serverless function — still 12.

### Notes
- **Where results are saved:** a deep-dive analysis (`/api/analyze`) and the
  nightly run store full per-company results (`screen_runs` + `screen_results` +
  `raw_fundamentals`); quick screens (`/api/screen`, used by custom jobs and
  multi-ticker compares) log a search summary and enqueue tickers for the ~20-min
  worker, which then stores a full run. All persistence requires a database
  (`DATABASE_URL`).

[0.22.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.22.0

## [0.21.0] - 2026-08-21

### Added
- **Saved custom jobs.** Name a custom job (its `metric op value` criteria,
  tickers, and ticked strategies) and save it to the database from the **Custom
  jobs** tab — then Load it back or Delete it. Jobs persist server-side in the
  settings blob (read publicly via `GET /api/settings`; saving is key-gated via
  `POST /api/settings`), so they survive reloads and follow you across devices.
  A new top-level `jobs` config key holds the list, validated by
  `validate_config` (each job needs a unique non-empty name and, if present,
  valid criteria/strategies). No new serverless function — stays within the
  12-function limit.

[0.21.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.21.0

## [0.20.1] - 2026-08-20

### Added
- **Activity banner.** A sticky banner at the top of the dashboard shows while a
  job is **running** (custom job / manual screen / analysis — accent, with a
  spinner) and when tickers are **queued** for the ~20-min deep-analysis worker
  (amber, auto-dismissing). Respects reduced-motion.

[0.20.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.20.1

## [0.20.0] - 2026-08-20

### Changed
- **Dashboard organized into tabs.** The main card now has three tabs, each
  keeping its own results and status: **📅 Scheduled report** (the latest nightly
  "hidden gems" shortlist, auto-loaded, with a Refresh button), **⚙️ Custom jobs**
  (build your own `metric op value` rules over tickers or an index template and
  run them), and **🔍 Manual searches** (the ticker search + Analyze + strategy
  picker). Templates moved into Custom jobs; manual searches no longer mix in
  custom criteria.

[0.20.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.20.0

## [0.19.2] - 2026-08-20

### Added
- **Health-score chart on Analytics.** A new "Health-score grades" chart buckets
  the composite 0–100 health of passing companies into A–F bands (one count per
  ticker, colored green/amber/red), alongside the news-sentiment chart. Backed
  by a `health` aggregation added to `/api/analytics`
  (`PostgresStorage.analytics`).

[0.19.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.19.2

## [0.19.1] - 2026-08-20

### Changed
- **Nightly "hidden gems" are ranked by composite health.** Every screen result
  now carries a `health_score` (the blended 0–100 Value/Quality/Growth score),
  and the nightly run sorts by it by default (`output.sort_by: "health"`, unless
  you set another sort) — so the strongest businesses rise to the top of the
  shortlist instead of ties being broken arbitrarily. `health_score` is a
  selectable/default dashboard column and is exported with each run.
  `Screener.rank` attaches it; `scoring.overall_health` is the helper.

[0.19.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.19.1

## [0.19.0] - 2026-08-20

### Added
- **Investment thesis tracker** (`/thesis.html`, `/api/thesis`). Write *why*
  you'd buy a stock as measurable conditions (`metric op value`, reusing the
  custom-criteria vocabulary); Stock-Comber snapshots the metrics as a
  **baseline**, then the nightly job re-checks the live fundamentals and marks
  each thesis **intact / weakening / broken**, showing exactly which conditions
  failed and how far each metric has drifted from the baseline. New
  `stock_comber/thesis.py`, a `theses` table, the `check-theses` CLI (wired into
  the scheduled screen workflow), and a "🎯 track thesis" link in the Analyze
  modal. Writes are gated by `STOCK_COMBER_API_KEY`.

[0.19.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.19.0

## [0.18.1] - 2026-08-20

### Added
- **Company snapshot header** in the Analyze deep-dive — exchange, industry,
  market cap, IPO year, shares outstanding, and a website link (with logo when
  available), from Finnhub `profile2`. Exposed as `profile` on `/api/analyze`.

[0.18.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.18.1

## [0.18.0] - 2026-08-20

### Added
- **Composite 0–100 scores.** The Analyze deep-dive now shows **Value**,
  **Quality**, **Growth** and a blended **Overall** score (0–100, with an A–F
  grade and a meter), computed by transparent documented bands over the
  fundamentals we already calculate — no ML, no paid data. Missing metrics are
  skipped and weights renormalised, so a score only disappears when nothing in
  that category is measurable. New `stock_comber/scoring.py`
  (`compute_scores`); exposed as `scores` on `/api/analyze`.

[0.18.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.18.0

## [0.17.0] - 2026-08-20

### Added
- **Index universe templates.** Screen the **Dow 30**, **Nasdaq-100** or
  **S&P 500** as a universe, filtered by market-cap band, volume, **sector** and
  **industry** (GICS sub-industry). Constituents ship as dated snapshots
  (`stock_comber/indices.py`).
  - **Nightly job:** set `universe.index` (+ the new `universe.nightly.industries`
    filter) in Settings; the capped, sector-diversified, rotating engine then
    draws from that index for full coverage over successive nights.
  - **Dashboard:** a **Templates** menu loads a filtered top-by-market-cap slice
    into the search box for a live side-by-side compare.
  - New read-only `GET /api/universe` returns the templates and filtered slices;
    the industry filter is honoured by `universe._passes`.

[0.17.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.17.0

## [0.16.0] - 2026-08-20

### Added
- **Store your Finnhub key from the Settings page.** A write-only key field on
  `/settings.html` saves the Finnhub API key into your database (under
  `data.finnhub_api_key`), authorized by the existing `STOCK_COMBER_API_KEY`.
  The key is **never returned** by `GET /api/settings` (redacted), a blank field
  never wipes a stored key, and the status pill reflects env **or** DB. Only the
  Finnhub key is storable — `DATABASE_URL` and `STOCK_COMBER_API_KEY` stay
  environment-only by necessity/design.

### Changed
- **Live endpoints honor DB settings.** `GET /api/screen` and `GET /api/analyze`
  now merge database-stored settings over the file defaults (via
  `effective_config`), so tuned thresholds and a stored Finnhub key drive live
  screens and deep-dives — not just the nightly job.

[0.16.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.16.0

## [0.15.4] - 2026-08-20

### Changed
- **Settings page covers all six analysts.** The Settings page (`/settings.html`)
  now lets you select and tune every strategy — the four newer lenses
  (Piotroski F-Score, Greenblatt Magic Formula, Lynch/GARP, Graham Net-Net) gain
  editable threshold cards alongside Graham and Buffett, and the custom-criteria
  metric list picks up the newer metrics (ROA, return-on-capital, earnings
  yield, NCAV/share, earnings CAGR). Saves to the database and drives the
  nightly screen, same as before. (Keys stay read-only status pills — secrets
  are set as environment variables, never entered in the browser.)

[0.15.4]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.15.4

## [0.15.3] - 2026-08-20

### Added
- **Recent searches on focus.** Focusing the (empty) ticker field now drops down
  your recent searches — deduplicated, labelled by source (🕓 analyze / live) —
  so you can re-run a prior ticker or set with one tap. Backed by the existing
  `/api/runs` search log; typing switches straight back to ticker autocomplete.

[0.15.3]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.15.3

## [0.15.2] - 2026-08-20

### Changed
- **Analyze is now a search icon inside the ticker field.** The Analyze button
  moved onto the same row as the ticker box — embedded at its right edge as a 🔍
  icon (with an "Analyze" aria-label + tooltip) — so the search row is tighter,
  especially on mobile. It shows a ⏳ while a request is in flight. Behaviour is
  unchanged: one ticker → deep-dive, several → compare table.

[0.15.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.15.2

## [0.15.1] - 2026-08-20

### Changed
- **Mega-cap CIK override** hardens SEC resolution for ~45 of the most-searched
  tickers (AAPL, MSFT, XOM, BRK.B, …). It is consulted only when the ticker
  map's CIK yields no annual fundamentals — the same trigger as the browse-edgar
  fallback — and is tried first, so those names resolve instantly without a
  network lookup. Because it fires only on an already-failing ticker, a wrong
  entry can never regress a ticker that currently resolves correctly.

[0.15.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.15.1

## [0.15.0] - 2026-08-20

### Added
- **Backtest.** A new **Backtest** page (`/backtest.html`) and `GET /api/backtest`
  replay each value lens across a company's fiscal-year history: for every year
  it re-evaluates the lens using only the fundamentals known *then* plus that
  year-end price, and compares its PASS vs. FAIL years to the **following year's**
  return — surfacing which lens had an "edge" for that name. Includes a
  per-year diverging bar chart and a ranked lens-edge table. New
  `stock_comber.backtest` and `YahooSource.fetch_history` (year-end closes).
  Point-in-time SEC fundamentals + Yahoo prices, one name at a time, no
  dividends/costs — explicitly educational, not a track record or advice.

[0.15.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.15.0

## [0.14.0] - 2026-08-20

### Added
- **Signals & alerts.** The analyst checklists now roll up into one plain
  **BUY / WATCH / AVOID** signal per company (transparent, rules-based:
  how many of the six value lenses clear it and how strongly — `stock_comber.signals`).
  Shown as a banner in the Analyze deep-dive and surfaced as an **alerts list**
  on the History page (most recently analyzed tickers, actionable first). New
  read-only `GET /api/signals` and `PostgresStorage.recent_results`. Educational
  summary — explicitly not investment advice.

[0.14.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.14.0

## [0.13.0] - 2026-08-20

### Added
- **Similar companies (same sector).** The Analyze deep-dive now lists
  same-sector peers (Finnhub `/stock/peers`): tap a peer chip to deep-dive it,
  or "Compare all in a table" to screen the whole peer group side by side.
  Exposed as `peers` on `/api/analyze` and `FinnhubSource.fetch_peers`. Needs a
  `FINNHUB_API_KEY`; degrades to a note when absent.

[0.13.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.13.0

## [0.12.1] - 2026-08-20

### Fixed
- **Mobile responsiveness.** The Strategies (and Columns/Export) menus no longer
  open off-screen on phones — on narrow viewports they become a viewport-pinned
  bottom sheet that always fits. The dashboard search row stacks and its buttons
  span full width; every page (dashboard, History, Settings, Analytics) gets
  tighter phone padding, and the Analytics charts now scale by aspect ratio
  instead of squishing. No horizontal page overflow at 360px.

[0.12.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.12.1

## [0.12.0] - 2026-08-20

### Changed
- **One button.** "Screen" and "Analyze now" are folded into a single **Analyze**
  button that adapts to input: **one ticker** runs the full deep-dive (all six
  analysts + news & sentiment, in the detail modal); **several tickers** compare
  them in the sortable table using the ticked strategies; an **empty box**
  reloads the latest scheduled report. The Enter key follows the same logic.

[0.12.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.12.0

## [0.11.1] - 2026-08-20

### Changed
- **Strategy picker is now a multi-select dropdown.** The Both/Graham/Buffett
  segmented buttons are replaced by a **Strategies ▾** checkbox menu listing all
  six investor lenses; tick any combination for the Screen table. Selection is
  remembered in your browser (defaults to Graham + Buffett).
- **Clearer Screen vs. Analyze now.** "Screen live" is renamed **Screen** with a
  tooltip and inline help explaining the difference: **Screen** compares up to 10
  tickers at once as a sortable table using the ticked strategies; **Analyze now**
  deep-dives a single ticker across all six analysts plus news & sentiment. Both
  are kept — they serve different jobs (batch table vs. one-ticker deep-dive).

[0.11.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.11.1

## [0.11.0] - 2026-08-20

### Added
- **Four more investor strategies**, all computed from the existing free SEC
  fundamentals + price and fully adjustable in config:
  - **Piotroski F-Score** (`piotroski`) — 9-signal financial-strength score.
  - **Greenblatt Magic Formula** (`greenblatt`) — earnings yield + return on capital.
  - **Peter Lynch GARP** (`lynch`) — PEG ≤ 1 with healthy growth and sane debt.
  - **Graham Net-Net / NCAV** (`netnet`) — price below net current asset value.

  Available via `--strategy`, the `strategies:` config list, and `?strategy=` on
  `/api/screen`. The dashboard **Analyze now** button now scores a ticker against
  *all six* lenses at once, each with its own pass/fail breakdown. Adds supporting
  metrics (ROA, return on capital, earnings yield, NCAV/share, earnings CAGR, PEG,
  F-score), which are also usable in custom criteria.
- **Manual analyses are logged to History.** The "Analyze now" path now records a
  `searches` entry (source `analyze`) in addition to storing the run, so every
  search — live screens and manual analyses alike — appears on the History page.

[0.11.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.11.0

## [0.10.0] - 2026-08-20

### Fixed
- **Fundamentals now resolve for tickers SEC maps to the "wrong" CIK.** SEC's
  `company_tickers.json` can point a ticker (e.g. **XOM**) at a registrant that
  has no XBRL 10-K facts, which produced an empty 0/0 screen. `fetch_company`
  now falls back to EDGAR's company search to find the CIK that actually files
  10-Ks for the ticker and re-fetches its `companyfacts`, so Graham/Buffett get
  real data. Only consulted when the mapped CIK yields nothing (no extra calls
  otherwise).

### Changed
- **Honest analysis states.** A result with no evaluable criteria no longer
  mislabels itself "near miss." The manual-analysis modal now distinguishes
  **PASS** / **did not pass** (with "met N of M criteria") from **not analyzed**,
  and, when fundamentals couldn't be retrieved, explains why instead of showing
  a blank 0/0. News sentiment still shows regardless. Added HTML-escaping for
  error text and news headlines.

[0.10.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.10.0

## [0.9.1] - 2026-08-20

### Fixed
- **Autocomplete no longer blocks "Analyze now" / "Screen live".** The ticker
  suggestions used to open as an overlay that covered the wrapped action
  buttons, so a click landed on a suggestion instead of the button and the
  analysis never ran. The suggestion list now renders in-flow beneath the
  controls (never over the buttons), closes as soon as an action starts, and
  carries proper combobox ARIA state.

[0.9.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.9.1

## [0.9.0] - 2026-08-20

### Added
- **Manual analysis button.** An **"Analyze now"** button on the dashboard runs
  the full, deep analysis on the first entered ticker immediately — all
  strategies, Finnhub enrichment, and recent news scored into an A–F sentiment
  grade — instead of waiting for the ~20-min queue worker. Results open in a
  modal (per-strategy pass/fail, sentiment summary, and news headlines) and,
  when a database is configured, the analysis is stored as its own run so it
  also appears in History and Analytics. Backed by a new `GET /api/analyze?ticker=…`
  endpoint (`run_analysis`, reusing `analysis.analyze_ticker`).

[0.9.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.9.0

## [0.8.0] - 2026-08-20

### Added
- **Analytics view** (`/analytics.html`) — a charts page over the stored
  history: screened-vs-passing per run (grouped bars, oldest→newest), the
  most-frequently-passing tickers, passing results by sector, and the news
  sentiment-grade distribution. Backed by a new read-only `GET /api/analytics`
  endpoint (`PostgresStorage.analytics`) that aggregates runs, results, the
  universe catalog and stored sentiment. Self-contained inline SVG, theme-aware,
  no external dependencies; linked from the dashboard and History page. Charts
  use the validated categorical palette with direct value labels.

[0.8.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.8.0

## [0.7.1] - 2026-08-20

### Added
- **On-demand analysis** — `stock-comber analyze-queue --seed AAPL,MSFT` enqueues
  and immediately analyses specific tickers; the `analyze` workflow gains a
  matching `seed` dispatch input. Handy for deep-analysing a name now instead of
  waiting for the queue.

[0.7.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.7.1

## [0.7.0] - 2026-08-20

### Added
- **Analysis queue.** Tickers a user screens are enqueued (`analysis_queue`
  table, `POST /api/queue`) and processed out-of-band by a new
  `analyze` GitHub Actions worker (every ~20 min) that runs a full analysis:
  all strategies, Finnhub metric enrichment, and recent **news + a sentiment
  grade**. Each processed ticker is stored as its own run. CLI:
  `stock-comber analyze-queue`. Queue status shows on the History page.
- **News & sentiment.** `FinnhubSource.fetch_news` pulls recent company news
  (free tier); `stock_comber/sentiment.py` scores headlines with a transparent
  finance lexicon into an A–F **sentiment grade** (no paid API, no ML dep),
  stored alongside the analysis.
- `GET /api/queue` (view) / `POST /api/queue` (enqueue, capped + de-duplicated).

### Notes
- Dataroma-style superinvestor ownership is a useful gem signal but has no free
  official API (scraping is fragile / against ToS); SEC 13F filings are the
  free, official alternative and a candidate for a future enrichment.

[0.7.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.7.0

## [0.6.0] - 2026-08-20

### Added
- **Activity log** — a **History page** (`public/history.html`, linked from the
  dashboard) listing stored nightly runs (date, strategies, counts, per-run
  CSV/JSON export links) and the ad-hoc **search log**. Backed by
  `GET /api/runs`. Live `/api/screen` queries are now recorded to a new
  `searches` table (query + counts) when a database is configured.
- **Ticker autocomplete** — the dashboard search box suggests tickers as you
  type (prefix/substring over the SEC ticker list), with keyboard navigation.
  Backed by `GET /api/tickers?q=` (`match_tickers` in `sec_edgar.py`).

[0.6.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.6.0

## [0.5.2] - 2026-08-20

### Fixed
- **Finnhub free-tier rate limiting (429s).** The first nightly run made ~200
  Finnhub calls and hit the ~60/min limit. Now Finnhub's budget is reserved for
  universe enrichment: it's dropped to **last** in the price chain (Yahoo/Stooq
  cover prices), per-ticker metric enrichment is **off by default**
  (`data.finnhub_enrich_results`), `fetch_profile` is a **single call** (volume
  is opt-in), calls are **throttled** (`data.finnhub_min_interval`, ~1.1s), and a
  circuit breaker stops calling Finnhub after repeated 429s in a run. A nightly
  run now uses ~1 Finnhub call per enriched name, within the free tier.

[0.5.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.5.2

## [0.5.1] - 2026-08-20

### Added
- **Settings page** (`public/settings.html`) — edit strategies, Graham/Buffett
  thresholds, the nightly universe filters (cap, market-cap band, volume,
  sectors, countries, extra tickers), custom criteria, and output preferences in
  the browser. Shows **key/DB status** (configured or not) without ever
  revealing secrets. Saves to the database, or **Download as YAML** when no DB is
  configured. Linked from the dashboard.
- **Settings API** (`api/settings.py`) — `GET /api/settings` returns the
  effective config + key status; `POST /api/settings?key=…` validates and merges
  changes into the stored settings (requires `DATABASE_URL` +
  `STOCK_COMBER_API_KEY`).

[0.5.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.5.1

## [0.5.0] - 2026-08-20

### Added
- **Nightly "hidden gems" universe** (`stock_comber/universe.py`) — instead of
  re-screening every listed company, the nightly job now screens a **capped,
  sector-diversified, rotating** pick tuned to find under-followed long-term
  value. Configurable filters: market-cap band (default $100M–$20B), minimum
  average volume, sectors, excluded sectors, countries (international included),
  per-sector cap, and nightly count (default 75).
- **Curated seed universe** (`seed_universe.py`) of ~65 diversified small/mid-cap
  and international names, expanded over time by a **Finnhub-backed catalog**
  (`universe`, `screen_state` tables): each night enriches a rotating batch with
  market cap / sector / country / volume (`FinnhubSource.fetch_profile`).
- **DB-stored settings** (`settings` table) deep-merged over the file/default
  config via `effective_config`, so a settings page can drive runs.
- `stock-comber screen --nightly` and a `universe.mode: nightly` config switch;
  the scheduled workflow now runs `--nightly` by default (with a `nightly=false`
  dispatch option for the old SEC-list mode).

### Notes
- New tickers beyond the seed come from `universe.extra_tickers` (settings) and
  the accumulating catalog; broad auto-discovery of the full symbol list is a
  planned follow-up (kept off by default to respect Finnhub's free-tier limits).

[0.5.0]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.5.0

## [0.4.2] - 2026-08-20

### Fixed
- **Scheduled run failed / didn't persist.** The workflow passed `--verbose`
  after the `screen` subcommand (argparse rejected it) and installed the package
  without `psycopg`, so persistence would have no-op'd even with `DATABASE_URL`
  set. The `screen` subcommand now accepts `--verbose` in either position, a
  `storage` extra provides `psycopg`, and the workflow installs `.[storage]`.

[0.4.2]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.4.2

## [0.4.1] - 2026-08-20

### Added
- **Selectable columns** in the dashboard — a Columns menu to toggle any of the
  17 metrics (plus strategy/pass/score) on or off; the choice persists in
  `localStorage`. Sorting works on whichever columns are shown.
- **Export button** — download the current results as CSV or JSON (client-side),
  with a pointer to the key-protected `/api/export` endpoint for programmatic use.

[0.4.1]: https://github.com/Bobs-Dev-Attic/Stock-Comber/releases/tag/v0.4.1

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
