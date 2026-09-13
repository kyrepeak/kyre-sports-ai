from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step3_is_visual_only_additive_over_certified_v2():
    source = _source("nfl_receiving_yards_hub_v3.py")
    assert "import nfl_receiving_yards_hub_v2 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v2"' in source
    assert "PAGE_BUILD_STEP = 3" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "_ORIGINAL_PLAYER_CARD_V2 = prior._player_card" in source
    assert "card = _ORIGINAL_PLAYER_CARD_V2(player, team, opponent)" in source
    assert "prior._player_card = _player_card_v3" in source
    assert "prior._player_card = original_card" in source


def test_step3_summary_contains_exact_descriptive_receiving_metrics():
    source = _source("nfl_receiving_yards_hub_v3.py")
    for label in (
        '"Receptions"',
        '"Receiving Yards"',
        '"Rec Yds / Game"',
        '"Yards / Reception"',
        '"Receiving TD"',
        '"Targets / Game"',
    ):
        assert label in source
    for field in (
        'player.get("receptions")',
        'player.get("receiving_yards")',
        'player.get("receiving_yards_per_game")',
        'player.get("yards_per_reception")',
        'player.get("receiving_touchdowns")',
    ):
        assert field in source


def test_step3_targets_are_explicit_only_and_fail_closed_for_display():
    source = _source("nfl_receiving_yards_hub_v3.py")
    assert 'targets_live = player.get("targets_data_available") is True' in source
    assert 'player.get("targets_per_game")' in source
    assert 'if targets_live else "—"' in source
    assert "targets render only when targets_data_available is explicitly true" in source
    assert "never inferred" in source


def test_step3_progress_and_copy_advance_only_summary_stage():
    source = _source("nfl_receiving_yards_hub_v3.py")
    assert ".krecv-progress .krecv-fill{width:30%!important}" in source
    assert "STEP 3 OF 10 • SUMMARY LIVE" in source
    assert '<span class="krecv-stage on">3 • SUMMARY ✅</span>' in source
    assert "✅ SUMMARY METRICS" in source
    assert "Volume/efficiency interpretation" in source
    assert "player-vs-team history" in source
    assert "sportsbook projection influence" in source
    assert "0.0%" in source


def test_step3_does_not_activate_later_analysis_or_betting_layers():
    source = _source("nfl_receiving_yards_hub_v3.py")
    assert "Step 3 is descriptive only" in source
    assert "opponent pass-defense" in source
    assert "player-vs-team history" in source
    assert "projection" in source.lower()
    assert "market" in source.lower()
    assert "probability" in source.lower()
    assert "EV" in source
    assert "Monte Carlo" in source
    assert "staking" in source
    assert "wager actions" in source
    assert "nfl_rushing_yards" not in source
    assert "nfl_passing_yards" not in source


def test_step5_defense_and_h2h_remain_reserved_in_frozen_v2_plan():
    source = _source("nfl_receiving_yards_hub_v2.py")
    assert '(5, "DEFENSE + H2H", False)' in source
    assert "player-vs-team history" in source


def test_router_v114_advances_only_receiving_to_v3():
    source = _source("streamlit_memory_lazy_router_v114.py")
    assert "import streamlit_memory_lazy_router_v113 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v113"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v3"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "if _receiving_route_active():" in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_boots_v114_and_preserves_v113_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v114 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V113_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V113_NFL_RECEIVING_YARDS_STEP2_PLAYER_CARDS_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V114_NFL_RECEIVING_YARDS_STEP3_SUMMARY_METRICS_2026-09-13"' in source


def test_certified_step2_and_router_v113_remain_historical_owners():
    page_v2 = _source("nfl_receiving_yards_hub_v2.py")
    router_v113 = _source("streamlit_memory_lazy_router_v113.py")
    assert 'MODEL_VERSION = "NFL RECEIVING YARDS V2 • PAGE BUILD STEP 2 • RECEIVER PLAYER CARDS"' in page_v2
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v1"' in page_v2
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v2"' in router_v113
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v112"' in router_v113
