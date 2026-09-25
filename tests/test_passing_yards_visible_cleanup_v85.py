from pathlib import Path
import re

import nfl_passing_yards_hub_v74 as v74
import nfl_passing_yards_hub_v85 as v85
import streamlit_memory_lazy_router_v236 as router236
import streamlit_memory_lazy_router_v237 as router237


def _fixture_body() -> str:
    return (
        '<section>'
        '<b>4038941 ESPN Athlete ID 24 ESPN Team ID no listed injuryAvailability '
        'ESPN CORE DEPTH CHART Market Decision Detail Model Confidence 22.8% '
        'How to read this clean detail</b><span>Unrelated Field</span>'
        '<div><b>READY</b><span>QB Status</span></div>'
        '<div><b>0</b><span>Skill Hard</span></div>'
        '<div><b>0</b><span>OL Hard</span></div>'
        '<div><b>0</b><span>Opp Secondary Hard</span></div>'
        '<div><b>OUTDOOR</b><span>Venue Type</span></div>'
        '<div><b>GRASS</b><span>Surface</span></div>'
        '<div><b>NORMAL</b><span>Weather</span></div>'
        '<div><b>67°F</b><span>Temperature</span></div>'
        '<div><b>8 mph</b><span>Wind</span></div>'
        '</section>'
    )


def _snapshot() -> dict:
    return {
        "state": "UNVERIFIED",
        "provider_ok": False,
        "game_id": "4038941",
        "selected_unavailable": [],
        "opponent_unavailable": [],
        "selected_explicit_inactive": [],
        "opponent_explicit_inactive": [],
    }


def test_v85_bounded_metric_does_not_cross_bold_boundary():
    body = _fixture_body()
    assert v85._bounded_metric(body, "QB Status") == "READY"
    assert v85._bounded_metric(body, "Surface") == "GRASS"
    assert v85._bounded_metric(body, "Weather") == "NORMAL"
    assert v85._bounded_metric(body, "Temperature") == "67°F"
    assert v85._bounded_metric(body, "Wind") == "8 mph"


def test_v85_bounded_metric_fails_closed_on_dump_value():
    body = '<b>Market Decision Detail Model Confidence 22.8%</b><span>Weather</span>'
    assert v85._bounded_metric(body, "Weather") == ""


def test_v74_panel_is_compact_with_v85_guard(monkeypatch):
    monkeypatch.setattr(v74, "_metric", v85._bounded_metric)
    panel = v74.build_availability_panel(_fixture_body(), _snapshot())

    assert '>READY</b><span>QB Status</span>' in panel
    assert '>0</b><span>Skill Hard</span>' in panel
    assert '>OUTDOOR</b><span>Venue Type</span>' in panel
    assert '>GRASS</b><span>Surface</span>' in panel
    assert '>NORMAL</b><span>Weather</span>' in panel
    assert '>8 mph</b><span>Wind</span>' in panel

    assert "Market Decision Detail" not in panel
    assert "How to read this clean detail" not in panel
    assert "Model Confidence" not in panel

    report = re.search(
        r'<div class="ks-py74-report"[^>]*>(.*?)</div>',
        panel,
        flags=re.S,
    )
    assert report is not None
    report_text = re.sub(r"<[^>]+>", " ", report.group(1))
    report_text = " ".join(report_text.split())
    assert len(report_text) < 700
    assert report_text.count("Final inactive report:") == 1
    assert "Environment:" in report_text
    assert "67°F" in report_text
    assert "8 mph" in report_text
    assert "NORMAL" in report_text
    assert "GRASS" in report_text


def test_cleanup_router_wraps_monster_router_without_replacing_it():
    assert router237.prior is router236
    assert router237.FROZEN_ROUTER == "streamlit_memory_lazy_router_v236"
    assert router237.FROZEN_PASSING_ROUTER == "streamlit_memory_lazy_router_v235"
    assert router237.PASSING_HUB == "nfl_passing_yards_hub_v85"


def test_app_activates_v237_only_at_entrypoint():
    app = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v237 import record_bootstrap_import_ms, render_app" in app
    assert "from streamlit_memory_lazy_router_v236 import record_bootstrap_import_ms, render_app" not in app
