import nfl_passing_yards_identity_v1 as identity


def test_unavailable_qb1_does_not_poison_verified_replacement(monkeypatch):
    qbs = [
        {
            "rank": 1,
            "athlete_id": "14",
            "name": "Sam Darnold",
            "source": "ESPN CORE DEPTH CHART",
        },
        {
            "rank": 2,
            "athlete_id": "3924327",
            "name": "Drew Lock",
            "source": "ESPN CORE DEPTH CHART",
        },
    ]

    monkeypatch.setattr(identity.depth_base, "_depth_payload", lambda team_id: ({}, {"ok": True, "http": 200}))
    monkeypatch.setattr(identity.depth_base, "_parse_qb_depth", lambda payload: list(qbs))
    monkeypatch.setattr(
        identity.game_day,
        "current_prop_eligible_keys",
        lambda abbr: (
            {"14", "3924327"},
            {"sam darnold", "drew lock"},
            {"ok": True, "http": 200},
        ),
    )

    injury_map = {
        "SEA": [
            {
                "athlete_id": "14",
                "name": "Sam Darnold",
                "status": "Out",
                "detail": "Ruled out",
            }
        ]
    }

    out = identity.resolve_team_qb_identity(
        "SEA",
        "Seattle Seahawks",
        2026,
        injury_map=injury_map,
        injury_feed_ok=True,
    )

    assert out["identity_verified"] is True
    assert out["qb1"]["athlete_id"] == "3924327"
    assert out["qb1"]["name"] == "Drew Lock"
    assert out["availability_alert"] is False
    assert out["transaction_alert"] is False
