from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "runless_proof_plane" / "cfb_step8_terminal_route_lock_screenshot_nonfatal_r13.py"


def test_r13_makes_only_screenshot_capture_nonfatal() -> None:
    assert TARGET.exists(), "R13 nonfatal screenshot cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "class _NonFatalScreenshotPage" in source
    assert "def screenshot(self, *args, **kwargs):" in source
    assert 'kwargs.setdefault("timeout", 8000)' in source
    assert "except Exception as exc:" in source
    assert "CFB_STEP8_SCREENSHOT_NONFATAL" in source


def test_r13_preserves_all_other_page_behavior_by_proxy() -> None:
    assert TARGET.exists(), "R13 nonfatal screenshot cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "def __getattr__(self, name):" in source
    assert "return getattr(self._page, name)" in source
    assert "raw_page = browser.new_page(viewport=viewport)" in source
    assert "page = _NonFatalScreenshotPage(raw_page)" in source


def test_r13_preserves_r12_terminal_chain() -> None:
    assert TARGET.exists(), "R13 nonfatal screenshot cert not implemented"
    source = TARGET.read_text(encoding="utf-8")
    assert "cfb_step8_terminal_route_lock_phoenix_wait_r12" in source
    assert '"step8-route-pointer-lock-postmerge-r13"' in source
    assert "terminal._cert_script = _r13_cert_script" in source
