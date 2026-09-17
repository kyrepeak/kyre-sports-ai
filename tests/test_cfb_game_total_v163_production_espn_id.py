from __future__ import annotations

from datetime import date

import cfb_game_total_clean_page_v14 as v163


def _espn_payload() -> dict:
    return {
        "events": [
            {
                "id": "401752801",
                "date": "2026-09-19T16:00:00Z",
                "competitions": [
                    {
                        "date": "2026-09-19T16:00:00Z",
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {
                                    "displayName": "Bowling Green Falcons",
                                    "shortDisplayName": "Bowling Green",
                                    "location": "Bowling Green",
                                    "name": "Falcons",
                                    "slug": "bowling-green-falcons",
                                },
                            },
                            {
                                "homeAway": "home",
                                "team": {
                                    "displayName": "Iowa State Cyclones",
                                    "shortDisplayName": "Iowa State",
                                    "location": "Iowa State",
                                    "name": "Cyclones",
                                    "slug": "iowa-state-cyclones",
                                },
                            },
                        ],
                        "venue": {"fullName": "Jack Trice Stadium"},
                    }
                ],
                "status": {"type": {"description": "Scheduled"}},
            }
        ]
    }


def test_load_games_recovers_official_espn_event_id_without_using_ncaa_game_id(monkeypatch):
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
    monkeypatch.setattr(v163, "_fetch_selector_espn_payload", lambda selected_day: _espn_payload())

    loaded = v163._load_games(date(2026, 9, 19))

    assert loaded[0]["espn_event_id"] == "401752801"
    assert v163._game_id(loaded[0]) == "401752801"
    assert frozen_row["espn_event_id"] == "", "V163 must not mutate the frozen schedule row"
    assert v163._game_id({"game_id": "NCAA-only"}) == "", "NCAA game_id is not an ESPN event identity"
