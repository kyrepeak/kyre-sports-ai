from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v10_is_presentation_only_successor_over_frozen_v9():
    import nfl_spread_hub_v10 as page
    assert page.PRESENTATION_ONLY is True
    assert page.FROZEN_PRIOR == "nfl_spread_hub_v9"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.LINE_LAB_SETTLEMENT_ONLY is True
    assert page.STAKE_SIZING_ENABLED is False
    assert page.WAGER_ACTIONS_ENABLED is False


def test_v10_has_strong_consumer_visual_hierarchy():
    source = (ROOT / "nfl_spread_hub_v10.py").read_text(encoding="utf-8")
    for token in (
        "MODEL READ",
        "LINE LAB",
        "WHY THE MODEL SEES IT",
        "RECENT MATCHUP HISTORY",
        "ksp10-model-read",
        "ksp10-ruler",
        "ksp10-reason-grid",
        "ksp10-history-row",
        "ksp10-team-logo",
    ):
        assert token in source
    assert "font-size:.45rem" not in source
    assert "font-size:.49rem" not in source


def test_v10_preserves_native_slider_and_frozen_settlement_math():
    source = (ROOT / "nfl_spread_hub_v10.py").read_text(encoding="utf-8")
    assert "st.slider(" in source
    assert "min_value=-30.5" in source
    assert "max_value=30.5" in source
    assert "step=0.5" in source
    assert "prior.settle_line" in source
    assert "simulate_game_spread" not in source
    assert "spread_mc.simulate" not in source


def test_current_api2_production_chain_routes_spread_canonically_without_repointing_app():
    terminal = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py").read_text(encoding="utf-8")
    density = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    routing_block = terminal.split('if route.sport_id == "nfl" and route.market_id in ', 1)[1].split("\n    return _prior_resolve_destination", 1)[0]
    assert '"spread"' in routing_block
    assert "return canonical_loader.resolve_destination(route)" in routing_block
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1 as prior" in density
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1" in app
