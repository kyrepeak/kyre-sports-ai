"""Universal tap-only selector activation above Universal Sports Navigation V2."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_universal_nav_v2 as prior
import universal_tap_only_selector_v1 as selector


MODEL_VERSION = "API2 UNIVERSAL TAP-ONLY SELECTOR V1"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v2"
UNIVERSAL_TAP_ONLY_SELECTOR_ENABLED = True


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    with selector.install_universal_tap_only_selectboxes():
        return prior.render_app()


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "UNIVERSAL_TAP_ONLY_SELECTOR_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
