"""CFB Game Total clean page V36 — Page 1 V2 Step 3 matchup hero + Phoenix time.

Additive presentation successor to frozen V35. It temporarily replaces only the
V11 day-strip, V14 selector-time, and V25 matchup-hero seams while delegating all
multi-source display data and frozen analytics to V35.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from threading import RLock
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_game_total_clean_page_v11 as day_owner
import cfb_game_total_clean_page_v14 as selector_owner
import cfb_game_total_clean_page_v25 as hero_owner
import cfb_game_total_clean_page_v35 as prior
import cfb_game_total_page1_step3_presentation_v1 as presentation

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V36 • PAGE1 V2 STEP3 MATCHUP HERO PHOENIX"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v35"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE1 V2 STEP3 MATCHUP HERO PHOENIX ACTIVE"
STEP3_MARKER = "CFB_GAME_TOTAL_PAGE1_V2_STEP3_MATCHUP_HERO_PHX_ACTIVE"

_LOCK = RLock()

STEP3_CSS = r"""
<style>
.gt236-hero{position:relative;overflow:hidden;margin:0 auto 10px;border:1px solid rgba(84,207,255,.55);border-radius:24px;background:radial-gradient(circle at 50% 5%,rgba(53,177,255,.20),transparent 32%),radial-gradient(circle at 12% 18%,rgba(31,230,213,.11),transparent 28%),linear-gradient(180deg,#071827 0%,#06121d 58%,#050c14 100%);box-shadow:0 18px 44px rgba(0,0,0,.32),0 0 34px rgba(64,190,255,.08);color:#f8fcff}
.gt236-glow{position:absolute;inset:0;pointer-events:none;opacity:.30;background:linear-gradient(90deg,transparent 49.8%,rgba(99,190,227,.20) 50%,transparent 50.2%),repeating-linear-gradient(90deg,transparent 0 12.3%,rgba(76,168,203,.055) 12.4% 12.55%);mask-image:linear-gradient(to bottom,transparent 0,black 17%,black 66%,transparent 88%)}
.gt236-topline{position:relative;z-index:1;padding:16px 20px 8px;text-align:center;color:#91b8d2;font-size:11px;font-weight:950;letter-spacing:.11em;text-transform:uppercase}
.gt236-stage{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1fr) 68px minmax(0,1fr);align-items:center;gap:16px;padding:14px 34px 26px;min-height:154px}
.gt236-team{display:flex;align-items:center;gap:18px;min-width:0}.gt236-team.home{justify-content:flex-end;text-align:right}.gt236-logo{width:96px;height:96px;flex:0 0 96px;display:grid;place-items:center;border-radius:26px;background:radial-gradient(circle,rgba(255,255,255,.07),transparent 68%)}
.gt236-logo img,.gt236-logo .gt159-logo,.gt236-logo .gt159-logo-fallback{width:88px!important;height:88px!important;max-width:88px!important;object-fit:contain;filter:drop-shadow(0 10px 18px rgba(0,0,0,.38))}
.gt236-copy{min-width:0}.gt236-copy strong{display:block;color:#fff;font-size:25px;line-height:1.04;font-weight:1000;letter-spacing:-.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt236-copy span{display:block;margin-top:7px;color:#94adbf;font-size:12px;font-weight:800}.gt236-copy em{display:inline-flex;margin-top:8px;padding:4px 11px;border:1px solid rgba(72,198,240,.35);border-radius:999px;background:rgba(25,111,154,.18);color:#67d7ff;font-style:normal;font-size:9px;font-weight:950;text-transform:uppercase}
.gt236-vs{width:54px;height:54px;margin:auto;display:grid;place-items:center;border:1px solid rgba(88,198,238,.45);border-radius:50%;background:#0a2434;color:#bcd4e4;font-size:10px;font-weight:1000;letter-spacing:.10em;box-shadow:0 0 0 7px rgba(4,15,24,.38),0 0 25px rgba(65,192,235,.12)}
.gt236-facts{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid rgba(83,165,199,.25);background:rgba(2,10,17,.55)}.gt236-facts>div{min-width:0;display:grid;grid-template-columns:25px minmax(0,1fr);grid-template-rows:auto auto;column-gap:8px;align-content:center;min-height:76px;padding:12px 15px;border-right:1px solid rgba(76,146,179,.17)}.gt236-facts>div:last-child{border-right:0}.gt236-facts i{grid-row:1/span 2;align-self:center;color:#64caff;font-style:normal;font-size:17px}.gt236-facts b{color:#f4f9fd;font-size:11px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt236-facts span{margin-top:4px;color:#8099ad;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt236-tabs{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:0 auto 16px;padding:5px;border:1px solid rgba(76,170,211,.24);border-radius:14px;background:#07141e}.gt236-tab{display:grid;place-items:center;min-height:42px;border-radius:10px;color:#8ca5b8;font-size:11px;font-weight:950;letter-spacing:.04em}.gt236-tab.active{background:linear-gradient(135deg,#16bfd8,#2388ff);color:white;box-shadow:0 7px 20px rgba(34,149,255,.20)}.gt236-tab.disabled{background:#091a26;color:#688092}
.gt236-day-wrap{max-width:900px;margin:0 auto 10px;padding:9px 10px 7px;border:1px solid rgba(65,157,194,.30);border-radius:13px;background:linear-gradient(120deg,rgba(5,24,35,.98),rgba(7,17,31,.98));box-sizing:border-box}.gt236-day-head{display:flex;align-items:center;justify-content:space-between;gap:12px;color:#edf7ff}.gt236-day-head b{font-size:11px;letter-spacing:.10em}.gt236-day-head span{font-size:9px;color:#58c9ff}.gt236-selected{margin:-2px auto 9px;text-align:center;color:#45f0ad;font-size:9px;font-weight:950;letter-spacing:.065em}
@media(max-width:760px){.gt236-hero{border-radius:18px}.gt236-topline{padding:12px 10px 5px;font-size:9px}.gt236-stage{grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);gap:7px;padding:10px 10px 18px;min-height:116px}.gt236-team{gap:7px}.gt236-logo{width:54px;height:54px;flex-basis:54px}.gt236-logo img,.gt236-logo .gt159-logo,.gt236-logo .gt159-logo-fallback{width:50px!important;height:50px!important;max-width:50px!important}.gt236-copy strong{font-size:16px}.gt236-copy span{font-size:9px;margin-top:4px}.gt236-copy em{font-size:7px;padding:3px 7px;margin-top:5px}.gt236-vs{width:34px;height:34px;font-size:8px;box-shadow:0 0 0 4px rgba(4,15,24,.34)}.gt236-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.gt236-facts>div{min-height:60px;padding:9px 8px}.gt236-facts>div:nth-child(2){border-right:0}.gt236-facts>div:nth-child(-n+2){border-bottom:1px solid rgba(76,146,179,.17)}.gt236-tabs{margin-bottom:11px}.gt236-tab{min-height:38px;font-size:10px}}
</style>
"""


def _query_raw_date() -> str:
    try:
        raw = st.query_params.get(day_owner.DATE_QUERY_KEY)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _future_day_strip_v36():
    now = datetime.now(ZoneInfo(presentation.PHOENIX_TZ))
    selected = presentation.normalized_future_selected_date(_query_raw_date(), now=now)
    if _query_raw_date() != selected.isoformat():
        day_owner._set_query_date(selected)

    st.markdown(
        '<div class="gt236-day-wrap" data-testid="gt236-future-day-strip">'
        '<div class="gt236-day-head"><b>📅 UPCOMING GAME DAYS</b><span>PHOENIX TIME • TOMORROW +</span></div></div>',
        unsafe_allow_html=True,
    )
    days = presentation.future_day_window(selected, now=now, count=7)
    columns = st.columns(7, gap="small")
    for column, candidate in zip(columns, days):
        label = f"{candidate.strftime('%a • %b')} {candidate.day}"
        if candidate == selected:
            label = "✓ " + label
        with column:
            if st.button(
                label,
                key=f"gt236_day_{candidate.isoformat()}",
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


def _kickoff_text_v36(game: Mapping[str, Any]) -> str:
    return presentation.phoenix_kickoff_text(game)


def _matchup_header_html_v36(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
) -> str:
    away_id = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
    home_id = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}
    return presentation.build_matchup_hero_html(
        identity,
        away,
        home,
        display_game,
        away_logo_html=hero_owner._logo(away_id),
        home_logo_html=hero_owner._logo(home_id),
    )


def _render_with_step3_presentation(callback, *args, **kwargs):
    with _LOCK:
        old_day = day_owner._render_day_strip
        old_kickoff = selector_owner._kickoff_text
        old_hero = hero_owner._matchup_header_html_v25
        day_owner._render_day_strip = _future_day_strip_v36
        selector_owner._kickoff_text = _kickoff_text_v36
        hero_owner._matchup_header_html_v25 = _matchup_header_html_v36
        try:
            return callback(*args, **kwargs)
        finally:
            day_owner._render_day_strip = old_day
            selector_owner._kickoff_text = old_kickoff
            hero_owner._matchup_header_html_v25 = old_hero


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP3_CSS, unsafe_allow_html=True)
    result = _render_with_step3_presentation(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP3_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page V36 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_CSS",
    "STEP3_MARKER",
    "_future_day_strip_v36",
    "_kickoff_text_v36",
    "_matchup_header_html_v36",
    "_render_with_step3_presentation",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
