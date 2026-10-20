from __future__ import annotations

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import PropObservation
from cfb_player_props_page2_roster_v1 import Page2Player


def _player(pid="p1", team="101", name="Player One", pos="QB"):
    return Page2Player(CanonicalPlayerIdentity(pid, team, name, pos, "Away State", "AWY"))


def _obs(book, side, line, price=-110, *, stamp="2026-10-20T04:00:00Z", player="p1", market="passing_yards"):
    return PropObservation(
        "401999001", player, "Player One", "101", market, book, side,
        float(line), price, stamp, "SportsGameOdds", f"evt-{book}", player,
        f"odd-{book}-{side}", True,
    )


def _context():
    return {
        "state": "ready", "official_game_id": "401999001", "slate_date": "2026-10-24",
        "away_team_id": "101", "away_team": "Away State",
        "home_team_id": "202", "home_team": "Home Tech",
        "kickoff_iso": "2026-10-24T19:30:00-04:00",
        "game": {
            "official_game_id": "401999001", "game_date": "2026-10-24",
            "away_team_id": "101", "away_team": "Away State",
            "home_team_id": "202", "home_team": "Home Tech",
            "kickoff_iso": "2026-10-24T19:30:00-04:00",
        },
    }


def test_best_over_is_lowest_line_and_best_under_is_highest_then_better_price():
    import cfb_player_props_page2_market_v1 as market

    rows = [
        _obs("FanDuel", "over", 250.5, -115),
        _obs("DraftKings", "over", 248.5, -120),
        _obs("BetMGM", "over", 248.5, -105),
        _obs("FanDuel", "under", 250.5, -115),
        _obs("DraftKings", "under", 252.5, -120),
        _obs("Caesars", "under", 252.5, +105),
    ]
    view = market.build_player_market_view(_player(), "passing_yards", rows)
    assert view["best_over"] == {"sportsbook": "BetMGM", "line": 248.5, "price": -105}
    assert view["best_under"] == {"sportsbook": "Caesars", "line": 252.5, "price": 105}
    assert view["book_count"] == 4
    assert view["consensus_line"] is not None


def test_stale_same_book_side_never_overwrites_fresher_quote():
    import cfb_player_props_page2_market_v1 as market

    rows = [
        _obs("FanDuel", "over", 245.5, -110, stamp="2026-10-20T03:00:00Z"),
        _obs("FanDuel", "over", 249.5, -108, stamp="2026-10-20T04:00:00Z"),
    ]
    view = market.build_player_market_view(_player(), "passing_yards", rows)
    assert view["best_over"]["line"] == 249.5
    assert len(view["observations"]) == 1


def test_movement_fails_closed_without_explicit_trusted_opening_evidence():
    import cfb_player_props_page2_market_v1 as market

    rows = [_obs("FanDuel", "over", 249.5, -110)]
    assert market.build_player_market_view(_player(), "passing_yards", rows)["movement"]["available"] is False
    first_seen = [{
        "canonical_player_id": "p1", "market_key": "passing_yards", "sportsbook": "FanDuel",
        "opening_line": 245.5, "source": "session-first-seen",
    }]
    assert market.build_player_market_view(_player(), "passing_yards", rows, opening_rows=first_seen)["movement"]["available"] is False


def test_verified_opening_and_current_same_book_exposes_truthful_delta():
    import cfb_player_props_page2_market_v1 as market

    rows = [_obs("FanDuel", "over", 249.5, -110)]
    opening = [{
        "canonical_player_id": "p1", "market_key": "passing_yards", "sportsbook": "FanDuel",
        "opening_line": 245.5, "opening_verified": True, "source": "provider-opening",
    }]
    movement = market.build_player_market_view(_player(), "passing_yards", rows, opening_rows=opening)["movement"]
    assert movement["available"] is True
    assert movement["opening_line"] == 245.5
    assert movement["current_line"] == 249.5
    assert movement["delta"] == 4.0
    assert movement["source"] == "provider-opening"


def test_game_aggregation_calls_each_provider_once_and_keeps_exact_game_players_only(monkeypatch):
    import cfb_player_props_page2_market_v1 as market

    calls = {"sgo": 0, "fd": 0}
    raws = [
        {
            "provider": "SportsGameOdds", "provider_event_id": "sgo-1", "provider_player_id": "x",
            "provider_market_id": "m1", "player_name": "Player One", "stat_id": "passing_yards",
            "sportsbook": "DraftKings", "side": "over", "line": 250.5, "price": -110,
            "observed_at_utc": "2026-10-20T04:00:00Z", "away_team": "Away State",
            "home_team": "Home Tech", "event_start": "2026-10-24T23:30:00Z",
        }
    ]
    monkeypatch.setattr(market.sgo, "fetch_sgo_cfb_player_props", lambda day: calls.__setitem__("sgo", calls["sgo"] + 1) or raws)
    monkeypatch.setattr(market.fanduel, "fetch_fanduel_cfb_player_props", lambda games: calls.__setitem__("fd", calls["fd"] + 1) or [])
    monkeypatch.setattr(
        market.game_identity,
        "_qualified_candidates",
        lambda provider_game, verified: (None, [{"verified": verified[0]}]),
    )

    out = market.load_game_prop_observations(_context(), [_player(), _player("p2", "202", "Home Runner", "RB")])
    assert calls == {"sgo": 1, "fd": 1}
    assert len(out) == 1
    assert out[0].official_game_id == "401999001"
    assert out[0].canonical_player_id == "p1"


def test_all_six_frozen_market_keys_group_without_inventing_rows():
    import cfb_player_props_page2_market_v1 as market

    keys = (
        "passing_yards", "rushing_yards", "receiving_yards",
        "receiving_receptions", "passing_touchdowns", "touchdowns",
    )
    rows = [_obs(f"Book-{idx}", "over", idx + 0.5, market=key) for idx, key in enumerate(keys, 1)]
    grouped = market.group_player_markets([_player()], rows)
    assert [item["market_key"] for item in grouped["p1"]] == list(keys)
    assert grouped.get("missing", []) == []
