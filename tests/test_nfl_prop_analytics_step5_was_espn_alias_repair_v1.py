import nfl_prop_analytics_roster_truth_v1 as step5


def test_was_uses_wsh_only_at_espn_lookup_boundary(monkeypatch):
    calls = []

    def fake_roster(team):
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

    monkeypatch.setattr(step5.game_day, "load_current_team_roster", fake_roster)

    rows, diag = step5._espn_team_rows("WAS")

    assert calls == ["WSH"]
    assert diag["ok"] is True
    assert rows[0]["espn_id"] == "1"
    assert rows[0]["position"] == "QB"


def test_non_washington_team_passes_through_unchanged(monkeypatch):
    calls = []

    monkeypatch.setattr(
        step5.game_day,
        "load_current_team_roster",
        lambda team: (calls.append(team) or [], {"ok": True, "http": 200}),
    )

    step5._espn_team_rows("IND")
    assert calls == ["IND"]


def test_canonical_output_contract_stays_was():
    assert step5._canon_team("WSH") == "WAS"
    assert step5.ESPN_TEAM_ALIASES["WAS"] == "WSH"



def _weekly_row(team, week, player_id, position="QB"):
    return {
        "season": 2026,
        "week": week,
        "team": team,
        "position": position,
        "status": "ACT",
        "full_name": f"{team} {position}",
        "espn_id": player_id,
        "jersey_number": 1,
        "gsis_id": f"00-{player_id}",
        "headshot_url": "",
    }


def test_exact_nflverse_week_wins_over_fallback():
    import pandas as pd

    frame = pd.DataFrame([
        _weekly_row("IND", 3, 101),
        _weekly_row("WAS", 3, 201),
        _weekly_row("IND", 4, 102),
        _weekly_row("WAS", 4, 202),
    ])
    week, fallback = step5._resolve_nflverse_week(
        frame,
        away="IND",
        home="WAS",
        season=2026,
        requested_week=4,
        target_date="2099-10-04",
    )
    assert week == 4
    assert fallback is False


def test_current_future_target_allows_exactly_one_week_latest_published_fallback():
    import pandas as pd

    frame = pd.DataFrame([
        _weekly_row("IND", 3, 101),
        _weekly_row("WAS", 3, 201),
    ])
    week, fallback = step5._resolve_nflverse_week(
        frame,
        away="IND",
        home="WAS",
        season=2026,
        requested_week=4,
        target_date="2099-10-04",
    )
    assert week == 3
    assert fallback is True


def test_fallback_fails_closed_when_more_than_one_week_stale():
    import pandas as pd

    frame = pd.DataFrame([
        _weekly_row("IND", 2, 101),
        _weekly_row("WAS", 2, 201),
    ])
    week, fallback = step5._resolve_nflverse_week(
        frame,
        away="IND",
        home="WAS",
        season=2026,
        requested_week=4,
        target_date="2099-10-04",
    )
    assert week is None
    assert fallback is False


def test_fallback_requires_common_week_for_both_teams():
    import pandas as pd

    frame = pd.DataFrame([
        _weekly_row("IND", 3, 101),
        _weekly_row("WAS", 2, 201),
    ])
    week, fallback = step5._resolve_nflverse_week(
        frame,
        away="IND",
        home="WAS",
        season=2026,
        requested_week=4,
        target_date="2099-10-04",
    )
    assert week is None
    assert fallback is False
