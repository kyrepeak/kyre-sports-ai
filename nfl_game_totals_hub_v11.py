"""NFL Game Totals V11 — preserve S-tier Page 1 and add selected-game Page 2.

This is a presentation/routing successor only. The frozen Page 1 decision model,
V8 projection, V9 market comparison, and V10 certification owners remain the
analytics authorities. Sportsbook data remains comparison-only and contributes
0.0% to projection math.
"""
from __future__ import annotations

from html import escape
from urllib.parse import quote
from typing import Any

import pandas as pd
import streamlit as st

import nfl_game_totals_page1_s_tier_v1 as page1
import nfl_game_totals_hub_v10 as v10

v9 = v10.v9
foundation = page1.foundation
mobile = page1.mobile

MODEL_VERSION = "NFL GAME TOTALS V11 • S-TIER PAGE1 • SELECTED GAME PAGE2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
PRESENTATION_ONLY = True
PAGE1_OWNER = "nfl_game_totals_page1_s_tier_v1"
PAGE2_ANALYTICS_OWNER = "nfl_game_totals_hub_v10+nfl_game_totals_hub_v9"

_LINK_CSS = r'''
<style data-api2-nfl-game-total-page2-route-v1="true">
.kgt-s1-details a{display:block;text-align:center;padding:8px;color:#dcebf3;font-weight:900;font-size:.60rem;text-decoration:none}
.kgt-s1-details a:hover{background:#0b2230;color:#8fdfff}
.kgt-p2{max-width:980px;margin:0 auto;color:#edf5fa}.kgt-p2 *{box-sizing:border-box}
.kgt-p2-back{display:inline-block;margin:2px 0 10px;color:#8fdfff;text-decoration:none;font-size:.62rem;font-weight:900}
.kgt-p2-hero{border:1px solid #285b76;border-radius:18px;background:linear-gradient(155deg,#081a26,#07121a);padding:14px;margin:2px 0 10px;box-shadow:0 12px 28px rgba(0,0,0,.2)}
.kgt-p2-kicker{color:#58c9ff;font-size:.48rem;font-weight:950;letter-spacing:.09em}.kgt-p2-title{margin-top:4px;font-size:1.18rem;font-weight:950}.kgt-p2-sub{margin-top:4px;color:#8ca5b5;font-size:.58rem;line-height:1.45}
.kgt-p2-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:9px}.kgt-p2-stat{border:1px solid #24495d;border-radius:10px;background:#07151d;padding:8px}.kgt-p2-stat span{display:block;color:#7895a7;font-size:.42rem;font-weight:950;letter-spacing:.07em}.kgt-p2-stat b{display:block;margin-top:3px;font-size:.82rem;color:#edf5fa}.kgt-p2-lock{margin:9px 0 2px;border:1px solid #28644f;border-radius:10px;padding:8px 9px;background:#081913;color:#8fe8c4;font-size:.50rem;line-height:1.4}
@media(max-width:760px){.kgt-s1-details a{padding:7px}.kgt-p2-hero{padding:11px;border-radius:16px}.kgt-p2-title{font-size:1rem}.kgt-p2-strip{grid-template-columns:1fr 1fr}.kgt-p2-stat{padding:7px}}
</style>
'''


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        value = ""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()


def _game_id(row: Any) -> str:
    try:
        value = row.get("game_id")
    except Exception:
        value = None
    return str(value or "").strip()


def _analysis_href(row: Any, day_str: str) -> str:
    gid = _game_id(row)
    return (
        "?sport=nfl&market=game-total&view=analysis&game="
        + quote(gid, safe="")
        + "&date="
        + quote(day_str, safe="")
    )


def _back_href(day_str: str) -> str:
    return "?sport=nfl&market=game-total&date=" + quote(day_str, safe="")


