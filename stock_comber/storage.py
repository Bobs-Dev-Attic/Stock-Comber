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

import copy
import json
import logging
import os
import time
from typing import Any, Optional

from .models import Company, ScreenResult

log = logging.getLogger("stock_comber.storage")

# In-process cache of the settings singleton, keyed by DSN. The settings blob is
# read on nearly every request (effective_config), so a short TTL removes that
# DB round-trip from the hot path on a warm serverless instance. Writes in the
# same process refresh it immediately; cross-instance staleness is bounded by
# the TTL. Set STOCK_COMBER_SETTINGS_TTL=0 to disable.
_SETTINGS_CACHE: dict[str, "tuple[float, dict]"] = {}
try:
    _SETTINGS_TTL = float(os.environ.get("STOCK_COMBER_SETTINGS_TTL", "30"))
except (TypeError, ValueError):
    _SETTINGS_TTL = 30.0

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
-- Covering index for the nightly cooldown lookup (recently_screened) and the
-- Full-list DISTINCT ON (ticker per recent run): keeps them off a full scan.
CREATE INDEX IF NOT EXISTS idx_results_run_ticker ON screen_results(run_id, ticker);
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
CREATE TABLE IF NOT EXISTS theses (
    id           BIGSERIAL PRIMARY KEY,
    ticker       TEXT NOT NULL,
    note         TEXT,                 -- why you bought (free text)
    conditions   JSONB NOT NULL,       -- [{metric, op, value}]
    baseline     JSONB,                -- metric snapshot at creation
    status       TEXT NOT NULL DEFAULT 'intact',  -- intact|weakening|broken
    last_checks  JSONB,                -- per-condition results from last check
    current      JSONB,                -- metric snapshot at last check
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_theses_ticker ON theses(ticker);
CREATE INDEX IF NOT EXISTS idx_theses_created ON theses(created_at DESC);
CREATE TABLE IF NOT EXISTS api_audit (
    id        BIGSERIAL PRIMARY KEY,
    ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    endpoint  TEXT NOT NULL,        -- e.g. 'screen', 'settings'
    method    TEXT NOT NULL,        -- GET | POST
    status    INTEGER NOT NULL,     -- HTTP-ish status recorded for the call
    scope     TEXT,                 -- rate-limit bucket: ip | key | global
    client    TEXT,                 -- non-secret client id (ip or key fingerprint)
    note      TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON api_audit(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_client ON api_audit(client, ts DESC);
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

    def last_scheduled_run_at(self):
        return None

    def list_runs(self, limit: int = 20) -> list[dict]:
        return []

    def get_run(self, run_id: int) -> Optional[dict]:
        return None

    def recent_results(self, limit_runs: int = 30) -> list[dict]:
        return []

    def list_all_results(self, limit: int = 500) -> list[dict]:
        return []

    def tickers_with_strategy(self, strategy: str, limit: int = 500) -> list[str]:
        return []

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

    def analytics(self, run_limit: int = 30) -> dict:
        return {"runs": [], "top_tickers": [], "sectors": [], "sentiment": [],
                "health": []}

    # -- theses (no-op) --
    def create_thesis(self, ticker, note, conditions, baseline) -> Optional[int]:
        return None

    def list_theses(self, limit: int = 100) -> list[dict]:
        return []

    def get_thesis(self, thesis_id: int) -> Optional[dict]:
        return None

    def update_thesis_check(self, thesis_id, status, current, checks) -> None:
        return None

    def delete_thesis(self, thesis_id: int) -> bool:
        return False

    # -- API audit / rate limit (no-op) --
    def record_api_call(self, endpoint, method, status, scope=None,
                        client=None, note=None) -> None:
        return None

    def list_api_audit(self, limit: int = 100, endpoint=None) -> list[dict]:
        return []

    def count_api_calls(self, client: str, window_seconds: int) -> int:
        return 0

    def recently_screened(self, days: int) -> set:
        return set()


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
                    "SELECT id, created_at, strategies, ticker_count, passing_count, meta "
                    "FROM screen_runs ORDER BY created_at DESC LIMIT %s", (limit,))
                return [
                    {"id": r[0], "created_at": r[1].isoformat(), "strategies": r[2],
                     "ticker_count": r[3], "passing_count": r[4], "meta": r[5] or {}}
                    for r in cur.fetchall()
                ]

    def last_scheduled_run_at(self):
        """Timestamp (tz-aware) of the most recent *scheduled* run, or None.

        Scheduled runs are tagged ``meta.source = 'schedule'`` (see cli.cmd_screen),
        so a manual analysis doesn't count as the schedule having fired — the
        catch-up gate uses this to run each slot exactly once."""
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT max(created_at) FROM screen_runs "
                    "WHERE meta->>'source' = 'schedule'")
                row = cur.fetchone()
                return row[0] if row else None

    def get_run(self, run_id: int) -> Optional[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            return self._run_payload(conn, run_id)

    def list_all_results(self, limit: int = 500) -> list[dict]:
        """Every company across all stored runs, deduped to the latest result
        per (ticker, strategy). Full per-company payload (metrics, criteria) so
        the dashboard's "Full list" can render and sort it like any screen.
        Ordered most-recent-run first, then by score."""
        cols = ["ticker", "name", "cik", "strategy", "passed", "score",
                "max_score", "score_pct", "metrics", "criteria", "errors",
                "run_id", "created_at"]
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ("
                    "  SELECT DISTINCT ON (sr.ticker, sr.strategy) "
                    "    sr.ticker, sr.name, sr.cik, sr.strategy, sr.passed, "
                    "    sr.score, sr.max_score, sr.score_pct, sr.metrics, "
                    "    sr.criteria, sr.errors, sr.run_id, r.created_at "
                    "  FROM screen_results sr "
                    "  JOIN screen_runs r ON r.id = sr.run_id "
                    "  ORDER BY sr.ticker, sr.strategy, r.created_at DESC"
                    ") x ORDER BY x.created_at DESC, x.score_pct DESC NULLS LAST "
                    "LIMIT %s", (limit,))
                out = []
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    if hasattr(d["created_at"], "isoformat"):
                        d["created_at"] = d["created_at"].isoformat()
                    out.append(d)
                return out

    def tickers_with_strategy(self, strategy: str, limit: int = 500) -> list[str]:
        """Distinct tickers that have at least one stored result under ``strategy``
        (e.g. ``custom``), most-recent first — used to re-analyse them on demand."""
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sr.ticker FROM screen_results sr "
                    "JOIN screen_runs r ON r.id = sr.run_id "
                    "WHERE sr.strategy = %s "
                    "GROUP BY sr.ticker "
                    "ORDER BY MAX(r.created_at) DESC "
                    "LIMIT %s", (strategy, limit))
                return [row[0] for row in cur.fetchall()]

    def recent_results(self, limit_runs: int = 30) -> list[dict]:
        """Per-strategy results from the most recent ``limit_runs`` runs.

        Rows: {run_id, created_at, ticker, name, strategy, passed, score_pct,
        max_score}. Ordered newest-run first. Used to compute per-ticker signals.
        """
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sr.run_id, r.created_at, sr.ticker, sr.name, "
                    "sr.strategy, sr.passed, sr.score_pct, sr.max_score "
                    "FROM screen_results sr JOIN screen_runs r ON r.id = sr.run_id "
                    "WHERE sr.run_id IN ("
                    "  SELECT id FROM screen_runs ORDER BY created_at DESC LIMIT %s) "
                    "ORDER BY r.created_at DESC, sr.ticker ASC",
                    (limit_runs,))
                cols = ["run_id", "created_at", "ticker", "name", "strategy",
                        "passed", "score_pct", "max_score"]
                out = []
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    d["created_at"] = d["created_at"].isoformat()
                    out.append(d)
                return out

    # -- analytics -------------------------------------------------------
    def analytics(self, run_limit: int = 30) -> dict:
        """Aggregations for the analytics dashboard.

        All read-only, non-sensitive counts:
          - runs: screened vs. passing per run over time (oldest→newest)
          - top_tickers: tickers that pass most often across runs
          - sectors: passing results grouped by universe sector
          - sentiment: distribution of stored news-sentiment grades
        """
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                # Runs over time (fetch newest N, then present oldest→newest).
                cur.execute(
                    "SELECT id, created_at, ticker_count, passing_count "
                    "FROM screen_runs ORDER BY created_at DESC LIMIT %s",
                    (run_limit,))
                runs = [
                    {"id": r[0], "created_at": r[1].isoformat(),
                     "ticker_count": r[2], "passing_count": r[3]}
                    for r in cur.fetchall()
                ]
                runs.reverse()

                # Tickers that pass most often (distinct runs they passed in).
                cur.execute(
                    "SELECT ticker, MAX(name) AS name, "
                    "COUNT(DISTINCT run_id) AS passes "
                    "FROM screen_results WHERE passed "
                    "GROUP BY ticker ORDER BY passes DESC, ticker ASC LIMIT 15")
                top_tickers = [
                    {"ticker": r[0], "name": r[1], "passes": r[2]}
                    for r in cur.fetchall()
                ]

                # Passing results by sector (join the universe catalog).
                cur.execute(
                    "SELECT COALESCE(NULLIF(u.sector, ''), 'Unknown') AS sector, "
                    "COUNT(*) AS n FROM screen_results sr "
                    "LEFT JOIN universe u ON u.ticker = sr.ticker "
                    "WHERE sr.passed GROUP BY sector ORDER BY n DESC, sector ASC "
                    "LIMIT 12")
                sectors = [{"sector": r[0], "count": r[1]} for r in cur.fetchall()]

                # News-sentiment grade distribution from stored analyses.
                cur.execute(
                    "SELECT finnhub->'sentiment'->>'grade' AS grade, COUNT(*) AS n "
                    "FROM raw_fundamentals "
                    "WHERE finnhub->'sentiment'->>'grade' IS NOT NULL "
                    "GROUP BY grade ORDER BY grade ASC")
                sentiment = [{"grade": r[0], "count": r[1]} for r in cur.fetchall()]

                # Composite health-score distribution (A–F bands), over distinct
                # passing tickers so a company counted once regardless of how
                # many strategies it cleared. Same grade cut-offs as scoring.py.
                cur.execute(
                    "WITH h AS ("
                    "  SELECT DISTINCT ON (ticker) ticker, "
                    "    (metrics->>'health_score')::float AS score "
                    "  FROM screen_results "
                    "  WHERE passed AND metrics ? 'health_score' "
                    "    AND (metrics->>'health_score') ~ '^-?[0-9.]+$' "
                    "  ORDER BY ticker, run_id DESC) "
                    "SELECT CASE "
                    "  WHEN score >= 80 THEN 'A' WHEN score >= 65 THEN 'B' "
                    "  WHEN score >= 50 THEN 'C' WHEN score >= 35 THEN 'D' "
                    "  ELSE 'F' END AS band, COUNT(*) AS n, ROUND(AVG(score)::numeric,1) "
                    "FROM h GROUP BY band ORDER BY band ASC")
                health = [{"band": r[0], "count": r[1], "avg": float(r[2])}
                          for r in cur.fetchall()]

        return {"runs": runs, "top_tickers": top_tickers,
                "sectors": sectors, "sentiment": sentiment, "health": health}

    # -- theses ----------------------------------------------------------
    _THESIS_COLS = ("id", "ticker", "note", "conditions", "baseline", "status",
                    "last_checks", "current", "created_at", "checked_at")

    @classmethod
    def _thesis_row(cls, r) -> dict:
        d = dict(zip(cls._THESIS_COLS, r))
        d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
        d["checked_at"] = d["checked_at"].isoformat() if d["checked_at"] else None
        return d

    def create_thesis(self, ticker, note, conditions, baseline) -> Optional[int]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO theses (ticker, note, conditions, baseline, "
                    "status, current, checked_at) VALUES "
                    "(%s,%s,%s,%s,'intact',%s, now()) RETURNING id",
                    (ticker.upper(), note, json.dumps(conditions, default=str),
                     json.dumps(baseline or {}, default=str),
                     json.dumps(baseline or {}, default=str)))
                tid = cur.fetchone()[0]
            conn.commit()
        return tid

    def list_theses(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, ticker, note, conditions, baseline, status, "
                    "last_checks, current, created_at, checked_at FROM theses "
                    "ORDER BY created_at DESC LIMIT %s", (limit,))
                return [self._thesis_row(r) for r in cur.fetchall()]

    def get_thesis(self, thesis_id: int) -> Optional[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, ticker, note, conditions, baseline, status, "
                    "last_checks, current, created_at, checked_at FROM theses "
                    "WHERE id = %s", (thesis_id,))
                row = cur.fetchone()
        return self._thesis_row(row) if row else None

    def update_thesis_check(self, thesis_id, status, current, checks) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE theses SET status=%s, current=%s, last_checks=%s, "
                    "checked_at=now() WHERE id=%s",
                    (status, json.dumps(current or {}, default=str),
                     json.dumps(checks or [], default=str), thesis_id))
            conn.commit()

    def delete_thesis(self, thesis_id: int) -> bool:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM theses WHERE id = %s", (thesis_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # -- API audit / rate limit -----------------------------------------
    def record_api_call(self, endpoint, method, status, scope=None,
                        client=None, note=None) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO api_audit (endpoint, method, status, scope, "
                    "client, note) VALUES (%s,%s,%s,%s,%s,%s)",
                    (str(endpoint)[:64], str(method)[:8], int(status),
                     (str(scope)[:16] if scope else None),
                     (str(client)[:80] if client else None),
                     (str(note)[:200] if note else None)))
            conn.commit()

    def list_api_audit(self, limit: int = 100, endpoint=None) -> list[dict]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                if endpoint:
                    cur.execute(
                        "SELECT ts, endpoint, method, status, scope, client, note "
                        "FROM api_audit WHERE endpoint = %s "
                        "ORDER BY ts DESC LIMIT %s", (endpoint, limit))
                else:
                    cur.execute(
                        "SELECT ts, endpoint, method, status, scope, client, note "
                        "FROM api_audit ORDER BY ts DESC LIMIT %s", (limit,))
                cols = ["ts", "endpoint", "method", "status", "scope", "client", "note"]
                out = []
                for r in cur.fetchall():
                    d = dict(zip(cols, r))
                    d["ts"] = d["ts"].isoformat() if d["ts"] else None
                    out.append(d)
                return out

    def count_api_calls(self, client: str, window_seconds: int) -> int:
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM api_audit WHERE client = %s "
                    "AND ts > now() - make_interval(secs => %s)",
                    (client, float(window_seconds)))
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def recently_screened(self, days: int) -> set:
        """Tickers screened by a *scheduled* run within the last ``days`` — used to
        keep the nightly report from re-analyzing the same stock too often. Manual
        analyses (meta.source manual/queue) are excluded, so they neither count
        toward the cooldown nor get suppressed by it."""
        if not days or days <= 0:
            return set()
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT res.ticker FROM screen_results res "
                    "JOIN screen_runs run ON run.id = res.run_id "
                    "WHERE run.created_at > now() - make_interval(days => %s) "
                    "AND COALESCE(run.meta->>'source','') NOT IN ('manual','queue')",
                    (float(days),))
                return {r[0].upper() for r in cur.fetchall() if r[0]}

    # -- settings --------------------------------------------------------
    def get_settings(self) -> dict:
        # Serve from the in-process cache when fresh (removes a DB round-trip
        # from the per-request hot path). Return a copy so callers can't mutate
        # the cached blob.
        if _SETTINGS_TTL > 0:
            hit = _SETTINGS_CACHE.get(self.dsn)
            if hit is not None and (time.time() - hit[0]) < _SETTINGS_TTL:
                return copy.deepcopy(hit[1])
        with self._connect() as conn:
            self._ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM settings WHERE id = 1")
                row = cur.fetchone()
        data = row[0] if row and isinstance(row[0], dict) else {}
        if _SETTINGS_TTL > 0:
            _SETTINGS_CACHE[self.dsn] = (time.time(), copy.deepcopy(data))
        return data

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
        # Refresh the cache so a read right after a write sees the new value
        # (and other warm instances catch up within the TTL).
        _SETTINGS_CACHE[self.dsn] = (time.time(), copy.deepcopy(data))

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
    """Find a Postgres connection string from config or the environment.

    Prefers an explicitly *pooled* endpoint when one is configured. Serverless
    functions open a connection per invocation, so on Neon/Vercel you should
    point ``STOCK_COMBER_DATABASE_URL_POOLED`` at the PgBouncer ``-pooler`` host
    to avoid exhausting direct connections under burst traffic; when it's unset
    the resolver falls back to the usual variables unchanged.
    """
    if config:
        dsn = config.get("storage", {}).get("dsn")
        if dsn:
            return dsn
    for var in ("STOCK_COMBER_DATABASE_URL_POOLED", "DATABASE_URL",
                "POSTGRES_URL", "POSTGRES_PRISMA_URL",
                "STOCK_COMBER_DATABASE_URL"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def get_storage(config: Optional[dict] = None):
    """Return a PostgresStorage if a DSN is configured, else NullStorage."""
    dsn = resolve_dsn(config)
    return PostgresStorage(dsn) if dsn else NullStorage()
