"""KYRE Streamlit router V2 — clean user shell with opt-in diagnostics.

Presentation-only wrapper over the frozen memory-safe lazy router. Internal route,
module-release and bridge-fallback diagnostics are hidden from the normal user
surface and remain available in a collapsed Developer Diagnostics expander.
Routing behavior, model loading and all sports projection math remain frozen.
"""
from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_v1 as frozen

MODEL_VERSION = "KYRE STREAMLIT ROUTER V2 • Clean diagnostics"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v1"
_USER_SHELL_SUBTITLE = "Fast, focused sports projection intelligence."


def _plain_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return " ".join(html.unescape(text).split())


def _is_internal_caption(value: Any) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return (
        "lazy route:" in lowered
        or text.startswith("Live odds bridge fallback:")
        or text.startswith("WNBA API schedule bridge fallback:")
    )


def _markdown_capture(original, diagnostics: list[str]):
    """Hide router telemetry and replace the technical shell subtitle."""
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if 'class="ks-route"' in text or "class='ks-route'" in text:
            cleaned = _plain_text(text)
            if cleaned:
                diagnostics.append(cleaned)
            return None
        if 'class="ks-shell"' in text or "class='ks-shell'" in text:
            body = text.replace(
                "Memory-safe lazy loading • one sport + one market loaded at a time.",
                _USER_SHELL_SUBTITLE,
            )
        return original(body, *args, **kwargs)
    return wrapped


def _caption_capture(original, diagnostics: list[str]):
    """Capture only internal route/fallback captions; preserve user/legal copy."""
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        if _is_internal_caption(body):
            text = str(body or "").strip()
            if text:
                diagnostics.append(text)
            return None
        return original(body, *args, **kwargs)
    return wrapped


def _render_developer_diagnostics(diagnostics: list[str]) -> None:
    if not diagnostics:
        return
    with st.sidebar.expander("🛠️ Developer Diagnostics", expanded=False):
        st.caption(f"Router: {frozen.MODEL_VERSION}")
        for item in diagnostics:
            st.caption(item)


def render_app() -> None:
    diagnostics: list[str] = []
    original_markdown = st.markdown
    original_caption = st.caption

    st.markdown = _markdown_capture(original_markdown, diagnostics)
    st.caption = _caption_capture(original_caption, diagnostics)
    try:
        frozen.render_app()
    finally:
        st.caption = original_caption
        st.markdown = original_markdown

    _render_developer_diagnostics(diagnostics)


__all__ = [
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "_caption_capture",
    "_is_internal_caption",
    "_markdown_capture",
    "_plain_text",
    "_render_developer_diagnostics",
    "render_app",
]
