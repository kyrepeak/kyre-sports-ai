from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v2.py"
CLIENT = ROOT / "sports_api" / "nfl_game_totals_page_client_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_step2_page_contract_exists_and_advances_build_state():
    assert PAGE.exists(), "Step 2 page module has not been implemented yet"
    source = _read(PAGE)
    assert 'MODEL_VERSION = "NFL GAME TOTALS V2' in source
    assert "PAGE_BUILD_STEP = 2" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "LIVE_MARKET_ENABLED = True" in source
    assert "PROJECTION_MODEL_ENABLED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STEP 2 OF 10" in source
    assert '"1", "VERIFIED SLATE", True' in source
    assert '"2", "LIVE TOTAL", True' in source


def test_step2_uses_hosted_game_totals_api_by_exact_espn_event_id():
    assert CLIENT.exists(), "Step 2 hosted API client has not been implemented yet"
    source = _read(CLIENT)
    assert 'DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"' in source
    assert 'API_PATH = "/api/v1/nfl/totals/market"' in source
    assert 'NFL_GAME_TOTALS_API_BASE_URL' in source
    assert 'event_id' in source
    assert 'exact_espn_event_id' in source
    assert 'nfl-game-totals-market-v1' in source
    assert 'sportsbook_projection_weight' in source
    assert 'wager_actions_enabled' in source


def test_step2_market_card_shows_total_prices_and_status_without_projection():
    source = _read(PAGE)
    for token in (
        "FANDUEL • LIVE MARKET",
        "TOTAL",
        "OVER",
        "UNDER",
        "MARKET UNAVAILABLE",
        "ACTIVE",
        "captured_at_utc",
        "updated_at_utc",
        "provider_event_id",
    ):
        assert token in source
    assert "TOTAL PROJECTION • STEP 8" in source
    assert "projection remains OFF" in source


def test_step2_client_fails_closed_and_rejects_identity_drift():
    source = _read(CLIENT)
    assert '"ready": False' in source
    assert '"market_available": False' in source
    assert '"markets": []' in source
    assert "payload event_id did not match requested ESPN event_id" in source
    assert "identity_mode did not remain exact_espn_event_id" in source
    assert "sportsbook projection weight changed from 0.0" in source
    assert "wager actions unexpectedly enabled" in source


def test_existing_nfl_router_advances_only_game_total_to_v2():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v2 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source
