"""CFB Game Total Page 1 visual cleanup Step 3 runtime activation.

Installs additive presentation hooks only after the frozen V38 page is freshly
imported by the exact CFB Game Total route. Frozen source files stay immutable.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import importlib
from threading import RLock
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from cfb_game_total_page1_visual_cleanup_step3_overview_v1 import (
    PHOENIX_TZ,
    build_overview_edge_html,
    build_team_snapshot_html,
    phoenix_day_window_including_today,
)

MODEL_VERSION = "CFB GAME TOTAL PAGE1 VISUAL CLEANUP • STEP 3 OVERVIEW TEAM SNAPSHOT V1"
TARGET_PAGE = "cfb_game_total_clean_page_v38"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
_INSTALL_ATTR = "_cfb_game_total_visual_cleanup_step3_installed"
_LOCK = RLock()


def _query_raw_date(st: Any, day_owner: Any) -> str:
    try:
        raw = st.query_params.get(day_owner.DATE_QUERY_KEY)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _today_day_strip(v36: Any):
    import streamlit as st

    day_owner = v36.day_owner
    now = datetime.now(ZoneInfo(PHOENIX_TZ))
    raw = _query_raw_date(st, day_owner)
    days = phoenix_day_window_including_today(raw or None, now=now, count=7)
    selected = days[0]
    if raw:
        try:
            requested = datetime.fromisoformat(raw[:10]).date()
            if requested >= now.date():
                selected = requested
                days = phoenix_day_window_including_today(selected, now=now, count=7)
        except ValueError:
            pass
    if raw != selected.isoformat():
        day_owner._set_query_date(selected)

    st.markdown(
        '<div class="gt236-day-wrap" data-testid="gtvc3-future-day-strip">'
        '<div class="gt236-day-head"><b>📅 UPCOMING GAME DAYS</b><span>PHOENIX TIME • TODAY +</span></div></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(7, gap="small")
    for column, candidate in zip(columns, days):
        label = f"{candidate.strftime('%a • %b')} {candidate.day}"
        if candidate == selected:
            label = "✓ " + label
        with column:
            if st.button(
                label,
                key=f"gtvc3_day_{candidate.isoformat()}",
                type="primary" if candidate == selected else "secondary",
                use_container_width=True,
            ):
                day_owner._set_query_date(candidate)
                st.rerun()
    selected_label = f"{selected.strftime('%A, %B')} {selected.day}, {selected.year}".upper()
    st.markdown(
        f'<div class="gt236-selected">SELECTED • {escape(selected_label)} • PHX</div>',
        unsafe_allow_html=True,
    )
    return selected


def _team_snapshot_renderer(v27: Any):
    def render(identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
        away_id = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
        home_id = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}
        logo = v27.team_owner.presentation_owner._team_logo
        return build_overview_edge_html(identity, away, home) + build_team_snapshot_html(
            identity,
            away,
            home,
            away_logo_html=logo(away_id),
            home_logo_html=logo(home_id),
        )
    return render


def _install_fresh_page_hooks(page: Any, restores: list[tuple[Any, str, Any]]) -> None:
    v36 = getattr(page, "prior", None)
    if v36 is None or not hasattr(v36, "_future_day_strip_v36"):
        raise RuntimeError("Step-3 Phoenix day-strip owner unavailable")
    old_day = v36._future_day_strip_v36
    v36._future_day_strip_v36 = lambda: _today_day_strip(v36)
    restores.append((v36, "_future_day_strip_v36", old_day))

    v27 = importlib.import_module("cfb_game_total_clean_page_v27")
    if not hasattr(v27, "_team_evidence_html_v27"):
        raise RuntimeError("Step-3 Team Evidence owner unavailable")
    old_team = v27._team_evidence_html_v27
    v27._team_evidence_html_v27 = _team_snapshot_renderer(v27)
    restores.append((v27, "_team_evidence_html_v27", old_team))


def install_step3_overview() -> bool:
    """Install one exact-route post-purge wrapper; idempotent and presentation-only."""
    with _LOCK:
        root = importlib.import_module("streamlit_memory_lazy_router_v1")
        render_owner = importlib.import_module("streamlit_memory_lazy_router_v160")
        route_owner = importlib.import_module("streamlit_memory_lazy_router_v181")
        current = render_owner._render_exact_game_total_surface
        if getattr(current, _INSTALL_ATTR, False):
            return True
        original = current

        def repaired_render_exact_game_total_surface(*args: Any, **kwargs: Any):
            if not route_owner._game_total_route_active():
                return original(*args, **kwargs)
            original_import = root._import
            restores: list[tuple[Any, str, Any]] = []

            def import_with_step3(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    _install_fresh_page_hooks(page, restores)
                return page

            root._import = import_with_step3
            try:
                return original(*args, **kwargs)
            finally:
                root._import = original_import
                for owner, attr, value in reversed(restores):
                    setattr(owner, attr, value)

        setattr(repaired_render_exact_game_total_surface, _INSTALL_ATTR, True)
        setattr(repaired_render_exact_game_total_surface, "_cfb_gt_step3_original", original)
        render_owner._render_exact_game_total_surface = repaired_render_exact_game_total_surface
        return True


__all__ = [
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TARGET_PAGE",
    "install_step3_overview",
]
