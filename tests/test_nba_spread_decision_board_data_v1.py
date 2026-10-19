from __future__ import annotations

import importlib
import importlib.util
from datetime import datetime, timezone

NOW = datetime(2026, 10, 19, 22, 0, 0, tzinfo=timezone.utc)


def _module():
    spec = importlib.util.find_spec("nba_spread_decision_board_data_v1")
    assert spec is not None, "nba_spread_decision_board_data_v1 must exist"
    return importlib.import_module("nba_spread_decision_board_data_v1")


def _game(*, fair=True, cover=True, play=False):
    game = {
        "game_key": "BOS@DET:2026-10-20",
        "game_date_phoenix": "2026-10-20",
        "away_tricode": "BOS",
        "home_tricode": "DET",
        "away_name": "Boston Celtics",
        "home_name": "Detroit Pistons",
        "status": "UPCOMING",
        "tip_phoenix": "4:00 PM MST",
    }
    if fair:
        game["step9_fair_spread"] = {
            "verification": "VERIFIED",
            "diagnostic_state": "PREGAME_MODEL_CAPTURED",
            "pregame_model": {
                "verification": "VERIFIED",
                "cover_verification": "VERIFIED" if cover else "UNAVAILABLE",
                "fair_away_spread": -3.0,
                "fair_home_spread": 3.0,
                "away_cover_probability": 0.58 if cover else None,
                "home_cover_probability": 0.42 if cover else None,
                "sportsbook_projection_influence": 0.0,
            },
        }
    else:
        game["step9_fair_spread"] = {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "INSUFFICIENT_VERIFIED_HISTORY",
            "pregame_model": None,
        }
    game["step10_decision"] = {
        "verification": "VERIFIED" if play else "UNAVAILABLE",
        "decision_state": "PLAY" if play else "NO_PLAY",
        "pick_text": "BOS -1.5" if play else "NO PLAY",
        "pick_strength": "LEAN" if play else "NO PLAY",
        "production_grade": "C" if play else "WATCH",
        "slate_rank": 1 if play else None,
        "spread_edge_points": 1.5 if play else 0.0,
    }
    return game


def _market(rows):
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "source": "SportsGameOdds",
        "observations": rows,
    }


def _row(book, away, home, *, observed="2026-10-19T21:59:00Z", away_price=None, home_price=None):
    return {
        "game_key": "BOS@DET:2026-10-20",
        "game_date_phoenix": "2026-10-20",
        "away_tricode": "BOS",
        "home_tricode": "DET",
        "sportsbook": book,
        "away_spread": away,
        "home_spread": home,
        "away_price": away_price,
        "home_price": home_price,
        "observed_at_utc": observed,
        "retrieved_at_utc": "2026-10-19T21:59:05Z",
        "source_transport": "SportsGameOdds",
    }


def _injuries():
    return {
        "verification": "VERIFIED",
        "features": [
            {
                "game_key": "BOS@DET:2026-10-20",
                "away_tricode": "BOS",
                "home_tricode": "DET",
                "verification": "VERIFIED",
                "away": {"counts": {"OUT": 1, "QUESTIONABLE": 0}, "players": [{"player_name": "A Player", "status": "OUT"}]},
                "home": {"counts": {"OUT": 2, "QUESTIONABLE": 2}, "players": []},
            }
        ],
    }


def test_two_book_consensus_is_deterministic_median_independent_of_order():
    mod = _module()
    games = [_game()]
    left = mod.build_market_by_game(games, _market([_row("FanDuel", -1.5, 1.5), _row("DraftKings", -2.5, 2.5)]), now_utc=NOW)
    right = mod.build_market_by_game(games, _market([_row("DraftKings", -2.5, 2.5), _row("FanDuel", -1.5, 1.5)]), now_utc=NOW)
    a = left["BOS@DET:2026-10-20"]
    b = right["BOS@DET:2026-10-20"]
    assert a["coverage"] == b["coverage"] == "CONSENSUS"
    assert a["sportsbook_count"] == b["sportsbook_count"] == 2
    assert a["away_spread"] == b["away_spread"] == -2.0
    assert a["home_spread"] == b["home_spread"] == 2.0


