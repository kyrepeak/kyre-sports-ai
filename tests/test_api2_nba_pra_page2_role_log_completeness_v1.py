from __future__ import annotations

from pathlib import Path

import nba_pra_page2_data_completeness_v1 as completeness


ROOT = Path(__file__).resolve().parents[1]


def test_full_game_log_combines_current_and_prior_verified_history() -> None:
    profile = {
        "current_games": [
            {"game_date": "2026-10-23", "opponent": "MIA", "minutes": 24.9, "points": 17, "rebounds": 4, "assists": 3},
            {"game_date": "2026-10-21", "opponent": "ORL", "minutes": 27.7, "points": 12, "rebounds": 5, "assists": 0},
        ],
        "prior_games": [
            {"game_date": "2026-04-13", "opponent": "DAL", "minutes": 30.0, "points": 15, "rebounds": 6, "assists": 2},
            {"game_date": "2026-04-11", "opponent": "DEN", "minutes": 29.0, "points": 11, "rebounds": 5, "assists": 4},
        ],
    }

    rows = completeness.combined_verified_games(profile)

    assert [row["game_date"] for row in rows] == ["2026-10-23", "2026-10-21", "2026-04-13", "2026-04-11"]
    assert [row["opponent"] for row in rows] == ["MIA", "ORL", "DAL", "DEN"]
    assert rows[0]["pra"] == 24.0


def test_verified_official_report_without_player_row_is_not_unverified() -> None:
    context = {
        "player_name": "Jaylen Wells",
        "team": "MEM",
        "availability": "UNVERIFIED",
        "player": {"player_name": "Jaylen Wells", "team": "MEM"},
    }
    snapshot = {
        "sources": {
            "injuries": {
                "verification": "VERIFIED",
                "source": "Kyre Sports API — NBA Official Injury Report",
                "reported_at_utc": "2026-10-25T23:30:00Z",
                "players": {
                    "otherplayer": {
                        "player_name": "Other Player",
                        "team_tricode": "MEM",
                        "status": "QUESTIONABLE",
                        "verification": "VERIFIED",
                    }
                },
            }
        }
    }

    out = completeness.enrich_role_availability_context(context, snapshot)

    assert out["availability"] == "NO OFFICIAL INJURY DESIGNATION"
    assert out["availability_verification"] == "VERIFIED"
    assert out["availability_source"] == "NBA Official Injury Report"
    assert out["teammate_injuries"] == [
        {"player_name": "Other Player", "status": "QUESTIONABLE", "reason": ""}
    ]


def test_selected_player_official_status_wins_and_teammates_are_separate() -> None:
    context = {
        "player_name": "Player A",
        "team": "MEM",
        "availability": "UNVERIFIED",
        "player": {"player_name": "Player A", "team": "MEM"},
    }
    snapshot = {
        "sources": {
            "injuries": {
                "verification": "VERIFIED",
                "players": {
                    "playera": {"player_name": "Player A", "team_tricode": "MEM", "status": "PROBABLE", "reason": "Ankle"},
                    "playerb": {"player_name": "Player B", "team_tricode": "MEM", "status": "OUT", "reason": "Knee"},
                },
            }
        }
    }

    out = completeness.enrich_role_availability_context(context, snapshot)

    assert out["availability"] == "PROBABLE"
    assert out["availability_reason"] == "Ankle"
    assert out["teammate_injuries"] == [{"player_name": "Player B", "status": "OUT", "reason": "Knee"}]


def test_live_sync_activates_role_log_successors() -> None:
    source = (ROOT / "nba_pra_page2_sync_v1.py").read_text(encoding="utf-8")
    assert "from nba_pra_page2_context_v2 import build_page2_context" in source
    assert "from nba_pra_page2_command_center_v3 import _css, build_page2_html" in source


def test_gateway_keeps_application_on_kyre_api_and_adds_verified_usage_fallback() -> None:
    init_source = (ROOT / "runless_v2" / "__init__.py").read_text(encoding="utf-8")
    fallback = (ROOT / "runless_v2" / "nba_pra_usage_fallback_v2.py").read_text(encoding="utf-8")
    assert "nba_pra_usage_fallback_v2" in init_source
    assert "basketball-reference.com/leagues/NBA_" in fallback
    assert "advanced.html" in fallback
    assert "usage_pct" in fallback
    assert "Application pages never call" in fallback
