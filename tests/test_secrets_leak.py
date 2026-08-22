"""Guard against leaking configured secrets back to the browser.

Secrets (the Finnhub API key, the database URL) are write-only over the API:
the settings endpoint must return only *booleans* indicating what is configured,
never the values themselves.
"""

import importlib.util
import os

_SETTINGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "api", "settings.py")


def _load_settings_module():
    spec = importlib.util.spec_from_file_location("api_settings", _SETTINGS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_redact_blanks_finnhub_key():
    m = _load_settings_module()
    cfg = {"data": {"finnhub_api_key": "super-secret-value", "cache_ttl_hours": 24}}
    safe = m._redact(cfg)
    assert safe["data"]["finnhub_api_key"] == ""          # blanked
    assert cfg["data"]["finnhub_api_key"] == "super-secret-value"  # original untouched
    assert safe["data"]["cache_ttl_hours"] == 24          # non-secrets kept


def test_redact_blanks_tiingo_key():
    m = _load_settings_module()
    cfg = {"data": {"tiingo_api_key": "tiingo-secret-value", "cache_ttl_hours": 24}}
    safe = m._redact(cfg)
    assert safe["data"]["tiingo_api_key"] == ""           # blanked
    assert cfg["data"]["tiingo_api_key"] == "tiingo-secret-value"  # original untouched


def test_status_reports_booleans_never_values(monkeypatch):
    m = _load_settings_module()
    monkeypatch.setenv("FINNHUB_API_KEY", "env-secret-123")
    monkeypatch.setenv("STOCK_COMBER_API_KEY", "api-secret-456")
    monkeypatch.setenv("TIINGO_API_KEY", "tiingo-secret-abc")
    cfg = {"data": {"finnhub_api_key": "stored-secret-789",
                    "tiingo_api_key": "stored-tiingo-000"}}
    status = m._status(cfg)
    flat = repr(status)
    for secret in ("env-secret-123", "api-secret-456", "stored-secret-789",
                   "tiingo-secret-abc", "stored-tiingo-000"):
        assert secret not in flat
    assert status["keys"]["finnhub"] is True              # reported as present
    assert status["keys"]["tiingo"] is True               # reported as present
    assert isinstance(status["keys"]["export_api"], bool)
