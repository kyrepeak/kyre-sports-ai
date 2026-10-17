"""Universal tap-only compatibility adapter for finite Streamlit selectboxes."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import inspect
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


def _selector_identity(label: str, explicit_key: str | None, *, frame) -> str:
    if explicit_key is not None:
        return str(explicit_key)
    if isinstance(frame, tuple) and len(frame) == 2:
        filename, line = frame
    else:
        filename = getattr(getattr(frame, "f_code", None), "co_filename", "unknown")
        line = getattr(frame, "f_lineno", 0)
    seed = f"{filename}:{int(line)}:{label}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return f"__tap_only_selectbox__{digest}"


def _pagination_key(selector_id: str) -> str:
    return f"__tap_only_page__{selector_id}"


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

        for position in range(start, end):
            value = values[position]
            selected_here = selected_index == position
            button_key = f"{selector_id}__tap_only__option__{position}"
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
    "PAGE_SIZE",
    "install_universal_tap_only_selectboxes",
    "_materialize_options",
    "_pagination_key",
    "_selector_identity",
    "_page_for_index",
    "_resolve_selection",
    "_tap_only_selectbox",
]
