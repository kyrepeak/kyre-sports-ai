from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_snapshot_r10.py"


def test_r10_re_resolves_page2_frame_and_uses_visibility_snapshots() -> None:
    assert TARGET.exists(), "R10 cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert 'PAGE2_ANCHOR_TESTID = "gtp2s8-final"' in source
    assert "SNAPSHOT_DEADLINE_SECONDS = 90.0" in source
    assert "_original_find(" in source
    assert "locator.is_visible(timeout=1500)" in source
    assert "missing = [" in source
    assert "PAGE2_REQUIRED_TESTIDS" in source
    assert "page.wait_for_timeout(750)" in source


def test_r10_preserves_low_memory_per_viewport_runner() -> None:
    assert TARGET.exists(), "R10 cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "all_viewports = dict(cert.VIEWPORTS)" in source
    assert "for name, viewport in all_viewports.items()" in source
    assert "cert.VIEWPORTS = {{name: viewport}}" in source
    assert "gc.collect()" in source
