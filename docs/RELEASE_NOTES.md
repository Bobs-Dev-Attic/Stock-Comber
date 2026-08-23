# Release notes

## v0.54.0 — Polygon.io enrichment, rate-limited to 5 calls/min (2026-08-23)

Have a **Polygon.io** API key? You can now store it (Settings → API keys, or the
`POLYGON_API_KEY` env var) and the nightly "hidden gems" run will use it to figure
out each candidate's **sector, market-cap size, and volume** — exactly the signals
the new stratified pick needs to spread across sizes. If you have both a Polygon and
a Finnhub key, Polygon is used for this; a Polygon key on its own is enough, so you
don't need Finnhub just to classify names.

It respects Polygon's **free-tier limit of 5 calls per minute** automatically —
calls are spaced ~12 seconds apart and back off if the API starts rejecting them, so
you won't blow through your quota. (Turn off the extra per-name volume lookup with
`data.polygon_enrich_volume: false` to spend half as many calls.) As with the other
keys, it's stored write-only, sent only in an `Authorization` header, and never shown
back to the browser or written to logs.

## v0.53.0 — Nightly picks a random, well-spread set across the market (2026-08-23)

The scheduled screen now does what you'd expect a "hidden gems" hunt to do: each run picks a
**random set that spans different sectors, market-cap sizes, and volume sizes**, and picks a
**different set every run** (e.g. every 6 hours). Under the hood it's a *seeded* random sample — random
enough to vary each run, but reproducible so the dashboard's "next run" preview still matches what
actually runs. The candidate pool also grew from a ~67-name curated list to the **whole SEC ticker
list (thousands of names)**; names start out unclassified and get their sector / market cap / volume
filled in over time by the nightly enrichment, so the spread across sizes keeps improving. Note:
classifying by market cap and volume needs a Finnhub API key — without one, the sample still spans
sectors but not sizes. Tune the size bands under `universe.nightly` if you want different tiers.

## v0.52.0 — Custom jobs run on the schedule too (2026-08-23)

Your saved **custom jobs** now run automatically on your schedule — not just the nightly "hidden
gems" screen. Each scheduled fire runs every job you've saved (its tickers, strategies and criteria)
and records each as its own entry in History → Past runs, so you'll actually see them there. To make
that legible, Past runs gained a **Source** column that shows where each run came from: the job's name
for a custom job, "Scheduled" for the nightly screen, or "Manual" for an analysis you kicked off. If
you save a lot of jobs, remember they now all run on every scheduled fire (6× a day on the default
schedule) — trim any you don't need from the Jobs tab.

## v0.51.0 — Scheduled report actually runs on time (2026-08-23)

The nightly/scheduled screen was quietly missing its slot. GitHub only lets scheduled workflows fire
so often and, in practice, throttles them to every 20–40 minutes — so the run, which only triggered
if a heartbeat landed in the exact minute you configured, kept getting skipped. The workflow still
reported success (it just did nothing), which is why no new scheduled run showed up for days. Now the
gate is **catch-up**: the first check at or after your scheduled time runs the report, and it's
tracked so it still fires exactly once even when GitHub is late. Manual analyses no longer count as
"the schedule already ran." No change needed on your end — set your schedule in Jobs → Scheduled
report as before.

## v0.50.2 — History tab shows the latest activity (2026-08-23)

The History tab used to load once and then keep showing that first snapshot, so a run or job that
happened after you'd already glanced at History — like today's scheduled run or an analysis you just
queued — wouldn't appear until you pressed ↻ Refresh or reloaded the page. Now it refreshes itself
every time you open the tab, so today's activity is always there.

## v0.50.1 — Scroll the Full list sideways from the top (2026-08-23)

The Full list has a lot of columns, and until now the only way to scroll it left-and-right was the
scrollbar at the very bottom — out of reach unless you scrolled past every row. There's now a matching
horizontal scrollbar **above** the table too, so you can move sideways right from the top. It only
shows up when the columns are wider than the screen.

## v0.50.0 — Entry zone on the Full list (2026-08-23)

The **value entry zone** now appears as a column on the Full list, so you can scan a reference entry
range (low–high) across every screened company at once and sort or group by it. It's computed from
each row's own figures — the Graham fair value, discounted by a margin of safety and nudged by the
backtest edge — and is included when you export. It shows a dash when a company has no Graham fair
value. This Full-list version is a quick estimate; the complete zone, which also weighs news sentiment
and volume and shows exactly how each input moved the number, still lives in the per-company deep-dive.
As always: a reference, not a price target or investment advice. If the column doesn't show up, enable
it from the **Columns** menu (your saved column choices take precedence over the new default).

