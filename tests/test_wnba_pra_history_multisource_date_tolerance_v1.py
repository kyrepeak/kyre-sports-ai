from __future__ import annotations

import importlib


def _module():
    return importlib.import_module("sports_api.wnba_pra_history_multisource_v1")


def test_same_opponent_one_day_source_shift_backfills_observed_pra():
    module = _module()
    primary = {
        "source": "ESPN WNBA Athlete Gamelog",
        "games": [
            {
                "game_date": "2026-09-22",
                "minutes": 37.0,
                "points": None,
                "rebounds": None,
                "assists": None,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            }
        ],
        "verification": {},
    }
    official = {
        "source": "WNBA.com Player Profile",
        "games": [
            {
                "game_date": "2026-09-21",
                "minutes": 37.0,
                "points": 27,
                "rebounds": 14,
                "assists": 4,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            }
        ],
        "verification": {},
    }

    result = module.merge_verified_histories(primary, official)

    game = result["games"][0]
    assert (game["points"], game["rebounds"], game["assists"]) == (27, 14, 4)
    assert result["verification"]["official_wnba_matched_games"] == 1
    assert result["verification"]["source_date_tolerance_matches"] == 1


def test_one_day_tolerance_fails_closed_when_same_opponent_match_is_ambiguous():
    module = _module()
    primary = {
        "source": "ESPN WNBA Athlete Gamelog",
        "games": [
            {
                "game_date": "2026-09-22",
                "minutes": None,
                "points": None,
                "rebounds": None,
                "assists": None,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            }
        ],
        "verification": {},
    }
    official = {
        "source": "WNBA.com Player Profile",
        "games": [
            {
                "game_date": "2026-09-21",
                "minutes": 37.0,
                "points": 27,
                "rebounds": 14,
                "assists": 4,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            },
            {
                "game_date": "2026-09-23",
                "minutes": 31.0,
                "points": 20,
                "rebounds": 7,
                "assists": 2,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            },
        ],
        "verification": {},
    }

    result = module.merge_verified_histories(primary, official)

    game = result["games"][0]
    assert game["points"] is None
    assert game["rebounds"] is None
    assert game["assists"] is None
    assert result["verification"]["source_date_tolerance_matches"] == 0
    assert result["verification"]["ambiguous_tolerance_matches_blocked"] == 1