def _with_page2_handoff(item: dict[str, Any], day_str: str) -> str:
    """Keep the frozen Page 1 card intact through the final handoff seam."""
    frozen = page1.build_decision_card_html(
        item["row"], item["snapshot"], item["scoring"], item["pace"],
        item["explosive"], item["red_zone"], item["environment"],
        item["projection"], item["read"],
    )
    marker = '<summary>VIEW FULL ANALYSIS →</summary>'
    if marker not in frozen:
        return frozen
    before, _unused = frozen.split(marker, 1)
    opening_control = before.rfind("<")
    if opening_control < 0:
        return frozen
    before = before[:opening_control]
    href = _analysis_href(item["row"], day_str)
    return (
        before
        + f'<div class="kgt-s1-details" data-testid="nfl-game-total-page2-link"><a href="{escape(href)}" target="_self">VIEW FULL ANALYSIS →</a></div>'
        + "</article>"
    )


def _initial_day() -> pd.Timestamp:
    requested = _query_value("date")
    if requested:
        try:
            return pd.Timestamp(pd.to_datetime(requested).date())
        except Exception:
            pass
    today = pd.Timestamp.now(tz=foundation.ET).date()
    return pd.Timestamp(mobile._initial_date(today))


def _page1() -> None:
    st.markdown(page1._CSS + _LINK_CSS, unsafe_allow_html=True)
    today = pd.Timestamp.now(tz=foundation.ET).date()
    mobile._apply_pending_date(today)
    selected = _initial_day().date()
    selected = mobile._auto_surface_next_slate(selected, today)

    c1, c2, c3 = st.columns([3.2, .6, .6])
    with c1:
        selected = st.date_input(
            "NFL Game Totals date", value=selected,
            key=mobile._WIDGET_DATE_KEY, label_visibility="collapsed",
        )
    selected = mobile._as_date(selected, today)
    mobile._sync_game_totals_date(selected)
    with c2:
        if st.button("→", key="kgt_v11_next", use_container_width=True):
            mobile._queue_next_game_day(selected)
    with c3:
        if st.button("↻", key="kgt_v11_reload", use_container_width=True):
            mobile._reload_game_totals_data()

    day_str = selected.isoformat()
    with st.spinner("Loading verified NFL Game Totals…"):
        games, diag = foundation.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or diag.get("request_ok") is not True:
        st.error("Verified NFL slate unavailable. No games were fabricated.")
        return
    if games.empty:
        st.markdown(
            f'<div class="kgt-s1"><div class="kgt-s1-head"><div><div class="kgt-s1-title">NFL GAME TOTALS</div><div class="kgt-s1-sub">{escape(day_str)} · No upcoming verified games</div></div></div></div>',
            unsafe_allow_html=True,
        )
        st.info("No verified NFL games were returned for this date. Use → for the next game day.")
        return

    mode = st.radio(
        "Sort", ["GAME TIME", "BEST EDGES"], horizontal=True,
        label_visibility="collapsed", key="kgt_v11_sort",
    )
    items = page1._collect(games, day_str)
    if mode == "BEST EDGES":
        items.sort(key=lambda item: abs(float(item["model"].get("edge") or 0.0)), reverse=True)
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum())
    st.markdown(
        f'<div class="kgt-s1"><div class="kgt-s1-head"><div><div class="kgt-s1-title">NFL GAME TOTALS</div><div class="kgt-s1-sub">{escape(day_str)} · {upcoming} Upcoming · {len(games)} verified game{"s" if len(games) != 1 else ""}</div></div></div></div>',
        unsafe_allow_html=True,
    )
    cards = "".join(_with_page2_handoff(item, day_str) for item in items)
    st.markdown(f'<div class="kgt-s1">{cards}</div>', unsafe_allow_html=True)


def _page2_css() -> str:
    return (
        v9.v8.v7.v6.v5.v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v9.v8.v7.v6.v5.v4.v3.v2._STEP2_CSS
        + v9.v8.v7.v6.v5.v4.v3._STEP3_CSS
        + v9.v8.v7.v6.v5.v4._STEP4_CSS
        + v9.v8.v7.v6.v5._STEP5_CSS
        + v9.v8.v7.v6._STEP6_CSS
        + v9.v8.v7._STEP7_CSS
        + v9.v8._STEP8_CSS
        + v9._STEP9_CSS
        + v10._STEP10_CSS
        + _LINK_CSS
    )


