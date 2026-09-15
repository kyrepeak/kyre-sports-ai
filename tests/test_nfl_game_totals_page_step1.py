from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v1.py"
NFL_HUB = ROOT / "nfl_hub_v18.py"
FROZEN_SPREAD_ROUTER = ROOT / "streamlit_memory_lazy_router_v136.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_step1_page_contract_exists_and_is_exactly_step_1_of_10():
    assert PAGE.exists(), "Step 1 page module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V1' in source
    assert "PAGE_BUILD_STEP = 1" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "LIVE_MARKET_ENABLED = False" in source


def test_step1_page_has_connected_ten_stage_build_rail():
    source = _read(PAGE)
    expected_stages = (
        "VERIFIED SLATE",
        "LIVE TOTAL",
        "OFFENSE VS DEFENSE",
        "PACE + POSSESSION",
        "EXPLOSIVE SCORING",
        "RED ZONE + DRIVES",
        "GAME ENVIRONMENT",
        "TOTAL PROJECTION",
        "MARKET + FINAL READ",
        "FINAL CERTIFICATION",
    )
    for stage in expected_stages:
        assert stage in source
    assert "STEP 1 OF 10" in source
    assert "CONNECTED BUILD" in source


def test_step1_uses_verified_espn_slate_and_phoenix_display_only():
    source = _read(PAGE)
    assert "from nfl_hub_v1 import ET, load_nfl_slate" in source
    assert 'PHOENIX_TZ_NAME = "America/Phoenix"' in source
    assert "Exact ESPN event identity" in source
    assert "Phoenix" in source
    assert "away_logo" in source
    assert "home_logo" in source
    assert "away_record" in source
    assert "home_record" in source
    assert "venue" in source
    assert "broadcast" in source


def test_step1_does_not_wire_fanduel_or_projection_yet():
    source = _read(PAGE)
    assert "nfl_game_totals_market_v1" not in source
    assert "fetch_nfl_game_totals" not in source
    assert "LIVE MARKET • STEP 2" in source
    assert "PROJECTION • STEP 8" in source


def test_nfl_hub_routes_only_game_total_to_new_page_and_preserves_other_markets():
    source = _read(NFL_HUB)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v1 import render_nfl_game_totals_hub" in source
    assert "return render_nfl_game_totals_hub()" in source
    assert "return base.render_nfl_hub(market)" in source
    assert 'if market == "Moneyline":' in source


def test_spread_v136_remains_frozen_and_delegates_non_spread_routes():
    source = _read(FROZEN_SPREAD_ROUTER)
    assert 'MODEL_VERSION = "KYRE STREAMLIT ROUTER V136' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v135"' in source
    assert "ACTIVE_SPREAD_V135_DEPENDENCY = False" in source
    assert "return _load_frozen_non_spread().render_app()" in source
