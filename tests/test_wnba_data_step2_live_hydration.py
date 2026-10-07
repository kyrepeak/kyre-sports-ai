from __future__ import annotations

from wnba_pra_game_center_stats_hydration_v1 import hydrate_zero_production_rows


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


def test_zero_only_game_center_row_is_hydrated_from_official_hosted_stats():
    rows = [
        {
            "PLAYER_ID": 999999,
            "PLAYER_NAME": "Rebecca Allen",
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
    ]

    hydrated, diag = hydrate_zero_production_rows(
        rows,
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
    rows = [{
        "PLAYER_ID": 999999,
        "PLAYER_NAME": "Unknown Player",
        "TEAM_ID": 1611661332,
        "MIN": 0.0,
        "PTS": 0.0,
        "REB": 0.0,
        "AST": 0.0,
        "PRA": 0.0,
        "DATA_SOURCE": "Current roster • no matched production row",
        "PLAYER_ID_SOURCE": "ESPN",
    }]
    hydrated, diag = hydrate_zero_production_rows(
        rows,
        season_payload=_payload(0, minutes=26.4, points=10.8, rebounds=3.1, assists=2.2),
        l10_payload=_payload(10, minutes=28.0, points=11.6, rebounds=3.5, assists=2.4),
        l5_payload=_payload(5, minutes=29.2, points=12.4, rebounds=3.8, assists=2.8),
        allowed_team_ids={1611661332},
    )
    assert hydrated[0]["DATA_SOURCE"] == "Current roster • no matched production row"
    assert diag == {"candidates": 1, "hydrated": 0, "unresolved": 1}
