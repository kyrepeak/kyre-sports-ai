from __future__ import annotations

from pathlib import Path


def _helper():
    import nfl_receiving_yards_history_card_v1 as helper

    return helper


def test_latest_exact_game_preserves_newest_first_exact_id_order() -> None:
    helper = _helper()
    history = {
        "ready": True,
        "games": [
            {
                "official_event_id": "401900001",
                "official_athlete_id": "123",
                "official_team_id": "8",
                "opponent_official_team_id": "2",
                "date": "2026-09-12T00:00Z",
                "receptions": 4,
                "receiving_yards": 94,
                "receiving_touchdowns": 1,
                "targets_data_available": True,
                "targets": 7,
            },
            {
                "official_event_id": "401800001",
                "official_athlete_id": "123",
                "official_team_id": "8",
                "opponent_official_team_id": "2",
                "date": "2025-09-12T00:00Z",
                "receptions": 6,
                "receiving_yards": 71,
                "receiving_touchdowns": 0,
                "targets_data_available": True,
                "targets": 9,
            },
        ],
    }
    game = helper.latest_exact_game(history, athlete_id="123", team_id="8", opponent_id="2")
    assert game is not None
    assert game["official_event_id"] == "401900001"


def test_latest_exact_game_skips_identity_mismatch_and_never_name_matches() -> None:
    helper = _helper()
    history = {
        "ready": True,
        "games": [
            {
                "official_event_id": "401900001",
                "official_athlete_id": "999",
                "official_team_id": "8",
                "opponent_official_team_id": "2",
                "player_name": "Same Display Name",
            },
            {
                "official_event_id": "401900002",
                "official_athlete_id": "123",
                "official_team_id": "8",
                "opponent_official_team_id": "2",
                "player_name": "Different Display Name",
                "receptions": 3,
                "receiving_yards": 58,
                "receiving_touchdowns": 0,
                "targets_data_available": False,
                "targets": None,
            },
        ],
    }
    game = helper.latest_exact_game(history, athlete_id="123", team_id="8", opponent_id="2")
    assert game is not None
    assert game["official_event_id"] == "401900002"
    assert helper.latest_exact_game(history, athlete_id="555", team_id="8", opponent_id="2") is None


def test_history_summary_formats_verified_receiving_line_and_missing_targets() -> None:
    helper = _helper()
    full = helper.format_last_vs_summary(
        {
            "receptions": 4,
            "receiving_yards": 94,
            "receiving_touchdowns": 1,
            "targets_data_available": True,
            "targets": 7,
        },
        "BUF",
    )
    assert full == "Last vs BUF • 4 REC • 94 YDS • 1 TD • 7 TGT"

    no_targets = helper.format_last_vs_summary(
        {
            "receptions": 3,
            "receiving_yards": 58,
            "receiving_touchdowns": 0,
            "targets_data_available": False,
            "targets": None,
        },
        "BUF",
    )
    assert no_targets == "Last vs BUF • 3 REC • 58 YDS • 0 TD • — TGT"


def test_v15_promotes_frozen_v5_exact_id_history_without_new_history_math() -> None:
    source = Path("nfl_receiving_yards_hub_v15.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v14"' in source
    assert 'FROZEN_HISTORY_PAGE = "nfl_receiving_yards_hub_v5"' in source
    assert "history_page._load_history" in source
    assert "latest_exact_game" in source
    assert "Last vs" in source
    assert "PLAYER VS DEFENSE HISTORY" in source
    assert "DEEP EVIDENCE" in source
    assert "DISPLAY_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "player_name ==" not in source
    assert "name.lower" not in source


def test_router_v146_advances_only_receiving_yards() -> None:
    source = Path("streamlit_memory_lazy_router_v146.py").read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v145"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v15"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_bootstraps_router_v146() -> None:
    source = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v146 import record_bootstrap_import_ms, render_app" in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V146_NFL_RECEIVING_YARDS_PLAYER_VS_DEFENSE_HISTORY_2026-09-16"' in source
