from pathlib import Path

import pandas as pd
# exact-head CI proof trigger for strict pregame roster-week fallback

import nfl_prop_analytics_roster_truth_v1 as step5


def _espn_row(player_id, name, position, active=True):
    return {
        "espn_id": str(player_id),
        "name": name,
        "position": position,
        "roster_status": "Active",
        "group_label": position,
        "active": active,
    }


def _nflverse_row(player_id, name, position, status="ACT", jersey="1"):
    return {
        "espn_id": str(player_id),
        "name": name,
        "position": position,
        "status": status,
        "jersey_number": jersey,
        "gsis_id": f"00-{player_id}",
        "headshot_url": "",
        "active": step5._nflverse_active(status),
    }


def test_step5_contract_is_roster_truth_only():
    source = Path("nfl_prop_analytics_roster_truth_v1.py").read_text()
    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 5 VERIFIED ROSTER TRUTH"',
        "STEP = 5",
        "PAGE = 2",
        "ROSTER_TRUTH_ONLY = True",
        "PLAYER_PROP_LOGIC = False",
        "SPORTSBOOK_ODDS_LOGIC = False",
        "PROJECTION_LOGIC = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        'data-nfl-prop-analytics-step5-roster="v1"',
        'data-prop-roster-verified="true"',
        "weekly_rosters/roster_weekly_{season}.csv",
    ):
        assert token in source, token


def test_exact_cross_source_id_and_position_required_for_verified():
    truth = step5._reconcile_team_roster(
        team="CAR",
        espn_rows=[
            _espn_row("1", "QB One", "QB"),
            _espn_row("2", "RB One", "RB"),
            _espn_row("3", "WR One", "WR"),
            _espn_row("4", "TE One", "TE"),
        ],
        nflverse_rows=[
            _nflverse_row("1", "QB One", "QB"),
            _nflverse_row("2", "RB One", "RB"),
            _nflverse_row("3", "WR One", "WR"),
            _nflverse_row("4", "TE One", "TE"),
        ],
    )
    assert truth["verified_count"] == 4
    assert truth["disagreement_count"] == 0
    assert set(truth["by_position"]) == {"QB", "RB", "WR", "TE"}
    assert all(row["source_count"] == 2 for row in truth["verified"])
    assert all(row["verified"] is True for row in truth["verified"])


def test_missing_source_or_position_mismatch_fails_closed_for_player():
    truth = step5._reconcile_team_roster(
        team="CLE",
        espn_rows=[
            _espn_row("1", "QB One", "QB"),
            _espn_row("2", "RB One", "RB"),
            _espn_row("3", "WR One", "WR"),
        ],
        nflverse_rows=[
            _nflverse_row("1", "QB One", "QB"),
            _nflverse_row("2", "RB One", "WR"),
            _nflverse_row("9", "TE Other", "TE"),
        ],
    )
    assert [row["espn_id"] for row in truth["verified"]] == ["1"]
    assert truth["disagreement_count"] == 3


def test_inactive_source_row_never_verifies():
    truth = step5._reconcile_team_roster(
        team="CAR",
        espn_rows=[_espn_row("1", "QB One", "QB", active=True)],
        nflverse_rows=[_nflverse_row("1", "QB One", "QB", status="INA")],
    )
    assert truth["verified_count"] == 0
    assert truth["disagreement_count"] == 1


def test_nflverse_week_filter_uses_exact_season_week_team_and_position():
    frame = pd.DataFrame([
        {"season": 2026, "week": 3, "team": "CAR", "position": "QB", "status": "ACT", "full_name": "QB One", "espn_id": 1, "jersey_number": 10, "gsis_id": "00-1", "headshot_url": ""},
        {"season": 2026, "week": 2, "team": "CAR", "position": "QB", "status": "ACT", "full_name": "Old QB", "espn_id": 2, "jersey_number": 11, "gsis_id": "00-2", "headshot_url": ""},
        {"season": 2026, "week": 3, "team": "CLE", "position": "QB", "status": "ACT", "full_name": "Other QB", "espn_id": 3, "jersey_number": 12, "gsis_id": "00-3", "headshot_url": ""},
        {"season": 2026, "week": 3, "team": "CAR", "position": "LB", "status": "ACT", "full_name": "LB One", "espn_id": 4, "jersey_number": 50, "gsis_id": "00-4", "headshot_url": ""},
    ])
    rows = step5._nflverse_team_week(frame, team="CAR", season=2026, week=3)
    assert len(rows) == 1
    assert rows[0]["espn_id"] == "1"
    assert rows[0]["position"] == "QB"