## v0.49.1 — Fix: grouping the Full list by Ticker (2026-08-23)

Grouping the Full list by **Ticker** was still showing a blank table. The list keeps one row per
company *per strategy*, so each ticker has several rows — and grouped rows were starting **collapsed**,
which hid them all. Groups now start **expanded**, so the data shows immediately; click a group's
header to collapse it. (An earlier fix only handled the case of one row per ticker, which isn't how
the list actually works.)

## v0.49.0 — Value entry zone (2026-08-23)

A full deep-dive analysis now shows a **value entry zone** — an illustrative reference range for
where a classic margin-of-safety buyer might start looking, not a price target and **not investment
advice**. It starts from the Graham fair value, takes a base discount (25%), and then adjusts that
discount using the signals you already see on the page: a stronger **backtest edge** trims it (more
historical confidence), positive **news sentiment** trims it a little, and unusually heavy **volume**
widens it (more uncertainty). You get a low–high range, a midpoint, a confidence badge, whether the
stock is currently below/within/above the zone, and — importantly — a line-by-line breakdown of every
input and how many percentage points it moved the discount, so nothing is a black box. If a company
has no Graham fair value (needs positive earnings and book value), the app says so instead of
inventing a number. Tune the base discount and bounds under `config.entry`.

## v0.48.0 — Nightly digest (RSS) (2026-08-22)

Stock-Comber now publishes a **nightly digest** you can subscribe to: an RSS feed of the value
stocks that passed the screens in the latest run, at **`/feed.xml`**. Point any feed reader at it (or
click "Nightly digest (RSS)" in the dashboard footer) and you'll get the fresh "hidden gems" each
night — ticker, company, strategy, score, and headline metrics — with the usual not-investment-advice
caveat. We deliberately chose RSS over email: it's a static, public feed with **no sign-up, no email
address to hand over, and nothing to unsubscribe from** — so it adds no privacy burden. If you self-host,
set `output.site_url` to your dashboard's address so the feed's links point at the right place.

## v0.47.0 — Backtests use the licensed feed too (2026-08-22)

Following v0.46.0 (which made Tiingo the primary source for live **prices**), the historical
**backtest** now also uses Tiingo when a key is configured — with dividend/split-**adjusted** closes,
so split events don't distort year-over-year returns. This covers all three places a backtest pulls
price history: the nightly "hidden gems" edge, a full deep-dive analysis, and the standalone backtest
endpoint. If you haven't set a Tiingo key, nothing changes — backtests keep using the free Yahoo
history. Tiingo now backs both quotes and backtests end-to-end.

## v0.46.0 — Licensed price provider (Tiingo) (2026-08-22)

Stock-Comber can now get its prices from **Tiingo**, a licensed market-data provider with a real
terms-of-service and reliability guarantee — a proper alternative to the free, unofficial Yahoo
endpoint that has always carried the highest terms-of-service risk. Add a **Tiingo API key** in
Settings (or set `TIINGO_API_KEY`), and it becomes the **primary** price source: screening quotes
come from the licensed feed, with the free Yahoo → Stooq chain kept as automatic fallbacks. If you
don't add a key, nothing changes — the free sources work exactly as before. The key is write-only
and never shown back, like the Finnhub key. This closes the "migrate price data to a licensed
provider" item that was documented as a plan in `docs/DATASOURCES.md`. (Prices route through Tiingo
now; the historical backtest still uses Yahoo — a scoped follow-up.)

## v0.45.2 — Fix: grouping the Full list by Ticker (2026-08-22)

Grouping the Full list by **Ticker** was showing a blank table. The Full list already keeps just
one row per company, so grouping by Ticker made a group for every single row — and because groups
start collapsed, every row was hidden behind its own toggle. Now a group that holds a single
company always shows that row (with no pointless expand arrow), so grouping by Ticker displays the
data as expected. Groups that actually hold several rows — grouping by Strategy or Passing, say —
still start collapsed and expand on click, exactly as before.

## v0.45.1 — Type-checking is now enforced (2026-08-22)

