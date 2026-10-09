from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cfb_game_total_page1_visual_cleanup_step3_overview_v1 as overview
import cfb_game_total_page1_visual_cleanup_step3_activation_v1 as activation


def test_phoenix_day_window_includes_today_and_friday() -> None:
    now = datetime(2026, 10, 9, 0, 30, tzinfo=ZoneInfo("America/Phoenix"))
    days = overview.phoenix_day_window_including_today(None, now=now, count=7)
    assert days[0].isoformat() == "2026-10-09"
    assert days[0].strftime("%A") == "Friday"
    assert days[-1].isoformat() == "2026-10-15"
    selected_saturday = overview.phoenix_day_window_including_today("2026-10-10", now=now, count=7)
    assert selected_saturday[0].isoformat() == "2026-10-09"
    assert selected_saturday[0].strftime("%A") == "Friday"


def test_overview_and_snapshot_use_dynamic_team_evidence_without_pending_copy() -> None:
    identity = {
        "away": {"team": "Alpha State", "conference": "A-10"},
        "home": {"team": "Beta Tech", "conference": "B-12"},
    }
    away = {
        "record": "4-1",
        "ppg": 36.2,
        "allowed_pg": 18.1,
        "point_diff_pg": 18.1,
        "recent_form": "WWLWW",
    }
    home = {
        "record": "3-2",
        "ppg": 28.4,
        "allowed_pg": 24.6,
        "point_diff_pg": 3.8,
        "recent_form": "WLWLW",
    }
    summary = overview.build_overview_edge_html(identity, away, home)
    snapshot = overview.build_team_snapshot_html(
        identity,
        away,
        home,
        away_logo_html="A",
        home_logo_html="B",
    )
    combined = summary + snapshot
    assert "FAVORABLE FOR" in combined
    assert "KEY EDGE" in combined
    assert "TOUGHNESS FOR" in combined
    assert "TEAM SNAPSHOT" in combined
    assert "Alpha State" in combined and "Beta Tech" in combined
    assert "36.2" in combined and "18.1" in combined
    assert "data limited" not in combined.lower()
    assert "pending" not in combined.lower()


def test_activation_contract_is_cfb_only_and_preserves_model_math() -> None:
    assert activation.MAY_MODIFY_PROJECTION is False
    assert activation.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert activation.MAY_MODIFY_OTHER_SPORTS is False
    assert activation.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert activation.TARGET_PAGE == "cfb_game_total_clean_page_v38"


def test_step3_source_does_not_hardcode_reference_matchup() -> None:
    source = (ROOT / "cfb_game_total_page1_visual_cleanup_step3_overview_v1.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "ucf" not in lowered
    assert "oklahoma st" not in lowered
    assert "america/phoenix" in lowered


def test_frozen_side_market_seam_activates_step3_without_wrapper_stacking() -> None:
    source = (ROOT / "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py").read_text(encoding="utf-8")
    assert "install_step3_overview" in source
    assert "_cfb_game_total_visual_cleanup_step3_installed" in source
    assert source.count("install_step3_overview()") == 2
