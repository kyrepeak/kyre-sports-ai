from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from time import monotonic
from typing import Any, Callable, ContextManager, Mapping, MutableMapping

from nfl_active_slate_controller_v1 import resolve_active_slate


MODE_KEY = "nfl_active_slate_mode"
ACTIVE_DATE_KEY = "nfl_active_slate_date"
MANUAL_DATE_KEY = "nfl_manual_slate_date"
STATE_KEY = "nfl_active_slate_state"
SOURCE_KEY = "nfl_active_slate_source"
CHECKED_AT_KEY = "nfl_active_slate_checked_at"
COMPAT_DATE_KEY = "nfl_v1_date"
_BRIDGE_SEED_PREFIX = "nfl_active_slate_bridge_seed::"


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def is_manual_mode(session: Mapping[str, Any]) -> bool:
    return str(session.get(MODE_KEY) or "").strip().upper() == "MANUAL"


def bridge_seed_key(widget_key: str) -> str:
    return f"{_BRIDGE_SEED_PREFIX}{widget_key}"


def _manual_result(manual_date: date) -> dict[str, Any]:
    return {
        "state": "MANUAL",
        "resolved_date": manual_date,
        "source": "manual",
        "reason": "manual_override",
        "advanced": False,
    }


def _future_reuse_result(active_date: date) -> dict[str, Any]:
    return {
        "state": "FOUND",
        "resolved_date": active_date,
        "source": "session_future_reuse",
        "reason": "verified_future_slate_reuse",
        "advanced": True,
    }


def prepare_nfl_active_slate(
    session: MutableMapping[str, Any],
    *,
    today_et: date,
    primary_loader: Callable,
    calendar_dates: Callable,
    now_monotonic: float | None = None,
) -> dict[str, Any]:
    mode = str(session.get(MODE_KEY) or "AUTO").strip().upper()
    if mode not in {"AUTO", "MANUAL"}:
        mode = "AUTO"
    session[MODE_KEY] = mode

    if mode == "MANUAL":
        manual_date = _coerce_date(session.get(MANUAL_DATE_KEY) or session.get(COMPAT_DATE_KEY))
        if manual_date is not None:
            session[MANUAL_DATE_KEY] = manual_date
            session[COMPAT_DATE_KEY] = manual_date
            session[STATE_KEY] = "MANUAL"
            session[SOURCE_KEY] = "manual"
            session[CHECKED_AT_KEY] = monotonic() if now_monotonic is None else float(now_monotonic)
            return _manual_result(manual_date)
        session[MODE_KEY] = "AUTO"

    active_date = _coerce_date(session.get(ACTIVE_DATE_KEY))
    if active_date is not None and active_date > today_et and session.get(STATE_KEY) == "FOUND":
        session[COMPAT_DATE_KEY] = active_date
        session[SOURCE_KEY] = "session_future_reuse"
        session[CHECKED_AT_KEY] = monotonic() if now_monotonic is None else float(now_monotonic)
        return _future_reuse_result(active_date)

    result = resolve_active_slate(
        today_et,
        primary_loader,
        calendar_dates,
    )
    session[STATE_KEY] = result.get("state")
    session[SOURCE_KEY] = result.get("source")
    session[CHECKED_AT_KEY] = monotonic() if now_monotonic is None else float(now_monotonic)
    resolved = _coerce_date(result.get("resolved_date"))
    if result.get("state") == "FOUND" and resolved is not None:
        session[ACTIVE_DATE_KEY] = resolved
        session[COMPAT_DATE_KEY] = resolved
        session.pop(MANUAL_DATE_KEY, None)
    return result


def _is_nfl_date_widget(label: Any, widget_key: Any) -> bool:
    label_text = str(label or "").strip().lower()
    key_text = str(widget_key or "").strip().lower()
    key_owned = key_text.startswith("nfl_") and "date" in key_text
    label_owned = "nfl" in label_text and "date" in label_text
    return key_owned or label_owned


def _target_date(session: Mapping[str, Any]) -> date | None:
    if is_manual_mode(session):
        return _coerce_date(session.get(MANUAL_DATE_KEY) or session.get(COMPAT_DATE_KEY))
    return _coerce_date(session.get(ACTIVE_DATE_KEY) or session.get(COMPAT_DATE_KEY))


def _enter_manual(session: MutableMapping[str, Any], chosen: date) -> None:
    session[MODE_KEY] = "MANUAL"
    session[MANUAL_DATE_KEY] = chosen
    session[COMPAT_DATE_KEY] = chosen
    session[STATE_KEY] = "MANUAL"
    session[SOURCE_KEY] = "manual"


@contextmanager
def install_nfl_date_input_bridge(session: MutableMapping[str, Any]) -> ContextManager[None]:
    import streamlit as st

    native_date_input = st.date_input

    def bridged_date_input(label: Any, *args: Any, **kwargs: Any):
        widget_key = kwargs.get("key")
        if not _is_nfl_date_widget(label, widget_key):
            return native_date_input(label, *args, **kwargs)

        key_text = str(widget_key or "").strip()
        target = _target_date(session)
        marker_key = bridge_seed_key(key_text) if key_text else ""
        last_seed = _coerce_date(session.get(marker_key)) if marker_key else None
        current_widget = _coerce_date(session.get(key_text)) if key_text else None

        if key_text and last_seed is not None and current_widget is not None and current_widget != last_seed:
            _enter_manual(session, current_widget)
            target = current_widget
        elif target is not None and key_text:
            session[key_text] = target

        if target is not None:
            kwargs["value"] = target
        if marker_key and target is not None:
            session[marker_key] = target

        chosen = native_date_input(label, *args, **kwargs)
        chosen_date = _coerce_date(chosen)
        if chosen_date is not None and target is not None and chosen_date != target:
            _enter_manual(session, chosen_date)
            if key_text:
                session[key_text] = chosen_date
            if marker_key:
                session[marker_key] = chosen_date
            return chosen_date
        return chosen

    st.date_input = bridged_date_input
    try:
        yield
    finally:
        st.date_input = native_date_input


__all__ = [
    "ACTIVE_DATE_KEY",
    "CHECKED_AT_KEY",
    "MANUAL_DATE_KEY",
    "MODE_KEY",
    "SOURCE_KEY",
    "STATE_KEY",
    "bridge_seed_key",
    "install_nfl_date_input_bridge",
    "is_manual_mode",
    "prepare_nfl_active_slate",
]
