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
        profile,
        "_exact_event_summary",
        lambda event_id: (_summary(), [{"provider": "summary"}]),
    )
    monkeypatch.setattr(profile.recovery, "_fetch_espn_teams", _directory)
    monkeypatch.setattr(
        profile,
        "_exact_team_detail",
        lambda team_id: (
            {
                "id": team_id,
                "name": {"324": "Chanticleers", "48": "Blue Hens"}[team_id],
                "groups": {"id": "9", "parent": {"id": "80"}},
            },
            [],
        ),
    )
    monkeypatch.setattr(profile.history, "_fetch_team_schedule", lambda team_id, season: ({}, []))

    away, home, diag = profile.enrich_step1_inputs(
        _identity(),
        {"conference": "Sun Belt", "record": "—", "head_coach": "Tim Beck"},
        {"conference": "CUSA", "record": "—", "head_coach": "Ryan Carty"},
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
    assert diag["away"]["directory_exact"] is False
    assert diag["away"]["detail_team_exact"] is True
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



def test_step1_fast_path_uses_exact_summary_and_team_detail_without_schedule(monkeypatch):
    monkeypatch.setattr(profile, "_exact_event_summary", lambda event_id: (_summary(), []))
    monkeypatch.setattr(
        profile,
        "_exact_team_detail",
        lambda team_id: (
            {
                "id": team_id,
                "name": {"324": "Chanticleers", "48": "Blue Hens"}[team_id],
                "groups": {"id": "9", "parent": {"id": "80"}},
            },
            [],
        ),
    )

    def fail_schedule(*args, **kwargs):
        raise AssertionError("Step 1 fast path must not call team schedule")

    monkeypatch.setattr(profile.history, "_fetch_team_schedule", fail_schedule)

    away, home, diag = profile.enrich_step1_inputs(
        _identity(),
        {"conference": "Sun Belt", "division_context": "FCS", "head_coach": "Ryan Beard"},
        {"conference": "CUSA", "division_context": "FCS", "head_coach": "Ryan Carty"},
        {"espn_event_id": "401869940", "game_date": "2026-09-19"},
    )

    assert away["mascot"] == "Chanticleers"
    assert home["mascot"] == "Blue Hens"
    assert away["record"] == "2-1"
    assert home["record"] == "3-0"
    assert away["classification"] == "FBS"
    assert home["classification"] == "FBS"
    assert away["head_coach"] == "Ryan Beard"
    assert home["head_coach"] == "Ryan Carty"
    assert diag["away"]["detail_team_exact"] is True
    assert diag["home"]["summary_exact"] is True
    assert diag["away"]["schedule_loaded"] is False

def test_step1_exact_team_detail_overrides_stale_profile_classification(monkeypatch):
    monkeypatch.setattr(profile, "_exact_event_summary", lambda event_id: (_summary(), []))
    monkeypatch.setattr(profile.recovery, "_fetch_espn_teams", lambda: {})
    monkeypatch.setattr(profile.history, "_fetch_team_schedule", lambda team_id, season: ({}, []))

    def detail(team_id):
        names = {"324": "Chanticleers", "48": "Blue Hens"}
        return (
            {
                "id": team_id,
                "name": names[team_id],
                "groups": {"id": "9", "parent": {"id": "80"}},
            },
            [],
        )

    monkeypatch.setattr(profile, "_exact_team_detail", detail)
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
        {"conference": "Sun Belt", "division_context": "FCS", "head_coach": "Ryan Beard"},
        {"conference": "CUSA", "division_context": "FCS", "head_coach": "Ryan Carty"},
        {"espn_event_id": "401869940", "game_date": "2026-09-19"},
    )

    assert away["classification"] == "FBS"
    assert home["classification"] == "FBS"
    assert away["mascot"] == "Chanticleers"
    assert home["mascot"] == "Blue Hens"
    assert away["record"] == "2-1"
    assert home["record"] == "3-0"
    assert diag["away"]["detail_team_exact"] is True
    assert diag["home"]["detail_team_exact"] is True



def test_step1_fast_profile_timeout_and_no_name_guessing_contract(monkeypatch):
    assert profile.FAST_PROFILE_TIMEOUT_SECONDS <= 4.0
    source = __import__("pathlib").Path(profile.__file__).read_text(encoding="utf-8")
    enrich_source = source[source.index("def enrich_step1_inputs"):]
    assert "recovery._fetch_espn_teams()" not in enrich_source
    side_source = source[source.index("def _enrich_side"):source.index("def enrich_step1_inputs")]
    assert "team_id.isdigit()" in side_source
    assert "history._fetch_team_schedule(" in side_source
    assert "deep._head_coach(" in side_source


