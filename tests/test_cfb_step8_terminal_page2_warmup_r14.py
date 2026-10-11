from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_page2_warmup_r14.py"


def test_r14_extends_only_page2_anchor_warmup() -> None:
    assert TARGET.exists(), "R14 Page2 warmup cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "PAGE2_FRAME_TIMEOUT_SECONDS = 100.0" in source
    assert "r11.PAGE2_FRAME_TIMEOUT_SECONDS = PAGE2_FRAME_TIMEOUT_SECONDS" in source


def test_r14_preserves_r13_r12_r11_chain() -> None:
    assert TARGET.exists(), "R14 Page2 warmup cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "cfb_step8_terminal_route_lock_screenshot_nonfatal_r13" in source
    assert "r13._r13_cert_script()" in source
    assert '"step8-route-pointer-lock-postmerge-r14"' in source
    assert "terminal._cert_script = _r14_cert_script" in source
