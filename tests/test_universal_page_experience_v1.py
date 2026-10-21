from __future__ import annotations

import importlib
import importlib.util


def _module():
    spec = importlib.util.find_spec("universal_page_experience_v1")
    assert spec is not None, "universal_page_experience_v1 must exist"
    return importlib.import_module("universal_page_experience_v1")


def test_universal_top_controller_contract() -> None:
    page = _module()
    markup = page.page_experience_controller_markup()
    compact = markup.replace(" ", "").lower()

    assert page.PAGE_EXPERIENCE_VERSION == "API2 UNIVERSAL PAGE EXPERIENCE V1"
    assert page.TOP_REVEAL_PX == 320
    assert page.LOADER_DELAY_MS == 140
    assert markup.count('topButton.setAttribute("data-kyre-universal-top", "v1")') == 1
    assert "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V1__" in markup
    assert "position:fixed" in compact
    assert "min-width:44px" in compact
    assert "min-height:44px" in compact
    assert "env(safe-area-inset-right" in compact
    assert "env(safe-area-inset-bottom" in compact
    assert "scrollto" in compact
    assert "prefers-reduced-motion" in compact
    assert "st.session_state" not in markup


def test_controller_reuses_singleton_and_detects_scroll_owner() -> None:
    page = _module()
    markup = page.page_experience_controller_markup()

    assert 'existing.version === "v1"' in markup
    assert "existing.refresh" in markup
    assert "querySelector('[data-testid=\"stAppViewContainer\"]')" in markup
    assert "document.scrollingElement" in markup
    assert "window.scrollTo" in markup or "host.scrollTo" in markup
    assert "addEventListener(\"scroll\"" in markup
    assert "removeEventListener(\"scroll\"" in markup


def test_transition_classifier_covers_page_changing_intents() -> None:
    page = _module()
    markup = page.page_experience_controller_markup()

    assert 'const PAGE_TRANSITION = "PAGE_TRANSITION"' in markup
    assert 'const LOCAL_INTERACTION = "LOCAL_INTERACTION"' in markup
    assert ".st-key-ks_universal_nav_shell" in markup
    assert "analy" in markup.lower()
    assert "open|view|back" in markup.lower()
    assert 'host.addEventListener("popstate"' in markup
    assert "routeSignature" in markup
    assert "armTransition" in markup


def test_local_controls_are_excluded_from_full_page_loader() -> None:
    page = _module()
    markup = page.page_experience_controller_markup().lower()

    for token in ('input', 'textarea', 'select', '[role="slider"]', '[type="range"]'):
        assert token in markup
    assert "local_interaction" in markup
    assert "canceltimer" in markup
    assert "hideoverlay" in markup


def test_fallback_loader_is_opaque_and_branded() -> None:
    page = _module()

    class Route:
        sport_id = "nba"
        market_id = "pra"
        params = {"player_id": "test-player"}

    markup = page.page_experience_fallback_markup(Route())
    compact = markup.replace(" ", "").lower()
    assert "kyre sports ai" in markup.lower()
    assert "#060b13" in compact
    assert "position:fixed" in compact
    assert "inset:0" in compact
    assert "nba pra" in markup.lower()
