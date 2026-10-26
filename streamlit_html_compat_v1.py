"""Sitewide Streamlit HTML compatibility for API2 presentation surfaces.

Streamlit Community Cloud currently emits CSS and native controls correctly while
pure HTML blocks sent through ``st.markdown(..., unsafe_allow_html=True)`` can be
omitted from the live delta tree. API2 has many presentation-only cards built on
that call shape. This shim routes only pure HTML/CSS presentation strings to the
dedicated ``st.html`` renderer while preserving normal Markdown, script-bearing
blocks, positional calls, and unsupported keyword semantics on the original
renderer.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

VERSION = "API2_STREAMLIT_HTML_COMPAT_V1"
_INSTALL_FLAG = "_kyre_sitewide_html_compat_v1_installed"
_ALLOWED_HTML_KWARGS = {"unsafe_allow_html", "width"}


def _is_pure_html(body: Any) -> bool:
    if not isinstance(body, str):
        return False
    text = body.lstrip()
    if not text.startswith("<"):
        return False
    # Keep script-bearing blocks on their original execution path. The shared
    # page-experience controller already uses st.html directly where scripts are
    # required, so this prevents the compatibility layer from changing script
    # semantics elsewhere.
    if "<script" in text.casefold():
        return False
    return True


def install_sitewide_html_compat(st_module: Any) -> bool:
    """Install one process-wide, stateless HTML rendering compatibility shim.

    Returns ``True`` when installed and ``False`` when already installed or when
    the dedicated HTML renderer is unavailable. The wrapper has no per-session
    mutable state, so concurrent Streamlit sessions share only immutable routing
    rules rather than presentation state.
    """
    if bool(getattr(st_module, _INSTALL_FLAG, False)):
        return False

    original_markdown = getattr(st_module, "markdown", None)
    html_renderer = getattr(st_module, "html", None)
    if not callable(original_markdown) or not callable(html_renderer):
        return False

    @wraps(original_markdown)
    def markdown_compat(body: Any, *args: Any, **kwargs: Any):
        unsafe = kwargs.get("unsafe_allow_html") is True
        supported_kwargs = set(kwargs).issubset(_ALLOWED_HTML_KWARGS)
        if unsafe and not args and supported_kwargs and _is_pure_html(body):
            html_kwargs: dict[str, Any] = {}
            if "width" in kwargs:
                html_kwargs["width"] = kwargs["width"]
            return html_renderer(body, **html_kwargs)
        return original_markdown(body, *args, **kwargs)

    setattr(st_module, "markdown", markdown_compat)
    setattr(st_module, _INSTALL_FLAG, True)
    return True


__all__ = ["VERSION", "install_sitewide_html_compat"]
