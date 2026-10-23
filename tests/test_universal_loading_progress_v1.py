from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / "universal_page_experience_v3.py"
RUNTIME = ROOT / "universal_page_experience_runtime_v4.py"


def test_progress_presentation_is_determinate_and_bounded() -> None:
    assert PRESENTATION.exists()
    source = PRESENTATION.read_text(encoding="utf-8")
    assert "PROGRESS_STAGES = (0, 15, 35, 70, 90, 100)" in source
    assert "def page_experience_progress_markup" in source
    assert "def page_experience_progress_update_markup" in source
    assert "max(0, min(100, int(percent)))" in source
    assert 'aria-valuemin="0"' in source
    assert 'aria-valuemax="100"' in source
    assert "kyre-upe-progress-value" in source
    assert "kyre-upe-progress-fill" in source
    assert "transition:width .22s ease" in source


def test_client_overlay_resets_to_zero_on_real_transition_without_fake_timer() -> None:
    assert PRESENTATION.exists()
    source = PRESENTATION.read_text(encoding="utf-8")
    assert "page_experience_controller_markup_v2" in source
    assert "__KYRE_UNIVERSAL_LOADING_PROGRESS_V1__" in source
    assert "MutationObserver" in source
    assert 'attributeFilter:["aria-hidden"]' in source
    assert "setProgress(0" in source
    assert "setInterval(" not in source
    assert "setTimeout(" not in source


def test_runtime_v4_progress_tracks_real_milestones_and_keeps_speed_guards() -> None:
    assert RUNTIME.exists()
    source = RUNTIME.read_text(encoding="utf-8")
    stages = [
        ('15, "Routing page"', source.index('15, "Routing page"')),
        ('35, "Loading page module"', source.index('35, "Loading page module"')),
        ('70, "Loading intelligence"', source.index('70, "Loading intelligence"')),
        ('90, "Preparing page"', source.index('90, "Preparing page"')),
        ('100, "Ready"', source.index('100, "Ready"')),
    ]
    assert [idx for _, idx in stages] == sorted(idx for _, idx in stages)
    assert source.index("core.resolve_destination(runtime.active)") < stages[1][1]
    assert source.index("core.load_destination(adapter)") < stages[2][1]
    assert stages[3][1] < source.index("adapter.renderer(loaded)") < stages[4][1]
    assert "core.can_commit(scope, runtime)" in source
    assert "core.commit_if_current(scope, current" in source
    assert source.count("adapter.renderer(loaded)") == 1
    assert "_run_bounded_prefetch" not in source
    assert "choose_prefetch" not in source
    assert "sleep(" not in source
