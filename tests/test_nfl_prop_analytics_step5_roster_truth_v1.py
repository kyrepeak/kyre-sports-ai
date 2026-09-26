from pathlib import Path

import pandas as pd

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


def test_hub_renders_step5_only_after_step4_handoff_ready():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    assert "handoff = render_matchup_shell()" in hub
    assert "if handoff:" in hub
    assert "render_verified_roster_truth(handoff)" in hub
    assert hub.index("render_matchup_shell()") < hub.index("render_verified_roster_truth(handoff)")


def test_step5_does_not_add_prop_odds_projection_or_passing_yards_logic():
    source = Path("nfl_prop_analytics_roster_truth_v1.py").read_text().lower()
    forbidden = (
        "sportsbook_line",
        "projection_model",
        "market_probability",
        "recommendation",
        "passing_yards_hub",
    )
    for token in forbidden:
        assert token not in source, token
