from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "universal_page_experience_v2.py"


def test_v2_source_exists_and_is_forward_only() -> None:
    assert TARGET.exists()
    source = TARGET.read_text(encoding="utf-8")
    assert "from universal_page_experience_v1 import" in source
    assert "PAGE_EXPERIENCE_VERSION = \"API2 UNIVERSAL PAGE EXPERIENCE V2\"" in source


def test_internal_links_are_forced_same_tab_without_touching_external_links() -> None:
    source = TARGET.read_text(encoding="utf-8")
    assert "new URL(raw, host.location.href)" in source
    assert "url.origin !== host.location.origin" in source
    assert 'anchor.setAttribute("target", "_self")' in source
    assert "MutationObserver" in source
    assert "setInterval(" not in source


def test_latest_tap_generation_invalidates_stale_delayed_work() -> None:
    source = TARGET.read_text(encoding="utf-8")
    assert "let navGeneration = 0" in source
    assert "const generation = ++navGeneration" in source
    assert "generation !== navGeneration" in source
    assert 'host.addEventListener("popstate"' in source
