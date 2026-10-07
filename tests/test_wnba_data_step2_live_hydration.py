from __future__ import annotations

import json

from wnba_pra_game_center_stats_hydration_v1 import (
    build_first_party_recent_stat_payloads,
    hydrate_zero_production_rows,
    parse_first_party_player_latest_games_html,
    parse_first_party_roster_html,
)


def _payload(last_n: int, *, minutes: float, points: float, rebounds: float, assists: float):
    return {
        "data_type": "official_player_season_statistics",
        "season": 2026,
        "last_n_games": last_n,
        "players": [
            {
                "player_id": 204319,
                "player_name": "Rebecca Allen",
                "official_team_id": 1611661332,
                "team_abbreviation": "TOR",
                "games_played": 20 if last_n == 0 else last_n,
                "stats": {
                    "minutes": minutes,
                    "points": points,
                    "rebounds": rebounds,
                    "assists": assists,
                },
            }
        ],
    }


def _zero_row(name: str = "Rebecca Allen"):
    return {
        "PLAYER_ID": 999999,
        "PLAYER_NAME": name,
        "TEAM_ID": 1611661332,
        "TEAM_ABBREVIATION": "TOR",
        "GP": 0,
        "MIN": 0.0,
        "PTS": 0.0,
        "REB": 0.0,
        "AST": 0.0,
        "PRA": 0.0,
        "L10_GP": 0,
        "L10_MIN": 0.0,
        "L10_PTS": 0.0,
        "L10_REB": 0.0,
        "L10_AST": 0.0,
        "L10_PRA": 0.0,
        "L5_GP": 0,
        "L5_MIN": 0.0,
        "L5_PTS": 0.0,
        "L5_REB": 0.0,
        "L5_AST": 0.0,
        "L5_PRA": 0.0,
        "DATA_SOURCE": "Current roster • no matched production row",
        "PLAYER_ID_SOURCE": "ESPN",
    }


def test_zero_only_game_center_row_is_hydrated_from_official_hosted_stats():
    hydrated, diag = hydrate_zero_production_rows(
        [_zero_row()],
        season_payload=_payload(0, minutes=26.4, points=10.8, rebounds=3.1, assists=2.2),
        l10_payload=_payload(10, minutes=28.0, points=11.6, rebounds=3.5, assists=2.4),
        l5_payload=_payload(5, minutes=29.2, points=12.4, rebounds=3.8, assists=2.8),
        allowed_team_ids={1611661332},
    )

    row = hydrated[0]
    assert diag == {"candidates": 1, "hydrated": 1, "unresolved": 0}
    assert row["PLAYER_ID"] == 204319
    assert row["PLAYER_ID_SOURCE"] == "WNBA Stats via Kyre Sports API"
    assert row["MIN"] == 26.4
    assert row["PTS"] == 10.8
    assert row["REB"] == 3.1
    assert row["AST"] == 2.2
    assert row["PRA"] == 16.1
    assert row["L10_MIN"] == 28.0
    assert row["L10_PRA"] == 17.5
    assert row["L5_MIN"] == 29.2
    assert row["L5_PRA"] == 19.0


def test_existing_real_production_is_never_overwritten():
    rows = [{
        "PLAYER_ID": 204319,
        "PLAYER_NAME": "Rebecca Allen",
        "TEAM_ID": 1611661332,
        "MIN": 31.0,
        "PTS": 13.0,
        "REB": 4.0,
        "AST": 3.0,
        "PRA": 20.0,
        "DATA_SOURCE": "WNBA Stats",
        "PLAYER_ID_SOURCE": "WNBA Stats",
    }]
    hydrated, diag = hydrate_zero_production_rows(
        rows,
        season_payload=_payload(0, minutes=26.4, points=10.8, rebounds=3.1, assists=2.2),
        l10_payload=_payload(10, minutes=28.0, points=11.6, rebounds=3.5, assists=2.4),
        l5_payload=_payload(5, minutes=29.2, points=12.4, rebounds=3.8, assists=2.8),
        allowed_team_ids={1611661332},
    )
    assert hydrated[0]["MIN"] == 31.0
    assert hydrated[0]["PRA"] == 20.0
    assert diag == {"candidates": 0, "hydrated": 0, "unresolved": 0}


