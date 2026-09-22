from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import nfl_receiving_yards_context_api_v1 as client


ROOT = Path(__file__).resolve().parents[1]
EVENT_ID = "401872925"
CAPTURED = "2026-09-13T16:43:21+00:00"
NOW = datetime(2026, 9, 13, 16, 43, 25, tzinfo=timezone.utc)


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _player(athlete_id: str, team_id: str, *, targets: bool) -> dict:
    return {
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "player_name": f"Receiver {athlete_id}",
        "position": "WR",
        "sample_games": 2,
        "receptions": 9,
        "receiving_yards": 126,
        "yards_per_reception": 14.0,
        "receptions_per_game": 4.5,
        "receiving_yards_per_game": 63.0,
        "receiving_touchdowns": 1,
        "targets_data_available": targets,
        "target_sample_games": 2 if targets else 0,
        "targets": 14 if targets else None,
        "targets_per_game": 7.0 if targets else None,
        "baseline_season": 2025,
    }


def _defense(team_id: str) -> dict:
    return {
        "official_team_id": team_id,
        "baseline_season": 2025,
        "sample_games": 17,
        "receptions_allowed_per_game": 21.0,
        "receiving_yards_allowed_per_game": 230.0,
        "yards_per_reception_allowed": 10.95,
        "receiving_touchdowns_allowed_per_game": 1.4,
        "targets_data_available": False,
        "target_sample_games": 0,
        "targets_allowed_per_game": None,
        "data_available": True,
    }


def _payload() -> dict:
    return {
        "schema_version": client.SCHEMA_VERSION,
        "ready": True,
        "official_event_id": EVENT_ID,
        "captured_at_utc": CAPTURED,
        "season": 2026,
        "identity": {
            "official_event_id_required": True,
            "official_athlete_id_required": True,
            "official_team_id_required": True,
            "player_name_display_only": True,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
            "targets_inferred": False,
        },
        "teams": [
            {
                "official_team_id": "4",
                "opponent_official_team_id": "27",
                "team_name": "Cincinnati Bengals",
                "team_abbreviation": "CIN",
                "home_away": "home",
                "player_baseline_season": 2025,
                "players": [_player("1001", "4", targets=True)],
                "opponent_pass_defense": _defense("27"),
            },
            {
                "official_team_id": "27",
                "opponent_official_team_id": "4",
                "team_name": "Tampa Bay Buccaneers",
                "team_abbreviation": "TB",
                "home_away": "away",
                "player_baseline_season": 2025,
                "players": [_player("2002", "27", targets=False)],
                "opponent_pass_defense": _defense("4"),
            },
        ],
        "source_note": "test fixture",
    }


def test_client_accepts_exact_id_explicit_target_contract():
    result = client.validate_context_payload(_payload(), EVENT_ID, now_utc=NOW)
    assert result["ready"] is True
    assert result["data_available"] is True
    assert result["sportsbook_influence"] == 0.0
    assert result["targets_inferred"] is False
    assert len(result["teams"]) == 2
    assert result["teams"][0]["players"][0]["targets"] == 14
    assert result["teams"][1]["players"][0]["targets"] is None


def test_client_rejects_inferred_targets():
    payload = _payload()
    player = payload["teams"][1]["players"][0]
    player["targets"] = 11
    player["targets_per_game"] = 5.5
    result = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "targets" in result["reason"].lower()


def test_client_rejects_wrong_or_duplicate_identity():
    payload = _payload()
    payload["teams"][1]["players"][0]["official_athlete_id"] = "1001"
    result = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
    assert result["ready"] is False
    assert "duplicate" in result["reason"].lower()


def test_step2_page_is_additive_over_receiving_v1_and_uses_exact_id_visuals():
    source = _source("nfl_receiving_yards_hub_v2.py")
    assert "import nfl_receiving_yards_hub_v1 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v1"' in source
    assert "PAGE_BUILD_STEP = 2" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "https://a.espncdn.com/i/headshots/nfl/players/full/" in source
    assert "https://a.espncdn.com/i/teamlogos/nfl/500/" in source
    assert "official_athlete_id" in source
    assert "official_team_id" in source
    assert "EXACT-ID RECEIVER" in source


def test_step2_page_reserves_later_steps_instead_of_leaking_metrics_or_market():
    source = _source("nfl_receiving_yards_hub_v2.py")
    assert "Summary statistics stay reserved for Step 3" in source
    assert "DEFENSE + H2H" in source
    assert "PROJECTION" in source
    assert "FANDUEL" in source
    assert "sportsbook projection influence <strong>0.0%</strong>" in source
    assert "probability, EV, Monte Carlo" in source
    assert "player-vs-team history" in source


def test_router_v113_advances_only_receiving_to_v2():
    source = _source("streamlit_memory_lazy_router_v113.py")
    assert "import streamlit_memory_lazy_router_v112 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v112"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v2"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "if _receiving_route_active():" in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_receiving_v1_rushing_v15_and_passing_chain_stay_frozen():
    recv_v1 = _source("nfl_receiving_yards_hub_v1.py")
    rushing_v15 = _source("nfl_rushing_yards_hub_v15.py")
    router_v112 = _source("streamlit_memory_lazy_router_v112.py")
    assert 'MODEL_VERSION = "NFL RECEIVING YARDS V1 • STEP 1 VERIFIED SLATE FOUNDATION"' in recv_v1
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v14"' in rushing_v15
    assert 'PHOENIX_TZ_NAME = "America/Phoenix"' in rushing_v15
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v111"' in router_v112


def test_app_boots_v113_and_preserves_v112_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v113 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V112_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V112_NFL_RECEIVING_YARDS_STEP1_FOUNDATION_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V113_NFL_RECEIVING_YARDS_STEP2_PLAYER_CARDS_2026-09-13"' in source
