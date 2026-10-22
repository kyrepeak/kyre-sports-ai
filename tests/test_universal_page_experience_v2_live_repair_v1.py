from __future__ import annotations

import importlib
import inspect


def test_top_control_has_real_page_top_target_and_mobile_hit_ownership() -> None:
    page = importlib.import_module("universal_page_experience_v1")
    assert hasattr(page, "page_experience_top_sentinel_markup")

    sentinel = page.page_experience_top_sentinel_markup()
    markup = page.page_experience_native_top_markup()
    compact = markup.replace(" ", "").lower()

    assert 'id="kyre-universal-page-top"' in sentinel
    assert 'href="#kyre-universal-page-top"' in markup
    assert "pointer-events:auto" in compact
    assert "touch-action:manipulation" in compact


def test_top_enhancement_prevents_default_and_scrolls_real_owner() -> None:
    page = importlib.import_module("universal_page_experience_v1")
    source = page.page_experience_controller_markup().replace(" ", "")

    assert "functiononTopClick(event)" in source
    assert "event.preventDefault()" in source
    assert "goTop();" in source
    assert 'topButton.addEventListener("click",onTopClick)' in source


def test_noninstant_route_transition_is_server_held_until_destination_commit() -> None:
    runtime = importlib.import_module("universal_page_experience_runtime_v1")
    source = inspect.getsource(runtime._render_page_experience_active)

    assert "page_experience_top_sentinel_markup" in source
    assert source.index("page_experience_top_sentinel_markup") < source.index("core._render_site_shell")
    assert "if is_transition:" in source
    assert "if is_transition and not client_controller:" not in source
    assert source.index("transition_slot.markdown") < source.index("core.load_destination")
    assert source.index("transition_slot.empty") > source.index("adapter.renderer")


def test_universal_loader_is_delayed_fade_takeover_not_stale_inline_status() -> None:
    page = importlib.import_module("universal_page_experience_v1")
    markup = page.page_experience_fallback_markup(None)
    compact = markup.replace(" ", "").lower()

    assert 'data-kyre-universal-loading="upe-v2-server"' in markup
    assert "position:fixed" in compact
    assert "inset:0" in compact
    assert "pointer-events:all" in compact
    assert "animation-delay:120ms" in compact
    assert "kyre sports ai" in markup.lower()
    assert "loading intelligence" in markup.lower()
    assert "kyre-upe-orbit" in markup


def test_client_transition_takeover_does_not_wait_for_streamlit_script_state() -> None:
    page = importlib.import_module("universal_page_experience_v1")
    source = page.page_experience_controller_markup().replace(" ", "")

    assert "functionarmTransition(name)" in source
    arm = source.split("functionarmTransition(name)", 1)[1].split("functionclassify", 1)[0]
    assert "showOverlay();" in arm
    assert "scriptState()!==\"NOTRUNNING\"" not in arm