def test_step1_exact_fallback_fills_schedule_profile_and_coach(monkeypatch):
    monkeypatch.setattr(profile, "_exact_event_summary", lambda event_id: ({}, []))
    monkeypatch.setattr(profile, "_exact_team_detail", lambda team_id: ({}, []))

    schedules = {
        "324": {
            "team": {
                "id": "324",
                "name": "Chanticleers",
                "groups": {"id": "37", "parent": {"id": "80"}},
            },
            "events": [
                {
                    "id": "a1",
                    "date": "2026-09-01T00:00:00Z",
                    "status": {"type": {"completed": True}},
                    "competitions": [{
                        "competitors": [
                            {"homeAway": "away", "score": "31", "team": {"id": "324"}},
                            {"homeAway": "home", "score": "17", "team": {"id": "999"}},
                        ]
                    }],
                },
                {
                    "id": "h1",
                    "date": "2026-09-01T00:00:00Z",
                    "status": {"type": {"completed": True}},
                    "competitions": [{
                        "competitors": [
                            {"homeAway": "away", "score": "14", "team": {"id": "998"}},
                            {"homeAway": "home", "score": "28", "team": {"id": "48"}},
                        ]
                    }],
                },
            ],
        },
        "48": {
            "team": {
                "id": "48",
                "name": "Blue Hens",
                "groups": {"id": "12", "parent": {"id": "81"}},
            },
            "events": [
                {
                    "id": "h1",
                    "date": "2026-09-01T00:00:00Z",
                    "status": {"type": {"completed": True}},
                    "competitions": [{
                        "competitors": [
                            {"homeAway": "away", "score": "14", "team": {"id": "998"}},
                            {"homeAway": "home", "score": "28", "team": {"id": "48"}},
                        ]
                    }],
                }
            ],
        },
    }
    monkeypatch.setattr(
        profile.history,
        "_fetch_team_schedule",
        lambda team_id, season: (schedules[team_id], [{"provider": "schedule"}]),
    )
    monkeypatch.setattr(
        profile.deep,
        "_head_coach",
        lambda team_id, season: (
            {
                "ready": True,
                "name": {"324": "Ryan Beard", "48": "Manny Rojas"}[team_id],
            },
            [{"provider": "coach"}],
        ),
    )

    away, home, diag = profile.enrich_step1_inputs(
        _identity(),
        {"conference": "Sun Belt"},
        {"conference": "CUSA"},
        {"espn_event_id": "401869940", "game_date": "2026-09-19"},
    )

    assert away["mascot"] == "Chanticleers"
    assert home["mascot"] == "Blue Hens"
    assert away["classification"] == "FBS"
    assert home["classification"] == "FCS"
    assert away["record"] == "1-0"
    assert home["record"] == "1-0"
    assert away["head_coach"] == "Ryan Beard"
    assert home["head_coach"] == "Manny Rojas"
    assert diag["away"]["schedule_loaded"] is True
    assert diag["home"]["schedule_loaded"] is True
    assert diag["away"]["head_coach_ready"] is True
    assert diag["home"]["head_coach_ready"] is True



def test_step1_exact_core_fallback_fills_mascot_and_record(monkeypatch):
    monkeypatch.setattr(profile, "_exact_event_summary", lambda event_id: ({}, []))
    monkeypatch.setattr(profile, "_exact_team_detail", lambda team_id: ({}, []))
    monkeypatch.setattr(profile.history, "_fetch_team_schedule", lambda team_id, season: ({}, []))
    monkeypatch.setattr(
        profile,
        "_exact_core_team_profile",
        lambda team_id, season: (
            {
                "id": team_id,
                "name": {"324": "Chanticleers", "48": "Blue Hens"}[team_id],
            },
            [{"provider": "core team"}],
        ),
    )
    monkeypatch.setattr(
        profile,
        "_exact_core_team_record",
        lambda team_id, season: (
            {
                "items": [{
                    "type": "total",
                    "summary": {"324": "2-1", "48": "3-0"}[team_id],
                }]
            },
            [{"provider": "core record"}],
        ),
    )
    monkeypatch.setattr(
        profile.deep,
        "_head_coach",
        lambda team_id, season: (
            {
                "ready": True,
                "name": {"324": "Ryan Beard", "48": "Ryan Carty"}[team_id],
            },
            [],
        ),
    )

    away, home, diag = profile.enrich_step1_inputs(
        _identity(),
        {"conference": "Sun Belt", "classification": "FBS"},
        {"conference": "CUSA", "classification": "FCS"},
        {"espn_event_id": "401869940", "game_date": "2026-09-19"},
    )

    assert away["mascot"] == "Chanticleers"
    assert home["mascot"] == "Blue Hens"
    assert away["record"] == "2-1"
    assert home["record"] == "3-0"
    assert away["head_coach"] == "Ryan Beard"
    assert home["head_coach"] == "Ryan Carty"
    assert diag["away"]["core_team_exact"] is True
    assert diag["home"]["core_team_exact"] is True
    assert diag["away"]["core_record_loaded"] is True
    assert diag["home"]["core_record_loaded"] is True


def test_step1_core_record_prefers_total_split():
    payload = {
        "items": [
            {"type": "home", "summary": "1-0"},
            {"type": "total", "summary": "2-1"},
            {"type": "away", "summary": "1-1"},
        ]
    }
    assert profile._record_from_core(payload) == "2-1"
