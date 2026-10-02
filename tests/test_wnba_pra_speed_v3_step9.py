from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/wnba_pra_speed_v3_step9_final_cert.py"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-speed-v3-step9-final-cert.json"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-speed-v3-step9-final-cert.yml"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard.py"
APP = ROOT / "app.py"


def _source() -> str:
    return CERT.read_text(encoding="utf-8")


def test_step9_direct_script_bootstraps_repo_root_permanently():
    source = _source()
    assert "if __package__ in {None, \"\"}:" in source
    assert "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))" in source


def test_step9_is_certification_only_and_keeps_final_speed_budgets():
    source = _source()
    tree = ast.parse(source)
    assert tree is not None
    assert "WARM_SAME_SESSION_SECONDS_MAX = 0.75" in source
    assert "CACHED_COLD_SECONDS_MAX = 1.50" in source
    assert "TRUE_COLD_SECONDS_MAX = 2.50" in source
    assert "VISIBLE_CONTINUITY_SECONDS_MAX = 0.75" in source
    assert "step5_profile.run(" in source
    assert "step8_profile.run(" in source
    assert '"frozen_steps_1_8_preserved": True' in source
    assert '"product_runtime_changed_by_step9": True' in source
    assert '"runtime_change_scope": "duplicate_player_identity_dedupe_guard+precompute_response_handoff"' in source
    assert '"precompute_response_handoff_required": True' in source
    assert '"projection_values_changed_by_step9": False' in source
    assert '"projection_math_changed_by_step9": False' in source
    assert '"market_math_changed_by_step9": False' in source
    assert '"data_meaning_changed_by_step9": False' in source


def test_step9_primes_exact_labeled_wnba_pra_route_before_frozen_profiles():
    source = _source()
    assert 'urlencode({"ks_jump_sport": "WNBA", "ks_jump_market": "PRA"})' in source
    assert 'SPORT_LABEL = "🏟️ Sport"' in source
    assert 'WNBA_MARKET_LABEL = "🎯 WNBA Market"' in source
    assert "def _choose_labeled_route_value(page, frame, label: str, value: str)" in source
    assert 'get_by_role("combobox", name=label, exact=True)' in source
    assert 'get_by_role("option", name=value, exact=True)' in source
    assert '_choose_labeled_route_value(page, frame, SPORT_LABEL, "WNBA")' in source
    assert '_choose_labeled_route_value(page, frame, WNBA_MARKET_LABEL, "PRA")' in source
    assert "_wait_page(" in source
    assert "frozen_route_to_wnba_pra" not in source
    assert "step5_profile._route_to_wnba_pra = primed_route" in source
    assert "step8_profile._route_to_wnba_pra = primed_route" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_LABELED_ROUTE_GREEN" in source


def test_step9_rejects_completed_and_past_wnba_slates():
    source = _source()
    assert "def _future_pregame_dates() -> tuple[str, ...]:" in source
    assert "for offset in range(0, UPCOMING_GAME_SEARCH_DAYS + 1)" in source
    assert 'casefold() != "scheduled"' in source
    assert 'verification.get("playable_pregame") is not True' in source
    assert "if day == today:" in source
    assert "if game_start <= now_utc:" in source
    assert "nav_profile.CERTIFIED_GAME_DATES = upcoming_game_dates" in source
    assert "step5_profile.CERTIFIED_GAME_DATES = upcoming_game_dates" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_NO_PAST_GAMES_GREEN" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_UPCOMING_GAME_VERIFIER_SCOPE_GREEN" in source


def test_step9_requires_browser_resident_step8_continuity():
    source = _source()
    assert '"game_card_continuity"' in source
    assert '"client_preview"' in source
    assert "server_shell_runtime_fallback_preserved" in source
    assert "frozen_steps_1_7_preserved" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_GREEN" in source


