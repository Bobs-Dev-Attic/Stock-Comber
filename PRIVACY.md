# Privacy

_Last updated: 2026-08-22_

Stock-Comber is an educational, open-source stock-screening tool. This document
describes what the hosted app does and does not collect. It is written to be
honest about the current implementation, not as a legal contract.

## What we collect

**No personal accounts, no tracking, no advertising.** The app has no login, no
analytics scripts, no third-party trackers, and no cookies used for tracking.

The only data the app records server-side (and only when a database is
configured) is operational:

- **Screening results** — the public company fundamentals and computed scores
  that the tool produces. This is public market data, not personal data.
- **An API access/audit log** — for each API request: the endpoint, HTTP method,
  resulting status, a timestamp, and a **non-secret client identifier**. The
  client identifier is either a coarse client IP (used only to rate-limit abuse)
  or a **one-way SHA-256 fingerprint** of an API key — never the key itself. This
  log exists to enforce rate limits and to give the operator visibility into API
  usage. See `stock_comber/apiguard.py` and `stock_comber/storage.py`.

**Secrets are write-only.** API keys and the database URL are read from the
environment (or stored write-only in the settings blob) and are **never returned
to the browser** — the settings endpoint reports only booleans for what is
configured. A regression test (`tests/test_secrets_leak.py`) enforces this.

## What we do not collect

- No names, emails, addresses, or other personal identifiers.
- No behavioural profiles, no cross-site tracking, no sale of data.
- No storage of raw API keys.

## Third-party data sources

The app fetches public data from SEC EDGAR, Yahoo Finance, Stooq, and (optionally)
Finnhub. Those requests carry only a ticker symbol and a descriptive
`User-Agent`; they do not carry any information about the person using the app.
See [`docs/DATASOURCES.md`](docs/DATASOURCES.md) for each provider.

## Self-hosting

Because the audit log and results live in a database **you** configure, a
self-hosted deployment keeps its data entirely under the operator's control. Run
without a `DATABASE_URL` and nothing is persisted at all.

## Nightly digest (RSS)

Stock-Comber publishes a nightly digest of the passing "hidden gems" as a static
**RSS feed** at `/feed.xml`. This collects **no personal data**: there is no
sign-up, no email address, no subscriber list, and nothing to unsubscribe from —
your reader simply fetches a public file. It carries only public screening
results (tickers, company names, metrics), the same data already shown on the
dashboard.

## Future features

If an opt-in feature that collects personal data is ever added (for example an
**email** digest, which — unlike the RSS feed above — would require storing an
address), this document will be updated first to describe exactly what is
collected, how to unsubscribe, and the applicable obligations (e.g. CAN-SPAM /
GDPR). No such feature exists today.

## Contact

Questions: open an issue on the
[GitHub repository](https://github.com/Bobs-Dev-Attic/Stock-Comber).

> Reminder: Stock-Comber is an educational tool, **not investment advice**.