Internal quality: `mypy` runs as a **blocking** check in CI for the core `stock_comber` package,
which now type-checks clean. Previously it ran but couldn't fail the build; now a new type error
stops a bad change before it lands. Clearing the backlog also fixed a handful of latent
`None`-handling rough edges. No change to how the app behaves.

## v0.45.0 — Trailing-twelve-month figures (2026-08-22)

Building on the quarterly data, Stock-Comber now computes **trailing-twelve-month (TTM)** revenue
and net income — a rolling one-year figure that stays current between annual filings. It uses the
standard roll-forward (last full fiscal year, plus this year's results so far, minus the same
period last year) and matches everything by date, so it's correct even for companies whose fiscal
year doesn't end in December. Add the **TTM revenue / TTM net income** columns from the Columns
menu; they show a dash when a company hasn't filed enough interim data to compute them. Also: you
can now **group the Full list by Ticker**, which collapses a company's per-strategy rows together.

## v0.44.0 — Group the Full list (2026-08-22)

The Full list gets a **Group by** dropdown. Pick a column — Strategy, Pass/Fail, Last analyzed,
or any metric — and the table collapses into groups, each with a header showing the value and how
many names are in it. Click a group's arrow to expand it and see its rows, click again to
collapse. It's handy for questions like "how many names pass under Buffett vs. Graham?" or
"which were analyzed today?" Your grouping choice sticks across refreshes; choose **No grouping**
to go back to the flat list.

## v0.43.0 — Quarterly (10-Q) fundamentals (2026-08-22)

Annual filings can be nearly a year stale; this adds the **latest quarter** from each company's
SEC **10-Q**. Stock-Comber now parses the most recent quarter's revenue, net income, and EPS
(plus the quarter-end balance sheet) straight from the same EDGAR data it already uses — no new
key or provider. You get four new optional columns — **Qtr revenue, Qtr net income, Qtr EPS,
Qtr current ratio** — and the deep-dive dialog shows which quarter the figures are from. The
strategy pass/fail logic still runs on the audited annual numbers; the quarterly view is there
for a fresher read alongside it.

## v0.42.3 — "Last analyzed" column (2026-08-22)

The Full list now has a **Last analyzed** column showing when each name was last screened (the
date of the most recent stored run that produced it). It's on by default, sortable — so you can
sort newest- or oldest-analyzed first — and included in exports. Rows that don't come from a
stored run show a dash. Hide it any time from the Columns menu.

## v0.42.2 — Remember the open tab (2026-08-22)

Refreshing the dashboard used to always drop you back on the Full list. Now it keeps you on
whichever tab you were viewing — Full list, Jobs, History, or API — remembered per browser. A
first visit (or anything unexpected in storage) still lands on the Full list as before.

## v0.42.1 — Content-Security-Policy (2026-08-22)

The dashboard now ships a hardened **Content-Security-Policy**. Everything is locked to the
site's own origin — no third-party scripts, no data exfiltration to other hosts, no framing, no
plugin/base-tag tricks — while still allowing the external company logos the analysis dialog
shows. Inline scripts and styles remain allowed (`'unsafe-inline'`), which is unavoidable for a
static single-file app on a CDN; a fully nonce-strict policy would need an edge middleware or a
build step and is tracked as a future item. Validated against the live app with zero violations.

## v0.42.0 — Product & strategy (2026-08-22)

The review backlog's final P4 batch — mostly docs and tooling, no app-behavior change. New
**`PRIVACY.md`** spells out that the app collects no personal data and keeps secrets write-only.
New **`docs/SCALING.md`** records how the project stays inside Vercel's free 12-function cap and
exactly what would justify upgrading to Pro. The README opens with a **"Why Stock-Comber"**
section leading with the real differentiators — multi-lens value consensus, a backtested edge on
every pick, and the nightly hidden-gems engine — and **`docs/DATASOURCES.md`** gains a
per-provider terms-of-service review. On the tooling side, CI now runs **`pip-audit`** and a
lenient **`mypy`** (both non-blocking for now), and **Dependabot** keeps dependencies patched.

## v0.41.0 — UX & accessibility (2026-08-22)

The review backlog's P3 batch, all in the dashboard. New visitors get a **dismissible welcome
note** that says what the tool is — a research shortlist, not advice — and points to the About
and Glossary pages. The **dialogs are now keyboard-accessible**: opening one moves focus inside
it, Tab stays trapped within it, **Escape** closes it, and focus returns to wherever you were;
the view tabs also navigate with the arrow keys. The layout was checked at phone width (375px)
with no horizontal overflow, and the **"not investment advice" footer** now appears on the
Settings and Thesis pages too. No functional changes to screening.