def _page2(game_id: str) -> None:
    requested_day = _query_value("date")
    if requested_day:
        try:
            selected = pd.to_datetime(requested_day).date()
        except Exception:
            selected = _initial_day().date()
    else:
        selected = _initial_day().date()
    mobile._sync_game_totals_date(selected)
    day_str = selected.isoformat()

    with st.spinner("Building selected-game NFL Game Totals analysis…"):
        games, diag = foundation.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or diag.get("request_ok") is not True:
        st.markdown(f'<a class="kgt-p2-back" href="{escape(_back_href(day_str))}" target="_self">← Back to Game Totals</a>', unsafe_allow_html=True)
        st.error("Verified NFL slate unavailable. No game was fabricated.")
        return

    selected_rows = games[games.get("game_id", pd.Series(dtype=str)).astype(str) == str(game_id)] if not games.empty else games
    if selected_rows.empty:
        st.markdown(_LINK_CSS + f'<div class="kgt-p2"><a class="kgt-p2-back" href="{escape(_back_href(day_str))}" target="_self">← Back to Game Totals</a></div>', unsafe_allow_html=True)
        st.warning("Selected matchup is not available on the verified slate. Return to Game Totals and choose an upcoming game.")
        return

    one_game = selected_rows.iloc[[0]].copy()
    item = page1._collect(one_game, day_str)[0]
    row = item["row"]
    model = item["model"]
    away = page1._text(row.get("away_team"), "Away")
    home = page1._text(row.get("home_team"), "Home")
    edge = model.get("edge")
    edge_text = f"{float(edge):+.1f}" if edge is not None else "—"

    st.markdown(
        _page2_css()
        + '<div class="kgt-p2">'
        + f'<a class="kgt-p2-back" href="{escape(_back_href(day_str))}" target="_self">← Back to Game Totals</a>'
        + '<section class="kgt-p2-hero">'
        + '<div class="kgt-p2-kicker">NFL GAME TOTALS • FULL ANALYSIS</div>'
        + f'<div class="kgt-p2-title">{escape(away)} @ {escape(home)}</div>'
        + f'<div class="kgt-p2-sub">{escape(day_str)} · selected-game analysis only · existing V8/V9/V10 analytics owners preserved</div>'
        + '<div class="kgt-p2-strip">'
        + f'<div class="kgt-p2-stat"><span>MARKET TOTAL</span><b>{page1._fmt(model.get("market_total"))}</b></div>'
        + f'<div class="kgt-p2-stat"><span>KYRE TOTAL</span><b>{page1._fmt(model.get("kyre_total"))}</b></div>'
        + f'<div class="kgt-p2-stat"><span>EDGE</span><b>{escape(edge_text)}</b></div>'
        + f'<div class="kgt-p2-stat"><span>FINAL READ</span><b>{escape(page1._text(model.get("lean"), "WAIT"))}</b></div>'
        + '</div>'
        + '<div class="kgt-p2-lock">Projection remains sportsbook-free • sportsbook projection influence 0.0% • stake sizing OFF • wager actions OFF.</div>'
        + '</section></div>',
        unsafe_allow_html=True,
    )

    full_card = v9._game_card(
        row,
        item["snapshot"], item["scoring"], item["pace"], item["explosive"],
        item["red_zone"], item["environment"], item["projection"], item["read"],
    )
    st.markdown(f'<div class="kgt-page"><div class="kgt-grid">{full_card}</div></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-cert"><b>✅ SELECTED-GAME ANALYSIS CERTIFIED</b><span>Verified slate + live total + offense/defense + pace + explosive scoring + red-zone/drive sustainability + environment + sportsbook-free projection + comparison-only market read. No wager execution enabled.</span></div>',
        unsafe_allow_html=True,
    )


def render_nfl_game_totals_hub() -> None:
    view = _query_value("view").lower()
    game_id = _query_value("game")
    if view == "analysis":
        return _page2(game_id)
    return _page1()


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total").strip().lower().replace(" ", "-") not in {"game-total", "game-totals"}:
        raise ValueError("NFL Game Totals V11 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED", "PRESENTATION_ONLY", "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
