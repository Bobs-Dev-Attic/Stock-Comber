from stock_comber.config import DEFAULT_CONFIG, _deep_merge, load_config, validate_config


def test_defaults_valid():
    assert validate_config(load_config()) == []


def test_deep_merge_preserves_untouched_keys():
    merged = _deep_merge(DEFAULT_CONFIG, {"graham": {"max_pe": 10.0}})
    assert merged["graham"]["max_pe"] == 10.0
    # Sibling keys survive the merge.
    assert merged["graham"]["max_pb"] == DEFAULT_CONFIG["graham"]["max_pb"]
    # Original is not mutated.
    assert DEFAULT_CONFIG["graham"]["max_pe"] == 15.0


def test_validate_flags_bad_strategy():
    cfg = load_config()
    cfg["strategies"] = ["graham", "nonsense"]
    problems = validate_config(cfg)
    assert any("nonsense" in p for p in problems)


def test_validate_flags_bad_pass_ratio():
    cfg = load_config()
    cfg["graham"]["pass_ratio"] = 1.5
    assert any("pass_ratio" in p for p in validate_config(cfg))


def test_jobs_default_is_empty_list():
    assert load_config()["jobs"] == []


def test_valid_job_passes():
    cfg = load_config()
    cfg["jobs"] = [{
        "name": "Cheap large-caps",
        "tickers": "AAPL, MSFT",
        "criteria": [{"metric": "pe_ratio", "op": "<=", "value": 15}],
        "strategies": ["graham", "buffett"],
    }]
    assert validate_config(cfg) == []


def test_job_requires_name():
    cfg = load_config()
    cfg["jobs"] = [{"criteria": [{"metric": "pe_ratio", "op": "<=", "value": 15}]}]
    assert any("name" in p for p in validate_config(cfg))


def test_job_flags_bad_criteria_and_strategy():
    cfg = load_config()
    cfg["jobs"] = [{
        "name": "Bad",
        "criteria": [{"metric": "not_a_metric", "op": "<=", "value": 15}],
        "strategies": ["nonsense"],
    }]
    problems = validate_config(cfg)
    assert any("metric" in p for p in problems)
    assert any("nonsense" in p for p in problems)


def test_job_flags_duplicate_names():
    cfg = load_config()
    cfg["jobs"] = [{"name": "Dupe"}, {"name": "dupe"}]
    assert any("duplicate job name" in p for p in validate_config(cfg))


def test_default_config_has_api_block():
    cfg = load_config()
    rl = cfg["api"]["rate_limit"]
    assert cfg["api"]["audit"] is True
    assert rl["enabled"] is True and rl["max_requests"] >= 1
    assert rl["scope"] in ("ip", "key", "global")


def test_validate_flags_bad_rate_limit():
    cfg = load_config()
    cfg["api"]["rate_limit"]["max_requests"] = 0
    cfg["api"]["rate_limit"]["scope"] = "planet"
    problems = validate_config(cfg)
    assert any("max_requests" in p for p in problems)
    assert any("scope" in p for p in problems)


def test_validate_accepts_tuned_rate_limit():
    cfg = load_config()
    cfg["api"]["rate_limit"] = {"enabled": False, "max_requests": 30,
                                "window_seconds": 10, "scope": "key"}
    assert validate_config(cfg) == []


def test_default_cooldown_and_validation():
    cfg = load_config()
    assert cfg["universe"]["nightly"]["reanalyze_cooldown_days"] == 90
    assert validate_config(cfg) == []
    cfg["universe"]["nightly"]["reanalyze_cooldown_days"] = -5
    assert any("reanalyze_cooldown_days" in p for p in validate_config(cfg))


def test_backtest_on_analysis_default_on():
    cfg = load_config()
    assert cfg["data"]["backtest_on_analysis"] is True
    assert validate_config(cfg) == []


def test_backtest_in_nightly_default_on():
    cfg = load_config()
    assert cfg["data"]["backtest_in_nightly"] is True
    assert validate_config(cfg) == []
