from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_receiving_v1_is_isolated_verified_slate_foundation():
    source = _source("nfl_receiving_yards_hub_v1.py")
    assert 'MODEL_VERSION = "NFL RECEIVING YARDS V1 • STEP 1 VERIFIED SLATE FOUNDATION"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "from nfl_hub_v1 import ET, load_nfl_slate" in source
    assert "SYSTEM_STEP = 1" in source
    assert "SYSTEM_TOTAL = 4" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "nfl_rushing_yards" not in source
    assert "nfl_passing_yards" not in source


def test_receiving_v1_matches_rushing_style_without_enabling_model_layers():
    source = _source("nfl_receiving_yards_hub_v1.py")
    for marker in (
        "Verified Slate",
        "Receiver Context",
        "Projection Engine",
        "FanDuel Market",
        "STEP 1 OF 4 • ACTIVE",
        "EXACT ESPN GAME IDs",
        "SPORTSBOOK INFLUENCE 0.0%",
    ):
        assert marker in source
    assert "probability" in source.lower()
    assert "monte carlo" in source.lower()
    assert "recommendations" in source.lower()
    assert "wager actions" in source.lower()


def test_receiving_game_cards_fail_safe_against_raw_markdown_html():
    source = _source("nfl_receiving_yards_hub_v1.py")
    assert "from textwrap import dedent" in source
    assert "return dedent(html).strip()" in source
    assert "unsafe_allow_html=True" in source
    assert "krecv-game" in source


def test_receiving_v1_uses_phoenix_display_only_clock():
    source = _source("nfl_receiving_yards_hub_v1.py")
    assert 'PHOENIX_TZ_NAME = "America/Phoenix"' in source
    assert 'PHOENIX_TZ_LABEL = "MST"' in source
    assert "eastern.astimezone(_PHOENIX)" in source
    assert '"clock_with_location": f"{label} • Phoenix"' in source
    assert "slate identity interpreted in America/New_York" in source


def test_router_v112_advances_only_receiving_yards():
    source = _source("streamlit_memory_lazy_router_v112.py")
    assert "import streamlit_memory_lazy_router_v111 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v111"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v1"' in source
    assert "if _receiving_route_active():" in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_boots_v112_and_preserves_v111_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v112 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V111_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V111_NFL_RUSHING_YARDS_PHOENIX_GAME_TIMES_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V112_NFL_RECEIVING_YARDS_STEP1_FOUNDATION_2026-09-13"' in source


def test_certified_rushing_v15_remains_frozen_owner():
    source = _source("nfl_rushing_yards_hub_v15.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v14"' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'PHOENIX_TZ_NAME = "America/Phoenix"' in source
