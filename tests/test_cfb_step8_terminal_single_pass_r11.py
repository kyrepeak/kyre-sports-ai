from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_single_pass_r11.py"


def test_r11_removes_repeated_run_public_wrappers() -> None:
    assert TARGET.exists(), "R11 single-pass cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "cert.run_public(" not in source
    assert "health = cert.base._wait_for_health(" in source
    assert "render_identity = cert.verify_render_identity()" in source


def test_r11_keeps_all_four_viewports_with_fresh_browser_per_viewport() -> None:
    assert TARGET.exists(), "R11 single-pass cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "all_viewports = dict(cert.VIEWPORTS)" in source
    assert "for name, viewport in all_viewports.items():" in source
    assert "browser = p.chromium.launch(" in source
    assert "current_day = cert._current_day_result(" in source
    assert "page1, selected_url, event_id = cert._page1_result(" in source
    assert "page2 = cert._page2_result(" in source
    assert "browser.close()" in source
    assert "gc.collect()" in source


def test_r11_preserves_anchor_rerender_and_terminal_contract() -> None:
    assert TARGET.exists(), "R11 single-pass cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert 'PAGE2_ANCHOR_TESTID = "gtp2s8-final"' in source
    assert "_rerender_safe_visible" in source
    assert '"step8-route-pointer-lock-postmerge-r11"' in source
    assert '"CFB_STEP8_R5_PUBLIC_PAYLOAD="' in source


def test_r11_rerender_selector_is_well_formed() -> None:
    assert TARGET.exists(), "R11 single-pass cert harness not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "frame.locator(f'[data-testid=\"{{testid}}\"]')" in source
