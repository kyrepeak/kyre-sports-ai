from pathlib import Path

import pytest
from fastapi import HTTPException

from sports_api.api import cfb_verified_games_v1 as identity

ROOT = Path(__file__).resolve().parents[1]


def _game(event_id: str, day: str, away: str, home: str) -> dict:
    return {
        "event_id": event_id,
        "game_date": day,
        "away_team": away,
        "home_team": home,
        "away_team_id": f"A-{event_id}",
        "home_team_id": f"H-{event_id}",
        "venue": "Test Stadium",
        "broadcast": "Test Network",
        "status": "Scheduled",
        "sources": ["verified test identity"],
    }


def test_verified_games_endpoint_is_date_scoped_feed_independent_and_deduped(monkeypatch):
    target = "2026-09-19"
    local = [
        _game("401900001", target, "Coastal Carolina Chanticleers", "Delaware Blue Hens"),
        _game("OLD-DATE", "2026-09-18", "Old Away", "Old Home"),
    ]
    github = [
        _game("401900001", target, "Coastal Carolina Chanticleers", "Delaware Blue Hens"),
        _game("401900002", target, "Bowling Green Falcons", "Iowa State Cyclones"),
    ]
    espn = [
        _game("401900002", target, "Bowling Green Falcons", "Iowa State Cyclones"),
        _game("401900003", target, "Akron Zips", "Minnesota Golden Gophers"),
    ]

    monkeypatch.setattr(identity, "load_verified_games", lambda: (local, {"snapshot_present": True}))
    monkeypatch.setattr(
        identity,
        "_fetch_github_verified_games",
        lambda: (github, {"ok": True, "source": "GitHub hourly CFB runtime snapshot"}),
    )
    monkeypatch.setattr(
        identity,
        "_fetch_espn_verified_games",
        lambda requested_day: (espn, {"ok": True, "date": requested_day}),
    )

    payload = identity.verified_games(game_date=target)

    assert payload["schema_version"] == "cfb_verified_games_v1"
    assert payload["game_date"] == target
    assert payload["game_count"] == 3
    assert [row["event_id"] for row in payload["games"]] == [
        "401900001",
        "401900002",
        "401900003",
    ]
    assert all(row["identity_verified"] is True for row in payload["games"])
    assert payload["identity_policy"] == {
        "official_id_source": "ESPN event_id",
        "synthetic_ids": False,
        "fuzzy_matching": False,
        "fail_closed": True,
    }
    assert payload["market_semantics"] == {
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
    }


def test_verified_games_endpoint_fails_closed_when_all_identity_sources_fail(monkeypatch):
    monkeypatch.setattr(identity, "load_verified_games", lambda: ([], {"snapshot_present": False}))
    monkeypatch.setattr(
        identity,
        "_fetch_github_verified_games",
        lambda: ([], {"ok": False, "error": "github unavailable"}),
    )
    monkeypatch.setattr(
        identity,
        "_fetch_espn_verified_games",
        lambda requested_day: ([], {"ok": False, "date": requested_day, "error": "espn unavailable"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        identity.verified_games(game_date="2026-09-19")

    assert exc_info.value.status_code == 503
    assert "verified CFB identity unavailable" in str(exc_info.value.detail)


def test_render_entrypoint_explicitly_mounts_verified_games_route():
    wrapper = (ROOT / "sports_api/main_cfb_verified_v1.py").read_text(encoding="utf-8")
    dockerfile = (ROOT / "sports_api/Dockerfile").read_text(encoding="utf-8")

    assert "from sports_api.main import app" in wrapper
    assert "app.add_api_route(" in wrapper
    assert '"/api/v1/cfb/markets/verified-games"' in wrapper
    assert "sports_api.main_cfb_verified_v1:app" in dockerfile
