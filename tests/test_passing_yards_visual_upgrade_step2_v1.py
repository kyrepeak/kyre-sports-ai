from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name: str) -> str:
    return (ROOT / name).read_text()

def test_step2_is_presentation_only_over_step1() -> None:
    body = read("nfl_passing_yards_hub_v47.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v46"' in body
    assert "PRESENTATION_ONLY = True" in body
    assert "MAY_MODIFY_PROJECTION = False" in body
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in body

def test_step2_replaces_only_final_responsive_builder() -> None:
    body = read("nfl_passing_yards_hub_v47.py")
    assert "original_builder = responsive._responsive_player_cards_html" in body
    assert "responsive._responsive_player_cards_html = _premium_command_center_html" in body
    assert "responsive._responsive_player_cards_html = original_builder" in body

def test_step2_renders_exactly_two_premium_player_cards() -> None:
    body = read("nfl_passing_yards_hub_v47.py")
    assert body.count("_premium_player(captured, 0)") == 1
    assert body.count("_premium_player(captured, 1)") == 1
    assert 'data-passing-yards-core="v47"' in body
    assert 'data-passing-player="{index}"' in body

def test_step2_preserves_primary_and_supporting_evidence() -> None:
    body = read("nfl_passing_yards_hub_v47.py")
    for key in (
        '"identity"', '"projection"', '"market"', '"profile"', '"defense"',
        '"pressure"', '"personnel"', '"environment"', '"context"', '"distribution"',
    ):
        assert key in body
    assert "Monster Projection" in body
    assert "Market + Edge" in body
    assert "Matchup" in body
    assert "Conditions" in body
    assert "Deep Data" in body

def test_step2_router_advances_only_passing_yards() -> None:
    body = read("streamlit_memory_lazy_router_v193.py")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v192"' in body
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v47"' in body
    assert 'if sport != "NFL" or market != PASSING_MARKET:' in body
    assert "return prior.render_app()" in body

def test_step2_app_boots_v193() -> None:
    app = read("app.py")
    assert "from streamlit_memory_lazy_router_v193 import record_bootstrap_import_ms, render_app" in app
