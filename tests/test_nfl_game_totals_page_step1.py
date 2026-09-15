from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v137.py"
APP = ROOT / "app.py"


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


def test_v137_routes_only_game_total_and_preserves_v136():
    assert ROUTER.exists(), "V137 Game Total router has not been implemented yet"
    source = _read(ROUTER)
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v136"' in source
    assert 'ACTIVE_GAME_TOTAL_HUB = "nfl_game_totals_hub_v1"' in source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "return _load_frozen_non_game_total().render_app()" in source


def test_streamlit_entrypoint_advances_to_v137_without_rewriting_v136():
    source = _read(APP)
    assert "streamlit_memory_lazy_router_v137" in source
    assert "STREAMLIT_MAIN_V137_NFL_GAME_TOTALS_STEP1_FOUNDATION_2026-09-15" in source
    assert "streamlit_memory_lazy_router_v136" in source
