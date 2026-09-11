from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_identity_v1 as identity


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_verified_depth_qb1_is_resolved_without_projection(monkeypatch) -> None:
    payload = {
        "depthCharts": [{
            "positions": {
                "qb": {
                    "position": {"abbreviation": "QB", "name": "Quarterback"},
                    "athletes": [
                        {"rank": 1, "athlete": {"id": "100", "displayName": "Verified QB One"}},
                        {"rank": 2, "athlete": {"id": "101", "displayName": "Verified QB Two"}},
                    ],
                }
            }
        }]
    }
    monkeypatch.setattr(identity.depth_base, "_depth_payload", lambda team_id: (payload, {"ok": True, "http": 200}))
    ctx = identity.resolve_team_qb_identity("IND", "Indianapolis Colts", 2026, {"IND": []}, True)
    assert ctx["depth_state"] == "VERIFIED"
    assert ctx["identity_verified"] is True
    assert ctx["qb1"]["athlete_id"] == "100"
    assert ctx["qb1"]["name"] == "Verified QB One"


def test_roster_fallback_never_becomes_verified_qb1(monkeypatch) -> None:
    monkeypatch.setattr(identity.depth_base, "_depth_payload", lambda team_id: ({}, {"ok": False, "http": 404}))
    monkeypatch.setattr(identity.depth_repair, "_core_depth_payload", lambda year, team_id: ({}, {"ok": False, "http": 404}))
    roster = {
        "athletes": [{
            "position": "Quarterback",
            "items": [{
                "id": "200",
                "displayName": "Roster Only QB",
                "position": {"abbreviation": "QB", "name": "Quarterback"},
            }],
        }]
    }
    monkeypatch.setattr(identity.depth_base, "_roster_payload", lambda team_id: (roster, {"ok": True, "http": 200}))
    ctx = identity.resolve_team_qb_identity("IND", "Indianapolis Colts", 2026, {"IND": []}, True)
    assert ctx["depth_state"] == "ROSTER FALLBACK"
    assert ctx["identity_verified"] is False
    assert ctx["qb1"] == {}


def test_invalid_game_id_fails_closed_before_external_identity_calls() -> None:
    out = identity.resolve_matchup_identity({"game_id": "synthetic-game"}, 2026)
    assert out["ready"] is False
    assert "official ESPN game ID" in out["reason"]


def test_step1_route_is_additive_and_preserves_v80() -> None:
    hub = _read("nfl_hub_v20.py")
    router = _read("streamlit_memory_lazy_router_v81.py")
    app = _read("app.py")

    assert "import nfl_hub_v19 as base" in hub
    assert "nfl_passing_yards_hub_v2" in hub
    assert "import streamlit_memory_lazy_router_v80 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v20"' in router
    assert "streamlit_memory_lazy_router_v81" in app
    assert "STREAMLIT_MAIN_V80_NFL_PASSING_YARDS_COMPACT_FOUNDATION_2026-09-11" in app
    assert "STREAMLIT_MAIN_V81_NFL_PASSING_YARDS_STEP1_IDENTITY_2026-09-11" in app


def test_step1_page_keeps_betting_model_off() -> None:
    page = _read("nfl_passing_yards_hub_v2.py")
    resolver = _read("nfl_passing_yards_identity_v1.py")
    assert "STEP 1 IDENTITY GREEN" in page
    assert "sportsbook influence 0.0%" in page
    assert "projection/Monte Carlo/ranking/recommendation OFF" in page
    assert "roster fallback never counts as verified QB1" in page
    assert "never promoted to verified QB1" in resolver
