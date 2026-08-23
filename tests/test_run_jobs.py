"""Scheduled execution of saved custom jobs (cli run-jobs)."""

from stock_comber import cli
from stock_comber.models import ScreenResult


def _base():
    from stock_comber.config import DEFAULT_CONFIG
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)


# -- _job_config mapping (pure, no network) --------------------------------
def test_job_config_criteria_adds_custom_strategy():
    job = {"name": "cheap", "tickers": "aapl, msft",
           "criteria": [{"metric": "pe_ratio", "op": "<=", "value": 15}],
           "strategies": ["graham"]}
    cfg, tickers = cli._job_config(job, _base())
    assert tickers == ["AAPL", "MSFT"]                       # parsed + upper-cased
    assert "custom" in cfg["strategies"] and "graham" in cfg["strategies"]
    assert cfg["custom"]["criteria"] == job["criteria"]
    assert cfg["universe"] == {"mode": "list", "tickers": ["AAPL", "MSFT"]}


def test_job_config_strategies_only():
    job = {"name": "q", "tickers": "KO", "strategies": ["buffett"]}
    cfg, tickers = cli._job_config(job, _base())
    assert cfg["strategies"] == ["buffett"]
    assert "custom" not in cfg["strategies"]


def test_job_config_defaults_when_empty():
    cfg, _ = cli._job_config({"name": "x", "tickers": "T"}, _base())
    assert cfg["strategies"] == ["graham", "buffett"]


def test_job_config_filters_unknown_strategies():
    job = {"name": "x", "tickers": "T", "strategies": ["graham", "bogus"]}
    cfg, _ = cli._job_config(job, _base())
    assert "bogus" not in cfg["strategies"] and "graham" in cfg["strategies"]


def test_job_config_no_tickers():
    cfg, tickers = cli._job_config({"name": "empty", "tickers": ""}, _base())
    assert tickers == []


# -- _run_one_job persistence (Screener stubbed, fake store) ----------------
class _FakeScreener:
    last = {}

    def __init__(self, cfg):
        _FakeScreener.last = cfg
        self.store = None
        self.last_companies = {}

    def run(self, tickers, progress=None):
        _FakeScreener.ran_tickers = list(tickers)   # what was actually screened
        return [ScreenResult(ticker=t, name=t, strategy="graham", passed=True,
                             score=8, max_score=10) for t in tickers]


class _FakeStore:
    enabled = True

    def __init__(self):
        self.saved = []

    def save_run(self, results, companies, meta=None):
        self.saved.append(meta)
        return 42


def test_run_one_job_persists_with_scheduled_job_meta(monkeypatch):
    monkeypatch.setattr(cli, "Screener", _FakeScreener)
    store = _FakeStore()
    job = {"name": "Cheap large-caps", "tickers": "AAPL, MSFT", "strategies": ["graham"]}
    run_id = cli._run_one_job(job, _base(), store)
    assert run_id == 42
    assert store.saved and store.saved[0]["source"] == "schedule"
    assert store.saved[0]["job"] == "Cheap large-caps"
    # The job's tickers drove the screen.
    assert _FakeScreener.last["universe"]["tickers"] == ["AAPL", "MSFT"]


def test_run_one_job_skips_when_no_tickers(monkeypatch):
    monkeypatch.setattr(cli, "Screener", _FakeScreener)
    store = _FakeStore()
    assert cli._run_one_job({"name": "empty", "tickers": ""}, _base(), store) is None
    assert store.saved == []


def test_cmd_run_jobs_no_jobs(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_load", lambda args: {"jobs": []})
    assert cli.cmd_run_jobs(object()) == 0
    assert "No saved custom jobs" in capsys.readouterr().out


def test_cmd_run_jobs_runs_each(monkeypatch, capsys):
    base = _base()
    base["jobs"] = [
        {"name": "a", "tickers": "AAPL", "strategies": ["graham"]},
        {"name": "b", "tickers": "MSFT", "strategies": ["buffett"]},
    ]
    monkeypatch.setattr(cli, "_load", lambda args: base)
    monkeypatch.setattr(cli, "Screener", _FakeScreener)
    store = _FakeStore()
    monkeypatch.setattr(cli, "get_storage", lambda cfg: store, raising=False)
    import stock_comber.storage as storage
    monkeypatch.setattr(storage, "get_storage", lambda cfg=None: store)
    assert cli.cmd_run_jobs(object()) == 0
    names = sorted(m["job"] for m in store.saved)
    assert names == ["a", "b"]
    assert "Ran 2 of 2" in capsys.readouterr().out


# -- pool sampling (random pick) -------------------------------------------
def test_sample_pool_no_pick_returns_whole_pool():
    pool = ["A", "B", "C", "D"]
    assert cli._sample_pool(pool, {"name": "x"}) == pool
    assert cli._sample_pool(pool, {"name": "x", "pick": 0}) == pool
    assert cli._sample_pool(pool, {"name": "x", "pick": 9}) == pool     # >= size => all


def test_sample_pool_draws_subset_and_is_seeded():
    pool = [f"T{i}" for i in range(20)]
    a = cli._sample_pool(pool, {"name": "job", "pick": 5})
    b = cli._sample_pool(pool, {"name": "job", "pick": 5})
    assert len(a) == 5 and set(a) <= set(pool)
    assert a == b                                    # reproducible within the run window
    c = cli._sample_pool(pool, {"name": "other", "pick": 5})
    assert a != c or set(a) != set(c)                # different job name -> different draw


def test_run_one_job_samples_the_pool(monkeypatch):
    monkeypatch.setattr(cli, "Screener", _FakeScreener)
    store = _FakeStore()
    pool = ", ".join(f"T{i}" for i in range(30))
    job = {"name": "pick3", "tickers": pool, "pick": 3, "strategies": ["graham"]}
    cli._run_one_job(job, _base(), store)
    screened = _FakeScreener.ran_tickers          # the sampled subset actually screened
    assert len(screened) == 3 and set(screened) <= {f"T{i}" for i in range(30)}
