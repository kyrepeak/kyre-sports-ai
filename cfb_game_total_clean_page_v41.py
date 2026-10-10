"""CFB Game Total clean page V41 — Phoenix-time day selector Step 4.

Additive successor to frozen V40. This layer keeps the exact native Page-1
website shell and frozen analytics while rebuilding only the visible GAME DAY
selector. Day ownership is explicitly America/Phoenix, selection persists in
the existing Game Total date query key, and the legacy V161 day strip is
suppressed for this render so Page 1 has one authoritative selector.

Step 4 deliberately does not load or rebuild games for the selected day; that
belongs to Step 5. Model, projection, probability, sportsbook influence,
schedule/provider behavior, event identity, other sports, and Page 2 remain
unchanged.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_game_total_clean_page_v11 as legacy_day
import cfb_game_total_clean_page_v40 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V41 • PHOENIX DAY SELECTOR STEP 4"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v40"
ACTIVE_MARKER = "CFB GAME TOTAL • PHOENIX DAY SELECTOR STEP 4 ACTIVE"
PHOENIX_DAY_MARKER = "CFB_GAME_TOTAL_PHOENIX_DAY_SELECTOR_STEP4_ACTIVE"
PHOENIX_TZ = ZoneInfo("America/Phoenix")
DATE_QUERY_KEY = legacy_day.DATE_QUERY_KEY
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
NETWORK_CALLS_ADDED = 0
SELECTOR_OWNS_GAME_LOADING = False

_DAY_LOCK = RLock()

PHOENIX_DAY_CSS = r"""
<style>
.gt241-wrap{position:relative;overflow:hidden;margin:-5px auto 18px;padding:14px 16px 13px;border:1px solid rgba(88,194,238,.25);border-radius:18px;background:linear-gradient(145deg,rgba(7,25,39,.96),rgba(5,16,27,.98));box-shadow:0 14px 34px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.025)}
.gt241-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 1px 10px}.gt241-title{display:flex;align-items:center;gap:9px;color:#f3faff;font-size:11px;font-weight:1000;letter-spacing:.11em;text-transform:uppercase}.gt241-calendar{display:grid;place-items:center;width:25px;height:25px;border:1px solid rgba(98,211,255,.38);border-radius:8px;background:rgba(24,115,154,.15);font-size:13px}.gt241-zone{display:flex;align-items:center;gap:7px;color:#7794a9;font-size:8px;font-weight:900;letter-spacing:.095em;text-transform:uppercase}.gt241-live{width:6px;height:6px;border-radius:50%;background:#45f0ad;box-shadow:0 0 10px rgba(69,240,173,.62)}
.gt241-help{margin:0 1px 9px;color:#7892a6;font-size:9px;font-weight:700}.gt241-selected{margin-top:9px;text-align:center;color:#6fe3ff;font-size:9px;font-weight:1000;letter-spacing:.075em;text-transform:uppercase}.gt241-selected strong{color:#f5fbff}.gt241-identity{display:none!important}
div[data-testid="stHorizontalBlock"] button[kind="secondary"]{min-height:42px!important;padding:4px 3px!important;border:1px solid rgba(79,153,194,.30)!important;border-radius:10px!important;background:linear-gradient(180deg,#081c2b,#071622)!important;color:#a9c0d1!important;font-size:9px!important;font-weight:900!important;box-shadow:none!important}
div[data-testid="stHorizontalBlock"] button[kind="primary"]{min-height:42px!important;padding:4px 3px!important;border:1px solid rgba(91,214,255,.70)!important;border-radius:10px!important;background:linear-gradient(145deg,rgba(19,106,146,.72),rgba(7,38,56,.98))!important;color:#f8fdff!important;font-size:9px!important;font-weight:1000!important;box-shadow:0 0 16px rgba(62,190,242,.13)!important}
@media(max-width:760px){.gt241-wrap{margin:-3px auto 14px;padding:11px 10px 10px;border-radius:15px}.gt241-zone{font-size:7px}.gt241-help{font-size:8px}.gt241-head{margin-bottom:8px}div[data-testid="stHorizontalBlock"]{gap:3px!important}div[data-testid="stHorizontalBlock"] button[kind="secondary"],div[data-testid="stHorizontalBlock"] button[kind="primary"]{min-height:38px!important;padding:3px 1px!important;font-size:8px!important;border-radius:8px!important}}
</style>
"""


def _query_date_value() -> str:
    try:
        raw: Any = st.query_params.get(DATE_QUERY_KEY)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _phoenix_today() -> date:
    return datetime.now(PHOENIX_TZ).date()


def _selected_day() -> date:
    raw = _query_date_value()
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now(PHOENIX_TZ).date()


def _set_query_date(selected: date) -> None:
    st.query_params[DATE_QUERY_KEY] = selected.isoformat()


def _day_window(selected: date) -> list[date]:
    start = selected - timedelta(days=2)
    return [start + timedelta(days=index) for index in range(7)]


def _selector_header_html() -> str:
    return (
        '<section class="gt241-wrap" data-testid="gt241-phoenix-day-selector" '
        f'data-step4-marker="{PHOENIX_DAY_MARKER}">'
        '<div class="gt241-head">'
        '<div class="gt241-title"><span class="gt241-calendar">📅</span>Game Day</div>'
        '<div class="gt241-zone"><span class="gt241-live"></span>PHOENIX TIME • MST</div>'
        '</div>'
        '<div class="gt241-help">Choose a date — this becomes the one authoritative day for the Game Total slate.</div>'
        '</section>'
    )


def _render_phoenix_day_selector() -> date:
    selected = _selected_day()
    today = _phoenix_today()
    st.markdown(PHOENIX_DAY_CSS, unsafe_allow_html=True)
    st.markdown(_selector_header_html(), unsafe_allow_html=True)

    columns = st.columns(7, gap="small")
    for column, candidate in zip(columns, _day_window(selected)):
        weekday = candidate.strftime("%a").upper()
        label = f"{weekday}\n{candidate.strftime('%b').upper()} {candidate.day}"
        if candidate == today:
            label = f"TODAY\n{candidate.strftime('%b').upper()} {candidate.day}"
        if candidate == selected:
            label = "✓ " + label
        with column:
            if st.button(
                label,
                key=f"gt241_phx_day_{candidate.isoformat()}",
                type="primary" if candidate == selected else "secondary",
                use_container_width=True,
            ):
                _set_query_date(candidate)
                st.rerun()

    selected_label = selected.strftime("%A, %B %d, %Y").replace(" 0", " ")
    st.markdown(
        '<div class="gt241-selected">SELECTED IN PHOENIX • '
        f'<strong>{escape(selected_label)}</strong></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="gt241-identity" data-testid="cfb-game-total-phoenix-day-step4-active">'
        f'{ACTIVE_MARKER} • America/Phoenix • game loading deferred to Step 5</div>',
        unsafe_allow_html=True,
    )
    return selected


def _legacy_day_strip_passthrough() -> date:
    """Feed the selected Phoenix day into the frozen body without re-rendering V161."""
    return _selected_day()


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Render frozen V40 shell, one Phoenix selector, then the unchanged V39 body."""
    with _DAY_LOCK:
        original_day_strip = legacy_day._render_day_strip
        legacy_day._render_day_strip = _legacy_day_strip_passthrough
        try:
            st.markdown(prior.PAGE1_SHELL_CSS, unsafe_allow_html=True)
            st.markdown(prior._page1_shell_html(), unsafe_allow_html=True)
            _render_phoenix_day_selector()
            return prior.prior.render_game_total_hub(
                section_header,
                status_info,
                team_logo,
                h,
            )
        finally:
            legacy_day._render_day_strip = original_day_strip


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V41 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "DATE_QUERY_KEY",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PHOENIX_DAY_CSS",
    "PHOENIX_DAY_MARKER",
    "PHOENIX_TZ",
    "SELECTOR_OWNS_GAME_LOADING",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_day_window",
    "_phoenix_today",
    "_render_phoenix_day_selector",
    "_selected_day",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
