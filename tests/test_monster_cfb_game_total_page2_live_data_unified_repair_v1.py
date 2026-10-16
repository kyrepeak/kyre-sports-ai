from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "cfb_game_total_page2_live_data_unified_repair_v1.py"
SAME_PAGE = ROOT / "cfb_game_total_page2_same_page_shell_repair_v1.py"


def _load_adapter():
    assert ADAPTER.is_file(), "unified Page-2 live-data adapter must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_live_data_repair", ADAPTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unified_live_data_repair_exists_and_is_wired_into_same_page_shell():
    assert ADAPTER.is_file(), "RED: Page-2 live-data adapter is not implemented yet"
    source = SAME_PAGE.read_text(encoding="utf-8")
    assert "import cfb_game_total_page2_live_data_unified_repair_v1 as live_data" in source
    assert "with live_data.install_page2_live_data_repair():" in source


def test_adapter_is_presentation_only_and_reuses_certified_cfb_owners():
    adapter = _load_adapter()
    source = ADAPTER.read_text(encoding="utf-8")
    assert adapter.MAY_MODIFY_MODEL is False
    assert adapter.MAY_MODIFY_PROJECTION is False
    assert adapter.MAY_MODIFY_PROBABILITY is False
    assert adapter.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert "import cfb_game_total_step3_form_v1 as step3_owner" in source
    assert "import cfb_game_total_step5_pace_v1 as pace_owner" in source
    assert "import cfb_game_total_step6_scoring_v1 as scoring_owner" in source
    assert "import requests" not in source


def test_score_only_completed_games_are_normalized_for_recent_trends():
    adapter = _load_adapter()
    profile = {
        "team": "Memphis",
        "completed_games": [
            {
                "date": "2026-10-03",
                "event_id": "401000001",
                "opponent": "Opponent",
                "score": "40-17",
                "result": "W",
            }
        ],
    }
    normalized = adapter.normalize_profile_history(profile)
    row = normalized["completed_games"][0]
    assert row["points_for"] == 40.0
    assert row["points_against"] == 17.0
    assert row["score"] == "40-17"


def test_pure_payload_enrichment_fills_page2_cards_without_touching_model_outputs():
    adapter = _load_adapter()
    payload = {
        "identity": {
            "away": {"team": "Memphis", "team_id": "235"},
            "home": {"team": "Tulane", "team_id": "2655"},
        },
        "display_game": {
            "game_date": "2026-10-16",
            "away_team": "Memphis",
            "home_team": "Tulane",
        },
        "away": {"team": "Memphis"},
        "home": {"team": "Tulane"},
        "raw": {"sentinel_model_value": 51.5},
        "final": {"projected_total": 51.5, "market_line": 54.5},
    }
    step3 = {
        "away": {
            "completed_games": [{"date": "2026-10-03", "score": "40-17"}],
            "recent_points_allowed_pg": 21.2,
        },
        "home": {
            "completed_games": [{"date": "2026-10-03", "score": "31-24"}],
            "recent_points_allowed_pg": 19.4,
        },
    }
    pace = {
        "away": {"plays_per_game": 72.4},
        "home": {"plays_per_game": 68.8},
    }
    scoring = {
        "expected_scoring_chances": 9.6,
        "evidence": {
            "away_offense": {"overall_explosive_rate": 0.16, "red_zone_td_rate": 0.67},
            "home_offense": {"overall_explosive_rate": 0.13, "red_zone_td_rate": 0.61},
            "away_defense": {"overall_explosive_rate": 0.11, "red_zone_td_rate": 0.52},
            "home_defense": {"overall_explosive_rate": 0.14, "red_zone_td_rate": 0.58},
        },
    }
    breakdown = {
        "away_1h": 17.0,
        "home_1h": 14.5,
        "away_2h": 15.0,
        "home_2h": 13.0,
        "q1": 14.0,
        "q2": 17.5,
        "q3": 13.5,
        "q4": 14.5,
    }

    enriched = adapter.enrich_page2_payload(
        payload,
        step3_bundle=step3,
        pace_contract=pace,
        scoring_contract=scoring,
        scoring_breakdown=breakdown,
    )

    assert enriched["away"]["plays_per_game"] == 72.4
    assert enriched["home"]["plays_per_game"] == 68.8
    assert enriched["away"]["explosive_rate"] == 0.16
    assert enriched["home"]["explosive_rate"] == 0.13
    assert enriched["away"]["red_zone_td_rate"] == 0.67
    assert enriched["home"]["red_zone_td_rate"] == 0.61
    assert enriched["away"]["points_allowed_pg"] == 21.2
    assert enriched["home"]["points_allowed_pg"] == 19.4
    assert enriched["raw"]["scoring_opportunities"] == 9.6
    assert enriched["raw"]["scoring_breakdown"] == breakdown
    assert enriched["raw"]["sentinel_model_value"] == 51.5
    assert enriched["final"] == payload["final"]


def test_page2_adapter_never_overwrites_already_owned_verified_values():
    adapter = _load_adapter()
    payload = {
        "identity": {},
        "display_game": {},
        "away": {
            "plays_per_game": 70.0,
            "explosive_rate": 0.20,
            "red_zone_td_rate": 0.72,
            "points_allowed_pg": 18.0,
        },
        "home": {},
        "raw": {},
        "final": {},
    }
    enriched = adapter.enrich_page2_payload(
        payload,
        pace_contract={"away": {"plays_per_game": 60.0}, "home": {}},
        scoring_contract={
            "evidence": {
                "away_offense": {"overall_explosive_rate": 0.10, "red_zone_td_rate": 0.50},
                "home_offense": {},
                "away_defense": {},
                "home_defense": {},
            }
        },
    )
    assert enriched["away"]["plays_per_game"] == 70.0
    assert enriched["away"]["explosive_rate"] == 0.20
    assert enriched["away"]["red_zone_td_rate"] == 0.72
    assert enriched["away"]["points_allowed_pg"] == 18.0
