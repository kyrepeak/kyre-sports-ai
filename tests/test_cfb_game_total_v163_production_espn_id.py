from __future__ import annotations

from datetime import date

import cfb_game_total_clean_page_v14 as v163


def _identity_payload() -> dict:
    return {
        "lines": [
            {
                "official_game_id": "401752801",
                "game_date": "2026-09-19",
                "official_away_team": "Bowling Green Falcons",
                "official_home_team": "Iowa State Cyclones",
                "identity_verified": True,
            },
            {
                "official_game_id": "SHOULD-NOT-MATCH",
                "game_date": "2026-09-19",
                "official_away_team": "Akron Zips",
                "official_home_team": "Minnesota Golden Gophers",
                "identity_verified": True,
            },
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def test_load_games_recovers_official_espn_event_id_from_api_without_using_ncaa_game_id(monkeypatch):
    frozen_row = {
        "game_id": "NCAA-12345",
        "espn_event_id": "",
        "game_date": "2026-09-19",
        "kickoff_et": "12:00 PM ET",
        "kickoff_iso": "2026-09-19T12:00:00-04:00",
        "away_team": "Bowling Green",
        "away_team_slug": "bowling-green",
        "home_team": "Iowa St.",
        "home_team_slug": "iowa-st",
        "identity_verified": True,
        "date_matches_query": True,
    }
    schedule = v163.v161.prior.frozen_page.frozen_v2.frozen_v1.schedule
    monkeypatch.setattr(
        schedule,
        "load_with_diagnostics",
        lambda selected_day: ([frozen_row], {"espn_matches": 0}),
    )
    monkeypatch.setattr(
        v163,
        "_fetch_selector_identity_payload",
        lambda selected_day: _identity_payload(),
    )

    loaded = v163._load_games(date(2026, 9, 19))

    assert loaded[0]["espn_event_id"] == "401752801"
    assert loaded[0]["selector_identity_source"] == "Kyre Sports API reconciled identity"
    assert v163._game_id(loaded[0]) == "401752801"
    assert frozen_row["espn_event_id"] == "", "V163 must not mutate the frozen schedule row"
    assert v163._game_id({"game_id": "NCAA-only"}) == "", "NCAA game_id is not an ESPN event identity"


def test_api_identity_matching_is_exact_date_two_team_and_fail_closed():
    games = [
        {
            "game_date": "2026-09-19",
            "away_team": "Tulane",
            "home_team": "Kansas St.",
            "espn_event_id": "",
        }
    ]
    payload = {
        "lines": [
            {
                "official_game_id": "WRONG-DATE",
                "game_date": "2026-09-20",
                "official_away_team": "Tulane Green Wave",
                "official_home_team": "Kansas State Wildcats",
                "identity_verified": True,
            },
            {
                "official_game_id": "UNVERIFIED",
                "game_date": "2026-09-19",
                "official_away_team": "Tulane Green Wave",
                "official_home_team": "Kansas State Wildcats",
                "identity_verified": False,
            },
            {
                "official_game_id": "401752999",
                "game_date": "2026-09-19",
                "official_away_team": "Tulane Green Wave",
                "official_home_team": "Kansas State Wildcats",
                "identity_verified": True,
            },
        ]
    }

    v163._enrich_selector_ids_from_api(games, payload, date(2026, 9, 19))

    assert games[0]["espn_event_id"] == "401752999"


def test_v163_does_not_fetch_espn_directly_for_selector_identity():
    assert not hasattr(v163, "_fetch_selector_espn_payload")
