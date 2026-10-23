from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1.py"
APP = ROOT / "app.py"


def test_repair_terminal_imports_nba_pra_owner_before_frozen_runtime() -> None:
    assert TERMINAL.exists()
    source = TERMINAL.read_text(encoding="utf-8")
    prior = "import streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 as prior"
    frozen = "import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime"
    assert prior in source
    assert frozen in source
    assert source.index(prior) < source.index(frozen)
    assert "_prior_resolve_destination = prior.resolve_destination" in source
    assert "render_page_experience_app_v3" in source


def test_repair_terminal_preserves_nba_pra_and_cfb_top_picks_routes() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert "route.sport_id == \"cfb\" and route.market_id == \"top-picks\"" in source
    assert "cfb_top_picks_page_v19" in source
    assert "prior.resolve_destination" in source
    prior_source = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py").read_text(encoding="utf-8")
    assert "nav_overlay.activate()" in prior_source
    assert "route.sport_id == \"nba\" and route.market_id == \"pra\"" in prior_source
    assert "nba_pra_runtime_v2" in prior_source


def test_repair_terminal_routes_nfl_rushing_yards_through_canonical_frozen_successor() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert 'route.sport_id == "nfl" and route.market_id == "rushing-yards"' in source
    assert "return canonical_loader.resolve_destination(route)" in source
    assert "nfl_rushing_yards_hub_v17" not in source


def test_app_activates_repair_terminal_only() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1" in source