## v0.40.0 — Memory & scale (2026-08-22)

The review backlog's P2 batch: making the nightly run faster and leaner as the universe grows.
The nightly **backtest fetches now run concurrently** on a small bounded pool
(`data.backtest_fetch_workers`, default 4) instead of one-at-a-time, so the report finishes
sooner without hammering the price source. **Reports stream to disk** row-by-row and copy the
dated file to `latest` at the filesystem level, so a big screen never holds the whole rendered
report in memory twice. And a new **streaming screen path** (`Screener.iter_results()` +
`retain_companies`) lets a memory-conscious caller process results without buffering every
company's fundamentals — the default `run()` is unchanged, and the CLI now frees the heavy
company objects as soon as a run is persisted. No behavior change to the reports themselves.

## v0.39.0 — Reliability & cost (2026-08-22)

The review backlog's P1 batch — quieter than a feature, but it makes the hosted app cheaper
and steadier under load. The **settings blob is now cached in-process** (default 30s), so the
dashboard's near-constant settings reads no longer hit the database on every request. On
Neon/Vercel you can point **`STOCK_COMBER_DATABASE_URL_POOLED`** at the PgBouncer `-pooler`
host and the app will prefer it, so bursts don't exhaust direct connections. A new **covering
index** keeps the nightly cooldown lookup off a full scan, the last naive `utcnow()` is now
timezone-aware, and **`/api/runs?audit=1` reports `rate_limit_degraded`** so a degrading
database path is visible instead of silently looking like "no rate limiting." No behavior
change for callers.

## v0.38.0 — Security hardening (2026-08-22)

The first batch of the review backlog's top-priority security items. **Rate limiting no
longer fully fails open:** if the database counter is unreachable, the API guard falls back to
a bounded in-memory limiter per instance, so an outage can't silently switch protection off —
and keyless requests are each limited by IP so one flood can't drain a shared bucket.
**Malformed tickers are rejected before any upstream fetch** through a single shared validator,
closing an SSRF/path-injection vector in the Yahoo and SEC data sources. Every response now
carries hardening **security headers** (nosniff, frame-deny, referrer-policy, HSTS, COOP). A
new test locks in that **no secret is ever returned to the browser**. And the **"not investment
advice" disclaimer** now appears in the dashboard footer and the analysis dialog, not just in
generated reports. No behavior changes for well-formed requests.

## v0.37.2 — Project docs for contributors and AI agents (2026-08-22)

Groundwork, not a feature: four documentation files that make the project faster and cheaper
to work on. **`ARCHITECTURE.md`** maps the codebase — the 12-serverless-function cap, what
each endpoint and library module does, and the theming/config/secrets contracts.
**`AGENTS.md`** captures the house rules: the one-feature-per-PR release process, the hard
constraints (never a 13th function, secrets stay write-only, no model IDs in artifacts), and
the gotchas learned the hard way. **`docs/DATASOURCES.md`** documents each upstream provider,
its terms-of-service posture, and how to swap it. **`TODO.md`** is a prioritized backlog from
a security/reliability/UX/product review. No code or behavior changed.

## v0.37.1 — Hover any metric to learn what it means (2026-08-22)

Every metric in the results table now explains itself. Hover a column header (they're
dotted-underlined to hint at it) or any value and you'll get a plain-language tooltip on
what the metric measures and why it matters — from P/E and ROE to liquidity, the health
score and the backtest edge. The same explanations appear on the Key-metrics tiles in a
stock's expanded breakdown. No more guessing what a column is telling you.

## v0.37.0 — Backtest edge in the nightly report (2026-08-22)

The nightly "hidden gems" report now carries a **Backtest edge %** for each stock — a single
number summarising how that name's value-lens PASS verdicts have historically played out
(the average, across lenses, of "next-year return after a PASS minus after a fail"). It
appears as a default column in the dashboard's Full list and in the downloadable CSV /
Markdown / HTML reports.

It's on by default; turn it off under **Settings → Analysis → "Show a backtest edge in the
nightly report"** if you'd rather keep the nightly run lean. Educational only (SEC
fundamentals + Yahoo year-end prices, not advice). If you've customised your columns, use
the column picker's reset to bring the new one in.

