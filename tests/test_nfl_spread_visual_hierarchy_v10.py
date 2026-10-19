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


def test_runtime_v23_owns_only_nfl_spread_and_preserves_v22():
    loader = (ROOT / "universal_runtime_v5_loader_v23.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "import universal_runtime_v5_loader_v22 as prior" in loader
    assert 'route.sport_id == "nfl" and route.market_id == "spread"' in loader
    assert '"nfl_spread_hub_v10"' in loader
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_spread_v10" in app
