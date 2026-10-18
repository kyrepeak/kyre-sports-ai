from importlib import import_module
from importlib.util import find_spec


def _registry():
    assert find_spec("universal_sports_nav_registry_v1") is not None, (
        "universal_sports_nav_registry_v1 must exist"
    )
    return import_module("universal_sports_nav_registry_v1")


def test_registry_has_exact_live_sport_order_and_defaults():
    nav = _registry()
    sports = nav.visible_sports()
    assert tuple(s.id for s in sports) == ("nfl", "cfb", "nba", "mlb", "wnba")
    assert nav.DEFAULT_SPORT_ID == "mlb"
    assert {s.id: s.default_market_id for s in sports} == {
        "nfl": "slate",
        "cfb": "moneyline",
        "nba": "spread",
        "mlb": "slate",
        "wnba": "pra",
    }


def test_registry_market_inventory_is_live_only_and_exact():
    nav = _registry()
    expected = {
        "nfl": ("slate", "moneyline", "spread", "game-total", "passing-yards", "rushing-yards", "receiving-yards", "receptions", "passing-tds", "anytime-td", "daily-picks"),
        "cfb": ("moneyline", "over-under", "game-total", "top-picks"),
        "nba": ("spread",),
        "mlb": ("slate", "one-plus-hit", "home-run", "hits-runs-rbis", "pitcher-strikeouts", "matchup-explorer", "daily-game-picks", "moneyline", "run-line", "game-total", "live-game", "live-odds"),
        "wnba": ("points", "rebounds", "assists", "rebounds-assists", "pra", "spread", "moneyline", "game-total", "daily-picks"),
    }
    for sport in nav.visible_sports():
        assert tuple(m.id for m in sport.markets if m.live) == expected[sport.id]
    assert nav.get_market("mlb", "two-plus-hits") is None


def test_registry_uses_exact_legacy_identity_contracts():
    nav = _registry()
    assert {s.id: s.legacy_sport for s in nav.visible_sports()} == {
        "nfl": "NFL",
        "cfb": "College Football",
        "nba": "NBA",
        "mlb": "MLB",
        "wnba": "WNBA",
    }
    assert nav.get_market("nfl", "passing-yards").legacy_market == "Passing Yards"
    assert nav.get_market("cfb", "over-under").legacy_market == "Over/Under"
    assert nav.get_market("cfb", "top-picks").legacy_market == "Top Picks"
    assert nav.get_market("cfb", "top-picks").legacy_market_key == "ks_cfb_market_touch"
    assert nav.get_market("mlb", "hits-runs-rbis").legacy_market == "Hits + Runs + RBIs"
    assert nav.get_market("wnba", "rebounds-assists").legacy_market == "Rebounds + Assists"
    assert nav.get_market("nba", "spread").legacy_market_key == "ks_nba_market_touch"


def test_registry_mlb_live_odds_flag_contract():
    nav = _registry()
    live = nav.get_market("mlb", "live-odds")
    assert ("ks_mlb_live_odds_route", True) in live.legacy_flags
    for market in nav.get_sport("mlb").markets:
        if market.id != "live-odds":
            assert ("ks_mlb_live_odds_route", False) in market.legacy_flags


def test_registry_validation_rejects_no_current_contract():
    nav = _registry()
    assert nav.validate_registry() == ()
    for sport in nav.visible_sports():
        assert nav.get_market(sport.id, sport.default_market_id).live is True
        assert sport.markets
        ids = [m.id for m in sport.markets]
        legacy = [(m.legacy_market, m.legacy_market_key) for m in sport.markets]
        assert len(ids) == len(set(ids))
        assert len(legacy) == len(set(legacy))
        for market in sport.markets:
            assert market.legacy_market
            assert market.legacy_market_key
