from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from universal_page_experience_v1 import page_experience_controller_markup
from universal_sports_nav_registry_v1 import SPORTS

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _route(sport_id: str, market_id: str, params: dict[str, str] | None = None):
    return SimpleNamespace(sport_id=sport_id, market_id=market_id, params=params or {})


def test_every_live_registered_route_gets_universal_page_experience() -> None:
    seen: set[tuple[str, str]] = set()
    for sport in SPORTS:
        for market in sport.markets:
            if not market.live:
                continue
            seen.add((sport.id, market.id))
            markup = page_experience_controller_markup(_route(sport.id, market.id))
            assert "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V1__" in markup
            assert sport.id.upper() in markup
            assert 'data-kyre-universal-top="v1"' in markup
            assert 'data-kyre-universal-loading="upe-v1"' in markup
    assert seen


def test_every_declared_game_or_player_deep_route_gets_same_controller() -> None:
    checked = 0
    for sport in SPORTS:
        for market in sport.markets:
            if not market.live or not ({"game_id", "player_id"} & set(market.page_params)):
                continue
            params: dict[str, str] = {}
            if "game_id" in market.page_params:
                params["game_id"] = "coverage-game"
            if "player_id" in market.page_params:
                params["player_id"] = "coverage-player"
            markup = page_experience_controller_markup(_route(sport.id, market.id, params))
            assert "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V1__" in markup
            assert "coverage-game" not in markup
            assert "coverage-player" not in markup
            checked += 1
    assert checked > 0


def test_current_overlay_deep_pages_and_page1_page2_actions_are_covered() -> None:
    for route in (
        _route("nba", "pra"),
        _route("nba", "pra", {"player_id": "nba-player"}),
        _route("wnba", "pra", {"player_id": "wnba-player"}),
        _route("cfb", "player-props", {"player_id": "cfb-player", "prop": "passing-yards"}),
        _route("nfl", "passing-yards", {"game_id": "nfl-game", "player_id": "nfl-player"}),
    ):
        markup = page_experience_controller_markup(route).lower()
        assert "page_transition" in markup
        assert "analy" in markup
        assert "back" in markup
        assert "popstate" in markup


def test_production_terminal_chain_inherits_once_without_page_specific_patches() -> None:
    v3 = _source("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py")
    v4 = _source("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4.py")
    nba = _source("streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py")
    app = _source("app.py")

    assert "universal_page_experience_runtime_v1" in v3
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 as prior" in v4
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4 as prior" in nba
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1" in app
    assert "universal_page_experience_runtime_v1" not in nba
    assert "universal_page_experience_runtime_v1" not in app
