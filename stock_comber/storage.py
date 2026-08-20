"""Persistence for screen runs, results, and the raw retrieved data.

The default backend is Postgres (e.g. a free Neon database), activated when a
``DATABASE_URL`` / ``POSTGRES_URL`` connection string is available. Without one,
a no-op backend is used so the app runs unchanged. The backend is chosen by
:func:`get_storage`; both implement the same small interface:

    save_run(results, companies, meta) -> run_id | None
    latest_run() -> dict | None
    list_runs(limit) -> list[dict]
    get_run(run_id) -> dict | None
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .models import Company, ScreenResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS screen_runs (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    strategies    JSONB NOT NULL,
    ticker_count  INTEGER NOT NULL,
    passing_count INTEGER NOT NULL,
    meta          JSONB
);
CREATE TABLE IF NOT EXISTS screen_results (
    id         BIGSERIAL PRIMARY KEY,
    run_id     BIGINT NOT NULL REFERENCES screen_runs(id) ON DELETE CASCADE,
    ticker     TEXT NOT NULL,
    name       TEXT,
    cik        TEXT,
    strategy   TEXT NOT NULL,
    passed     BOOLEAN NOT NULL,
    score      DOUBLE PRECISION,
    max_score  DOUBLE PRECISION,
    score_pct  DOUBLE PRECISION,
    metrics    JSONB,
    criteria   JSONB,
    errors     JSONB
);
CREATE TABLE IF NOT EXISTS raw_fundamentals (
    id         BIGSERIAL PRIMARY KEY,
    run_id     BIGINT NOT NULL REFERENCES screen_runs(id) ON DELETE CASCADE,
    ticker     TEXT NOT NULL,
    cik        TEXT,
    annuals    JSONB,
    quote      JSONB,
    finnhub    JSONB
);
CREATE INDEX IF NOT EXISTS idx_results_run ON screen_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_ticker ON screen_results(ticker);
CREATE INDEX IF NOT EXISTS idx_runs_created ON screen_runs(created_at DESC);
CREATE TABLE IF NOT EXISTS settings (
    id         INTEGER PRIMARY KEY DEFAULT 1,
    data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT settings_singleton CHECK (id = 1)
);
CREATE TABLE IF NOT EXISTS universe (
    ticker      TEXT PRIMARY KEY,
    name        TEXT,
    exchange    TEXT,
    country     TEXT,
    sector      TEXT,
    market_cap  DOUBLE PRECISION,
    avg_volume  DOUBLE PRECISION,
    source      TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS screen_state (
    key   TEXT PRIMARY KEY,
    value JSONB NOT NULL
);
"""


def _result_row(run_id: Any, r: ScreenResult) -> tuple:
    """Flatten a ScreenResult into a screen_results insert tuple."""
    return (
        run_id, r.ticker, r.name, r.cik, r.strategy, r.passed,
        r.score, r.max_score, round(r.score_pct, 2),
        json.dumps(r.metrics, default=str),
        json.dumps([c.to_dict() for c in r.criteria], default=str),
        json.dumps(r.errors, default=str),
    )


def _raw_row(run_id: Any, company: Company) -> tuple:
    """Flatten a Company's retrieved data into a raw_fundamentals insert tuple."""
    annuals = [a.to_dict() for a in company.annuals]
    quote = company.quote.__dict__ if company.quote else None
    finnhub = getattr(company, "extra", None)
    return (
        run_id, company.ticker, company.cik,
        json.dumps(annuals, default=str),
        json.dumps(quote, default=str),
        json.dumps(finnhub, default=str) if finnhub else None,
    )


class NullStorage:
    """No-op backend used when no database is configured."""

    enabled = False

    def save_run(self, results, companies, meta=None) -> Optional[int]:
        return None

    def latest_run(self) -> Optional[dict]:
        return None

    def list_runs(self, limit: int = 20) -> list[dict]:
        return []

    def get_run(self, run_id: int) -> Optional[dict]:
        return None

    def get_settings(self) -> dict:
        return {}

    def save_settings(self, data: dict) -> None:
        return None

    def get_universe(self) -> list[dict]:
        return []

    def upsert_universe(self, rows: list[dict]) -> None:
        return None

    def get_state(self, key: str):
        return None

    def set_state(self, key: str, value) -> None:
        return None