def _weekly_frame_for_roster_weeks(weeks):
    rows = []
    for week in weeks:
        for team, base in (("IND", 100), ("WAS", 200)):
            for offset, pos in enumerate(("QB", "RB", "WR", "TE"), start=1):
                rows.append({
                    "season": 2026,
                    "week": week,
                    "team": team,
                    "position": pos,
                    "status": "ACT",
                    "full_name": f"{team} {pos}",
                    "espn_id": base + offset,
                    "jersey_number": offset,
                    "gsis_id": f"00-{base + offset}",
                    "headshot_url": "",
                })
    return pd.DataFrame(rows)


def test_nflverse_roster_week_prefers_exact_requested_week():
    frame = _weekly_frame_for_roster_weeks((3, 4))
    week, diag = step5._resolve_nflverse_roster_week(
        frame,
        teams=("IND", "WAS"),
        season=2026,
        requested_week=4,
        allow_previous_week=True,
    )
    assert week == 4
    assert diag["ok"] is True
    assert diag["lag"] == 0


def test_nflverse_roster_week_allows_only_immediate_prior_week_pregame():
    frame = _weekly_frame_for_roster_weeks((1, 2, 3))
    week, diag = step5._resolve_nflverse_roster_week(
        frame,
        teams=("IND", "WAS"),
        season=2026,
        requested_week=4,
        allow_previous_week=True,
    )
    assert week == 3
    assert diag["ok"] is True
    assert diag["lag"] == 1


def test_nflverse_roster_week_rejects_stale_or_nonpregame_fallback():
    frame = _weekly_frame_for_roster_weeks((1, 2))
    stale_week, stale_diag = step5._resolve_nflverse_roster_week(
        frame,
        teams=("IND", "WAS"),
        season=2026,
        requested_week=4,
        allow_previous_week=True,
    )
    assert stale_week is None
    assert stale_diag["ok"] is False

    frame = _weekly_frame_for_roster_weeks((1, 2, 3))
    closed_week, closed_diag = step5._resolve_nflverse_roster_week(
        frame,
        teams=("IND", "WAS"),
        season=2026,
        requested_week=4,
        allow_previous_week=False,
    )
    assert closed_week is None
    assert closed_diag["ok"] is False


def test_espn_roster_boundary_maps_canonical_was_to_provider_wsh(monkeypatch):
    calls = []

    def fake_loader(team):
        calls.append(team)
        return (
            [
                {
                    "athlete_id": "1",
                    "name": "Washington QB",
                    "position": "QB",
                    "roster_status": "Active",
                    "group_label": "QB",
                    "prop_eligible": True,
                }
            ],
            {"ok": True, "http": 200},
        )

    monkeypatch.setattr(step5.game_day, "load_current_team_roster", fake_loader)
    rows, diag = step5._espn_team_rows("WAS")

    assert calls == ["WSH"]
    assert diag["ok"] is True
    assert rows[0]["espn_id"] == "1"
    assert rows[0]["position"] == "QB"
    assert step5._canon_team("WSH") == "WAS"


