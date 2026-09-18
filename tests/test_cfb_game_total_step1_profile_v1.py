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



def test_step1_fast_profile_timeout_and_no_broad_fallback_contract(monkeypatch):
    assert profile.FAST_PROFILE_TIMEOUT_SECONDS <= 4.0
    source = __import__("pathlib").Path(profile.__file__).read_text(encoding="utf-8")
    enrich_source = source[source.index("def enrich_step1_inputs"):]
    assert "recovery._fetch_espn_teams()" not in enrich_source
    side_source = source[source.index("def _enrich_side"):source.index("def enrich_step1_inputs")]
    assert "history._fetch_team_schedule(" not in side_source
    assert "deep._head_coach(" not in side_source
