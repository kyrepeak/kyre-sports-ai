from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_runtime_recovery_r15.py"


def test_r15_allows_transient_current_day_runtime_banner_to_recover() -> None:
    assert TARGET.exists(), "R15 runtime-recovery cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "last_runtime_error = \"\"" in source
    assert "if runtime_error:" in source
    assert "last_runtime_error = runtime_error" in source
    assert "time.sleep(0.25)" in source


def test_r15_still_fails_if_runtime_error_persists() -> None:
    assert TARGET.exists(), "R15 runtime-recovery cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "if last_runtime_error:" in source
    assert "CURRENT_DAY_RUNTIME_ERROR" in source
    assert "CURRENT_DAY_PHOENIX_TODAY_MISSING" in source


def test_r15_preserves_r14_terminal_chain() -> None:
    assert TARGET.exists(), "R15 runtime-recovery cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "cfb_step8_terminal_route_lock_page2_warmup_r14" in source
    assert "r14._r14_cert_script()" in source
    assert '"step8-route-pointer-lock-postmerge-r15"' in source
    assert "terminal._cert_script = _r15_cert_script" in source
