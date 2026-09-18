from __future__ import annotations

import cfb_game_total_step1_profile_v1 as profile


def _identity():
    return {
        "away": {"team_id": "324", "team": "Coastal Carolina"},
        "home": {"team_id": "48", "team": "Delaware"},
    }


def _summary():
    return {
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {"id": "324", "name": "Chanticleers"},
                            "records": [{"type": "total", "summary": "2-1"}],
                        },
                        {
                            "homeAway": "home",
                            "team": {"id": "48", "name": "Blue Hens"},
                            "records": [{"type": "total", "summary": "3-0"}],
                        },
                    ]
                }
            ]
        }
    }


def _directory():
    return {
        "sports": [
            {
                "leagues": [
                    {
                        "teams": [
                            {
                                "team": {
                                    "id": "324",
                                    "name": "Chanticleers",
                                    "groups": {"id": "37", "parent": {"id": "80"}},
                                }
                            },
                            {
                                "team": {
                                    "id": "48",
                                    "name": "Blue Hens",
                                    "groups": {"id": "12", "parent": {"id": "80"}},
                                }
                            },
                        ]
                    }
                ]
            }
        ]
    }


def test_step1_exact_profile_fills_required_display_fields(monkeypatch):
    monkeypatch.setattr(
        profile.environment,
        "_fetch_summary",
        lambda event_id: (_summary(), [{"provider": "summary"}]),
    )
    monkeypatch.setattr(profile.recovery, "_fetch_espn_teams", _directory)
    monkeypatch.setattr(profile.history, "_fetch_team_schedule", lambda team_id, season: ({}, []))

    def coach(team_id, season):
        names = {"324": "Tim Beck", "48": "Ryan Carty"}
        return (
            {
                "ready": True,
                "name": names[team_id],
                "id": f"coach-{team_id}",
                "source": "ESPN Core current-season head coach",
            },
            [],
        )

    monkeypatch.setattr(profile.deep, "_head_coach", coach)

    away, home, diag = profile.enrich_step1_inputs(
        _identity(),
        {"conference": "Sun Belt", "record": "—"},
        {"conference": "CUSA", "record": "—"},
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
        },
    )

    assert away["mascot"] == "Chanticleers"
    assert home["mascot"] == "Blue Hens"
    assert away["classification"] == "FBS"
    assert home["classification"] == "FBS"
    assert away["record"] == "2-1"
    assert home["record"] == "3-0"
    assert away["head_coach"] == "Tim Beck"
    assert home["head_coach"] == "Ryan Carty"
    assert diag["away"]["directory_exact"] is True
    assert diag["home"]["summary_exact"] is True
    assert diag["sportsbook_projection_influence"] == 0.0
    assert diag["may_modify_projection"] is False


def test_step1_profile_uses_exact_team_id_only(monkeypatch):
    monkeypatch.setattr(profile.environment, "_fetch_summary", lambda event_id: ({}, []))
    monkeypatch.setattr(profile.recovery, "_fetch_espn_teams", _directory)
    monkeypatch.setattr(
        profile.deep,
        "_head_coach",
        lambda team_id, season: (_ for _ in ()).throw(
            AssertionError("coach lookup must not run without exact team id")
        ),
    )

    away, home, _ = profile.enrich_step1_inputs(
        {"away": {"team": "Coastal Carolina"}, "home": {"team": "Delaware"}},
        {},
        {},
        {"game_date": "2026-09-19"},
    )
    assert "mascot" not in away
    assert "classification" not in away
    assert "head_coach" not in away
    assert "mascot" not in home


def test_step1_classification_supports_exact_fcs_group():
    team_obj = {"groups": {"id": "40", "parent": {"id": "81"}}}
    assert profile._classification({}, team_obj) == "FCS"
    assert profile._classification({"division_context": "FBS"}, team_obj) == "FCS"


def test_step1_profile_is_presentation_only():
    assert profile.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert profile.MAY_MODIFY_PROJECTION is False



def test_step1_schedule_fallback_recovers_mascot_record_and_current_classification(monkeypatch):
    monkeypatch.setattr(profile.environment, "_fetch_summary", lambda event_id: ({}, []))
    monkeypatch.setattr(profile.recovery, "_fetch_espn_teams", lambda: {})

    def schedule(team_id, season):
        names = {"324": ("Coastal Carolina", "Chanticleers"), "48": ("Delaware", "Blue Hens")}
        school, mascot = names[team_id]
        return (
            {
                "team": {
                    "id": team_id,
                    "displayName": school,
                    "name": mascot,
                    "groups": {"id": "9", "parent": {"id": "80"}},
                },
                "events": [
                    {
                        "id": f"{team_id}-w",
                        "date": "2026-09-05T18:00:00Z",
                        "status": {"type": {"completed": True}},
                        "competitions": [{
                            "competitors": [
                                {
                                    "homeAway": "home",
                                    "score": "31",
                                    "team": {"id": team_id, "displayName": school, "name": mascot},
                                },
                                {
                                    "homeAway": "away",
                                    "score": "14",
                                    "team": {"id": "9999", "displayName": "Opponent"},
                                },
                            ]
                        }],
                    },
                    {
                        "id": f"{team_id}-l",
                        "date": "2026-09-12T18:00:00Z",
                        "status": {"type": {"completed": True}},
                        "competitions": [{
                            "competitors": [
                                {
                                    "homeAway": "away",
                                    "score": "17",
                                    "team": {"id": team_id, "displayName": school, "name": mascot},
                                },
                                {
                                    "homeAway": "home",
                                    "score": "24",
                                    "team": {"id": "9998", "displayName": "Opponent 2"},
                                },
                            ]
                        }],
                    },
                ],
            },
            [],
        )

    monkeypatch.setattr(profile.history, "_fetch_team_schedule", schedule)
    monkeypatch.setattr(
        profile.deep,
        "_head_coach",
        lambda team_id, season: (
            {"ready": True, "name": "Coach Name", "id": "1", "source": "ESPN Core"},
            [],
        ),
    )

    away, home, diag = profile.enrich_step1_inputs(
        _identity(),
        {"conference": "Sun Belt", "division_context": "FCS"},
        {"conference": "CUSA", "division_context": "FCS"},
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
        },
    )

    assert away["mascot"] == "Chanticleers"
    assert home["mascot"] == "Blue Hens"
    assert away["record"] == "1-1"
    assert home["record"] == "1-1"
    assert away["classification"] == "FBS"
    assert home["classification"] == "FBS"
    assert diag["away"]["schedule_team_exact"] is True
    assert diag["home"]["schedule_loaded"] is True