def test_step9_duplicate_key_guard_preserves_frozen_game_center_bytes():
    overlay = OVERLAY.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "def _dedupe_game_center_payload(payload: Any) -> Any:" in overlay
    assert "seen_player_ids: set[int] = set()" in overlay
    assert "duplicate_player_rows_suppressed" in overlay
    assert "game_center.load_game_center = guarded_loader" in overlay
    assert "game_center.load_game_center = original_loader" in overlay
    assert 'MAY_MODIFY_WNBA_MODEL = False' in overlay
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in overlay
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard import record_bootstrap_import_ms, render_app" in app
    assert "Frozen WNBA PRA Speed V3 Step 8 compatibility: from streamlit_memory_lazy_router_wnba_pra_speed_v3_step8 import record_bootstrap_import_ms, render_app" in app


def test_step9_precompute_handoff_reuses_existing_future_and_preserves_fallback():
    overlay = OVERLAY.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "PRECOMPUTE_JOIN_SECONDS = 2.25" in overlay
    assert "PRECOMPUTE_HANDOFF_MAX_AGE_SECONDS = 5.0" in overlay
    assert "_STEP9_PRECOMPUTED_BUNDLES.pop(_bundle_key(player_id), None)" in overlay
    assert "age_seconds > PRECOMPUTE_HANDOFF_MAX_AGE_SECONDS" in overlay
    assert "def _capture_precompute_bundle(player_id: int)" in overlay
    assert "step7_precompute._warm_one = _capture_precompute_bundle" in overlay
    assert "def _join_precompute(player_id: int)" in overlay
    assert "future.result(timeout=PRECOMPUTE_JOIN_SECONDS)" in overlay
    assert "never launch a new one" in overlay
    assert "def _pair_from_precomputed_outer(" in overlay
    assert "streamlit_network_reads=0" in overlay
    assert '"network_reads": 0' in overlay
    assert "original_loader(str(game_id), pid)" in overlay
    assert "step7_precompute._warm_one = original_warm_one" in overlay
    assert "step4_cache.load_cached_bundle_pair = original_bundle_loader" in overlay
    assert "MAY_MODIFY_WNBA_MODEL = False" in overlay
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in overlay
    assert "WNBA_PRA_SPEED_V3_STEP9_PRECOMPUTE_HANDOFF_2026_10_01_R3" in app


def test_step9_emits_final_green_and_frozen_tokens():
    source = _source()
    required = (
        "WNBA_PRA_SPEED_V3_STEP9_TRUE_COLD_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_WARM_SAME_SESSION_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_CACHED_COLD_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_FROZEN_STEPS1_8_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_DUPLICATE_KEY_GUARD_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_PRECOMPUTE_HANDOFF_PERFORMANCE_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_PROFILE_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_FROZEN",
    )
    for token in required:
        assert token in source


def test_step9_ledger_is_done_and_step2a_locked():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Speed V3"
    assert ledger["step"] == 9
    assert ledger["total_steps"] == 9
    assert ledger["status"] == "DONE"
    assert ledger["speed_targets"] == {
        "warm_same_session_seconds_max": 0.75,
        "cached_cold_seconds_max": 1.5,
        "true_cold_seconds_max": 2.5,
        "visible_continuity_seconds_max": 0.75,
    }
    assert ledger["protected"]["speed_v3_steps_1_8"] is True
    assert ledger["two_a"]["one_active_pr_max"] == 1
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["two_a"]["no_unchanged_failed_reruns"] is True
    assert ledger["action_log"]["head_chain_hash"] == "0" * 64
    assert ledger["action_log"]["events"] == []
    assert ledger["action_log"]["consumed_receipts"] == []


def test_step9_workflow_has_exact_scope_and_main_production_gate():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA PRA Speed V3 Step 9 Final Certification" in workflow
    assert "Enforce exact Step-9 PR scope" in workflow
    assert "Run Step-9 permanent contract" in workflow
    assert "Run final production speed certification" in workflow
    assert "python -m devsystem.wnba_pra_speed_v3_step9_final_cert" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_IMPORT_PATH_REPAIR_GREEN" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_LABELED_ROUTE_VERIFIER_SCOPE_GREEN" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_UPCOMING_GAME_VERIFIER_SCOPE_GREEN" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_DUPLICATE_KEY_GUARD_SCOPE_GREEN" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_PRECOMPUTE_HANDOFF_SCOPE_GREEN" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_BRANCH_GREEN" in workflow