class PostgresStorage:
    """Postgres-backed persistence (psycopg 3). Connections are per-operation,
    which suits serverless. Schema is created lazily on first write."""

    enabled = True

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._schema_ready = False

    def _connect(self):
        import psycopg  # lazy: only needed when a DB is actually configured
        return psycopg.connect(self.dsn, connect_timeout=10)

    def _ensure_schema(self, conn) -> None:
        if self._schema_ready:
            return
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
        self._schema_ready = True

    def save_run(self, results: list[ScreenResult],
                 companies: Optional[dict] = None,
                 meta: Optional[dict] = None) -> Optional[int]:
        companies = companies or {}
        strategies = sorted({r.strategy for r in results})
        tickers = {r.ticker for r in results}
        passing = sum(1 for r in results if r.passed)
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO screen_runs (strategies, ticker_count, "
                    "passing_count, meta) VALUES (%s, %s, %s, %s) RETURNING id",
                    (json.dumps(strategies), len(tickers), passing,
                     json.dumps(meta or {}, default=str)),
                )
                run_id = cur.fetchone()[0]
                if results:
                    cur.executemany(
                        "INSERT INTO screen_results (run_id, ticker, name, cik, "
                        "strategy, passed, score, max_score, score_pct, metrics, "
                        "criteria, errors) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        [_result_row(run_id, r) for r in results],
                    )
                if companies:
                    cur.executemany(
                        "INSERT INTO raw_fundamentals (run_id, ticker, cik, "
                        "annuals, quote, finnhub) VALUES (%s,%s,%s,%s,%s,%s)",
                        [_raw_row(run_id, c) for c in companies.values()],
                    )
            conn.commit()
        return run_id

    def _run_payload(self, conn, run_id: int) -> Optional[dict]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, strategies, ticker_count, passing_count "
                "FROM screen_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            run = {
                "id": row[0], "created_at": row[1].isoformat(),
                "strategies": row[2], "ticker_count": row[3],
                "passing_count": row[4],
            }
            cur.execute(
                "SELECT ticker, name, cik, strategy, passed, score, max_score, "
                "score_pct, metrics, criteria, errors FROM screen_results "
                "WHERE run_id = %s ORDER BY passed DESC, score_pct DESC", (run_id,))
            cols = ["ticker", "name", "cik", "strategy", "passed", "score",
                    "max_score", "score_pct", "metrics", "criteria", "errors"]
            run["results"] = [dict(zip(cols, r)) for r in cur.fetchall()]
        return run

    def latest_run(self) -> Optional[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM screen_runs ORDER BY created_at DESC LIMIT 1")
                row = cur.fetchone()
            if not row:
                return None
            return self._run_payload(conn, row[0])

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, created_at, strategies, ticker_count, passing_count "
                    "FROM screen_runs ORDER BY created_at DESC LIMIT %s", (limit,))
                return [
                    {"id": r[0], "created_at": r[1].isoformat(), "strategies": r[2],
                     "ticker_count": r[3], "passing_count": r[4]}
                    for r in cur.fetchall()
                ]

    def get_run(self, run_id: int) -> Optional[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            return self._run_payload(conn, run_id)

    # -- settings --------------------------------------------------------
    def get_settings(self) -> dict:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM settings WHERE id = 1")
                row = cur.fetchone()
        return row[0] if row and isinstance(row[0], dict) else {}

    def save_settings(self, data: dict) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO settings (id, data, updated_at) "
                    "VALUES (1, %s, now()) ON CONFLICT (id) DO UPDATE "
                    "SET data = EXCLUDED.data, updated_at = now()",
                    (json.dumps(data, default=str),))
            conn.commit()

    # -- universe catalog ------------------------------------------------
    def get_universe(self) -> list[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ticker, name, exchange, country, sector, "
                    "market_cap, avg_volume, source FROM universe")
                cols = ["ticker", "name", "exchange", "country", "sector",
                        "market_cap", "avg_volume", "source"]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def upsert_universe(self, rows: list[dict]) -> None:
        if not rows:
            return
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO universe (ticker, name, exchange, country, "
                    "sector, market_cap, avg_volume, source, updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now()) "
                    "ON CONFLICT (ticker) DO UPDATE SET "
                    "name=COALESCE(EXCLUDED.name, universe.name), "
                    "exchange=COALESCE(EXCLUDED.exchange, universe.exchange), "
                    "country=COALESCE(EXCLUDED.country, universe.country), "
                    "sector=COALESCE(EXCLUDED.sector, universe.sector), "
                    "market_cap=COALESCE(EXCLUDED.market_cap, universe.market_cap), "
                    "avg_volume=COALESCE(EXCLUDED.avg_volume, universe.avg_volume), "
                    "source=EXCLUDED.source, updated_at=now()",
                    [(r.get("ticker"), r.get("name"), r.get("exchange"),
                      r.get("country"), r.get("sector"), r.get("market_cap"),
                      r.get("avg_volume"), r.get("source", "seed"))
                     for r in rows if r.get("ticker")])
            conn.commit()

    # -- rotation / misc state ------------------------------------------
    def get_state(self, key: str):
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM screen_state WHERE key = %s", (key,))
                row = cur.fetchone()
        return row[0] if row else None

    def set_state(self, key: str, value) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO screen_state (key, value) VALUES (%s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (key, json.dumps(value, default=str)))
            conn.commit()


def resolve_dsn(config: Optional[dict] = None) -> Optional[str]:
    """Find a Postgres connection string from config or the environment."""
    if config:
        dsn = config.get("storage", {}).get("dsn")
        if dsn:
            return dsn
    for var in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL",
                "STOCK_COMBER_DATABASE_URL"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def get_storage(config: Optional[dict] = None):
    """Return a PostgresStorage if a DSN is configured, else NullStorage."""
    dsn = resolve_dsn(config)
    return PostgresStorage(dsn) if dsn else NullStorage()
