"""NFL Moneyline V11 — no-flash presentation execution over certified V10.

V11 changes presentation execution only. Frozen V8 still computes the complete
Moneyline analytical chain, V9 still owns the matchup-card presentation, and
V10 still owns the Kyre Sports API transport swap. V11 temporarily replaces
V9's disposable legacy renderer with a silent Streamlit execution path so V8
can populate its certified session-state outputs without sending the old
step-first UI to the browser before V9 paints the matchup cards.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

import streamlit as st

import nfl_moneyline_hub_v9 as frozen_v9
import nfl_moneyline_hub_v10 as v10

MODEL_VERSION = "NFL MONEYLINE V11 • NO-FLASH EXECUTION • V10/V9/V8 FROZEN"
FROZEN_TRANSPORT = "nfl_moneyline_hub_v10"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
PRESENTATION_EXECUTION_ONLY = True
LEGACY_UI_EMISSION_ENABLED = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def _noop(*args, **kwargs):
    """Pickle-safe shared no-op used by the silent Streamlit facade."""
    return None


class _SilentBlock:
    """Minimal DeltaGenerator-like object used only during frozen V8 execution."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def empty(self):
        return self

    def container(self, *args, **kwargs):
        return self

    def expander(self, *args, **kwargs):
        return self

    def status(self, *args, **kwargs):
        return self

    def spinner(self, *args, **kwargs):
        return self

    def progress(self, *args, **kwargs):
        return self

    def columns(self, spec, *args, **kwargs):
        return _silent_columns(spec)

    def tabs(self, labels, *args, **kwargs):
        return [_SilentBlock() for _ in list(labels or [])]

    def __getattr__(self, _name):
        # Keep unknown legacy calls silent while remaining safe for Streamlit's
        # cache message/result pickling. Never return a locally-created closure.
        return _noop


def _silent_block(*args, **kwargs):
    return _SilentBlock()


def _silent_columns(spec, *args, **kwargs):
    try:
        count = int(spec)
    except (TypeError, ValueError):
        try:
            count = len(spec)
        except Exception:
            count = 1
    return [_SilentBlock() for _ in range(max(0, count))]


def _silent_tabs(labels, *args, **kwargs):
    try:
        count = len(labels)
    except Exception:
        count = 0
    return [_SilentBlock() for _ in range(max(0, count))]


def _state_value(key: Any, fallback: Any):
    if key is not None:
        try:
            if key in st.session_state:
                return st.session_state[key]
            st.session_state[key] = fallback
        except Exception:
            pass
    return fallback


def _silent_date_input(label, value="today", *args, **kwargs):
    key = kwargs.get("key")
    if value == "today":
        value = st.session_state.get("nfl_v1_date", date.today())
    return _state_value(key, value)


def _silent_text_input(label, value="", *args, **kwargs):
    return _state_value(kwargs.get("key"), value)


def _silent_number_input(label, *args, **kwargs):
    value = kwargs.get("value", 0.0)
    return _state_value(kwargs.get("key"), value)


def _silent_bool_widget(label, value=False, *args, **kwargs):
    return bool(_state_value(kwargs.get("key"), value))


def _silent_selectbox(label, options, *args, **kwargs):
    key = kwargs.get("key")
    if key is not None:
        try:
            if key in st.session_state:
                return st.session_state[key]
        except Exception:
            pass
    try:
        values = list(options)
    except Exception:
        values = []
    index = kwargs.get("index", 0)
    value = None if index is None or not values else values[max(0, min(int(index), len(values) - 1))]
    return _state_value(key, value)


def _silent_multiselect(label, options, default=None, *args, **kwargs):
    try:
        value = list(default) if default is not None else []
    except Exception:
        value = []
    return _state_value(kwargs.get("key"), value)


def _silent_slider(label, *args, **kwargs):
    value = kwargs.get("value")
    if value is None and len(args) >= 3:
        value = args[2]
    return _state_value(kwargs.get("key"), value)


def _silent_data_editor(data=None, *args, **kwargs):
    return data


@contextmanager
def _silent_streamlit_execution():
    """Suppress legacy V1-V8 UI emission while preserving real session state."""
    originals = {}

    def patch(name: str, replacement) -> None:
        if hasattr(st, name):
            originals[name] = getattr(st, name)
            setattr(st, name, replacement)

    display_calls = (
        "markdown", "caption", "write", "text", "title", "header", "subheader",
        "success", "info", "warning", "error", "exception", "dataframe", "table",
        "json", "code", "image", "plotly_chart", "pyplot", "line_chart", "area_chart",
        "bar_chart", "scatter_chart", "map", "metric", "divider", "latex", "html",
        "audio", "video", "badge",
    )
    for name in display_calls:
        patch(name, _noop)

    for name in ("container", "empty", "expander", "spinner", "status", "popover", "progress"):
        patch(name, _silent_block)
    patch("columns", _silent_columns)
    patch("tabs", _silent_tabs)

    patch("date_input", _silent_date_input)
    patch("text_input", _silent_text_input)
    patch("text_area", _silent_text_input)
    patch("number_input", _silent_number_input)
    patch("checkbox", _silent_bool_widget)
    patch("toggle", _silent_bool_widget)
    patch("selectbox", _silent_selectbox)
    patch("radio", _silent_selectbox)
    patch("multiselect", _silent_multiselect)
    patch("slider", _silent_slider)
    patch("select_slider", _silent_slider)
    patch("button", lambda *args, **kwargs: False)
    patch("form_submit_button", lambda *args, **kwargs: False)
    patch("download_button", lambda *args, **kwargs: False)
    patch("file_uploader", lambda *args, **kwargs: None)
    patch("data_editor", _silent_data_editor)

    if hasattr(st, "sidebar"):
        originals["sidebar"] = st.sidebar
        st.sidebar = _SilentBlock()

    try:
        yield
    finally:
        for name, original in reversed(tuple(originals.items())):
            setattr(st, name, original)


def _silent_run_frozen_engine() -> None:
    """Execute the exact frozen V8 chain without emitting its legacy UI."""
    with _silent_streamlit_execution():
        frozen_v9.frozen.render_nfl_moneyline_hub()


def render_nfl_hub(market: str = "Moneyline"):
    market = str(market or "Moneyline")
    if market != "Moneyline":
        raise RuntimeError("Moneyline V11 direct handler is Moneyline only.")

    original_runner = frozen_v9._run_frozen_engine
    frozen_v9._run_frozen_engine = _silent_run_frozen_engine
    try:
        return v10.render_nfl_hub(market)
    finally:
        frozen_v9._run_frozen_engine = original_runner


__all__ = [
    "FROZEN_ENGINE",
    "FROZEN_PRESENTATION",
    "FROZEN_TRANSPORT",
    "LEGACY_UI_EMISSION_ENABLED",
    "MODEL_VERSION",
    "PRESENTATION_EXECUTION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_silent_run_frozen_engine",
    "_silent_streamlit_execution",
    "render_nfl_hub",
]
