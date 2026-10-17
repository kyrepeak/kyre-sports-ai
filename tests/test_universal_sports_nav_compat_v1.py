from importlib import import_module
from importlib.util import find_spec

from universal_sports_nav_controller_v1 import RouteState


def _compat():
    assert find_spec("universal_sports_nav_compat_v1") is not None, (
        "universal_sports_nav_compat_v1 must exist"
    )
    return import_module("universal_sports_nav_compat_v1")


def _state(sport, market):
    return RouteState(sport, market, "tap", 1, {sport: market})


def test_apply_legacy_route_state_translates_all_sports_without_erasing_other_memory():
    compat = _compat()
    cases = [
        ("nfl", "spread", "NFL", "ks_nfl_market_touch", "Spread"),
        ("cfb", "game-total", "College Football", "ks_cfb_market_touch", "Game Total"),
        ("nba", "spread", "NBA", "ks_nba_market_touch", "Spread"),
        ("mlb", "moneyline", "MLB", "ks_mlb_market_touch", "Moneyline"),
        ("wnba", "pra", "WNBA", "ks_wnba_market_touch", "PRA"),
    ]
    for sport, market, legacy_sport, key, legacy_market in cases:
        session = {"ks_nfl_market_touch": "Moneyline", "page_player": "keep"}
        changed = compat.apply_legacy_route_state(_state(sport, market), session)
        assert session["ks_sport_touch"] == legacy_sport
        assert session[key] == legacy_market
        assert session["page_player"] == "keep"
        assert "ks_sport_touch" in changed


def test_mlb_live_odds_flag_is_owned_by_registry_mapping():
    compat = _compat()
    session = {}
    compat.apply_legacy_route_state(_state("mlb", "live-odds"), session)
    assert session["ks_mlb_live_odds_route"] is True
    compat.apply_legacy_route_state(_state("mlb", "slate"), session)
    assert session["ks_mlb_live_odds_route"] is False


def test_bridge_suppresses_only_known_top_level_navigation_selectboxes():
    compat = _compat()
    calls = []
    def delegate(label, options, *args, **kwargs):
        calls.append((label, tuple(options)))
        return options[0]

    bridge = compat.make_legacy_selectbox_bridge(delegate, _state("nfl", "spread"))
    assert bridge("🏟️ Sport", ["MLB", "WNBA", "NFL"]) == "NFL"
    assert bridge("🎯 NFL Market", ["Slate", "Moneyline", "Spread"]) == "Spread"
    assert calls == []

    assert bridge("📅 Date", ["2026-10-18", "2026-10-19"]) == "2026-10-18"
    assert bridge("Player", ["A", "B"]) == "A"
    assert bridge("Game", ["G1", "G2"]) == "G1"
    assert [c[0] for c in calls] == ["📅 Date", "Player", "Game"]


def test_known_top_level_labels_contract_is_exact():
    compat = _compat()
    assert compat.LEGACY_TOP_LEVEL_LABELS == frozenset({
        "🏟️ Sport", "🎯 NFL Market", "🎯 CFB Market", "🎯 NBA Market",
        "🎯 MLB Market", "🎯 WNBA Market",
    })
