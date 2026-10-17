"""Universal tap-only compatibility adapter for finite Streamlit selectboxes."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

import streamlit as st


PAGE_SIZE = 20
_MISSING = object()
_NATIVE_SELECTBOX_STACK: list[Any] = []


def _materialize_options(options: Iterable[Any]) -> list[Any]:
    try:
        return list(options)
    except TypeError as exc:
        raise TypeError("tap-only selectbox options must be iterable") from exc


def _equal(left: Any, right: Any) -> bool:
    try:
        result = left == right
        return bool(result) if isinstance(result, bool) else False
    except Exception:
        return left is right


def _find_index(values: list[Any], stored: Any) -> int | None:
    if stored is _MISSING:
        return None
    for position, value in enumerate(values):
        if value is stored or _equal(value, stored):
            return position
    return None


def _resolve_selection(
    values: list[Any], *, stored: Any, index: int | None
) -> tuple[int | None, Any | None]:
    stored_index = _find_index(values, stored)
    if stored_index is not None:
        return stored_index, values[stored_index]
    if index is None or not values:
        return None, None
    safe_index = int(index)
    if safe_index < 0 or safe_index >= len(values):
        raise IndexError("selectbox index out of range")
    return safe_index, values[safe_index]


def _page_for_index(selected_index: int | None, total: int, page_size: int = PAGE_SIZE) -> int:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if selected_index is None or total <= 0:
        return 0
    safe_index = max(0, min(int(selected_index), total - 1))
    return safe_index // page_size


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
):
    values = _materialize_options(options)
    stored = _state_get(key)
    selected_index, selected = _resolve_selection(values, stored=stored, index=index)

    if key is not None and selected is not None and _find_index(values, stored) is None:
        _state_set(key, selected)

    if label_visibility == "visible" and label:
        st.caption(str(label))

    trigger = format_func(selected) if selected is not None else (placeholder or "Choose an option")
    popover_kwargs = {
        "help": help,
        "disabled": bool(disabled or not values),
        "width": width,
        "key": f"{key or 'tap_only'}__tap_only__popover",
    }
    with st.popover(str(trigger), **popover_kwargs):
        for position, value in enumerate(values[:PAGE_SIZE]):
            selected_here = selected_index == position
            button_key = f"{key or 'tap_only'}__tap_only__{position}"
            clicked = st.button(
                ("✓ " if selected_here else "") + str(format_func(value)),
                key=button_key,
                disabled=bool(disabled),
                width="stretch",
                type="primary" if selected_here else "secondary",
            )
            if clicked and not disabled:
                _state_set(key, value)
                selected_index, selected = position, value

    return selected


@contextmanager
def install_universal_tap_only_selectboxes():
    native = st.selectbox
    _NATIVE_SELECTBOX_STACK.append(native)

    def bridge(label, options, *args, **kwargs):
        if kwargs.get("accept_new_options") is True:
            return native(label, options, *args, **kwargs)
        return _tap_only_selectbox(label, options, *args, **kwargs)

    st.selectbox = bridge
    try:
        yield
    finally:
        st.selectbox = native
        _NATIVE_SELECTBOX_STACK.pop()


__all__ = [
    "PAGE_SIZE",
    "install_universal_tap_only_selectboxes",
    "_materialize_options",
    "_page_for_index",
    "_resolve_selection",
    "_tap_only_selectbox",
]
