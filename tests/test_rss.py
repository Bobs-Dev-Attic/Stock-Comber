"""Nightly RSS digest: well-formed feed, passing-only items, escaping, caps."""

import xml.etree.ElementTree as ET

from stock_comber.models import ScreenResult
from stock_comber.report import to_rss


def _r(ticker, name, passed, score, strategy="graham", metrics=None):
    return ScreenResult(
        ticker=ticker, name=name, strategy=strategy, passed=passed,
        score=score, max_score=100.0, metrics=metrics or {})


def _cfg(**over):
    cfg = {"strategies": ["graham", "buffett"],
           "output": {"top_n": 50, "site_url": "https://example.test"}}
    cfg["output"].update(over)
    return cfg


def test_feed_is_well_formed_xml():
    xml = to_rss([_r("AAPL", "Apple", True, 88)], _cfg())
    root = ET.fromstring(xml)                 # raises on malformed XML
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    chan = root.find("channel")
    assert chan.find("title").text == "Stock-Comber — Nightly Hidden Gems"
    assert chan.find("link").text == "https://example.test"
    assert chan.find("lastBuildDate").text                    # present


def test_only_passing_rows_become_items():
    rows = [_r("AAPL", "Apple", True, 88), _r("MSFT", "Microsoft", False, 60),
            _r("JNJ", "J&J", True, 70)]
    root = ET.fromstring(to_rss(rows, _cfg()))
    items = root.findall("channel/item")
    assert len(items) == 2                                    # near-miss excluded
    titles = " ".join(i.find("title").text for i in items)
    assert "AAPL" in titles and "JNJ" in titles and "MSFT" not in titles


def test_top_n_caps_items():
    rows = [_r(f"T{i}", f"Co {i}", True, 90) for i in range(10)]
    root = ET.fromstring(to_rss(rows, _cfg(top_n=3)))
    assert len(root.findall("channel/item")) == 3


def test_special_characters_are_escaped_and_parse():
    # A raw '&' / '<' in a company name must not break the XML.
    rows = [_r("BUD", "AT&T <Holdings>", True, 75)]
    xml = to_rss(rows, _cfg())
    root = ET.fromstring(xml)                                 # would raise if unescaped
    title = root.find("channel/item/title").text
    assert "AT&T <Holdings>" in title                          # decoded round-trip


def test_guid_is_not_a_permalink_and_is_unique_per_ticker():
    rows = [_r("AAPL", "Apple", True, 88), _r("JNJ", "J&J", True, 70)]
    root = ET.fromstring(to_rss(rows, _cfg()))
    guids = root.findall("channel/item/guid")
    assert all(g.attrib.get("isPermaLink") == "false" for g in guids)
    assert len({g.text for g in guids}) == 2                   # distinct per ticker


def test_metrics_appear_in_description():
    rows = [_r("AAPL", "Apple", True, 88,
               metrics={"price": 187.0, "pe_ratio": 22.0, "backtest_edge_pct": 4.5})]
    root = ET.fromstring(to_rss(rows, _cfg()))
    desc = root.find("channel/item/description").text
    assert "Price" in desc and "P/E" in desc and "not investment advice" in desc


def test_default_site_url_when_unset():
    root = ET.fromstring(to_rss([_r("AAPL", "Apple", True, 88)],
                                {"strategies": [], "output": {}}))
    assert root.find("channel/link").text.startswith("https://github.com/")


def test_rss_registered_as_output_format():
    from stock_comber.report import RENDERERS, STREAMERS
    assert STREAMERS["rss"][1] == "xml"
    assert RENDERERS["rss"][1] == "xml"