def test_one_book_is_limited_coverage_never_consensus():
    mod = _module()
    market = mod.build_market_by_game([_game()], _market([_row("FanDuel", -1.5, 1.5)]), now_utc=NOW)["BOS@DET:2026-10-20"]
    assert market["coverage"] == "LIMITED"
    assert market["sportsbook_count"] == 1
    assert market["label"] == "1 book verified"
    assert market.get("consensus") is not True


def test_fair_spread_remains_ready_when_market_and_cover_are_unavailable():
    mod = _module()
    state = mod.build_decision_board_state(
        [_game(fair=True, cover=False)],
        {"verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE", "observations": []},
        _injuries(),
        {"verification": "UNAVAILABLE", "diagnostic_state": "PUBLIC_BETTING_UNAVAILABLE"},
        now_utc=NOW,
    )
    card = state["games"][0]
    assert card["fair"]["verification"] == "VERIFIED"
    assert card["fair"]["away_spread"] == -3.0
    assert card["market"]["coverage"] == "UNAVAILABLE"
    assert card["cover"]["verification"] == "UNAVAILABLE"
    assert card["edge_points"] is None


def test_market_can_display_while_fair_model_waits_for_verified_history():
    mod = _module()
    state = mod.build_decision_board_state(
        [_game(fair=False)],
        _market([_row("FanDuel", -1.5, 1.5), _row("DraftKings", -2.0, 2.0)]),
        _injuries(),
        {"verification": "UNAVAILABLE"},
        now_utc=NOW,
    )
    card = state["games"][0]
    assert card["market"]["coverage"] == "CONSENSUS"
    assert card["fair"]["verification"] == "UNAVAILABLE"
    assert card["fair"]["reason"] == "Fair model waiting for verified history"
    assert card["cover"]["verification"] == "UNAVAILABLE"
    assert card["edge_points"] is None


def test_injuries_are_separated_by_team_and_public_pending_is_hidden():
    mod = _module()
    state = mod.build_decision_board_state(
        [_game()], _market([_row("FanDuel", -1.5, 1.5)]), _injuries(), {"verification": "UNAVAILABLE"}, now_utc=NOW
    )
    card = state["games"][0]
    assert card["injuries"]["away_summary"] == "BOS: 1 OUT"
    assert card["injuries"]["home_summary"] == "DET: 2 OUT • 2 Q"
    assert card["public_betting"] is None


def test_display_edge_uses_exact_displayed_market_and_fair_spread_only():
    mod = _module()
    state = mod.build_decision_board_state(
        [_game()], _market([_row("FanDuel", -1.5, 1.5), _row("DraftKings", -1.5, 1.5)]), _injuries(), {"verification": "UNAVAILABLE"}, now_utc=NOW
    )
    card = state["games"][0]
    assert card["edge_points"] == 1.5


def test_line_movement_uses_verified_time_order_and_calls_retained_history_first_seen():
    mod = _module()
    state = mod.build_decision_board_state(
        [_game()],
        _market([_row("FanDuel", -1.5, 1.5), _row("DraftKings", -1.5, 1.5)]),
        _injuries(),
        {"verification": "UNAVAILABLE"},
        now_utc=NOW,
        market_history={
            "BOS@DET:2026-10-20": [
                {"away_spread": -2.0, "home_spread": 2.0, "observed_at_utc": "2026-10-19T20:00:00Z", "verification": "VERIFIED"},
                {"away_spread": -1.5, "home_spread": 1.5, "observed_at_utc": "2026-10-19T21:59:00Z", "verification": "VERIFIED"},
            ]
        },
    )
    movement = state["games"][0]["line_movement"]
    assert movement["label"] == "First seen -2 → Current -1.5"
    assert "Open" not in movement["label"]


def test_best_opportunities_filters_frozen_verified_plays_without_new_ranking():
    mod = _module()
    play = _game(play=True)
    no_play = _game(play=False)
    no_play["game_key"] = "PHI@NYK:2026-10-20"
    no_play["away_tricode"] = "PHI"
    no_play["home_tricode"] = "NYK"
    state = mod.build_decision_board_state(
        [play, no_play],
        _market([_row("FanDuel", -1.5, 1.5), _row("DraftKings", -1.5, 1.5)]),
        _injuries(),
        {"verification": "UNAVAILABLE"},
        now_utc=NOW,
    )
    assert [item["game_key"] for item in state["best_opportunities"]] == ["BOS@DET:2026-10-20"]
    assert state["best_opportunities"][0]["slate_rank"] == 1
