from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STEP8 = ROOT / "wnba_pra_speed_v3_step8_visible_first.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step8.py"
APP = ROOT / "app.py"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-speed-v3-step8-visible-first.yml"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-speed-v3-step8-visible-first.json"
PROFILE = ROOT / "devsystem/wnba_pra_speed_v3_step8_public_profile.py"

FROZEN_STEP7 = {
    "wnba_pra_speed_v3_step7_precompute.py": "8416b49b9fdf5b75656ea03248a0d6edf17a68a5",
    "streamlit_memory_lazy_router_wnba_pra_speed_v3_step7.py": "013aedd14a669c57aa09368ba7ecd9d5ef699f7f",
    "devsystem/wnba_pra_speed_v3_step7_public_profile.py": "ff1b597be14b1a370b6da2b0528065041061367e",
    "tests/test_wnba_pra_speed_v3_step7.py": "451a7a6833dd0e7223c56144f26c03aa9c02a1f6",
    ".github/workflows/wnba-pra-speed-v3-step7-precompute.yml": "56ff291abf9d92a18e2978ae4213381efbcd78fb",
    "devsystem/task_ledgers/wnba-pra-speed-v3-step7-precompute.json": "d954bb7f1e81c8eb52b8f0697bdc7b6ec85b0309",
}


def _blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)],
        cwd=ROOT,
        text=True,
    ).strip()


def test_step8_surfaces_exist():
    assert STEP8.exists()
    assert ROUTER.exists()


def test_step8_contract_is_visible_first_only():
    module = importlib.import_module("wnba_pra_speed_v3_step8_visible_first")
    contract = module.VISIBLE_FIRST_CONTRACT
    assert contract["step"] == "8/9"
    assert contract["visible_before_loader"] is True
    assert contract["client_preview_before_rerun"] is True
    assert contract["client_preview_source"] == "frozen_game_center_projection_card"
    assert contract["client_preview_transport"] == "css_focus_within"
    assert contract["shell_render_phase"] == "router_entry_before_frozen_parent"
    assert contract["loader_wrapper_renders_shell"] is False
    assert contract["shell_is_temporary"] is True
    assert contract["shell_lifetime"] == "until_final_result_marker"
    assert contract["server_side_clear"] is False
    assert contract["final_marker_css_handoff"] is True
    assert contract["final_renderer_unchanged"] is True
    assert contract["frozen_speed_v3_steps_1_7_modified"] is False
    assert contract["network_calls_added"] == 0
    assert contract["projection_runs_added"] == 0
    assert contract["sportsbook_calls_added"] == 0
    assert contract["qualification_runs_added"] == 0
    assert contract["ranking_runs_added"] == 0
    assert contract["monte_carlo_runs_added"] == 0
    assert contract["projection_math_changed"] is False
    assert contract["market_math_changed"] is False
    assert contract["data_meaning_changed"] is False
    assert contract["sportsbook_projection_influence"] == 0.0
    assert contract["warm_same_session_target_seconds_max"] == 0.75
    assert contract["cached_cold_target_seconds_max"] == 1.50
    assert contract["true_cold_target_seconds_max"] == 2.50


