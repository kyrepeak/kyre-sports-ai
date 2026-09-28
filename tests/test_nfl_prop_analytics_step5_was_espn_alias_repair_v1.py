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
