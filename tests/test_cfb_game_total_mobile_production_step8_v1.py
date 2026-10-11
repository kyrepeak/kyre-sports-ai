from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/cfb_game_total_mobile_production_step8_v1.py"
TARGETS = ROOT / "devsystem/production_targets_v1.json"
PLAN = ROOT / "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-v1.json"
LEDGER = ROOT / "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-v1.json"

SOURCE_MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
LIVE_RENDER_COMMIT = "879c28265efde1810a5e30352fa2dcb269c1052a"
RENDER_SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
RENDER_BRANCH = "mlb-step17b-shared-host-cert"
HANDOFF_CERT_DAY = "2026-10-10"


def _load_cert():
    assert CERT.exists(), "Step 8 mobile/production certification owner is not implemented yet"
    spec = importlib.util.spec_from_file_location("cfb_gt_step8_mobile_prod", CERT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step8_certification_owner_is_non_mutating_and_final_step():
    module = _load_cert()
    assert module.MODEL_VERSION == "CFB GAME TOTAL • MOBILE + PRODUCTION • STEP 8 V1"
    assert module.SOURCE_MAIN_SHA == SOURCE_MAIN_SHA
    assert module.MAY_MODIFY_PAGE1 is False
    assert module.MAY_MODIFY_PAGE2 is False
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_MODIFY_OTHER_SPORTS is False
    assert module.NETWORK_CALLS_ADDED == 0
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert module.GITHUB_ACTIONS_FALLBACK == 0


def test_step8_render_identity_target_matches_current_live_deploy():
    payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    render = payload["render_api"]
    assert render["service_id"] == RENDER_SERVICE_ID
    assert render["source_branch"] == RENDER_BRANCH
    assert render["certified_commit"] == LIVE_RENDER_COMMIT
    assert render["auto_deploy"] is False


def test_step8_public_contract_covers_page1_page2_and_all_viewports():
    module = _load_cert()
    assert module.RENDER_CERTIFIED_COMMIT == LIVE_RENDER_COMMIT
    assert module.EVENT_QUERY_KEY == "ks_cfb_game_total_event_id"
    assert module.PHOENIX_TZ == "America/Phoenix"
    assert module.PAGE1_TESTID == "gt163-game-strip"
    assert set(module.VIEWPORTS) == {"mobile390", "mobile430", "tablet", "desktop"}
    assert module.VIEWPORTS["mobile390"]["width"] == 390
    assert module.VIEWPORTS["mobile430"]["width"] == 430
    assert module.VIEWPORTS["tablet"]["width"] == 768
    assert module.VIEWPORTS["desktop"]["width"] == 1440
    assert "gtp2s2-matchup-hero" in module.PAGE2_REQUIRED_TESTIDS
    assert "gtp2s7-line-lab" in module.PAGE2_REQUIRED_TESTIDS
    assert "gtp2s8-final" in module.PAGE2_REQUIRED_TESTIDS


def test_step8_native_frame_detection_does_not_require_obsolete_combobox():
    module = _load_cert()
    source = CERT.read_text(encoding="utf-8")
    assert callable(module._find_cfb_frame)
    assert module.PAGE1_FRAME_MARKERS == ("PHOENIX TIME", "GAMES ON THIS DAY")
    assert "combo_count >= 1" not in source
    assert "base._find_app_frame(page" not in source


def test_step8_current_phoenix_day_is_verified_separately_from_handoff_slate():
    module = _load_cert()
    current_query = parse_qs(urlparse(module.current_day_route()).query)
    expected_day = datetime.now(ZoneInfo("America/Phoenix")).date().isoformat()
    assert current_query["ks_sport"] == ["College Football"]
    assert current_query["ks_cfb_market"] == ["Game Total"]
    assert current_query["ks_cfb_game_total_date"] == [expected_day]
    assert callable(module._current_day_result)


def test_step8_handoff_route_uses_deterministic_game_bearing_slate():
    module = _load_cert()
    query = parse_qs(urlparse(module.page1_route()).query)
    assert module.HANDOFF_CERT_DAY == HANDOFF_CERT_DAY
    assert query["ks_sport"] == ["College Football"]
    assert query["ks_cfb_market"] == ["Game Total"]
    assert query["ks_cfb_game_total_date"] == [HANDOFF_CERT_DAY]


def test_step8_browser_navigation_threads_requested_base_url():
    module = _load_cert()
    source = CERT.read_text(encoding="utf-8")
    custom = "https://example.invalid/staging"
    assert module.page1_route(custom).startswith(custom + "/?")
    assert module.current_day_route(custom).startswith(custom + "/?")
    assert "page1_route(base_url" in source
    assert "current_day_route(base_url" in source


def test_step8_page2_requires_observed_event_identity_not_inherited_identity():
    _load_cert()
    source = CERT.read_text(encoding="utf-8")
    assert "if observed_events != {event_id}:" in source
    assert "if observed_events and observed_events != {event_id}:" not in source


def test_step8_runless_plan_executes_public_cert_and_ledger_is_finalization_scoped():
    assert PLAN.exists(), "Step 8 Runless proof plan is not implemented yet"
    assert LEDGER.exists(), "Step 8 task ledger is not implemented yet"
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert plan["task_id"] == "cfb-game-total-mobile-production-step8-v1"
    assert plan["workstream"] == "cfb-game-total-native-website-rebuild-v1"
    assert plan["freeze_token"] == "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
    assert plan["probes"] == []
    assert "devsystem/production_targets_v1.json" in plan["artifacts"]
    assert "devsystem/cfb_game_total_mobile_production_step8_v1.py" in plan["artifacts"]
    public_commands = [
        command for command in plan["commands"]
        if len(command) >= 3
        and command[0] == "python"
        and command[1] == "-m"
        and command[2] == "devsystem.cfb_game_total_mobile_production_step8_v1"
    ]
    assert len(public_commands) == 1
    assert "--base-url" in public_commands[0]
    assert "https://pickvault.streamlit.app" in public_commands[0]
    assert ledger["step"] == "8/8"
    assert ledger["step9_started"] is False
    assert ledger["green_plus_frozen_claimed"] is False