def test_step8_shell_is_emitted_before_frozen_parent_and_retained_through_final(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step8_visible_first")
    events = []

    player = {
        "player_id": 101,
        "player_name": "Test Player",
        "team_abbreviation": "TST",
        "role_label": "ACTIVE",
        "designation": "NO DESIGNATION",
        "starter_confirmed": True,
        "projected_minutes": 31.0,
        "projected_pts": 18.0,
        "projected_reb": 6.0,
        "projected_ast": 4.0,
        "projected_pra": 28.0,
    }
    game = {
        "game_id": "game-1",
        "away_team": "Away",
        "home_team": "Home",
    }

    class FakeSlot:
        def markdown(self, value, **kwargs):
            assert 'data-wnba-pra-speed-v3-step8-shell="visible"' in value
            assert "Test Player" in value
            events.append("shell")

        def empty(self):
            raise AssertionError("Step-8 shell must not be cleared in the same server run")

    monkeypatch.setattr(module.player_intelligence, "_selected_player", lambda: player)
    monkeypatch.setattr(module.player_intelligence, "_selected_game", lambda: game)
    monkeypatch.setattr(module.st, "empty", lambda: FakeSlot())
    monkeypatch.setattr(module, "_record", lambda **kwargs: events.append(("record", kwargs)))

    state = module.navigation.NavigationState(
        page=module.navigation.PAGE_PLAYER,
        game_id="game-1",
        player_id="101",
    )
    shell_slot = module.render_visible_shell_early(state)
    events.append("parent-entry")

    def frozen_loader(game_id, player_id):
        events.append("loader")
        assert game_id == "game-1"
        assert player_id == 101
        return {"state": "frozen"}

    result = module.load_player_intelligence_visible_first(
        frozen_loader,
        "game-1",
        101,
        shell_slot=shell_slot,
    )

    assert result == {"state": "frozen"}
    assert events.index("shell") < events.index("parent-entry") < events.index("loader")
    assert "clear" not in events
    records = [row[1] for row in events if isinstance(row, tuple) and row[0] == "record"]
    assert any(row.get("shell_before_loader") is True for row in records)
    assert any(row.get("shell_render_phase") == "router_entry_before_frozen_parent" for row in records)
    assert any(row.get("shell_removed_before_final_renderer") is False for row in records)
    assert any(row.get("shell_retained_through_final") is True for row in records)

def test_step8_context_mismatch_does_not_invent_visible_shell(monkeypatch):
    module = importlib.import_module("wnba_pra_speed_v3_step8_visible_first")
    events = []
    monkeypatch.setattr(
        module.player_intelligence,
        "_selected_player",
        lambda: {"player_id": 999},
    )
    monkeypatch.setattr(
        module.player_intelligence,
        "_selected_game",
        lambda: {"game_id": "other"},
    )
    monkeypatch.setattr(module, "_record", lambda **kwargs: events.append(kwargs))

    class ForbiddenSlot:
        def markdown(self, *args, **kwargs):
            raise AssertionError("mismatched context must not emit a shell")
        def empty(self):
            raise AssertionError("mismatched context must not allocate a shell")

    monkeypatch.setattr(module.st, "empty", lambda: ForbiddenSlot())
    state = module.navigation.NavigationState(
        page=module.navigation.PAGE_PLAYER,
        game_id="game-1",
        player_id="101",
    )
    shell_slot = module.render_visible_shell_early(state)
    assert shell_slot is None
    result = module.load_player_intelligence_visible_first(
        lambda game_id, player_id: {"ok": True},
        "game-1",
        101,
        shell_slot=shell_slot,
    )
    assert result == {"ok": True}
    assert any(row.get("shell_emitted") is False for row in events)

def test_step8_router_wraps_frozen_step7_only():
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_wnba_pra_speed_v3_step7 as frozen_parent" in source
    assert "performance.load_player_intelligence_same_session" in source
    assert "shell_slot = step8.render_visible_shell_early(state)" in source
    assert "shell_slot=shell_slot" in source
    assert "step8.render_step8_route(frozen_parent.render_app)" in source
    assert source.index("render_visible_shell_early") < source.index("frozen_parent.render_app")
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step7"' in source
    assert "MAY_MODIFY_WNBA_MODEL = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step8_activation_is_wired_without_breaking_step7_compatibility():
    source = APP.read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step8 "
        "import record_bootstrap_import_ms, render_app"
        in source
    )
    assert (
        "Frozen WNBA PRA Speed V3 Step 7 compatibility: "
        "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step7 "
        "import record_bootstrap_import_ms, render_app"
        in source
    )


def test_step8_freezes_all_step7_artifact_blobs():
    for path, expected in FROZEN_STEP7.items():
        assert _blob(ROOT / path) == expected, path


def test_step8_exact_scope_guard_fetches_base_history_permanently():
    source = WORKFLOW.read_text(encoding="utf-8")
    focused = source.split("focused-contract:", 1)[1].split("public-profile:", 1)[0]
    assert "fetch-depth: 0" in focused
    assert 'git diff --name-only "$BASE_SHA" "$HEAD_SHA"' in focused


def test_step8_task_ledger_has_valid_genesis_action_log():
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert payload["status"] == "DONE"
    log = payload["action_log"]
    assert log["head_chain_hash"] == "0" * 64
    assert log["events"] == []
    assert log["consumed_receipts"] == []
    debt = payload["regression_debt"]
    assert debt["state"] == "CLEARED"
    assert debt["open_debt_count"] == 0


