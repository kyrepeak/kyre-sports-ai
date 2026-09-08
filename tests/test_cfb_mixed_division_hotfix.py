"""Regression checks for CFB mixed-division schedule/data hotfix."""
from __future__ import annotations

import copy

import pytest

import cfb_schedule_v2 as schedule
import cfb_team_data_v1 as frozen_team
import cfb_team_data_v2 as team_data


def _contest(
    contest_id,
    away_name,
    away_slug,
    away_conf,
    home_name,
    home_slug,
    home_conf,
    start_date="09/10/2026",
    start_time="8:00 PM ET",
):
    return {
        "contestId": contest_id,
        "startDate": start_date,
        "startTime": start_time,
        "gameState": "P",
        "broadcasterName": "ACC Network",
        "teams": [
            {
                "isHome": False,
                "nameShort": away_name,
                "seoname": away_slug,
                "conferenceSeo": away_conf,
            },
            {
                "isHome": True,
                "nameShort": home_name,
                "seoname": home_slug,
                "conferenceSeo": home_conf,
                "teamRank": 7,
            },
        ],
    }


def _espn_event(
    event_id,
    away_display,
    away_location,
    away_slug,
    home_display,
    home_location,
    home_slug,
):
    return {
        "id": event_id,
        "date": "2026-09-11T00:00:00Z",
        "status": {"type": {"description": "Scheduled"}},
        "competitions": [
            {
                "neutralSite": False,
                "venue": {"fullName": "Hard Rock Stadium"},
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {
                            "displayName": away_display,
                            "location": away_location,
                            "slug": away_slug,
                        },
                    },
                    {
                        "homeAway": "home",
                        "team": {
                            "displayName": home_display,
                            "location": home_location,
                            "slug": home_slug,
                        },
                    },
                ],
            }
        ],
    }


def test_fcs_division_query_is_explicit_and_season_scoped():
    params = schedule._ncaa_params_for_division(2026, 12)
    assert schedule.NCAA_FCS_DIVISION == 12
    assert '"division":12' in params["variables"]
    assert '"seasonYear":2026' in params["variables"]


def test_ncaa_fcs_crossover_is_kept_when_espn_fbs_group_confirms_event():
    fcs_payload = {
        "data": {
            "contests": [
                _contest(
                    "800001",
                    "Florida A&M",
                    "florida-am",
                    "swac",
                    "Miami (FL)",
                    "miami-fl",
                    "acc",
                )
            ]
        }
    }
    espn_payload = {
        "events": [
            _espn_event(
                "402000001",
                "Florida A&M Rattlers",
                "Florida A&M",
                "florida-am-rattlers",
                "Miami Hurricanes",
                "Miami",
                "miami-hurricanes",
            )
        ]
    }

    games, diag = schedule._cross_division_games(
        fcs_payload,
        espn_payload,
        "2026-09-10",
    )

    assert len(games) == 1
    game = games[0]
    assert game["away_team"] == "Florida A&M"
    assert game["home_team"] == "Miami (FL)"
    assert game["game_id"] == "800001"
    assert game["identity_key"] == "ncaa:800001"
    assert game["identity_verified"] is True
    assert game["mixed_division_supplement"] is True
    assert "FBS crossover" in game["schedule_source"]
    assert diag["fcs_crossovers_kept"] == 1


def test_pure_fcs_game_is_rejected_without_espn_fbs_group_match():
    fcs_payload = {
        "data": {
            "contests": [
                _contest(
                    "800002",
                    "FCS Away",
                    "fcs-away",
                    "fcs-conf",
                    "FCS Home",
                    "fcs-home",
                    "fcs-conf",
                )
            ]
        }
    }
    games, diag = schedule._cross_division_games(
        fcs_payload,
        {"events": []},
        "2026-09-10",
    )
    assert games == []
    assert diag["fcs_non_fbs_events_rejected"] == 1


def test_merge_preserves_primary_and_adds_only_new_crossover():
    primary = [
        {
            "game_id": "1",
            "identity_key": "ncaa:1",
            "game_date": "2026-09-10",
            "away_team_slug": "a",
            "home_team_slug": "b",
            "kickoff_iso": "2026-09-10T19:00:00-04:00",
        }
    ]
    crossover = [
        {
            "game_id": "2",
            "identity_key": "ncaa:2",
            "game_date": "2026-09-10",
            "away_team_slug": "florida-am",
            "home_team_slug": "miami-fl",
            "kickoff_iso": "2026-09-10T20:00:00-04:00",
        }
    ]
    out, diag = schedule._merge_primary_and_crossovers(primary, crossover)
    assert [g["game_id"] for g in out] == ["1", "2"]
    assert diag["mixed_division_added"] == 1


def _team_game(date, opponent, opp_slug, location, pf, pa, result):
    return frozen_team.TeamGame(
        date=date,
        opponent=opponent,
        opponent_slug=opp_slug,
        location=location,
        points_for=pf,
        points_against=pa,
        result=result,
        margin=pf - pa,
    )


