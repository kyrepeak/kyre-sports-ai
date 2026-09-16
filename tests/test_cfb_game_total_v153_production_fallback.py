from __future__ import annotations

import json
from pathlib import Path

import cfb_game_total_runtime_display_v1 as runtime_display


def _fixture_payload() -> dict:
    return {
        "version": 1,
        "generated_at": "2026-09-16T21:00:00Z",
        "games": [
            {
                "game_date": "2026-09-17",
                "away_team": "Syracuse",
                "home_team": "Pittsburgh",
                "venue": "Acrisure Stadium",
                "broadcast": "ESPN",
                "status": "Scheduled",
                "away": {
                    "team_id": "183",
                    "record_text": "1-1",
                    "ppg": 42.0,
                    "points_allowed_pg": 12.0,
                    "point_diff_pg": 30.0,
                    "recent_form": "WL",
                    "completed_games": [
                        {
                            "date": "2026-09-05",
                            "location": "home",
                            "points_for": 66.0,
                            "points_against": 3.0,
                            "opponent": "New Hampshire Wildcats",
                        },
                        {
                            "date": "2026-09-12",
                            "location": "home",
                            "points_for": 18.0,
                            "points_against": 21.0,
                            "opponent": "California Golden Bears",
                        },
                    ],
                },
                "home": {
                    "team_id": "221",
                    "record_text": "2-0",
                    "ppg": 35.5,
                    "points_allowed_pg": 10.5,
                    "point_diff_pg": 25.0,
                    "recent_form": "WW",
                    "completed_games": [
                        {
                            "date": "2026-09-05",
                            "location": "home",
                            "points_for": 59.0,
                            "points_against": 14.0,
                            "opponent": "Miami (OH)",
                        },
                        {
                            "date": "2026-09-12",
                            "location": "home",
                            "points_for": 12.0,
                            "points_against": 7.0,
                            "opponent": "UCF",
                        },
                    ],
                },
            }
        ],
    }


def test_game_total_snapshot_is_used_before_shared_live_reconciliation(tmp_path, monkeypatch) -> None:
    snapshot = tmp_path / "cfb_game_total_runtime_snapshot_v1.json"
    snapshot.write_text(json.dumps(_fixture_payload()), encoding="utf-8")
    monkeypatch.setattr(runtime_display, "GAME_TOTAL_SNAPSHOT_PATH", snapshot)

    def _must_not_call_live(*args, **kwargs):
        raise AssertionError("shared live reconciliation must not run when Game Total snapshot covers matchup")

    monkeypatch.setattr(runtime_display.frozen_runtime, "reconcile_runtime", _must_not_call_live)

    game = {
        "game_date": "2026-09-17",
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
    }
    display_game, away, home, diag = runtime_display.reconcile_display_bundle(
        game,
        "2026-09-17",
        {"team": "Syracuse"},
        {"team": "Pittsburgh"},
    )

    assert display_game["away_espn_team_id"] == "183"
    assert display_game["home_espn_team_id"] == "221"
    assert display_game["venue"] == "Acrisure Stadium"
    assert display_game["broadcast"] == "ESPN"
    assert away["record_text"] == "1-1"
    assert home["record_text"] == "2-0"
    assert len(away["completed_games"]) == 2
    assert len(home["completed_games"]) == 2
    assert diag["game_total_deterministic_snapshot_used"] is True


def test_checked_in_game_total_snapshot_covers_syracuse_pittsburgh() -> None:
    path = Path("data/cfb_game_total_runtime_snapshot_v1.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("games") or []
    target = next(
        row
        for row in rows
        if row.get("game_date") == "2026-09-17"
        and row.get("away_team") == "Syracuse"
        and row.get("home_team") == "Pittsburgh"
    )

    assert target["away"]["team_id"] == "183"
    assert target["home"]["team_id"] == "221"
    assert target["away"]["record_text"] == "1-1"
    assert target["home"]["record_text"] == "2-0"
    assert len(target["away"]["completed_games"]) == 2
    assert len(target["home"]["completed_games"]) == 2
