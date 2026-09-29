from __future__ import annotations

from pathlib import Path

import wnba_pra_navigation_v2_step1 as nav


NAV_SOURCE = Path("wnba_pra_navigation_v2_step1.py").read_text(encoding="utf-8")
ROUTER = Path("streamlit_memory_lazy_router_wnba_nav_v2_step1.py").read_text(encoding="utf-8")
APP = Path("app.py").read_text(encoding="utf-8")


class _FakeQuery(dict):
    pass


class _FakeState(dict):
    pass


class _FakeStreamlit:
    def __init__(self):
        self.query_params = _FakeQuery()
        self.session_state = _FakeState()


def test_navigation_contract_is_three_level_lazy_and_math_safe():
    contract = nav.NAVIGATION_CONTRACT
    assert contract["step"] == "1/7"
    assert contract["three_levels"] == ["slate", "game", "player"]
    assert contract["default_level"] == "slate"
    assert contract["heavy_modules_prefetched"] is False
    assert contract["page2_prefetched_from_page1"] is False
    assert contract["page3_prefetched_from_page1"] is False
    assert contract["page3_prefetched_from_page2"] is False
    assert contract["legacy_surface_preserved_until_step2"] is True
    assert contract["api_ownership_changed"] is False
    assert contract["projection_math_changed"] is False
    assert contract["market_math_changed"] is False
    assert contract["ranking_changed"] is False
    assert contract["qualification_changed"] is False
    assert contract["monte_carlo_changed"] is False
    assert contract["sportsbook_projection_influence"] == 0.0


def test_normalize_state_fails_closed_to_nearest_valid_parent():
    assert nav.normalize_state("garbage") == nav.NavigationState()
    assert nav.normalize_state("game") == nav.NavigationState()
    assert nav.normalize_state("game", "game-1") == nav.NavigationState(
        page="game", game_id="game-1"
    )
    assert nav.normalize_state("player", "game-1") == nav.NavigationState(
        page="game", game_id="game-1"
    )
    assert nav.normalize_state("player", "game-1", "player-9") == nav.NavigationState(
        page="player", game_id="game-1", player_id="player-9"
    )


def test_back_state_moves_one_level_at_a_time():
    player = nav.NavigationState(page="player", game_id="g1", player_id="p1")
    game = nav.back_state(player)
    assert game == nav.NavigationState(page="game", game_id="g1")
    assert nav.back_state(game) == nav.NavigationState()
    assert nav.back_state(nav.NavigationState()) == nav.NavigationState()


def test_session_and_query_navigation_round_trip(monkeypatch):
    fake = _FakeStreamlit()
    monkeypatch.setattr(nav, "st", fake)

    game = nav.go_to_game("401234")
    assert game.page == "game"
    assert fake.session_state[nav.SESSION_GAME] == "401234"
    assert fake.query_params[nav.QUERY_PAGE] == "game"
    assert fake.query_params[nav.QUERY_GAME] == "401234"

    player = nav.go_to_player("401234", "athlete-7")
    assert player.page == "player"
    assert fake.session_state[nav.SESSION_PLAYER] == "athlete-7"
    assert fake.query_params[nav.QUERY_PLAYER] == "athlete-7"

    resolved = nav.current_state()
    assert resolved == player

    back = nav.go_back()
    assert back.page == "game"
    assert back.game_id == "401234"
    assert nav.QUERY_PLAYER not in fake.query_params

    slate = nav.go_to_slate()
    assert slate == nav.NavigationState()
    assert nav.QUERY_GAME not in fake.query_params
    assert nav.QUERY_PLAYER not in fake.query_params


def test_step1_dispatch_calls_frozen_renderer_once_and_records_zero_prefetch(monkeypatch):
    fake = _FakeStreamlit()
    monkeypatch.setattr(nav, "st", fake)
    calls = []

    result = nav.render_step1_foundation(lambda: calls.append("legacy") or "ok")

    assert result == "ok"
    assert calls == ["legacy"]
    perf = fake.session_state[nav.PERF_KEY]
    assert perf["page"] == "slate"
    assert perf["future_page_prefetches"] == 0
    assert perf["dispatch_ms_before_legacy"] >= 0.0


def test_step1_navigation_module_has_no_heavy_or_product_imports():
    assert "import pandas" not in NAV_SOURCE
    assert "requests." not in NAV_SOURCE
    assert "import wnba_" not in NAV_SOURCE
    assert "from wnba_" not in NAV_SOURCE
    assert "market_snapshot(" not in NAV_SOURCE
    assert "import monte" not in NAV_SOURCE.lower()
    assert "from monte" not in NAV_SOURCE.lower()


def test_wnba_nav_router_owns_only_wnba_pra_and_delegates_other_wnba_markets():
    assert 'OWNED_SPORT = "WNBA"' in ROUTER
    assert 'OWNED_MARKET = "PRA"' in ROUTER
    assert "if normalized != OWNED_MARKET:" in ROUTER
    assert "return frozen_renderer(market)" in ROUTER
    assert "navigation.render_step1_foundation" in ROUTER
    assert "return prior.render_app()" in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_app_activates_semantic_wnba_router_and_preserves_v245_compatibility():
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step1 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V245 compatibility" in APP
