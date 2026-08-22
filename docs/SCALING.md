# Scaling & the Vercel Hobby → Pro decision

Stock-Comber is engineered to run on **Vercel's free Hobby tier**. The binding
constraint there is the **12 Serverless Functions per project** limit, and the app
sits exactly at 12 `api/*.py` functions (see `ARCHITECTURE.md` → "The 12-function
cap"). This document records how we stay under it, and the concrete triggers that
would justify upgrading to **Vercel Pro** (~$20/mo).

## How we stay at 12 functions

New API surface has been added without new functions by:

- **Reusing an endpoint with a query parameter** — e.g. the audit log lives at
  `GET /api/runs?audit=1`, and nightly previews at `GET /api/universe?nightly=1`.
- **Adding library modules under `stock_comber/`** rather than endpoints — e.g.
  `apiguard.py` (rate limit + audit) and `validation.py` (ticker validation) are
  imported by the handlers, not deployed as their own functions.

**Rule:** do not add a 13th `api/*.py`. If a feature truly needs a new endpoint,
that is the signal to evaluate the upgrade below — not to quietly break the cap.

## Other Hobby-tier limits to watch

| Limit | Hobby | Notes |
|---|---|---|
| Serverless Functions / project | **12** | The binding constraint today (we're at 12). |
| Function duration | up to 60 s | `screen`/`analyze` are set to 60 s; heavy runs must stay within it. |
| Function memory | 1024 MB used | `screen`/`analyze` request 1024 MB; the P2 streaming work keeps peak memory down. |
| Deployment / bandwidth | Fair-use | Fine for a personal dashboard; a public launch could change this. |
| Cron jobs | Limited | We drive scheduling from GitHub Actions (`schedule.py`), not Vercel Cron, so this isn't a blocker. |

## Triggers to upgrade to Pro

Upgrade when **any** of these becomes true — not preemptively:

1. **A 13th function is genuinely needed.** A feature that can't be folded into an
   existing endpoint or a library module. Pro raises the function cap.
2. **Sustained public traffic** that brushes Hobby's fair-use bandwidth, or that
   needs the rate limiter's precise (DB-backed) path to hold under concurrency
   beyond a single warm instance.
3. **Longer / heavier jobs** — a materially larger nightly universe that needs more
   than 60 s or more memory per invocation.
4. **Team collaboration / analytics** — Pro's built-in analytics and preview
   protection become worth it once more than one person maintains the deploy.

When upgrading, revisit: raising the function cap may let `apiguard.py` /
`validation.py` stay as libraries (no need to change them), but the audit/preview
query-param endpoints _could_ be split into dedicated functions for clarity.

## Cost-control alternatives (before paying)

- **Upstash Redis (free tier)** for a shared, cross-instance rate limiter and a
  config/response cache — without adding a serverless function.
- **Neon pooled endpoint** (`STOCK_COMBER_DATABASE_URL_POOLED`) so bursts don't
  exhaust direct Postgres connections (already supported — see `resolve_dsn`).
- **Lazy imports** in handlers to keep cold starts small.

The current architecture already applies the latter two; Upstash is the natural
next step if abuse or scale demands a real shared limiter before a Pro upgrade.
