from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v11_is_presentation_only_successor_over_v10():
    import nfl_spread_hub_v11 as page
    assert page.PRESENTATION_ONLY is True
    assert page.FROZEN_PRIOR == "nfl_spread_hub_v10"
    assert page.LINE_LAB_SETTLEMENT_ONLY is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False
    assert page.WAGER_ACTIONS_ENABLED is False


def test_v11_has_s_tier_consumer_hierarchy_and_restrained_surfaces():
    source = (ROOT / "nfl_spread_hub_v11.py").read_text(encoding="utf-8")
    for token in (
        "ksp11-shell",
        "ksp11-matchup-hero",
        "ksp11-decision",
        "ksp11-line-stage",
        "ksp11-evidence-row",
        "ksp11-history-table",
        "MODEL LEAN",
        "MARKET",
        "MODEL FAIR",
        "SELECTED",
        "WHY THIS LINE",
    ):
        assert token in source
    assert "MAX_CONTENT_WIDTH" in source
    assert "st.slider(" in source
    assert "min_value=-30.5" in source
    assert "max_value=30.5" in source
    assert "step=0.5" in source
    assert "simulate_game_spread" not in source
    assert "spread_mc.simulate" not in source


def test_v25_overrides_only_nfl_spread_and_preserves_v24():
    loader = (ROOT / "universal_runtime_v5_loader_v25.py").read_text(encoding="utf-8")
    overlay = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "import universal_runtime_v5_loader_v24 as prior" in loader
    assert 'route.sport_id == "nfl" and route.market_id == "spread"' in loader
    assert '"nfl_spread_hub_v11"' in loader
    assert "from universal_runtime_v5_loader_v25 import" in overlay
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7" in app
    assert "nfl_spread_hub_v11" not in app


def test_v11_does_not_mutate_frozen_model_contracts():
    source = (ROOT / "nfl_spread_hub_v11.py").read_text(encoding="utf-8")
    assert "prior.settle_line" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "WAGER_ACTIONS_ENABLED = False" in source
    assert "STAKE_SIZING_ENABLED = False" in source