## v0.36.0 — Backtest built into every analysis (2026-08-22)

Every deep-dive analysis now includes a **backtest** right in the report. For each value
lens you'll see how its historical PASS verdicts actually played out: how many years it
passed, the average next-year return after a PASS, its **edge** (that return minus the
return after a fail), and the PASS hit-rate — plus a link to the full backtest page.

It's **on by default**; if you'd rather keep analyses fast, turn it off under **Settings →
Analysis → “Run a backtest in each analysis.”** The backtest is educational (SEC
fundamentals + Yahoo year-end prices, not advice) and never blocks the analysis.

## v0.35.1 — See your next scheduled runs (2026-08-22)

The Scheduled report dialog now lists the **next five run times** for the schedule you're
setting up, each with a countdown, and it updates as you tweak the frequency, interval,
time, or days. Handy for confirming a sub-daily cadence (or a weekday-only rule) does what
you expect before you save.

## v0.35.0 — Run the scheduled report more than once a day (2026-08-22)

The scheduled report can now run on a **sub-daily** cadence. In Jobs → Scheduled report →
Configure, the new **Frequency** control lets you choose *Once a day* (as before) or *Every
N hours* (1, 2, 3, 4, 6, 8 or 12 hours) at a chosen minute past the hour, on the days you
pick. Resolution is down to 5 minutes (the hosting platform's finest).

Crucially, each run now covers **fresh names**: the universe rotation advances every hour,
so running e.g. every 4 hours spreads coverage across the candidate pool through the day
instead of re-screening the same list — and the next-run preview reflects exactly what each
run will pick. Together with the 90-day re-analysis cooldown, frequent runs broaden coverage
rather than repeat work.

## v0.34.1 — See the cooldown in the next-run preview (2026-08-22)

The "what the next run will screen" preview (Jobs → Scheduled report → Configure) now spells
out the re-analysis cooldown: how long the window is (e.g. 90 days) and how many
recently-screened stocks are being held back this run — hover the count to see which tickers.
It also reminds you that manual analyses are exempt. When the cooldown is turned off, the
line simply doesn't appear.

## v0.34.0 — Nightly re-analysis cooldown (2026-08-22)

The scheduled nightly report no longer re-analyzes the same stock too often. Once a name
has been screened by a scheduled run, it's skipped by the nightly for a configurable window
(default **90 days**), so each night's picks spread across fresh candidates instead of
repeating recent ones. **Manual analyses are exempt** — you can deep-dive any ticker on
demand whenever you like, and those runs don't start (or count toward) the cooldown.

Tune it under **Settings → nightly universe → Re-analyze cooldown (days)** (set 0 to turn
it off). The "what the next run will screen" preview honors the cooldown too. And if every
eligible name happens to be on cooldown, the run still produces a report rather than coming
back empty.

## v0.33.2 — Theme toggle on every page (2026-08-22)

Every sub-page (Settings, About, Definitions, Strategies, Analytics, Backtest, Theses) now
has its own theme switch — a small button in the top-right corner that cycles **System →
Light → Dark** and shares your choice with the dashboard. Change your theme from wherever
you happen to be.

## v0.33.1 — Banner really closes + theme everywhere (2026-08-22)

Two fixes on top of v0.33.0:

- **The top banner now truly closes.** A CSS rule was keeping it on screen even after it
  was told to hide, so it looked stuck. That's fixed — tapping it, the auto-hide, and
  opening a dialog all dismiss it for real.
- **Your theme choice applies everywhere.** Picking Light or Dark from the dashboard menu
  now carries to every other page (Settings, About, Definitions, Strategies, Analytics,
  Backtest, Theses); "System" continues to follow your device.

## v0.33.0 — Theme toggle & un-stuck activity banner (2026-08-22)

**Pick your theme.** The ☰ menu now has a theme switch that cycles **System → Light →
Dark**. Your choice is remembered and applied instantly on the next visit (no flash), and
"System" just follows your device's setting.

**No more "stuck" banner.** The green activity banner at the top now always clears itself —
it auto-hides after at most 45 seconds even if a request is slow, and you can tap it to
dismiss it right away (the analysis keeps running in the background).

## v0.32.3 — Fix hidden close button on the analysis dialog (2026-08-22)

On phones, the green "Analyzing…" banner could sit on top of the **✕** that closes a
stock's analysis dialog, making it hard to dismiss. The banner now disappears as soon as
the dialog opens, and the dialog is layered above the banner regardless — so the close
button is always visible and tappable.

## v0.32.2 — Responsive History tab (2026-08-22)

The History tab now adapts to the window width: its cards (Queued & running, Past runs,
Searches) sit side by side on wide screens and stack into a single column on narrow ones,
instead of always being three full-width rows. Nothing overflows the page at any size.

## v0.32.1 — Rate-limit indicator on the API tab (2026-08-22)

The **API** tab now shows, at a glance, where you stand against the rate limit: a
usage meter (green → amber → red) with **used / limit**, how many requests are left in
the current window, and how requests are bucketed (by IP, key, or global). If the limit
is turned off, or no database is configured, the indicator says so plainly. It refreshes
whenever you refresh or filter the access log.

## v0.32.0 — API audit log & configurable rate limit (2026-08-22)

**See who's calling the API.** Every request to the JSON API is now recorded in an access
log — the endpoint, method, resulting status, time, and a **non-secret** client id (the
caller's IP, or a short fingerprint of the API key; the key itself is never stored).
Browse it on the dashboard's **API** tab, filter by endpoint, or fetch it with
`GET /api/runs?audit=1`.

**Throttle abusive callers.** A configurable per-client rate limit protects the API:
by default 120 requests per 60 seconds, bucketed by IP. Over-limit requests get an HTTP
`429` (and are logged as such). Adjust everything under **Settings → API access & rate
limit** — turn enforcement on/off, set the request count and window, and pick how clients
are bucketed (by IP, by API key, or globally).

Both features kick in only when a database is configured, and they're built to be safe:
the guard **fails open**, so a logging or rate-limit hiccup can never take the API down.
No new serverless function was added — the app stays within its hosting limits.

## v0.31.0 — Click History rows to open the analysis (2026-08-21)

The **History** tab is now interactive. Click any row in **Queued & running** (or a
single-ticker row under **Searches**) to open that stock's full analysis dialog — all six
value/quality lenses plus news & sentiment — without retyping the ticker. Rows highlight
and underline on hover so it's clear they're clickable; run summaries and multi-ticker
searches stay as read-only rows.

The queue is also more responsive: while any job is still queued or running, the list
auto-refreshes every ~12 seconds and dims in-flight rows, so a finished deep-dive shows up
on its own — the refresh stops once everything is done or you leave the tab.

## v0.30.3 — Average volume in the nightly reports (2026-08-21)

The generated nightly report now carries an **Avg volume** column in every human-readable
format (CSV, Markdown, HTML), so each pick's liquidity is right there in the report
alongside price, P/E and ROE. (The JSON report already included every metric.)

## v0.30.2 — Show dollar volume by default (2026-08-21)

The **$ volume / day** column now also appears in the results table by default, next to
**Avg volume** — so both liquidity gauges are visible at a glance. If you've customised
your columns, your layout is untouched; use the column picker's reset to adopt the new
default.

## v0.30.1 — Show average volume by default (2026-08-21)

The **Avg volume** column now appears in the results table out of the box, so you can see
each stock's liquidity at a glance without adding it from the column picker. If you've
previously customised your columns, your layout is untouched — use the column picker's
reset to adopt the new default.

## v0.30.0 — Volume / liquidity custom metrics (2026-08-21)

You can now screen on **how actively a stock trades**. Two new metrics are computed for
every company and can be used in any custom criterion:

- **Avg volume** (`avg_volume`) — average daily share volume. Uses the smoothed
  3-month/10-day figure on enriched (deep-dive) analyses, otherwise the latest day's
  volume.
- **$ volume / day** (`dollar_volume`) — average daily **dollar** volume (price ×
  average share volume). This is the standard liquidity measure: higher means you can buy
  or sell size without moving the price.

Build a rule like `dollar_volume >= 5000000` in the custom-strategy builder (dashboard,
Settings, or Thesis) to skip illiquid names, or add the columns from the results-table
picker to eyeball liquidity. Volume comes from the price fetch we already do, so it works
on the live screen with no new API calls — and there's no new serverless function
(still 12). See the **Liquidity** section of the glossary for details.

## v0.29.2 — Screen the whole next-run pool at once (2026-08-21)

The next-run preview (Jobs → Scheduled report → Configure) now has a **"▶ Screen all
N"** button. Instead of tapping tickers one at a time, click it once to run a live
fundamentals screen over the entire next-run pool — using the nightly run's own
configured strategies — and see every result in the Jobs-tab table. Tapping an
individual ticker still opens its full deep-dive (news &amp; sentiment). The batch is
capped at 40 tickers to stay within the serverless time limit, and adds no new function.

## v0.29.1 — Deep-dive preview from the next-run list (2026-08-21)

The next-run preview (Jobs → Scheduled report → Configure) now lets you **tap any
ticker to preview its full deep-dive analysis** — all six value/quality lenses plus
news &amp; sentiment — before the nightly run gets to it. Tapping a ticker closes the
schedule dialog and opens that stock's analysis.

## v0.29.0 — Preview the next run's picks & explain failures (2026-08-21)

- **See what the next scheduled analysis will screen.** Open **Jobs → Scheduled
  report → Configure** and there's now a "What the next run will screen" preview: the
  actual capped, diversified, rotating list of tickers the nightly run will analyze
  on its next date (hover any ticker for its sector). It runs the real nightly
  universe-selection logic, so it matches what the hosted run will do.
- **"Why it didn't pass."** When you open a stock's expanded breakdown, it now leads
  with a clear section listing just the criteria it failed and why — the rule plus
  the company's actual value against the target (e.g. "Net profit margin above 10% —
  actual 8 vs target 10"). The full pass/fail checklist still follows underneath.

## v0.28.0 — See & fine-tune scheduled-report strategies (2026-08-21)

**Where are the scheduled report's parameters?** They live on the **Settings** page
(☰ menu → Settings) — the strategies checklist plus every Graham / Buffett /
Piotroski / Greenblatt / Lynch / Net-Net threshold, the nightly-universe knobs, and
custom criteria, all saved to the database that drives the nightly run.

This release makes that reachable straight from the Scheduled report:

- The **Scheduled report** card now lists the strategies the nightly run uses.
- The schedule dialog shows them as clickable **chips** that jump to that strategy's
  thresholds in Settings — e.g. click **Buffett** to fine-tune its min ROE, or
  **Graham** for its max P/E — with an "edit all in Settings" link too.

Nothing about how thresholds are stored changed; this just surfaces and links the
existing editor.

## v0.27.1 — Job results preview in the dialog (2026-08-21)

Clicking **▶ Run now** in the custom-job dialog now shows a **preview of the
results right there** — a compact table of the top names (by health) with a
"X results · Y passing" summary — instead of closing the dialog. An **Open full
results →** button jumps to the complete table when you want it. Running a saved
job from its card on the overview still goes straight to the full table.

## v0.27.0 — Redesigned Jobs tab with dialogs (2026-08-21)

The **Jobs** tab is now a clean overview of the three job types, each a card with a
single action button — and the parameters open in a **dialog window** when you click:

- **📅 Scheduled report** shows a live summary (enabled · time · days) and a
  **Configure** button that opens the schedule dialog.
- **🧮 Custom jobs** lists your configured jobs (name + summary) with **▶ Run**,
  **Edit**, and **Delete** on each. **+ Add job** opens the builder dialog (criteria,
  tickers, index templates, strategies); **Edit** reopens a saved job in it.
- **🔍 Manual search** opens a dialog with the ticker box and strategy picker.

The **countdown to the next scheduled run** now appears on the Jobs tab as well as
the Full list, so you can see it wherever you are.

## v0.26.0 — Next-run countdown & index filter (2026-08-21)

- **Countdown to the next scheduled run.** The **Full list** tab now shows a live
  countdown to the next hosted run — e.g. *"Next scheduled run in 2h 14m 03s · Fri
  06:30 UTC"* — computed from your saved schedule and ticking every second. If the
  nightly run is turned off it says so, and it updates immediately when you change
  and save the schedule.
- **Filter the Full list by index.** A new dropdown lets you narrow the list to the
  constituents of an index — **Dow 30**, **Nasdaq-100**, or **S&P 500** — so you can
  see just those names. It combines with the ticker/name filter and "passing only",
  and the status line shows how many of the total are showing.

## v0.25.2 — Queued & running jobs on the History tab (2026-08-21)

The History tab's analysis-queue card is now **Queued & running**. Jobs are ordered
with anything **running** first, then **queued**, then finished/failed, each with a
color-coded status badge so active work stands out. An "active" count (running +
queued) appears in the card header and in the tab's status line.

## v0.25.1 — Saved jobs shown on the Jobs tab (2026-08-21)

The **Jobs** tab now lists your configured jobs instead of hiding them in a
dropdown. Each saved job is a card showing its name and a summary — tickers, how
many rules it has, and which strategies it runs — with its own **▶ Run**, **Load**,
and **Delete** buttons. Saving a new job or deleting one updates the list right
away.

## v0.25.0 — Remembered table sort & column order (2026-08-21)

The results table now keeps your view the way you left it:

- **Sort is remembered.** The column you sort by and its direction persist across
  reloads, rather than snapping back to Score (descending) each time.
- **Columns are draggable.** Drag a column header to reorder the table; the order is
  saved and restored on your next visit. Ticker stays pinned as the first column.

Both are stored per-browser (`localStorage`), alongside the existing remembered
column selection.

## v0.24.0 — Minute-precise schedule, API tab, no footer (2026-08-21)

- **The nightly schedule now honours the minute.** The hosted job runs every
  5 minutes and fires at the exact configured time — a run set for 06:15 UTC runs
  at 06:15, not the top of the hour. Five minutes is GitHub Actions' finest
  schedule resolution, so the time picker steps in 5-minute increments.
- **New 🔌 API tab** documenting every endpoint — public reads and key-gated
  writes — with method, path, and description. This replaces the API links that
  used to sit in the footer.
- **The footer is gone.** Navigation is in the ☰ side menu, the API reference is in
  the API tab, and the disclaimer and data sources live on the About page.

## v0.23.0 — Schedule drives the hosted run; side-drawer menu (2026-08-21)

**The nightly schedule you set in the app now actually controls the hosted run.**
Previously the Jobs-tab schedule only recorded a preference while the hosted run
fired on a fixed GitHub Actions cron. Now the workflow runs on an hourly heartbeat
and checks the schedule stored in the database each hour, running only on a
matching hour. Set the time and days in **Jobs → Scheduled report**, click Save,
and the change takes effect automatically — no code or YAML edits.

- When no schedule has been saved (or no database is connected), it falls back to
  the original default: 06:xx UTC on weekdays.
- Because the check runs hourly, the run fires at the top of the configured hour
  (the minute is approximate). A manual run from GitHub Actions always fires.
- Under the hood: a new `schedule-gate` CLI command and `should_run_now()` logic,
  plus a `schedule_configured` flag on `/api/settings` so the form shows the true
  hosted default before you've saved anything.

**Header menu is now a slide-in side drawer.** The ☰ menu opens a panel that slides
in from the right with a dimmed backdrop, closable with ×, the backdrop, or Esc —
replacing the popover that previously docked to the bottom of the screen on narrow
viewports.

## v0.22.0 — Dashboard reorganized: Full list, Jobs & History (2026-08-21)

The dashboard is now built around three tabs, with a navigation menu in the header.

- **📋 Full list (landing).** The page now opens on the complete list of every
  company Stock-Comber has screened, across all stored runs — deduped to each
  name's most recent result. Filter by ticker/name and toggle "passing only". When
  no database is connected, it falls back to the latest nightly report.
- **⚙️ Jobs.** One place to set up and run the different job types:
  - **Scheduled report** — enable/disable the nightly run and set its time &amp; days.
    (The hosted run is triggered by GitHub Actions; this saves your preferred
    cadence.)
  - **Custom job** — the `metric op value` builder, index templates, and your
    **saved jobs** with a new **▶ Run** button that loads and runs a saved job in
    one click (alongside Load / Delete / Save).
  - **Manual search** — one ticker for a full deep-dive, or several to compare.
- **🕓 History.** The analysis queue (jobs waiting for the ~20-min worker) plus
  every past run and search.
- **☰ Menu** in the header links to **Settings**, **About**, **Definition of
  terms**, and **Strategies** (plus Analytics / Backtest / Theses). Three new
  reference pages explain what the tool is, define every metric (searchable), and
  lay out the six value/quality strategies.

**On saving results:** deep-dive analyses and the nightly run are stored in full
(and now surfaced in the Full list &amp; History); quick screens are logged as a
summary and enqueue their tickers for a full analysis. All persistence requires a
database (`DATABASE_URL`).

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
