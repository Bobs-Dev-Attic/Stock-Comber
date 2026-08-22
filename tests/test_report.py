import io
import json

from stock_comber.criteria import evaluate_graham
from stock_comber.report import (
    stream_csv, stream_html, to_csv, to_html, to_json, to_markdown, write_reports,
)


def _results(strong_company, config):
    return [evaluate_graham(strong_company, config)]


def test_json_roundtrip(strong_company, config):
    results = _results(strong_company, config)
    payload = json.loads(to_json(results, config))
    assert payload["count"] == 1
    assert payload["results"][0]["ticker"] == "STRONG"
    assert "score_pct" in payload["results"][0]


def test_csv_has_header_and_row(strong_company, config):
    out = to_csv(_results(strong_company, config), config)
    lines = out.strip().splitlines()
    assert lines[0].startswith("ticker,name,strategy")
    assert "avg_volume" in lines[0].split(",")
    assert "STRONG" in lines[1]


def test_markdown_and_html_render(strong_company, config):
    md = to_markdown(_results(strong_company, config), config)
    assert "Stock-Comber screening report" in md
    html = to_html(_results(strong_company, config), config)
    assert "<table>" in html and "STRONG" in html


def test_streaming_writers_match_string_renderers(strong_company, config):
    results = _results(strong_company, config)
    buf = io.StringIO()
    stream_csv(results, config, buf)
    assert buf.getvalue() == to_csv(results, config)
    buf = io.StringIO()
    stream_html(results, config, buf)
    assert buf.getvalue() == to_html(results, config)


def test_write_reports_latest_matches_stamped(tmp_path, strong_company, config):
    config["output"]["dir"] = str(tmp_path)
    config["output"]["formats"] = ["csv", "html"]
    write_reports(_results(strong_company, config), config)
    for ext in ("csv", "html"):
        stamped = list(tmp_path.glob(f"screen-*.{ext}"))[0].read_text()
        latest = (tmp_path / f"latest.{ext}").read_text()
        assert stamped == latest and "STRONG" in stamped


def test_write_reports(tmp_path, strong_company, config):
    config["output"]["dir"] = str(tmp_path)
    config["output"]["formats"] = ["json", "csv", "markdown", "html"]
    paths = write_reports(_results(strong_company, config), config)
    assert len(paths) == 8  # 4 formats x (dated + latest)
    for p in paths:
        assert (tmp_path / p.split("/")[-1]).exists()
