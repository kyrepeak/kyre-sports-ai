"""Regression checks for CFB Schedule V3 full-FBS slate fallback."""
from __future__ import annotations

import cfb_schedule_v3 as schedule


def _directory_payload():
    return {
        "sports": [
            {
                "leagues": [
                    {
                        "teams": [
                            {
                                "team": {
                                    "id": "1",
                                    "slug": "miami-hurricanes",
                                    "location": "Miami",
                                    "displayName": "Miami Hurricanes",
                                    "abbreviation": "MIA",
                                }
                            },
                            {
                                "team": {
                                    "id": "2",
                                    "slug": "ohio-state-buckeyes",
                                    "location": "Ohio State",
                                    "displayName": "Ohio State Buckeyes",
                                    "abbreviation": "OSU",
                                }
                            },
                        ]
                    }
                ]
            }
        ]
    }


def _event(event_id, away_id, away_name, away_slug, home_id, home_name, home_slug):
    return {
        "id": str(event_id),
        "date": "2026-09-12T16:00:00Z",
        "status": {"type": {"description": "Scheduled"}},
        "competitions": [
            {
                "neutralSite": False,
                "venue": {"fullName": "Test Stadium"},
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {
                            "id": str(away_id),
                            "location": away_name,
                            "displayName": away_name,
                            "slug": away_slug,
                        },
                    },
                    {
                        "homeAway": "home",
                        "team": {
                            "id": str(home_id),
                            "location": home_name,
                            "displayName": home_name,
                            "slug": home_slug,
                        },
                    },
                ],
            }
        ],
    }


def test_fbs_directory_index_captures_ids_slugs_and_names():
    index = schedule._fbs_team_index(_directory_payload())
    assert "1" in index["ids"]
    assert "miami-hurricanes" in index["slugs"]
    assert schedule._team_key("Miami") in index["names"]
    assert schedule._team_key("Ohio State Buckeyes") in index["names"]


def test_unscoped_filter_keeps_fbs_vs_fcs_and_fbs_vs_fbs():
    index = schedule._fbs_team_index(_directory_payload())
    payload = {
        "events": [
            _event(
                "100",
                "900",
                "Florida A&M",
                "florida-am-rattlers",
                "1",
                "Miami",
                "miami-hurricanes",
            ),
            _event(
                "101",
                "2",
                "Ohio State",
                "ohio-state-buckeyes",
                "1",
                "Miami",
                "miami-hurricanes",
            ),
            _event(
                "102",
                "800",
                "FCS Away",
                "fcs-away",
                "801",
                "FCS Home",
                "fcs-home",
            ),
        ]
    }

    filtered, diag = schedule._filter_unscoped_to_fbs(payload, index)

    ids = [event["id"] for event in filtered["events"]]
    assert ids == ["100", "101"]
    assert diag["unscoped_events"] == 3
    assert diag["fbs_scoped_events"] == 2
    assert diag["non_fbs_events_rejected"] == 1


def test_competitor_membership_uses_verified_directory_id_or_slug():
    index = schedule._fbs_team_index(_directory_payload())
    competitor = {
        "team": {
            "id": "1",
            "slug": "something-different",
            "location": "Different Display",
        }
    }
    assert schedule._competitor_is_fbs(competitor, index) is True

    competitor = {
        "team": {
            "id": "999",
            "slug": "ohio-state-buckeyes",
            "location": "Different Display",
        }
    }
    assert schedule._competitor_is_fbs(competitor, index) is True


def test_merge_adds_new_fbs_event_and_does_not_duplicate_existing_matchup():
    base = [
        {
            "game_id": "1",
            "identity_key": "espn:1",
            "game_date": "2026-09-12",
            "kickoff_iso": "2026-09-12T12:00:00-04:00",
            "away_team": "Florida A&M",
            "away_team_slug": "florida-am-rattlers",
            "home_team": "Miami",
            "home_team_slug": "miami-hurricanes",
        }
    ]
    payload = {
        "events": [
            _event(
                "100",
                "900",
                "Florida A&M",
                "florida-am-rattlers",
                "1",
                "Miami",
                "miami-hurricanes",
            ),
            _event(
                "101",
                "2",
                "Ohio State",
                "ohio-state-buckeyes",
                "1",
                "Miami",
                "miami-hurricanes",
            ),
        ]
    }

    out, added = schedule._merge_verified_fbs_events(
        base,
        payload,
        "2026-09-12",
    )

    assert added == 1
    assert len(out) == 2
    added_rows = [g for g in out if g.get("full_fbs_slate_fallback")]
    assert len(added_rows) == 1
    assert added_rows[0]["game_id"] == "101"
    assert added_rows[0]["schedule_source"] == "ESPN FBS team-directory verified fallback"


def test_no_directory_means_no_unscoped_event_can_be_classified_as_fbs():
    payload = {
        "events": [
            _event(
                "100",
                "900",
                "Florida A&M",
                "florida-am-rattlers",
                "1",
                "Miami",
                "miami-hurricanes",
            )
        ]
    }
    filtered, diag = schedule._filter_unscoped_to_fbs(
        payload,
        {"ids": set(), "slugs": set(), "names": set()},
    )
    assert filtered["events"] == []
    assert diag["fbs_scoped_events"] == 0
    assert diag["non_fbs_events_rejected"] == 1
