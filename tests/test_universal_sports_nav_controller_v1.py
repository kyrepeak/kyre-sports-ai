from importlib import import_module
from importlib.util import find_spec


def _controller():
    assert find_spec("universal_sports_nav_controller_v1") is not None, (
        "universal_sports_nav_controller_v1 must exist"
    )
    return import_module("universal_sports_nav_controller_v1")


def test_fresh_session_uses_preserved_mlb_slate_default():
    nav = _controller()
    state = nav.resolve_route()
    assert (state.sport_id, state.market_id, state.source, state.epoch) == ("mlb", "slate", "default", 0)


def test_valid_canonical_cold_start_beats_memory_and_legacy():
    nav = _controller()
    state = nav.resolve_route(
        canonical_sport="nfl",
        canonical_market="spread",
        last_market_by_sport={"nfl": "moneyline"},
        legacy_sport="MLB",
        legacy_market="Slate",
    )
    assert (state.sport_id, state.market_id, state.source) == ("nfl", "spread", "canonical_url")


def test_explicit_tap_beats_stale_canonical_and_legacy():
    nav = _controller()
    intent = nav.RouteIntent(sport_id="nba", market_id="spread", source="tap")
    state = nav.resolve_route(
        intent=intent,
        canonical_sport="cfb",
        canonical_market="game-total",
        legacy_sport="College Football",
        legacy_market="Game Total",
        epoch=7,
    )
    assert (state.sport_id, state.market_id, state.source, state.epoch) == ("nba", "spread", "tap", 8)


def test_sport_tap_restores_last_live_market_or_default():
    nav = _controller()
    current = nav.RouteState("mlb", "slate", "default", 3, {"nfl": "spread", "cfb": "not-live"})
    nfl = nav.apply_sport_intent(current, "nfl")
    assert (nfl.sport_id, nfl.market_id, nfl.epoch) == ("nfl", "spread", 4)
    cfb = nav.apply_sport_intent(nfl, "cfb")
    assert (cfb.sport_id, cfb.market_id, cfb.epoch) == ("cfb", "moneyline", 5)


def test_market_tap_updates_only_active_sport_memory():
    nav = _controller()
    state = nav.RouteState("nfl", "slate", "default", 2, {"mlb": "moneyline", "nfl": "slate"})
    changed = nav.apply_market_intent(state, "spread")
    assert changed.market_id == "spread"
    assert changed.epoch == 3
    assert dict(changed.last_market_by_sport) == {"mlb": "moneyline", "nfl": "spread"}


def test_epoch_changes_only_when_route_changes():
    nav = _controller()
    state = nav.RouteState("nfl", "spread", "tap", 9, {"nfl": "spread"})
    same_sport = nav.apply_sport_intent(state, "nfl")
    same_market = nav.apply_market_intent(state, "spread")
    assert same_sport.epoch == 9
    assert same_market.epoch == 9
    assert nav.remembered_market(state, "nfl") == "spread"


def test_invalid_canonical_fails_closed_to_live_defaults():
    nav = _controller()
    state = nav.resolve_route(canonical_sport="nfl", canonical_market="not-real", last_market_by_sport={"nfl": "not-live"})
    assert (state.sport_id, state.market_id) == ("nfl", "daily-picks")
