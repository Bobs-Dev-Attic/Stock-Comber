# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
