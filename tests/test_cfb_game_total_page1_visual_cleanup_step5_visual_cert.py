from __future__ import annotations

import json
from pathlib import Path

from devsystem.cfb_game_total_page1_visual_cleanup_step5_visual_cert_v1 import (
    GITHUB_ACTIONS_FALLBACK,
    MAY_MODIFY_PRODUCT_RUNTIME,
    PHOENIX_TZ,
    REQUIRED_TESTIDS,
    SPORTSBOOK_PROJECTION_INFLUENCE,
    VIEWPORTS,
    evidence_is_terminal_green,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "devsystem/live_evidence/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json"
CERT = ROOT / "devsystem/cfb_game_total_page1_visual_cleanup_step5_visual_cert_v1.py"


def test_step5_viewport_and_safety_contract() -> None:
    assert VIEWPORTS == {
        "mobile": {"width": 390, "height": 844},
        "tablet": {"width": 768, "height": 1024},
        "desktop": {"width": 1440, "height": 1200},
    }
    assert PHOENIX_TZ == "America/Phoenix"
    assert SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert MAY_MODIFY_PRODUCT_RUNTIME is False
    assert GITHUB_ACTIONS_FALLBACK == 0


def test_step5_required_live_markers_cover_steps2_through4() -> None:
    required = set(REQUIRED_TESTIDS)
    assert {
        "gtvc2-matchup-hero",
        "gtvc2-context-strip",
        "gtvc2-view-tabs",
        "gtvc3-future-day-strip",
        "gtvc3-overview-edge",
        "gtvc3-team-snapshot",
        "gtvc4-games-on-day",
        "gtvc4-data-footer",
    }.issubset(required)


def test_step5_browser_uses_current_category_handoff_before_asserting_visuals() -> None:
    source = CERT.read_text(encoding="utf-8")
    assert '"ks_jump_sport": "CFB"' in source
    assert '"ks_jump_market": GAME_TOTAL_MARKET' in source
    assert 'page.goto(route_handoff(base_url)' in source
    assert 'base._read_sport_options' not in source
    assert 'base._choose(page, frame, 0, CFB_SPORT)' not in source


def test_step5_terminal_live_evidence() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence_is_terminal_green(payload)
