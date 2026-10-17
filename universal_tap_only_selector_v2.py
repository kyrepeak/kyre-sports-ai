"""Universal tap-only selector V2 — exact-value button identity across reruns.

V2 preserves the frozen V1 selectbox compatibility contract while changing only
option-button identity: keys are derived from the raw option value instead of
its current list position. A reordered slate therefore cannot turn a tap for
one exact game into a tap for a different game.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import inspect
import json
from typing import Any

import streamlit as st

import universal_tap_only_selector_v1 as prior

PAGE_SIZE = prior.PAGE_SIZE
_MISSING = prior._MISSING
_NATIVE_SELECTBOX_STACK: list[Any] = []
_materialize_options = prior._materialize_options
_equal = prior._equal
_find_index = prior._find_index
_resolve_selection = prior._resolve_selection
_page_for_index = prior._page_for_index
_selector_identity = prior._selector_identity
_pagination_key = prior._pagination_key


def _state_get(key: Any, default: Any = _MISSING) -> Any:
    if key is None:
        return default
    try:
        return st.session_state.get(key, default)
    except Exception:
        return default


def _state_set(key: Any, value: Any) -> None:
    if key is not None:
        st.session_state[key] = value


def _stable_option_token(value: Any) -> str:
    """Return an order-independent token for one raw option value."""
    try:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        payload = repr(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _tap_only_selectbox(
    label: str,
    options,
    index: int | None = 0,
    format_func=str,
    key=None,
    help: str | None = None,
    on_change: Any = "rerun",
    args=None,
    kwargs=None,
    *,
    placeholder: str | None = None,
    disabled: bool = False,
    label_visibility: str = "visible",
    accept_new_options: bool = False,
    filter_mode: str = "fuzzy",
    width: Any = "stretch",
    bind=None,
    persist_state=None,
    _caller_frame=None,
):
    values = _materialize_options(options)
    if _caller_frame is None:
        _caller_frame = inspect.currentframe().f_back
    selector_id = _selector_identity(label, None if key is None else str(key), frame=_caller_frame)
    state_key = key if key is not None else selector_id
    stored = _state_get(state_key)
    selected_index, selected = _resolve_selection(values, stored=stored, index=index)

    if selected is not None and _find_index(values, stored) is None:
        _state_set(state_key, selected)

    if label_visibility == "visible" and label:
        st.caption(str(label))

    trigger = format_func(selected) if selected is not None else (placeholder or "Choose an option")
    popover_kwargs = {
        "help": help,
        "disabled": bool(disabled or not values),
        "width": width,
        "key": f"{selector_id}__tap_only__popover",
    }
    with st.popover(str(trigger), **popover_kwargs):
        total = len(values)
        page_key = _pagination_key(selector_id)
        page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        stored_page = _state_get(page_key)
        if stored_page is _MISSING:
            page = _page_for_index(selected_index, total)
        else:
            try:
                page = max(0, min(int(stored_page), page_count - 1))
            except (TypeError, ValueError):
                page = _page_for_index(selected_index, total)
        start = page * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)

        occurrence_by_token: dict[str, int] = {}
        for prior_value in values[:start]:
            token = _stable_option_token(prior_value)
            occurrence_by_token[token] = occurrence_by_token.get(token, 0) + 1

        for position in range(start, end):
            value = values[position]
            selected_here = selected_index == position
            option_token = _stable_option_token(value)
            occurrence = occurrence_by_token.get(option_token, 0)
            occurrence_by_token[option_token] = occurrence + 1
            button_key = f"{selector_id}__tap_only__option__{option_token}__{occurrence}"
            clicked = st.button(
                ("✓ " if selected_here else "") + str(format_func(value)),
                key=button_key,
                disabled=bool(disabled),
                width="stretch",
                type="primary" if selected_here else "secondary",
            )
            if clicked and not disabled:
                _state_set(state_key, value)
                selected_index, selected = position, value
                if callable(on_change):
                    on_change(*(args or ()), **(kwargs or {}))

        if total > PAGE_SIZE:
            st.caption(f"items {start + 1}–{end} of {total}")
            prev_clicked = st.button(
                "Previous",
                key=f"{selector_id}__tap_only__prev",
                disabled=bool(disabled or page <= 0),
                width="stretch",
            )
            next_clicked = st.button(
                "Next",
                key=f"{selector_id}__tap_only__next",
                disabled=bool(disabled or page >= page_count - 1),
                width="stretch",
            )
            if prev_clicked and not disabled and page > 0:
                _state_set(page_key, page - 1)
            if next_clicked and not disabled and page < page_count - 1:
                _state_set(page_key, page + 1)

    return selected


@contextmanager
def install_universal_tap_only_selectboxes():
    native = st.selectbox
    _NATIVE_SELECTBOX_STACK.append(native)

    def bridge(label, options, *args, **kwargs):
        if kwargs.get("accept_new_options") is True:
            return native(label, options, *args, **kwargs)
        caller_frame = inspect.currentframe().f_back
        return _tap_only_selectbox(label, options, *args, _caller_frame=caller_frame, **kwargs)

    st.selectbox = bridge
    try:
        yield
    finally:
        st.selectbox = native
        _NATIVE_SELECTBOX_STACK.pop()


__all__ = [
    "PAGE_SIZE", "install_universal_tap_only_selectboxes", "_find_index", "_materialize_options",
    "_pagination_key", "_selector_identity", "_page_for_index", "_resolve_selection",
    "_stable_option_token", "_tap_only_selectbox",
]
