from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_cumulative_r11.py"


def test_r11_accumulates_visible_page2_sections_across_rerenders() -> None:
    assert TARGET.exists(), "R11 cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert 'PAGE2_ANCHOR_TESTID = "gtp2s8-final"' in source
    assert "SNAPSHOT_DEADLINE_SECONDS = 90.0" in source
    assert "seen_visible = set()" in source
    assert "seen_visible.add(testid)" in source
    assert "missing = [testid for testid in cert.PAGE2_REQUIRED_TESTIDS if testid not in seen_visible]" in source
    assert "_original_find(" in source
    assert "locator.is_visible(timeout=1500)" in source


def test_r11_keeps_one_browser_process_per_viewport() -> None:
    assert TARGET.exists(), "R11 cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "all_viewports = dict(cert.VIEWPORTS)" in source
    assert "for name, viewport in all_viewports.items()" in source
    assert "cert.VIEWPORTS = {{name: viewport}}" in source
    assert "gc.collect()" in source
