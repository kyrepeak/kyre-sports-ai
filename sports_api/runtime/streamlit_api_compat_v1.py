"""Tiny Streamlit compatibility surface for the FastAPI runtime only.

The API imports legacy shared modules that use Streamlit cache decorators and a
few UI helpers. Installing the full Streamlit UI stack in Vercel's FastAPI
function pulls PyArrow and other large packages into ephemeral storage. This
module provides only the import/runtime surface the server needs and is
installed by the API entrypoint before routers are imported.
"""
from __future__ import annotations

import sys
import types
from contextlib import nullcontext
from typing import Any, Callable


class _NoopCache:
    def __call__(self, func: Callable[..., Any] | None = None, **_: Any):
        def decorate(inner: Callable[..., Any]) -> Callable[..., Any]:
            return inner

        return decorate(func) if callable(func) else decorate

    def clear(self) -> None:
        return None


def _noop(*_: Any, **__: Any) -> None:
    return None


def _empty_text(*_: Any, **__: Any) -> str:
    return ""


def _false(*_: Any, **__: Any) -> bool:
    return False


def _context(*_: Any, **__: Any):
    return nullcontext()


def install_streamlit_api_compat() -> types.ModuleType:
    """Install and return a lightweight `streamlit` module for API execution."""
    existing = sys.modules.get("streamlit")
    if existing is not None and getattr(existing, "__kyre_api_compat__", False):
        return existing

    module = types.ModuleType("streamlit")
    module.__kyre_api_compat__ = True
    module.cache_data = _NoopCache()
    module.cache_resource = _NoopCache()
    module.secrets = {}
    module.session_state = {}
    module.error = _noop
    module.warning = _noop
    module.info = _noop
    module.success = _noop
    module.markdown = _noop
    module.caption = _noop
    module.write = _noop
    module.dataframe = _noop
    module.rerun = _noop
    module.expander = _context
    module.container = _context
    module.spinner = _context
    module.text_input = _empty_text
    module.button = _false
    sys.modules["streamlit"] = module
    return module
