"""Regression checks for College Football Step 2 schedule + game identity."""
from __future__ import annotations

import copy
import inspect

import cfb_hub_v2 as hub
import cfb_schedule_v1 as schedule


def _contest(contest_id="7000001", start_date="09/12/2026", start_time="7:30 PM ET"):
    return {
        "contestId": contest_id,
        "startDate": start_date,
        "startTime": start_time,
        "gameState": "P",
        "broadcasterName": "ABC",
        "url": f"/game/{contest_id}",
        "teams": [
            {
                "isHome": False,
                "nameShort": "Ohio State",
                "seoname": "ohio-state",
                "conferenceSeo": "big-ten",
                "teamRank": 1,
            },
            {
                "isHome": True,
                "nameShort": "Texas",
                "seoname": "texas",
                "conferenceSeo": "sec",
                "teamRank": 5,
            },
        ],
    }


def _ncaa_payload():
    return {
        "data": {
            "schedules": [
                {
                    "week": 2,
                    "contests": [
                        _contest(),
                        _contest(),
                        _contest("7000999", "09/19/2026", "7:30 PM ET"),
                    ],
                }
            ]
        }
    }


def _espn_payload():
    return {
        "events": [
            {
                "id": "401999999",
                "date": "2026-09-12T23:30:00Z",
                "status": {"type": {"description": "Scheduled"}},
                "competitions": [
                    {
                        "venue": {"fullName": "Darrell K Royal-Texas Memorial Stadium"},
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {
                                    "displayName": "Ohio State Buckeyes",
                                    "location": "Ohio State",
                                    "name": "Buckeyes",
                                    "slug": "ohio-state-buckeyes",
                                },
                            },
                            {
                                "homeAway": "home",
                                "team": {
                                    "displayName": "Texas Longhorns",
                                    "location": "Texas",
                                    "name": "Longhorns",
                                    "slug": "texas-longhorns",
                                },
                            },
                        ],
                    }
                ],
            }
        ]
    }


def test_ncaa_persisted_query_contract_is_fbs_and_season_scoped():
    params = schedule._ncaa_params(2026)
    assert schedule.NCAA_SPORT_CODE == "MFB"
    assert schedule.NCAA_FBS_DIVISION == 11
    assert schedule.NCAA_SCHEDULE_QUERY_NAME == "NCAA_schedules_today_web"
    assert schedule.NCAA_SCHEDULE_HASH in params["extensions"]
    assert '"seasonYear":2026' in params["variables"]
    assert '"division":11' in params["variables"]


def test_official_schedule_filters_date_and_dedupes_stable_ncaa_id():
    games, diag = schedule._parse_ncaa_schedule(_ncaa_payload(), "2026-09-12")

    assert len(games) == 1
    game = games[0]
    assert game["game_id"] == "7000001"
    assert game["identity_key"] == "ncaa:7000001"
    assert game["identity_verified"] is True
    assert game["date_matches_query"] is True
    assert game["away_team"] == "Ohio State"
    assert game["home_team"] == "Texas"
    assert game["away_conference"] == "big-ten"
    assert game["home_conference"] == "sec"
    assert game["kickoff_et"] == "7:30 PM ET"
    assert game["schedule_source"] == "NCAA official schedule GraphQL"
    assert diag["duplicate_event_ids_dropped"] == 1
    assert diag["off_date_contests_ignored"] == 1


def test_espn_only_enriches_identity_record_without_replacing_ncaa_id():
    games, _ = schedule._parse_ncaa_schedule(_ncaa_payload(), "2026-09-12")
    before_identity = copy.deepcopy(
        {
            "game_id": games[0]["game_id"],
            "identity_key": games[0]["identity_key"],
            "away_team_slug": games[0]["away_team_slug"],
            "home_team_slug": games[0]["home_team_slug"],
        }
    )

    matched = schedule._enrich_with_espn(games, _espn_payload(), "2026-09-12")

    assert matched == 1
    game = games[0]
    assert game["game_id"] == before_identity["game_id"]
    assert game["identity_key"] == before_identity["identity_key"]
    assert game["away_team_slug"] == before_identity["away_team_slug"]
    assert game["home_team_slug"] == before_identity["home_team_slug"]
    assert game["venue"] == "Darrell K Royal-Texas Memorial Stadium"
    assert game["espn_event_id"] == "401999999"
    assert game["enrichment_source"] == "ESPN College Football scoreboard"


def test_dedupe_protects_natural_identity_if_provider_emits_new_id_for_same_game():
    games, _ = schedule._parse_ncaa_schedule({"data": {"contests": [_contest()]}}, "2026-09-12")
    clone = copy.deepcopy(games[0])
    clone["game_id"] = "DIFFERENT-ID"
    clone["identity_key"] = "ncaa:DIFFERENT-ID"

    out, diag = schedule._dedupe_official([games[0], clone])

    assert len(out) == 1
    assert diag["duplicate_identity_rows_dropped"] == 1


def test_hub_card_exposes_required_identity_fields_and_no_fake_projection():
    games, _ = schedule._parse_ncaa_schedule(_ncaa_payload(), "2026-09-12")
    schedule._enrich_with_espn(games, _espn_payload(), "2026-09-12")
    html = hub._game_card(games[0])

    assert "STEP 2 • OFFICIAL SCHEDULE + GAME IDENTITY" in html
    assert "Ohio State" in html
    assert "Texas" in html
    assert "big-ten" in html and "sec" in html
    assert "7:30 PM ET" in html
    assert "Darrell K Royal-Texas Memorial Stadium" in html
    assert "NCAA contest ID" in html and "7000001" in html
    assert "Stable identity key" in html and "ncaa:7000001" in html
    assert "ESPN enrichment ID" in html and "401999999" in html
    assert "no betting projection adjustment" in html


def test_step2_builds_on_frozen_v1_and_does_not_add_model_math():
    source = inspect.getsource(hub)
    assert hub.FROZEN_CFB_HUB == "cfb_hub_v1"
    assert hub.CFB_MARKETS == ["Moneyline", "Over/Under", "Game Total"]
    forbidden = (
        "import numpy",
        "np.random",
        "def simulate",
        "def win_probability",
        "fair_odds =",
        "projected_total =",
    )
    for token in forbidden:
        assert token not in source
