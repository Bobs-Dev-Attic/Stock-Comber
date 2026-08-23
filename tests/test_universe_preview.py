"""The nightly-preview endpoint helper, incl. the Remix seed offset."""

import importlib.util
import os

_UNIVERSE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "api", "universe.py")


def _load():
    spec = importlib.util.spec_from_file_location("api_universe", _UNIVERSE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _params(**kw):
    # parse_qs-shaped: every value is a one-element list.
    return {k: [str(v)] for k, v in kw.items()}


def test_preview_remix_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    m = _load()
    out = m.build_nightly_preview(_params(ordinal=739000, hour=6))
    assert out["remix"] == 0
    assert out["nightly"] is True
    assert isinstance(out["results"], list)


def test_preview_remix_zero_matches_unremixed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    m = _load()
    base = m.build_nightly_preview(_params(ordinal=739000, hour=6))
    same = m.build_nightly_preview(_params(ordinal=739000, hour=6, remix=0))
    assert [r["ticker"] for r in base["results"]] == [r["ticker"] for r in same["results"]]


def test_preview_remix_changes_the_pick(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    m = _load()
    base = m.build_nightly_preview(_params(ordinal=739000, hour=6))
    remixed = m.build_nightly_preview(_params(ordinal=739000, hour=6, remix=1))
    assert remixed["remix"] == 1
    # A remix draws a different well-spread set from the same pool (order/selection
    # differs) while the run's date is unchanged.
    assert base["date"] == remixed["date"]
    assert [r["ticker"] for r in base["results"]] != [r["ticker"] for r in remixed["results"]]
