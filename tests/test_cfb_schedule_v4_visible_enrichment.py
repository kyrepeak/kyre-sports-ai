"""Regression tests for alias-safe Schedule V4 enrichment."""
from __future__ import annotations

import cfb_schedule_v4 as schedule


def _game():
    return {
        "game_id": "ncaa-1",
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "away_team_slug": "florida-am",
        "home_team": "Miami (FL)",
        "home_team_slug": "miami-fl",
        "venue": "Venue unavailable",
        "broadcast": "Broadcast unavailable",
        "status": "Scheduled",
        "identity_verified": True,
        "date_matches_query": True,
    }


def _payload():
    return {
        "events": [{
            "id": "401858213",
            "date": "2026-09-11T00:00:00Z",
            "week": {"number": 2},
            "status": {"type": {"description": "Scheduled"}},
            "competitions": [{
                "neutralSite": False,
                "venue": {"fullName": "Hard Rock Stadium"},
                "broadcasts": [{"names": ["ACC Network"]}],
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {
                            "id": "50",
                            "displayName": "Florida A&M Rattlers",
                            "shortDisplayName": "Florida A&M",
                            "location": "Florida A&M",
                            "slug": "florida-am-rattlers",
                        },
                        "records": [{"name": "overall", "summary": "1-1"}],
                    },
                    {
                        "homeAway": "home",
                        "team": {
                            "id": "2390",
                            "displayName": "Miami Hurricanes",
                            "shortDisplayName": "Miami",
                            "location": "Miami",
                            "slug": "miami-hurricanes",
                        },
                        "curatedRank": {"current": 7},
                        "records": [{"name": "overall", "summary": "1-0"}],
                    },
                ],
            }],
        }],
    }


def test_parenthetical_miami_alias_matches_espn_miami():
    rows = schedule._event_rows(_payload(), "2026-09-10")
    assert len(rows) == 1
    assert schedule._match(_game(), rows[0]) is True


def test_enrichment_repairs_visible_schedule_fields():
    game = _game()
    matched = schedule._enrich_games([game], _payload(), "2026-09-10")
    assert matched == 1
    assert game["espn_event_id"] == "401858213"
    assert game["away_espn_team_id"] == "50"
    assert game["home_espn_team_id"] == "2390"
    assert game["away_record_summary"] == "1-1"
    assert game["home_record_summary"] == "1-0"
    assert game["home_rank"] == 7
    assert game["venue"] == "Hard Rock Stadium"
    assert game["broadcast"] == "ACC Network"
    assert game["status"] == "Scheduled"
    assert game["espn_week"] == 2
    assert game["schedule_v4_espn_enriched"] is True