def test_fcs_check_profile_can_be_repaired_from_official_fcs_evidence():
    game = {
        "away_team": "Florida A&M",
        "away_team_slug": "florida-am",
        "away_conference": "swac",
        "away_rank": None,
    }
    ledgers = {
        "floridaam": [
            _team_game(
                "2026-09-06",
                "South Carolina State",
                "south-carolina-state",
                "neutral",
                27,
                20,
                "W",
            )
        ],
        "southcarolinastate": [
            _team_game(
                "2026-09-06",
                "Florida A&M",
                "florida-am",
                "neutral",
                20,
                27,
                "L",
            )
        ],
    }
    meta = {
        "floridaam": {
            "team": "Florida A&M",
            "team_slug": "florida-am",
            "conference": "swac",
            "schedule_rank": None,
        }
    }
    fcs_stats = {
        "away": {
            "scoring_offense": {"value_numeric": 27.0},
            "scoring_defense": {"value_numeric": 20.0},
            "total_offense": {"value_numeric": 410.0},
            "total_defense": {"value_numeric": 350.0},
        }
    }
    frozen_profile = {
        "team": "Florida A&M",
        "data_quality": {"grade": "CHECK"},
    }

    repaired, ok = team_data._repair_profile(
        "away",
        game,
        frozen_profile,
        ledgers,
        meta,
        fcs_stats,
    )

    assert ok is True
    assert repaired["division_context"] == "FCS"
    assert repaired["record_text"] == "1-0"
    assert repaired["ppg"] == pytest.approx(27.0)
    assert repaired["points_allowed_pg"] == pytest.approx(20.0)
    assert repaired["data_quality"]["grade"] == "READY"
    assert "FCS" in repaired["data_source"]


def test_non_fcs_check_profile_is_not_repaired():
    frozen_profile = {
        "team": "Unknown",
        "data_quality": {"grade": "CHECK"},
    }
    repaired, ok = team_data._repair_profile(
        "away",
        {
            "away_team": "Unknown",
            "away_team_slug": "unknown",
        },
        frozen_profile,
        {},
        {},
        {"away": {}},
    )
    assert ok is False
    assert repaired == frozen_profile


def test_fcs_category_discovery_retargets_frozen_parser():
    html = """
    <select>
      <option value="/stats/football/fcs/current/team/28">Scoring Offense</option>
      <option value="/stats/football/fcs/current/team/22">Scoring Defense</option>
    </select>
    """
    categories = team_data._fcs_categories(html)
    assert "scoring_offense" in categories
    assert "scoring_defense" in categories
    assert "/stats/football/fcs/" in categories["scoring_offense"]["url"]


def test_espn_fbs_fallback_builds_verified_schedule_identity():
    payload = {
        "events": [
            {
                **_espn_event(
                    "402000001",
                    "Florida A&M Rattlers",
                    "Florida A&M",
                    "florida-am-rattlers",
                    "Miami Hurricanes",
                    "Miami",
                    "miami-hurricanes",
                ),
                "competitions": [
                    {
                        "neutralSite": False,
                        "venue": {"fullName": "Hard Rock Stadium"},
                        "broadcasts": [{"names": ["ACC Network"]}],
                        "competitors": [
                            {
                                "homeAway": "away",
                                "records": [{"name": "overall", "summary": "1-0"}],
                                "team": {
                                    "displayName": "Florida A&M Rattlers",
                                    "location": "Florida A&M",
                                    "slug": "florida-am-rattlers",
                                },
                            },
                            {
                                "homeAway": "home",
                                "curatedRank": {"current": 7},
                                "records": [{"name": "overall", "summary": "1-0"}],
                                "team": {
                                    "displayName": "Miami Hurricanes",
                                    "location": "Miami",
                                    "slug": "miami-hurricanes",
                                },
                            },
                        ],
                    }
                ],
            }
        ]
    }

    games = schedule._espn_schedule_games(payload, "2026-09-10")

    assert len(games) == 1
    game = games[0]
    assert game["identity_key"] == "espn:402000001"
    assert game["identity_verified"] is True
    assert game["date_matches_query"] is True
    assert game["away_team"] == "Florida A&M"
    assert game["home_team"] == "Miami"
    assert game["away_record_summary"] == "1-0"
    assert game["home_record_summary"] == "1-0"
    assert game["home_rank"] == 7
    assert game["schedule_source"] == "ESPN FBS scoreboard verified fallback"


def test_stats_only_repair_uses_published_game_count_and_scoring_without_fake_recent_form():
    game = {
        "away_team": "Florida A&M",
        "away_team_slug": "florida-am-rattlers",
        "away_record_summary": "1-0",
    }
    stats = {
        "scoring_offense": {
            "value_numeric": 27.0,
            "value": "27.0",
            "headers": ["Rank", "Team", "G", "Pts", "Avg"],
            "row": ["25", "Florida A&M", "1", "27", "27.0"],
        },
        "scoring_defense": {
            "value_numeric": 20.0,
            "value": "20.0",
            "headers": ["Rank", "Team", "G", "Pts", "Avg"],
            "row": ["30", "Florida A&M", "1", "20", "20.0"],
        },
        "total_offense": {
            "value_numeric": 410.0,
            "headers": ["Rank", "Team", "G", "YPG"],
            "row": ["20", "Florida A&M", "1", "410.0"],
        },
    }

    repaired, ok = team_data._stats_only_repair(
        "away",
        game,
        {"team": "Florida A&M", "data_quality": {"grade": "CHECK"}},
        stats,
    )

    assert ok is True
    assert repaired["record"]["games"] == 1
    assert repaired["record_text"] == "1-0"
    assert repaired["ppg"] == pytest.approx(27.0)
    assert repaired["points_allowed_pg"] == pytest.approx(20.0)
    assert repaired["recent_form"] == "—"
    assert repaired["recent_ppg"] is None
    assert repaired["sos_opponent_win_pct"] is None
    assert repaired["data_quality"]["grade"] == "LIMITED"
