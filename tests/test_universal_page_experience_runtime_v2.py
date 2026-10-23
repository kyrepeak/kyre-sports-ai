from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "universal_page_experience_runtime_v2.py"


def test_runtime_v2_exists_and_mounts_v2_controller() -> None:
    assert TARGET.exists()
    source = TARGET.read_text(encoding="utf-8")
    assert "page_experience_controller_markup_v2" in source
    assert "render_page_experience_app_v2" in source


def test_runtime_v2_preserves_stale_write_guards_and_single_destination_render() -> None:
    source = TARGET.read_text(encoding="utf-8")
    assert "core.can_commit(scope, runtime)" in source
    assert "core.commit_if_current(scope, current" in source
    assert source.count("adapter.renderer(loaded)") == 1


def test_runtime_v2_does_not_background_prefetch() -> None:
    source = TARGET.read_text(encoding="utf-8")
    assert "_run_bounded_prefetch" not in source
    assert "choose_prefetch" not in source
