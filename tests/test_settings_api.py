"""The settings API stores the Finnhub key in the database but must never
return it, and a blank field must not wipe a stored key."""

import importlib.util
import os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "api", "settings.py")
_spec = importlib.util.spec_from_file_location("api_settings", _PATH)
settings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(settings)


def test_redact_blanks_stored_finnhub_key():
    cfg = {"data": {"finnhub_api_key": "secret123", "cache_dir": "/x"},
           "strategies": ["graham"]}
    safe = settings._redact(cfg)
    assert safe["data"]["finnhub_api_key"] == ""     # hidden
    assert safe["data"]["cache_dir"] == "/x"          # other data preserved
    assert cfg["data"]["finnhub_api_key"] == "secret123"  # original untouched


def test_status_reflects_stored_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert settings._status({"data": {"finnhub_api_key": "k"}})["keys"]["finnhub"] is True
    assert settings._status({"data": {}})["keys"]["finnhub"] is False


def test_blank_secret_is_stripped_not_stored():
    incoming = {"data": {"finnhub_api_key": ""}, "strategies": ["graham"]}
    settings._strip_blank_secrets(incoming)
    assert "finnhub_api_key" not in incoming["data"]   # blank dropped → keep current


def test_nonblank_secret_is_kept():
    incoming = {"data": {"finnhub_api_key": "abc"}}
    settings._strip_blank_secrets(incoming)
    assert incoming["data"]["finnhub_api_key"] == "abc"