def test_load_truth_requires_all_four_positions_on_both_teams(monkeypatch):
    frame = pd.DataFrame([
        {"season": 2026, "week": 3, "team": team, "position": pos, "status": "ACT", "full_name": f"{team} {pos}", "espn_id": idx, "jersey_number": idx, "gsis_id": f"00-{idx}", "headshot_url": ""}
        for team, base in (("CAR", 100), ("CLE", 200))
        for idx, pos in ((base + 1, "QB"), (base + 2, "RB"), (base + 3, "WR"), (base + 4, "TE"))
    ])

    monkeypatch.setattr(
        step5,
        "_load_nflverse_weekly",
        lambda season: (frame, {"ok": True, "http": 200, "rows": len(frame)}),
    )

    def fake_espn(team):
        base = 100 if team == "CAR" else 200
        return (
            [
                _espn_row(base + 1, f"{team} QB", "QB"),
                _espn_row(base + 2, f"{team} RB", "RB"),
                _espn_row(base + 3, f"{team} WR", "WR"),
                _espn_row(base + 4, f"{team} TE", "TE"),
            ],
            {"ok": True, "http": 200},
        )

    monkeypatch.setattr(step5, "_espn_team_rows", fake_espn)

    truth = step5.load_verified_roster_truth({
        "state": "ready",
        "selection_key": "CAR-CLE",
        "away": "CAR",
        "home": "CLE",
        "target_date": "2026-09-27",
        "week": 3,
    })
    assert truth["state"] == "live"
    assert truth["source_count"] == 2
    assert truth["verified_count"] == 8
    assert truth["disagreement_count"] == 0


def test_load_truth_fails_closed_when_one_position_missing(monkeypatch):
    frame = pd.DataFrame([
        {"season": 2026, "week": 3, "team": "CAR", "position": "QB", "status": "ACT", "full_name": "CAR QB", "espn_id": 101, "jersey_number": 1, "gsis_id": "00-101", "headshot_url": ""},
        {"season": 2026, "week": 3, "team": "CLE", "position": "QB", "status": "ACT", "full_name": "CLE QB", "espn_id": 201, "jersey_number": 1, "gsis_id": "00-201", "headshot_url": ""},
    ])
    monkeypatch.setattr(
        step5,
        "_load_nflverse_weekly",
        lambda season: (frame, {"ok": True, "http": 200}),
    )
    monkeypatch.setattr(
        step5,
        "_espn_team_rows",
        lambda team: ([_espn_row("101" if team == "CAR" else "201", f"{team} QB", "QB")], {"ok": True, "http": 200}),
    )

    truth = step5.load_verified_roster_truth({
        "state": "ready",
        "selection_key": "CAR-CLE",
        "away": "CAR",
        "home": "CLE",
        "target_date": "2026-09-27",
        "week": 3,
    })
    assert truth["state"] == "fail-closed"


def test_hub_runs_roster_then_availability_before_unified_roster():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    current_contract = """handoff = render_matchup_shell()
        if handoff:
            render_page2_responsive_polish()
            roster_truth = load_verified_roster_truth(handoff)
            if roster_truth and roster_truth.get("state") == "live":
                availability_truth = load_availability_depth_truth(handoff, roster_truth)
                if availability_truth and availability_truth.get("state") == "live":
                    render_unified_roster_availability(handoff, roster_truth, availability_truth)
"""
    assert current_contract in hub
    assert "render_verified_roster_truth(handoff)" not in hub

    handoff_index = hub.index("handoff = render_matchup_shell()")
    roster_index = hub.index("roster_truth = load_verified_roster_truth(handoff)", handoff_index)
    availability_index = hub.index(
        "availability_truth = load_availability_depth_truth(handoff, roster_truth)",
        roster_index,
    )
    unified_index = hub.index(
        "render_unified_roster_availability(handoff, roster_truth, availability_truth)",
        availability_index,
    )
    assert handoff_index < roster_index < availability_index < unified_index


def test_step5_does_not_add_prop_odds_projection_or_passing_yards_logic():
    source = Path("nfl_prop_analytics_roster_truth_v1.py").read_text().lower()
    forbidden = (
        "sportsbook_line",
        "projection_model",
        "market_probability",
        "passing_yards_hub",
    )
    for token in forbidden:
        assert token not in source, token
