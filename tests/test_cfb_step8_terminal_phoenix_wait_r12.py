from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_phoenix_wait_r12.py"


def test_r12_waits_for_phoenix_today_after_selector_rerender() -> None:
    assert TARGET.exists(), "R12 Phoenix-day rerender-safe cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "_rerender_safe_current_day_result" in source
    assert '"TODAY" in body and "PHOENIX TIME" in body' in source
    assert "deadline = time.monotonic()" in source
    assert "time.sleep(0.25)" in source


def test_r12_refinds_frame_if_streamlit_replaces_it() -> None:
    assert TARGET.exists(), "R12 Phoenix-day rerender-safe cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "frame, scans = cert._find_cfb_frame(" in source
    assert "except Exception:" in source
    assert "required_testids=(cert.PHOENIX_DAY_TESTID,)" in source


def test_r12_preserves_single_pass_terminal_owner() -> None:
    assert TARGET.exists(), "R12 Phoenix-day rerender-safe cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "cfb_step8_terminal_route_lock_single_pass_r11" in source
    assert '"step8-route-pointer-lock-postmerge-r12"' in source
    assert "terminal._cert_script = _r12_cert_script" in source
