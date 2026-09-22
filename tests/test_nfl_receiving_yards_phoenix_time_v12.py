from __future__ import annotations

from datetime import date
from pathlib import Path


def _helper():
    import nfl_receiving_yards_phoenix_time_v1 as helper

    return helper


def test_september_research_matchup_converts_et_to_phoenix_mst() -> None:
    helper = _helper()
    label = "DET @ BUF • 8:15 PM ET • ESPN 401872932"
    assert helper.format_research_matchup_label(label, date(2026, 9, 17)) == (
        "DET @ BUF • 5:15 PM MST • ESPN 401872932"
    )


def test_winter_research_matchup_converts_et_to_phoenix_mst() -> None:
    helper = _helper()
    label = "DET @ BUF • 8:15 PM ET • ESPN 401872932"
    assert helper.format_research_matchup_label(label, date(2026, 12, 17)) == (
        "DET @ BUF • 6:15 PM MST • ESPN 401872932"
    )


def test_tbd_or_unparseable_labels_fail_closed() -> None:
    helper = _helper()
    assert helper.format_research_matchup_label(
        "DET @ BUF • TBD • ESPN 401872932", date(2026, 9, 17)
    ) == "DET @ BUF • TBD • ESPN 401872932"
    assert helper.format_research_matchup_label("not a matchup", date(2026, 9, 17)) == "not a matchup"


def test_v12_is_display_only_over_frozen_v11() -> None:
    source = Path("nfl_receiving_yards_hub_v12.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v11"' in source
    assert 'RESEARCH_MATCHUP_LABEL = "🎯 Receiver research matchup"' in source
    assert "format_research_matchup_label" in source
    assert "original_selectbox" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "DISPLAY_ONLY = True" in source


def test_router_v143_advances_only_receiving_yards() -> None:
    source = Path("streamlit_memory_lazy_router_v143.py").read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v142"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v12"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_bootstraps_router_v143() -> None:
    source = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v143 import record_bootstrap_import_ms, render_app" in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V143_NFL_RECEIVING_YARDS_PHOENIX_TIME_2026-09-16"' in source
