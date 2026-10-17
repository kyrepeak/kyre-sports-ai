from importlib import import_module
from importlib.util import find_spec

from universal_sports_nav_controller_v1 import RouteState


def _url():
    assert find_spec("universal_sports_nav_url_v1") is not None, (
        "universal_sports_nav_url_v1 must exist"
    )
    return import_module("universal_sports_nav_url_v1")


def test_parse_canonical_query_handles_scalar_and_list_values():
    url = _url()
    parsed = url.parse_canonical_query({"sport": ["mlb", "nfl"], "market": ["moneyline", "spread"], "date": "2026-10-18"})
    assert (parsed.sport_id, parsed.market_id) == ("nfl", "spread")
    assert parsed.page_params == {"date": "2026-10-18"}


def test_legacy_query_normalizes_to_canonical_route():
    url = _url()
    parsed = url.normalize_legacy_query(
        {"ks_sport": "College Football", "ks_cfb_market": "Game Total", "game_id": "401", "date": "2026-10-18"},
        {},
    )
    assert (parsed.sport_id, parsed.market_id) == ("cfb", "game-total")
    assert parsed.page_params == {"game_id": "401", "date": "2026-10-18"}


def test_newer_universal_session_state_beats_stale_legacy_query():
    url = _url()
    parsed = url.normalize_legacy_query(
        {"ks_sport": "College Football", "ks_cfb_market": "Game Total"},
        {"ks_universal_sport": "nba", "ks_universal_market": "spread", "ks_universal_nav_source": "tap"},
    )
    assert (parsed.sport_id, parsed.market_id) == ("nba", "spread")


def test_query_patch_is_idempotent_and_removes_legacy_universal_keys():
    url = _url()
    state = RouteState("nfl", "spread", "tap", 2, {"nfl": "spread"})
    query = {"sport": "nfl", "market": "spread", "ks_sport": "NFL", "ks_nfl_market": "Moneyline"}
    patch = url.query_patch_for_state(state, query)
    assert patch.set_values == ()
    assert set(patch.delete_keys) == {"ks_sport", "ks_nfl_market"}
    assert url.apply_query_patch(query, patch) is True
    assert query == {"sport": "nfl", "market": "spread"}
    assert url.apply_query_patch(query, url.query_patch_for_state(state, query)) is False


def test_page_params_preserved_only_when_valid_for_destination():
    url = _url()
    cfb = RouteState("cfb", "game-total", "tap", 1, {"cfb": "game-total"})
    q = {"sport": "mlb", "market": "one-plus-hit", "date": "2026-10-18", "game_id": "401", "player_id": "p9"}
    patch = url.query_patch_for_state(cfb, q)
    assert "date" not in patch.delete_keys
    assert "game_id" not in patch.delete_keys
    assert "player_id" in patch.delete_keys

    nba = RouteState("nba", "spread", "tap", 2, {"nba": "spread"})
    q2 = {"sport": "nfl", "market": "passing-yards", "player_id": "qb1", "date": "2026-10-18"}
    patch2 = url.query_patch_for_state(nba, q2)
    assert "player_id" in patch2.delete_keys
    assert "date" not in patch2.delete_keys


def test_apply_query_patch_writes_canonical_route_once():
    url = _url()
    state = RouteState("wnba", "pra", "tap", 4, {"wnba": "pra"})
    query = {"date": "2026-10-18"}
    patch = url.query_patch_for_state(state, query)
    assert dict(patch.set_values) == {"sport": "wnba", "market": "pra"}
    assert url.apply_query_patch(query, patch) is True
    assert query["sport"] == "wnba" and query["market"] == "pra"
