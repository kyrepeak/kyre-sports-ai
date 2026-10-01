"""WNBA PRA Speed V3 Step 9 — duplicate Streamlit key guard.

Presentation/control-plane wrapper only. It preserves the frozen WNBA PRA
runtime and intercepts only repeated Game Center player-button keys generated
by the frozen Step-3 UI. The first occurrence is untouched; later duplicate
occurrences receive a deterministic suffix for the duration of one render.

No player identity, navigation target, projection, model math, market math,
provider behavior, data semantics, or speed threshold changes here.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step8 as frozen_parent

PLAYER_BUTTON_KEY_PREFIX = "wnba_nav_v2_step3_player_"
DUPLICATE_KEY_SUFFIX = "__step9_dup_"

record_bootstrap_import_ms = frozen_parent.record_bootstrap_import_ms


def _with_duplicate_game_center_key_guard(callback: Callable[[], Any]) -> Any:
    """Make only repeated frozen Game Center player-button keys unique."""
    original_button = st.button
    seen: dict[str, int] = {}

    def guarded_button(*args: Any, **kwargs: Any):
        raw_key = kwargs.get("key")
        if isinstance(raw_key, str) and raw_key.startswith(PLAYER_BUTTON_KEY_PREFIX):
            occurrence = seen.get(raw_key, 0)
            seen[raw_key] = occurrence + 1
            if occurrence:
                kwargs["key"] = f"{raw_key}{DUPLICATE_KEY_SUFFIX}{occurrence}"
        return original_button(*args, **kwargs)

    st.button = guarded_button
    try:
        return callback()
    finally:
        st.button = original_button


def render_app():
    return _with_duplicate_game_center_key_guard(frozen_parent.render_app)


__all__ = [
    "DUPLICATE_KEY_SUFFIX",
    "PLAYER_BUTTON_KEY_PREFIX",
    "record_bootstrap_import_ms",
    "render_app",
]
