import pytest

import nfl_game_day_availability_v1 as game_day
from devsystem import passing_yards_data_starter_truth_step1_v1 as audit


def _ctx(qbs, qb1):
    return {
        "abbr": "TST",
        "depth_state": "VERIFIED",
        "current_roster_verified": True,
        "identity_verified": True,
        "qbs": qbs,
        "qb1": qb1,
        "depth_source": "ESPN DEPTH CHART",
    }


def test_expected_depth_qb1_is_green(monkeypatch):
    qbs = [
        {"rank": 1, "athlete_id": "1", "name": "Healthy One", "injury_status": "No listed injury"},
        {"rank": 2, "athlete_id": "2", "name": "Backup Two", "injury_status": "No listed injury"},
    ]
    monkeypatch.setattr(
        game_day,
        "current_prop_eligible_keys",
        lambda abbr: ({"1", "2"}, {"healthy one", "backup two"}, {"ok": True, "http": 200}),
    )
    out = audit.audit_team_context(_ctx(qbs, qbs[0]))
    assert out["starter_class"] == "EXPECTED_DEPTH_QB1"
    assert out["starter_name"] == "Healthy One"


def test_out_depth_qb1_promotes_verified_replacement(monkeypatch):
    qbs = [
        {"rank": 1, "athlete_id": "1", "name": "Injured One", "injury_status": "Out"},
        {"rank": 2, "athlete_id": "2", "name": "Replacement Two", "injury_status": "No listed injury"},
    ]
    monkeypatch.setattr(
        game_day,
        "current_prop_eligible_keys",
        lambda abbr: ({"1", "2"}, {"injured one", "replacement two"}, {"ok": True, "http": 200}),
    )
    out = audit.audit_team_context(_ctx(qbs, qbs[1]))
    assert out["starter_class"] == "VERIFIED_REPLACEMENT"
    assert out["replacement_reason"] == "unavailable"
    assert out["starter_name"] == "Replacement Two"


def test_stale_depth_qb1_promotes_current_roster_replacement(monkeypatch):
    qbs = [
        {"rank": 1, "athlete_id": "1", "name": "Stale One", "injury_status": "No listed injury"},
        {"rank": 2, "athlete_id": "2", "name": "Current Two", "injury_status": "No listed injury"},
    ]
    monkeypatch.setattr(
        game_day,
        "current_prop_eligible_keys",
        lambda abbr: ({"2"}, {"current two"}, {"ok": True, "http": 200}),
    )
    out = audit.audit_team_context(_ctx(qbs, qbs[1]))
    assert out["starter_class"] == "VERIFIED_REPLACEMENT"
    assert out["replacement_reason"] == "not-current-active-roster"


def test_unavailable_selected_qb_fails_closed(monkeypatch):
    qbs = [{"rank": 1, "athlete_id": "1", "name": "Injured One", "injury_status": "Inactive"}]
    monkeypatch.setattr(
        game_day,
        "current_prop_eligible_keys",
        lambda abbr: ({"1"}, {"injured one"}, {"ok": True, "http": 200}),
    )
    with pytest.raises(audit.StarterTruthFailure, match="unavailable QB selected"):
        audit.audit_team_context(_ctx(qbs, qbs[0]))


def test_unjustified_replacement_fails_closed(monkeypatch):
    qbs = [
        {"rank": 1, "athlete_id": "1", "name": "Healthy One", "injury_status": "No listed injury"},
        {"rank": 2, "athlete_id": "2", "name": "Backup Two", "injury_status": "No listed injury"},
    ]
    monkeypatch.setattr(
        game_day,
        "current_prop_eligible_keys",
        lambda abbr: ({"1", "2"}, {"healthy one", "backup two"}, {"ok": True, "http": 200}),
    )
    with pytest.raises(audit.StarterTruthFailure, match="without a verified reason"):
        audit.audit_team_context(_ctx(qbs, qbs[1]))
