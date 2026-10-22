from __future__ import annotations

import importlib
import inspect


def test_native_top_fallback_is_fixed_visible_and_no_javascript() -> None:
    page = importlib.import_module("universal_page_experience_v1")
    markup = page.page_experience_native_top_markup()
    compact = markup.replace(" ", "").lower()

    assert 'data-kyre-universal-top="v2"' in markup
    assert 'href="#"' in markup
    assert "↑ TOP" in markup
    assert "position:fixed" in compact
    assert "min-width:44px" in compact
    assert "min-height:44px" in compact
    assert "env(safe-area-inset-right" in compact
    assert "env(safe-area-inset-bottom" in compact
    assert 'aria-hidden="true"' not in markup
    assert "<script" not in markup.lower()


def test_runtime_mounts_native_top_before_javascript_controller() -> None:
    runtime = importlib.import_module("universal_page_experience_runtime_v1")
    source = inspect.getsource(runtime._mount_page_experience_controller)

    assert "page_experience_native_top_markup" in source
    assert "unsafe_allow_html=True" in source
    assert source.index("page_experience_native_top_markup") < source.index("page_experience_controller_markup")
