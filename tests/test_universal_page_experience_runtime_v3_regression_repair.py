from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "universal_page_experience_runtime_v3.py"


def test_runtime_v3_restores_transition_loading_before_client_controller_mount() -> None:
    assert TARGET.exists()
    source = TARGET.read_text(encoding="utf-8")
    assert "page_experience_controller_markup_v2" in source
    assert "render_page_experience_app_v3" in source
    assert "if is_transition:" in source
    transition_idx = source.index("if is_transition:")
    mount_idx = source.index("_mount_page_experience_controller_v3")
    assert transition_idx < mount_idx
    assert "page_experience_fallback_markup(runtime.active)" in source


def test_runtime_v3_keeps_speed_guards_without_background_prefetch() -> None:
    source = TARGET.read_text(encoding="utf-8")
    assert "core.can_commit(scope, runtime)" in source
    assert "core.commit_if_current(scope, current" in source
    assert source.count("adapter.renderer(loaded)") == 1
    assert "_run_bounded_prefetch" not in source
    assert "choose_prefetch" not in source
