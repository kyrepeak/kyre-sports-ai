from pathlib import Path

import nfl_prop_analytics_availability_depth_v1 as step6


def _player(player_id, name, position, team):
    return {
        "espn_id": str(player_id),
        "name": name,
        "position": position,
        "team": team,
        "verified": True,
        "source_count": 2,
    }


def _team_truth(team, base):
    rows = [
        _player(base + 1, f"{team} QB", "QB", team),
        _player(base + 2, f"{team} RB", "RB", team),
        _player(base + 3, f"{team} WR", "WR", team),
        _player(base + 4, f"{team} TE", "TE", team),
    ]
    return {
        "team": team,
        "verified": rows,
        "by_position": {
            pos: [row for row in rows if row["position"] == pos]
            for pos in step6.POSITIONS
        },
        "verified_count": 4,
    }


def _roster_truth():
    return {
        "state": "live",
        "selection_key": "CAR-CLE",
        "teams": {
            "CAR": _team_truth("CAR", 100),
            "CLE": _team_truth("CLE", 200),
        },
    }


def _handoff():
    return {
        "state": "ready",
        "selection_key": "CAR-CLE",
        "away": "CAR",
        "home": "CLE",
        "away_name": "Panthers",
        "home_name": "Browns",
        "target_date": "2026-09-27",
        "week": 3,
    }


def _depth(team, base):
    return {
        str(base + 1): {"espn_id": str(base + 1), "position": "QB", "depth_rank": 1, "source": "ESPN SITE DEPTH"},
        str(base + 2): {"espn_id": str(base + 2), "position": "RB", "depth_rank": 1, "source": "ESPN SITE DEPTH"},
        str(base + 3): {"espn_id": str(base + 3), "position": "WR", "depth_rank": 2, "source": "ESPN SITE DEPTH"},
        str(base + 4): {"espn_id": str(base + 4), "position": "TE", "depth_rank": 1, "source": "ESPN SITE DEPTH"},
    }, {"ok": True, "team": team, "source": "ESPN SITE DEPTH", "http": 200}


def test_step6_contract_is_availability_depth_only():
    source = Path("nfl_prop_analytics_availability_depth_v1.py").read_text()
    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 6 GAME-DAY AVAILABILITY + DEPTH ROLES"',
        "STEP = 6",
        "PAGE = 2",
        "AVAILABILITY_DEPTH_ONLY = True",
        "PLAYER_PROP_LOGIC = False",
        "SPORTSBOOK_ODDS_LOGIC = False",
        "PROJECTION_LOGIC = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        'data-nfl-prop-analytics-step6-availability="v1"',
        'data-prop-step6-availability-state=',
        'data-prop-step6-depth-verified=',
    ):
        assert token in source, token


def test_pending_does_not_get_promoted_to_available():
    row = _player(101, "CAR QB", "QB", "CAR")
    state, label = step6._availability_for_player(
        row,
        snapshot={"state": "PENDING", "away_unavailable": []},
        side="away",
    )
    assert state == "PENDING"
    assert label == "GAME-DAY PENDING"


def test_exact_event_unavailable_overrides_pending():
    row = _player(101, "CAR QB", "QB", "CAR")
    state, label = step6._availability_for_player(
        row,
        snapshot={
            "state": "PENDING",
            "away_unavailable": [
                {"athlete_id": "101", "name": "CAR QB", "status": "Inactive"}
            ],
        },
        side="away",
    )
    assert state == "UNAVAILABLE"
    assert label == "INACTIVE"


def test_confirmed_unlisted_player_can_be_available():
    row = _player(101, "CAR QB", "QB", "CAR")
    state, label = step6._availability_for_player(
        row,
        snapshot={"state": "CONFIRMED", "away_unavailable": []},
        side="away",
    )
    assert state == "AVAILABLE"
    assert label == "GAME-DAY AVAILABLE"


def test_exact_depth_id_attaches_role_without_changing_identity():
    team = _team_truth("CAR", 100)
    depth, diag = _depth("CAR", 100)
    annotated = step6._annotate_team(
        team,
        depth_rows=depth,
        depth_diag=diag,
        snapshot={"state": "PENDING", "away_unavailable": []},
        side="away",
    )
    qb = annotated["by_position"]["QB"][0]
    wr = annotated["by_position"]["WR"][0]
    assert qb["espn_id"] == "101"
    assert qb["depth_verified"] is True
    assert qb["depth_role"] == "QB1 • STARTER"
    assert wr["depth_role"] == "WR2 • DEPTH"
    assert all(row["availability_state"] == "PENDING" for row in annotated["players"])


