from pathlib import Path

from sports_api.api import cfb_team_identity_v1 as identity_api

ROOT = Path(__file__).resolve().parents[1]


def test_team_identity_payload_keeps_exact_espn_ids_and_logo_urls():
    payload = identity_api.build_team_identity_payload(
        "2026-09-19",
        [
            {
                "event_id": "401869940",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
                "away_team_id": "324",
                "home_team_id": "48",
            }
        ],
        {"ok": True},
    )
    assert payload["game_count"] == 1
    row = payload["games"][0]
    assert row["event_id"] == "401869940"
    assert row["away_team_id"] == "324"
    assert row["home_team_id"] == "48"
    assert row["away_logo"].endswith("/324.png")
    assert row["home_logo"].endswith("/48.png")
    assert row["identity_verified"] is True
    assert payload["synthetic_ids"] is False
    assert payload["projection_weight"] == 0.0
    assert payload["may_modify_projection"] is False


def test_team_identity_payload_fails_closed_without_exact_numeric_ids():
    payload = identity_api.build_team_identity_payload(
        "2026-09-19",
        [
            {
                "event_id": "401869940",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
                "away_team_id": "",
                "home_team_id": "48",
            }
        ],
        {"ok": True},
    )
    assert payload["games"] == []
    assert payload["game_count"] == 0


def test_shared_health_router_registers_v164_identity_route():
    source = (ROOT / "sports_api" / "api" / "health.py").read_text(encoding="utf-8")
    assert "cfb_team_identity_v1 import router as cfb_team_identity_router" in source
    assert "router.routes.extend(cfb_team_identity_router.routes)" in source