def test_step8_public_profile_reacquires_frames_across_reruns_permanently():
    source = PROFILE.read_text(encoding="utf-8")
    assert 'FINAL_HERO_SELECTOR = ".wn4-hero"' in source
    assert "def _visible_step8_surface(page, player_name: str):" in source
    assert "for candidate in page.frames:" in source
    assert "def _wait_first_visible_content(page, started: float, player_name: str):" in source
    assert "_wait_first_visible_content(" in source
    assert "WNBA_PRA_SPEED_V3_STEP8_FRAME_REACQUIRE_GREEN" in source
    assert "MutationObserver" not in source
    assert "__ksStep8ShellObservedAt" not in source
    assert "MAX_VISIBLE_SHELL_SECONDS = 0.75" in source
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA_PRA_SPEED_V3_STEP8_FRAME_RESILIENT_VERIFIER_SCOPE_GREEN" in workflow

def test_step8_router_emits_shell_before_frozen_parent_permanently():
    router = ROUTER.read_text(encoding="utf-8")
    runtime = STEP8.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "state = step8.navigation.current_state()" in router
    assert "shell_slot = step8.render_visible_shell_early(state)" in router
    assert router.index("render_visible_shell_early") < router.index("frozen_parent.render_app")
    assert "shell_slot=shell_slot" in router
    assert '"shell_render_phase": "router_entry_before_frozen_parent"' in runtime
    assert '"loader_wrapper_renders_shell": False' in runtime
    assert "WNBA_PRA_SPEED_V3_STEP8_PRODUCT_REPAIR_SCOPE_GREEN" in workflow


def test_step8_shell_lifetime_handoff_is_permanent():
    runtime = STEP8.read_text(encoding="utf-8")
    profile = PROFILE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "shell_slot.empty()" not in runtime
    assert '"shell_lifetime": "until_final_result_marker"' in runtime
    assert '"server_side_clear": False' in runtime
    assert '"final_marker_css_handoff": True' in runtime
    assert 'body:has([data-wnba-pra-speed-v3-step8-result="true"])' in runtime
    assert 'data-shell-retained-through-final' in runtime
    assert 'data-shell-retained-through-final' in profile
    assert "WNBA_PRA_SPEED_V3_STEP8_SHELL_LIFETIME_GREEN" in profile
    assert "WNBA_PRA_SPEED_V3_STEP8_SHELL_LIFETIME_REPAIR_SCOPE_GREEN" in workflow


def test_step8_client_preview_is_browser_visible_before_rerun_permanently():
    runtime = STEP8.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    profile = PROFILE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'data-wnba-pra-speed-v3-step8-click-preview="true"' in runtime
    assert ":focus-within" in runtime
    assert ":has(button:active)" in runtime
    assert "render_game_player_with_client_preview" in runtime
    assert "st.container(key=key)" in runtime
    assert "game_center._render_player_card = client_preview_player_card" in router
    assert "game_center._render_player_card = original_player_card" in router
    assert "CLIENT_PREVIEW_SELECTOR" in profile
    assert '"client_preview"' in profile
    assert 'button_name = f"Open {first_name} PRA"' in profile
    assert 'get_by_role("button", name=button_name, exact=False).first' in profile
    assert 'get_by_role("button", name="Open", exact=False).first' not in profile
    assert "first.focus()" in profile
    assert profile.index("first.focus()") < profile.index("first.click()")
    assert 'if visible_path != "client_preview":' in profile
    assert "WNBA_PRA_SPEED_V3_STEP8_FOCUS_ENGAGEMENT_GREEN" in profile
    assert "WNBA_PRA_SPEED_V3_STEP8_CLIENT_PREVIEW_GREEN" in profile
    assert "MAX_VISIBLE_SHELL_SECONDS = 0.75" in profile
    assert "WNBA_PRA_SPEED_V3_STEP8_CLIENT_PREVIEW_REPAIR_SCOPE_GREEN" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP8_FOCUS_ENGAGEMENT_VERIFIER_SCOPE_GREEN" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP8_PLAYER_SELECTOR_VERIFIER_SCOPE_GREEN" in workflow
