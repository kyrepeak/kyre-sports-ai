from __future__ import annotations


def _context() -> dict:
    return {
        "state": "ready",
        "official_game_id": "401999001",
        "espn_event_id": "401999001",
        "slate_date": "2026-10-24",
        "away_team_id": "101",
        "away_team": "Away State",
        "away_abbr": "AWY",
        "home_team_id": "202",
        "home_team": "Home Tech",
        "home_abbr": "HOM",
    }


def _athlete(pid: str, name: str, position: str, **extra) -> dict:
    row = {
        "id": pid,
        "fullName": name,
        "position": {"abbreviation": position},
    }
    row.update(extra)
    return row


def test_offensive_roster_keeps_only_qb_rb_wr_te_and_preserves_verified_metadata(monkeypatch):
    import cfb_player_props_page2_roster_v1 as roster

    calls: list[str] = []
    payloads = {
        "101": {
            "athletes": [
                _athlete("qb1", "Quarter Back", "QB", jersey="7", experience={"displayValue": "Junior"}, headshot={"href": "https://img.example/qb1.png"}),
                _athlete("rb1", "Runner One", "RB", jersey="2"),
                _athlete("wr1", "Wide One", "WR"),
                _athlete("te1", "Tight One", "TE"),
                _athlete("ol1", "Line One", "OL"),
                _athlete("qb1", "Quarter Back", "QB", jersey="7"),
            ]
        },
        "202": {"athletes": [_athlete("qb2", "Home Quarter", "QB", jersey="12")]},
    }

    def fake_fetch(team_id: str):
        calls.append(team_id)
        return payloads[team_id], []

    monkeypatch.setattr(roster.environment, "_fetch_roster", fake_fetch)
    out = roster.load_offensive_roster(_context())

    assert calls == ["101", "202"]
    assert [p.position for p in out["away"]] == ["QB", "RB", "WR", "TE"]
    assert [p.official_player_id for p in out["away"]] == ["qb1", "rb1", "wr1", "te1"]
    qb = out["away"][0]
    assert qb.official_team_id == "101"
    assert qb.canonical_name == "Quarter Back"
    assert qb.jersey_number == "7"
    assert qb.class_year == "Junior"
    assert qb.headshot_url == "https://img.example/qb1.png"
    assert out["away"][1].headshot_url == ""
    assert len({p.official_player_id for p in out["away"]}) == len(out["away"])


def test_roster_never_drops_explicit_out_player(monkeypatch):
    import cfb_player_props_page2_roster_v1 as roster

    monkeypatch.setattr(
        roster.environment,
        "_fetch_roster",
        lambda team_id: ({"athletes": [_athlete(f"{team_id}-qb", "Still Listed", "QB", status={"name": "Out"})]}, []),
    )
    out = roster.load_offensive_roster(_context())
    assert [p.canonical_name for p in out["away"]] == ["Still Listed"]
    assert [p.canonical_name for p in out["home"]] == ["Still Listed"]


def test_availability_requires_explicit_player_status_and_fails_closed():
    import cfb_player_props_page2_availability_v1 as availability

    assert availability.normalize_availability(
        {"athletes": [{"id": "p1", "status": {"name": "Out"}}]}, player_id="p1"
    )["state"] == "OUT"
    assert availability.normalize_availability(
        {"athletes": [{"id": "p1", "status": {"name": "Doubtful"}}]}, player_id="p1"
    )["state"] == "DOUBTFUL"
    assert availability.normalize_availability(
        {"athletes": [{"id": "p1", "status": {"name": "Questionable"}}]}, player_id="p1"
    )["state"] == "QUESTIONABLE"
    assert availability.normalize_availability(
        {"athletes": [{"id": "p1", "status": {"name": "Active"}}]}, player_id="p1"
    )["state"] == "AVAILABLE"

    # Roster presence, recent production, or a betting price cannot certify health.
    unknown = availability.normalize_availability(
        {"athletes": [{"id": "p1", "statistics": {"yards": 200}, "price": -110}]},
        player_id="p1",
    )
    assert unknown["state"] == "UNVERIFIED"
    assert unknown["verified"] is False


def test_availability_ignores_other_players_and_ambiguous_labels():
    import cfb_player_props_page2_availability_v1 as availability

    out = availability.normalize_availability(
        {"athletes": [
            {"id": "other", "status": {"name": "Out"}},
            {"id": "p1", "status": {"name": "Expected to play"}},
        ]},
        player_id="p1",
    )
    assert out["state"] == "UNVERIFIED"
    assert out["verified"] is False


def test_game_availability_reads_exact_event_summary_once(monkeypatch):
    import cfb_player_props_page2_availability_v1 as availability
    import cfb_player_props_page2_roster_v1 as roster
    from cfb_player_props_identity_v1 import CanonicalPlayerIdentity

    players = [
        roster.Page2Player(CanonicalPlayerIdentity("p1", "101", "Away QB", "QB", "Away State", "AWY")),
        roster.Page2Player(CanonicalPlayerIdentity("p2", "202", "Home RB", "RB", "Home Tech", "HOM")),
    ]
    calls: list[str] = []

    def fake_summary(event_id: str):
        calls.append(event_id)
        return {
            "injuries": [
                {"athlete": {"id": "p1"}, "status": "Out"},
                {"athlete": {"id": "p2"}, "status": "Active"},
            ]
        }, []

    monkeypatch.setattr(availability.environment, "_fetch_summary", fake_summary)
    out = availability.load_game_availability(_context(), players)
    assert calls == ["401999001"]
    assert out["p1"]["state"] == "OUT"
    assert out["p2"]["state"] == "AVAILABLE"
