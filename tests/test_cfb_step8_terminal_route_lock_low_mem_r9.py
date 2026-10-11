from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_low_mem_r9.py"


def test_r9_anchors_page2_on_final_marker_with_safe_window() -> None:
    assert TARGET.exists(), "R9 cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert 'PAGE2_ANCHOR_TESTID = "gtp2s8-final"' in source
    assert "PAGE2_FRAME_TIMEOUT_SECONDS = 60.0" in source
    assert 'required_testids=(PAGE2_ANCHOR_TESTID,)' in source
    assert 'tuple(required_testids) == tuple(cert.PAGE2_REQUIRED_TESTIDS)' in source


def test_r9_restarts_browser_per_viewport_and_collects_gc() -> None:
    assert TARGET.exists(), "R9 cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "for name, viewport in all_viewports.items()" in source
    assert "cert.VIEWPORTS = {{name: viewport}}" in source
    assert "cert.run_public(" in source
    assert "gc.collect()" in source
