from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
PAGE = ROOT / "cfb_game_total_clean_page_v40.py"


def test_step3_native_page1_shell_contract() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "CFB_GAME_TOTAL_NATIVE_PAGE1_SHELL_STEP3_ACTIVE" in source
    assert "data-testid=\"gt240-native-page1-shell\"" in source
    assert "College Football" in source
    assert "Game Total" in source
    assert "KYRE SPORTS AI" in source
    assert "cfb_game_total_clean_page_v39" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_MARKET_OWNERSHIP = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "MAY_MODIFY_PAGE2 = False" in source
    assert "NETWORK_CALLS_ADDED = 0" in source


def test_step3_router_advances_only_page1_owner() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v40"' in source
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in source
    assert "install_games_on_day_step2_visual()" in source
    assert "install_games_on_day_step3_details()" in source
    assert "install_games_on_day_step4_interaction_mobile()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step3_does_not_own_future_day_selector() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "ZoneInfo" not in source
    assert "query_params" not in source
    assert "st.button" not in source
    assert "st.rerun" not in source
