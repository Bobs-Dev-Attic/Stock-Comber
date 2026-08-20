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
CREATE TABLE IF NOT EXISTS searches (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    source        TEXT,                 -- 'live' | 'nightly' | 'cli'
    tickers       JSONB,
    strategies    JSONB,
    custom        JSONB,
    result_count  INTEGER,
    passing_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at DESC);
CREATE TABLE IF NOT EXISTS analysis_queue (
    ticker       TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending|processing|done|error
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_id       BIGINT,
    note         TEXT
);
CREATE INDEX IF NOT EXISTS idx_queue_status ON analysis_queue(status, requested_at);
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

    def log_search(self, source, tickers, strategies, custom,
                   result_count, passing_count) -> None:
        return None

    def list_searches(self, limit: int = 25) -> list[dict]:
        return []

    def enqueue(self, tickers) -> int:
        return 0

    def list_queue(self, limit: int = 50) -> list[dict]:
        return []

    def pop_pending(self, limit: int = 5) -> list[str]:
        return []

    def mark_queue(self, ticker, status, run_id=None, note=None) -> None:
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

    # -- search log ------------------------------------------------------
    def log_search(self, source, tickers, strategies, custom,
                   result_count, passing_count) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO searches (source, tickers, strategies, custom, "
                    "result_count, passing_count) VALUES (%s,%s,%s,%s,%s,%s)",
                    (source, json.dumps(tickers, default=str),
                     json.dumps(strategies, default=str),
                     json.dumps(custom, default=str) if custom else None,
                     result_count, passing_count))
            conn.commit()

    def list_searches(self, limit: int = 25) -> list[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, created_at, source, tickers, strategies, custom, "
                    "result_count, passing_count FROM searches "
                    "ORDER BY created_at DESC LIMIT %s", (limit,))
                cols = ["id", "created_at", "source", "tickers", "strategies",
                        "custom", "result_count", "passing_count"]
                out = []
                for r in cur.fetchall():
                    d = dict(zip(cols, r))
                    d["created_at"] = d["created_at"].isoformat()
                    out.append(d)
                return out

    # -- analysis queue --------------------------------------------------
    def enqueue(self, tickers) -> int:
        rows = [(t.upper(),) for t in tickers if t]
        if not rows:
            return 0
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO analysis_queue (ticker, status, requested_at, "
                    "updated_at) VALUES (%s, 'pending', now(), now()) "
                    "ON CONFLICT (ticker) DO UPDATE SET status='pending', "
                    "requested_at=now(), updated_at=now() "
                    "WHERE analysis_queue.status <> 'processing'", rows)
            conn.commit()
        return len(rows)

    def list_queue(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ticker, status, requested_at, updated_at, run_id, note "
                    "FROM analysis_queue ORDER BY requested_at DESC LIMIT %s",
                    (limit,))
                cols = ["ticker", "status", "requested_at", "updated_at",
                        "run_id", "note"]
                out = []
                for r in cur.fetchall():
                    d = dict(zip(cols, r))
                    d["requested_at"] = d["requested_at"].isoformat()
                    d["updated_at"] = d["updated_at"].isoformat()
                    out.append(d)
                return out

    def pop_pending(self, limit: int = 5) -> list[str]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE analysis_queue SET status='processing', updated_at=now() "
                    "WHERE ticker IN (SELECT ticker FROM analysis_queue "
                    "WHERE status='pending' ORDER BY requested_at LIMIT %s) "
                    "RETURNING ticker", (limit,))
                tickers = [r[0] for r in cur.fetchall()]
            conn.commit()
        return tickers

    def mark_queue(self, ticker, status, run_id=None, note=None) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE analysis_queue SET status=%s, run_id=%s, note=%s, "
                    "updated_at=now() WHERE ticker=%s",
                    (status, run_id, note, ticker.upper()))
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