def test_unresolved_zero_row_stays_identifiable_as_unresolved_not_fake_verified_data():
    hydrated, diag = hydrate_zero_production_rows(
        [_zero_row("Unknown Player")],
        season_payload=_payload(0, minutes=26.4, points=10.8, rebounds=3.1, assists=2.2),
        l10_payload=_payload(10, minutes=28.0, points=11.6, rebounds=3.5, assists=2.4),
        l5_payload=_payload(5, minutes=29.2, points=12.4, rebounds=3.8, assists=2.8),
        allowed_team_ids={1611661332},
    )
    assert hydrated[0]["DATA_SOURCE"] == "Current roster • no matched production row"
    assert diag == {"candidates": 1, "hydrated": 0, "unresolved": 1}


def test_first_party_roster_and_latest_games_can_hydrate_when_bulk_stats_are_down():
    roster_html = """
    <html><body><script>
    {"playerId":204319,"playerName":"Rebecca Allen","teamId":"1611661332","teamAbbreviation":"TOR","playerLink":"https://www.wnba.com/player/204319"}
    </script></body></html>
    """
    roster = parse_first_party_roster_html(roster_html, 1611661332)
    assert roster == [{
        "player_id": 204319,
        "player_name": "Rebecca Allen",
        "official_team_id": 1611661332,
        "team_abbreviation": "TOR",
    }]

    next_data = {
        "props": {
            "pageProps": {
                "player": {
                    "playerId": 204319,
                    "latestGames": [
                        {"SEASON_ID":"22026","PLAYER_ID":204319,"GAME_ID":"1022600001","GAME_DATE":"OCT 04, 2026","MIN":"30:00","PTS":16,"REB":4,"AST":5},
                        {"SEASON_ID":"22026","PLAYER_ID":204319,"GAME_ID":"1022600002","GAME_DATE":"SEP 30, 2026","MIN":"28:30","PTS":12,"REB":3,"AST":4},
                        {"SEASON_ID":"22026","PLAYER_ID":204319,"GAME_ID":"1022600003","GAME_DATE":"SEP 27, 2026","MIN":"31:30","PTS":14,"REB":5,"AST":6},
                    ],
                }
            }
        }
    }
    player_html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(next_data) + '</script>'
    games = parse_first_party_player_latest_games_html(
        player_html,
        expected_player_id=204319,
        season=2026,
    )
    assert len(games) == 3
    assert games[0]["MIN"] == 30.0
    assert games[0]["PTS"] == 16.0

    windows = build_first_party_recent_stat_payloads([
        {**roster[0], "games": games}
    ], season=2026)
    hydrated, diag = hydrate_zero_production_rows(
        [_zero_row()],
        season_payload=windows[0],
        l10_payload=windows[10],
        l5_payload=windows[5],
        allowed_team_ids={1611661332},
        data_source="WNBA.com First-Party • player.latestGames recent observed history",
        player_id_source="WNBA.com First-Party roster identity",
    )
    row = hydrated[0]
    assert diag == {"candidates": 1, "hydrated": 1, "unresolved": 0}
    assert row["PLAYER_ID"] == 204319
    assert row["PLAYER_ID_SOURCE"] == "WNBA.com First-Party roster identity"
    assert row["MIN"] == 30.0
    assert round(row["PTS"], 4) == 14.0
    assert round(row["REB"], 4) == 4.0
    assert round(row["AST"], 4) == 5.0
    assert round(row["PRA"], 4) == 23.0
    assert row["L5_GP"] == 3
