from __future__ import annotations

import json
from pathlib import Path

import cfb_player_props_action_v1 as action
import cfb_player_props_fanduel_bound_v2 as fanduel_v2
import cfb_player_props_page2_completeness_v1 as completeness
from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_page2_roster_v1 import Page2Player

ROOT = Path(__file__).resolve().parents[1]


def _player() -> Page2Player:
    return Page2Player(CanonicalPlayerIdentity(
        "roman-16", "mtsu-1", "Roman Gagliano", "QB",
        "Middle Tennessee", "MTSU",
    ), jersey_number="16", class_year="Sophomore")


def _context():
    return {
        "state": "ready",
        "official_game_id": "401999001",
        "slate_date": "2026-10-20",
        "away_team_id": "mtsu-1",
        "home_team_id": "fiu-1",
        "away_team": "Middle Tennessee",
        "home_team": "FIU",
        "kickoff_iso": "2026-10-20T23:00:00Z",
        "game": {
            "official_game_id": "401999001",
            "game_date": "2026-10-20",
            "away_team_id": "mtsu-1",
            "home_team_id": "fiu-1",
            "away_team": "Middle Tennessee",
            "home_team": "FIU",
            "kickoff_iso": "2026-10-20T23:00:00Z",
        },
    }


def test_fanduel_v2_binds_provider_event_to_verified_game(monkeypatch):
    payload = {
        "attachments": {
            "events": {
                "fd-game": {
                    "eventId": "fd-game",
                    "name": "Middle Tennessee @ FIU",
                    "openDate": "2026-10-20T23:00:00Z",
                }
            },
            "markets": {
                "m1": {
                    "marketId": "m1",
                    "eventId": "fd-game",
                    "marketName": "Passing Yards",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        {"participantId": "fd-roman", "runnerName": "Roman Gagliano", "result": {"type": "OVER"}, "handicap": 194.5, "americanOdds": -114},
                        {"participantId": "fd-roman", "runnerName": "Roman Gagliano", "result": {"type": "UNDER"}, "handicap": 194.5, "americanOdds": -114},
                    ],
                }
            },
        }
    }
    monkeypatch.setattr(fanduel_v2, "_fetch_payload", lambda: payload)
    rows = fanduel_v2.fetch_fanduel_cfb_player_props([_context()["game"]])
    assert len(rows) == 2
    assert {row["official_game_id"] for row in rows} == {"401999001"}
    assert {row["away_team"] for row in rows} == {"Middle Tennessee"}
    assert {row["home_team"] for row in rows} == {"FIU"}
    assert {row["event_start"] for row in rows} == {"2026-10-20T23:00:00Z"}


def test_action_parser_extracts_verified_prop_rows_from_next_data():
    payload = {
        "props": {"pageProps": {"playerProps": [{
            "game": {
                "id": "an-game", "start_time": "2026-10-20T23:00:00Z",
                "away_team": {"display_name": "Middle Tennessee"},
                "home_team": {"display_name": "FIU"},
            },
            "player": {"id": "272129", "full_name": "Roman Gagliano", "team": {"display_name": "Middle Tennessee"}},
            "market": {"id": "an-pass", "name": "Pass Yds", "stat_key": "passing_yards"},
            "book": {"display_name": "FanDuel"},
            "side": "over", "line": 194.5, "odds": -114,
        }]}}
    }
    html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + '</script>'
    rows = action.parse_action_props_page(html, observed_at_utc="2026-10-20T17:10:00Z")
    assert len(rows) == 1
    row = rows[0]
    assert row["player_name"] == "Roman Gagliano"
    assert row["stat_id"] == "passing_yards"
    assert row["line"] == 194.5
    assert row["sportsbook"] == "FanDuel"
    assert row["away_team"] == "Middle Tennessee"
    assert row["home_team"] == "FIU"


def test_completeness_merges_sources_and_recovers_missing_player(monkeypatch):
    player = _player()
    context = _context()
    base = {
        "official_game_id": "401999001", "official_player_id": "roman-16",
        "official_team_id": "mtsu-1", "player_name": "Roman Gagliano",
        "stat_id": "passing_yards", "observed_at_utc": "2026-10-20T17:10:00Z",
        "provider_event_id": "source-game", "provider_player_id": "source-player",
        "provider_market_id": "source-market",
    }
    monkeypatch.setattr(completeness.sgo, "fetch_sgo_cfb_player_props", lambda day: [])
    monkeypatch.setattr(completeness.fanduel, "fetch_fanduel_cfb_player_props", lambda games: [
        {**base, "provider": "FanDuel", "sportsbook": "FanDuel", "side": "over", "line": 194.5, "price": -114},
        {**base, "provider": "FanDuel", "sportsbook": "FanDuel", "side": "under", "line": 194.5, "price": -114},
    ])
    monkeypatch.setattr(completeness.action, "fetch_action_cfb_player_props", lambda: [
        {**base, "provider": "ActionNetwork", "sportsbook": "DraftKings", "side": "over", "line": 193.5, "price": -110},
        {**base, "provider": "ActionNetwork", "sportsbook": "DraftKings", "side": "under", "line": 193.5, "price": -110},
    ])
    observations, diagnostics = completeness.load_game_prop_observations_with_diagnostics(context, [player])
    assert len(observations) == 4
    assert {row.sportsbook for row in observations} == {"FanDuel", "DraftKings"}
    assert diagnostics["players_with_markets"] == 1
    assert diagnostics["market_count"] == 1
    assert diagnostics["sportsbook_count"] == 2
    assert diagnostics["provider_count"] == 2


def test_coverage_summary_is_professional_and_fail_closed():
    summary = completeness.build_coverage_summary([], [_player()])
    assert summary == {
        "players_with_markets": 0,
        "roster_players": 1,
        "market_count": 0,
        "sportsbook_count": 0,
        "provider_count": 0,
        "freshest_observed_at_utc": "",
    }


def test_page2_uses_completeness_owner_and_market_coverage_bar():
    source = (ROOT / "cfb_player_props_page2_v1.py").read_text()
    assert "cfb_player_props_page2_completeness_v1 as completeness_owner" in source
    assert "load_game_prop_observations_with_diagnostics" in source
    assert "Market Coverage" in source
    assert "players with lines" in source
    assert "sportsbooks" in source


def test_projection_math_remains_book_independent():
    source = (ROOT / "cfb_player_props_page2_completeness_v1.py").read_text()
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    page = (ROOT / "cfb_player_props_page2_v1.py").read_text()
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE" in page