def test_load_step6_accepts_pending_as_truth_not_availability_confirmation(monkeypatch):
    monkeypatch.setattr(
        step6,
        "resolve_espn_event",
        lambda handoff: {
            "ok": True,
            "event_id": "401999999",
            "state": "pre",
            "http": 200,
        },
    )
    monkeypatch.setattr(
        step6.game_day,
        "load_event_injury_map",
        lambda event_id: ({}, {"ok": True, "http": 200}),
    )
    monkeypatch.setattr(
        step6.game_day,
        "event_availability_snapshot",
        lambda *args, **kwargs: {
            "state": "PENDING",
            "prop_gate_open": False,
            "away_unavailable": [],
            "home_unavailable": [],
        },
    )
    monkeypatch.setattr(
        step6,
        "_load_team_depth",
        lambda team, season: _depth(team, 100 if team == "CAR" else 200),
    )

    truth = step6.load_availability_depth_truth(_handoff(), _roster_truth())
    assert truth["state"] == "live"
    assert truth["availability_state"] == "PENDING"
    assert truth["availability_confirmed"] is False
    assert truth["pending_count"] == 8
    assert truth["depth_verified_count"] == 8


def test_load_step6_marks_exact_event_inactive_and_keeps_others_pending(monkeypatch):
    monkeypatch.setattr(
        step6,
        "resolve_espn_event",
        lambda handoff: {
            "ok": True,
            "event_id": "401999999",
            "state": "pre",
            "http": 200,
        },
    )
    monkeypatch.setattr(
        step6.game_day,
        "load_event_injury_map",
        lambda event_id: ({}, {"ok": True, "http": 200}),
    )
    monkeypatch.setattr(
        step6.game_day,
        "event_availability_snapshot",
        lambda *args, **kwargs: {
            "state": "PENDING",
            "prop_gate_open": False,
            "away_unavailable": [
                {"athlete_id": "101", "name": "CAR QB", "status": "Inactive"}
            ],
            "home_unavailable": [],
        },
    )
    monkeypatch.setattr(
        step6,
        "_load_team_depth",
        lambda team, season: _depth(team, 100 if team == "CAR" else 200),
    )

    truth = step6.load_availability_depth_truth(_handoff(), _roster_truth())
    assert truth["state"] == "live"
    assert truth["unavailable_count"] == 1
    car_qb = truth["teams"]["CAR"]["by_position"]["QB"][0]
    assert car_qb["availability_state"] == "UNAVAILABLE"
    assert car_qb["availability_label"] == "INACTIVE"


def test_missing_required_position_depth_fails_closed(monkeypatch):
    monkeypatch.setattr(
        step6,
        "resolve_espn_event",
        lambda handoff: {
            "ok": True,
            "event_id": "401999999",
            "state": "pre",
            "http": 200,
        },
    )
    monkeypatch.setattr(
        step6.game_day,
        "load_event_injury_map",
        lambda event_id: ({}, {"ok": True, "http": 200}),
    )
    monkeypatch.setattr(
        step6.game_day,
        "event_availability_snapshot",
        lambda *args, **kwargs: {
            "state": "PENDING",
            "away_unavailable": [],
            "home_unavailable": [],
        },
    )

    def fake_depth(team, season):
        rows, diag = _depth(team, 100 if team == "CAR" else 200)
        rows = {k: v for k, v in rows.items() if v["position"] != "TE"}
        return rows, {**diag, "ok": True}

    monkeypatch.setattr(step6, "_load_team_depth", fake_depth)
    truth = step6.load_availability_depth_truth(_handoff(), _roster_truth())
    assert truth["state"] == "fail-closed"
    assert truth["reason"] == "required position depth roles incomplete"


def test_unverified_exact_event_provider_fails_closed(monkeypatch):
    monkeypatch.setattr(
        step6,
        "resolve_espn_event",
        lambda handoff: {
            "ok": False,
            "event_id": "",
            "state": "",
            "reason": "exact ESPN matchup not found",
        },
    )
    truth = step6.load_availability_depth_truth(_handoff(), _roster_truth())
    assert truth["state"] == "fail-closed"


def test_hub_orders_step6_after_step5_live_roster():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    assert "roster_truth = render_verified_roster_truth(handoff)" in hub
    assert 'roster_truth.get("state") == "live"' in hub
    assert "render_availability_depth_truth(handoff, roster_truth)" in hub
    assert hub.index("render_verified_roster_truth(handoff)") < hub.index(
        "render_availability_depth_truth(handoff, roster_truth)"
    )


def test_step6_keeps_prop_odds_projection_flags_off():
    assert step6.PLAYER_PROP_LOGIC is False
    assert step6.SPORTSBOOK_ODDS_LOGIC is False
    assert step6.PROJECTION_LOGIC is False
    assert step6.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step6.MAY_MODIFY_PASSING_YARDS is False
    assert step6.MAY_MODIFY_EXISTING_NFL_MARKETS is False
