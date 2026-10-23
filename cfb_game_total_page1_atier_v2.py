"""CFB Game Total Page 1 A-tier V2 — compact mobile-first Kyre market board."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_page1_api_bootstrap_repair_r1 as gateway
import cfb_game_total_page1_atier_v1 as base

MODEL_VERSION = "CFB GAME TOTAL PAGE1 A-TIER V2 • COMPACT MOBILE DECISION BOARD"
MARKET = "Game Total"
PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False

_CSS = r"""
<style>
.cfbgt2-shell{margin:2px 0 10px}.cfbgt2-eyebrow{font-size:.53rem;letter-spacing:.14em;font-weight:950;color:#68d9ff;text-transform:uppercase}.cfbgt2-title{font-size:1.55rem;line-height:1.02;font-weight:1000;color:#f7fbff;margin:4px 0}.cfbgt2-sub{font-size:.58rem;color:#8299aa;max-width:700px;line-height:1.45}.cfbgt2-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:10px 0 11px}.cfbgt2-summary>div{padding:8px 9px;border:1px solid rgba(91,181,224,.16);border-radius:11px;background:#071722}.cfbgt2-summary small{display:block;font-size:.27rem;letter-spacing:.08em;text-transform:uppercase;color:#6f8fa2;font-weight:950;white-space:nowrap}.cfbgt2-summary b{display:block;margin-top:3px;color:#e9f9ff;font-size:.57rem}.cfbgt2-summary .good b{color:#78e8bd}.cfbgt2-summary .warn b{color:#f0ca79}.cfbgt2-date{display:inline-flex;align-items:center;min-height:31px;border:1px solid rgba(95,190,233,.20);background:#081925;border-radius:10px;padding:0 10px;font-size:.38rem;font-weight:850;color:#b8d7e6;white-space:nowrap}.cfbgt2-board{padding:8px 10px;border:1px solid rgba(87,193,238,.20);border-radius:12px;background:linear-gradient(145deg,#071923,#081d2a);margin:8px 0 10px}.cfbgt2-board b{font-size:.40rem;color:#7ddfff;letter-spacing:.07em;text-transform:uppercase}.cfbgt2-board span{display:block;margin-top:3px;font-size:.34rem;color:#7897a8}.cfbgt2-search-label{font-size:.37rem;color:#86a3b4;font-weight:900;letter-spacing:.06em;text-transform:uppercase;margin:7px 0 5px}.cfbgt2-card{border:1px solid rgba(83,181,226,.27);border-radius:17px;background:radial-gradient(circle at 8% 0%,rgba(34,101,137,.15),transparent 38%),linear-gradient(145deg,#07141f,#081b27);margin:9px 0 11px;overflow:hidden;box-shadow:0 10px 26px rgba(0,0,0,.18)}.cfbgt2-head{display:grid;grid-template-columns:1fr auto;gap:9px;align-items:center;padding:10px 11px;border-bottom:1px solid rgba(112,159,187,.12)}.cfbgt2-match{display:flex;align-items:center;gap:8px;min-width:0}.cfbgt2-num{width:25px;height:25px;flex:0 0 25px;display:grid;place-items:center;border:1px solid rgba(77,202,255,.46);border-radius:50%;color:#83e2ff;font-size:.42rem;font-weight:1000}.cfbgt2-teams{min-width:0;font-size:.72rem;color:#f7fbff;font-weight:950;line-height:1.18;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt2-teams small{display:block;margin-top:2px;font-size:.31rem;color:#7d99a9;font-weight:750}.cfbgt2-badge{border:1px solid rgba(84,220,164,.34);background:rgba(13,82,61,.24);color:#7cebc0;border-radius:999px;padding:5px 7px;font-size:.27rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}.cfbgt2-badge.partial{border-color:rgba(229,185,87,.36);background:rgba(103,74,13,.22);color:#efd083}.cfbgt2-badge.empty{border-color:rgba(130,153,168,.25);background:rgba(61,74,83,.18);color:#9db3bf}.cfbgt2-marketrow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;padding:9px 9px 7px}.cfbgt2-cell{min-width:0;min-height:54px;padding:8px 8px 7px;border:1px solid rgba(111,161,190,.14);border-radius:11px;background:#081923}.cfbgt2-cell small{display:block;font-size:.24rem;letter-spacing:.065em;text-transform:uppercase;color:#6f8c9f;font-weight:950;white-space:nowrap}.cfbgt2-cell strong{display:block;margin-top:5px;font-size:.72rem;color:#f4fbff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt2-cell em{display:block;margin-top:2px;font-size:.25rem;font-style:normal;color:#7898a9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt2-total{background:linear-gradient(145deg,#0a2232,#0c2940);border-color:rgba(79,204,255,.34)}.cfbgt2-total strong{font-size:1.05rem;color:#7fe3ff}.cfbgt2-over strong{color:#83e9c1}.cfbgt2-under strong{color:#f0d18a}.cfbgt2-signal{margin:0 9px 7px;padding:8px 9px;border:1px solid rgba(92,181,222,.15);border-radius:11px;background:rgba(5,20,30,.72)}.cfbgt2-signal-top{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center}.cfbgt2-signal small{display:block;font-size:.24rem;letter-spacing:.07em;text-transform:uppercase;color:#6f8c9f;font-weight:950}.cfbgt2-signal strong{display:block;margin-top:3px;font-size:.55rem;color:#eaf8ff}.cfbgt2-lean{border:1px solid rgba(91,181,224,.22);border-radius:999px;padding:4px 7px;font-size:.27rem;font-weight:950;color:#82ddff;white-space:nowrap}.cfbgt2-lean.over{color:#78e8bd;border-color:rgba(120,232,189,.27)}.cfbgt2-lean.under{color:#f0ca79;border-color:rgba(240,202,121,.27)}.cfbgt2-lean.empty{color:#a9bac3;border-color:rgba(169,186,195,.20)}.cfbgt2-probbar{height:5px;border-radius:999px;background:rgba(240,202,121,.28);overflow:hidden;margin:7px 0 5px}.cfbgt2-probfill{height:100%;border-radius:999px;background:linear-gradient(90deg,#48cfa2,#78e8bd)}.cfbgt2-read{font-size:.32rem;color:#91aebd;line-height:1.35}.cfbgt2-read b{color:#cbe8f4}.cfbgt2-foot{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;padding:0 9px 9px}.cfbgt2-proof{min-width:0;font-size:.28rem;color:#6f8f9f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt2-proof b{color:#aed6e5}.cfbgt2-open{display:inline-flex;align-items:center;justify-content:center;min-width:112px;min-height:29px;padding:0 10px;border:1px solid rgba(72,201,255,.46);border-radius:999px;background:#082639;color:#83e3ff!important;text-decoration:none!important;font-size:.29rem;font-weight:1000;letter-spacing:.055em;white-space:nowrap}.cfbgt2-empty{padding:15px;border:1px solid rgba(130,153,168,.22);border-radius:14px;background:#0a151c;color:#aec1cb;font-size:.45rem}
@media(max-width:620px){.cfbgt2-shell{margin-top:0}.cfbgt2-title{font-size:1.31rem}.cfbgt2-sub{font-size:.53rem}.cfbgt2-summary{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.cfbgt2-summary>div{padding:7px 6px}.cfbgt2-summary small{font-size:.23rem}.cfbgt2-summary b{font-size:.51rem}.cfbgt2-date{width:100%;box-sizing:border-box}.cfbgt2-head{padding:9px}.cfbgt2-teams{font-size:.67rem}.cfbgt2-badge{font-size:.23rem;padding:4px 6px}.cfbgt2-marketrow{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:7px}.cfbgt2-cell{min-height:49px;padding:7px 6px}.cfbgt2-cell small{font-size:.20rem}.cfbgt2-cell strong{font-size:.65rem}.cfbgt2-total strong{font-size:.91rem}.cfbgt2-cell em{font-size:.21rem}.cfbgt2-signal{margin:0 7px 6px;padding:7px}.cfbgt2-signal strong{font-size:.49rem}.cfbgt2-read{font-size:.29rem}.cfbgt2-foot{grid-template-columns:1fr auto;padding:0 7px 7px}.cfbgt2-proof{font-size:.23rem}.cfbgt2-open{min-width:101px;min-height:27px;font-size:.25rem;padding:0 8px}}
@media(max-width:370px){.cfbgt2-badge{display:none}.cfbgt2-head{grid-template-columns:1fr}.cfbgt2-cell small{font-size:.18rem}.cfbgt2-cell strong{font-size:.60rem}.cfbgt2-total strong{font-size:.84rem}.cfbgt2-foot{grid-template-columns:1fr}.cfbgt2-open{width:100%;box-sizing:border-box}.cfbgt2-proof{white-space:normal}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _prob_width(over: float | None) -> str:
    if over is None:
        return "50%"
    pct = max(0.0, min(100.0, over * 100.0))
    return f"{pct:.1f}%"


def _render_card(game: Mapping[str, Any], index: int, selected_day) -> None:
    quote = base._quote(game)
    total_value = quote.get("total_line")
    has_total = total_value is not None and total_value != ""
    over, under = base._no_vig_probabilities(quote.get("over_price"), quote.get("under_price"))
    read_title, read_body, read_class = base._market_read(over, under, has_total=has_total)
    book = _clean(quote.get("sportsbook")) or "Kyre Sports API verified market"
    observed = _clean(quote.get("observed_at_utc")) or "Freshness pending"
    integrity = _clean(game.get("market_integrity")) or "PENDING"
    badge, badge_class = base._badge(integrity)
    href = base._game_href(game, selected_day)
    link = (
        f'<a class="cfbgt2-open" href="{escape(href, quote=True)}" target="_self">OPEN ANALYSIS →</a>'
        if href else '<span class="cfbgt2-open">ANALYSIS PENDING</span>'
    )
    no_vig = "Pending" if over is None or under is None else f"O {base._pct(over)} • U {base._pct(under)}"
    lean_label = read_title.replace(" MARKET", "").replace("PRICE DATA ", "").strip()
    st.markdown(
        '<div class="cfbgt2-card">'
        '<div class="cfbgt2-head">'
        f'<div class="cfbgt2-match"><span class="cfbgt2-num">{index}</span><div class="cfbgt2-teams">{escape(base._name(game,"away"))} <span style="color:#66889a">@</span> {escape(base._name(game,"home"))}<small>{escape(base._kickoff(game))}</small></div></div>'
        f'<span class="cfbgt2-badge{badge_class}">{escape(badge)}</span>'
        '</div>'
        '<div class="cfbgt2-marketrow">'
        f'<div class="cfbgt2-cell cfbgt2-total"><small>MARKET TOTAL</small><strong>{escape(base._line(total_value))}</strong><em>{escape(book)}</em></div>'
        f'<div class="cfbgt2-cell cfbgt2-over"><small>OVER PRICE</small><strong>{escape(base._american(quote.get("over_price")))}</strong><em>Current price</em></div>'
        f'<div class="cfbgt2-cell cfbgt2-under"><small>UNDER PRICE</small><strong>{escape(base._american(quote.get("under_price")))}</strong><em>Current price</em></div>'
        '</div>'
        '<div class="cfbgt2-signal">'
        '<div class="cfbgt2-signal-top">'
        f'<div><small>NO-VIG MARKET</small><strong>{escape(no_vig)}</strong></div>'
        f'<span class="cfbgt2-lean {escape(read_class)}">{escape(lean_label)}</span>'
        '</div>'
        f'<div class="cfbgt2-probbar"><div class="cfbgt2-probfill" style="width:{escape(_prob_width(over), quote=True)}"></div></div>'
        f'<div class="cfbgt2-read"><b>MARKET READ</b> • {escape(read_body)}</div>'
        '</div>'
        f'<div class="cfbgt2-foot"><div class="cfbgt2-proof"><b>{escape(integrity)}</b> • {escape(book)} • {escape(observed)}</div>{link}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_game_total_page1() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    requested = base._requested_date()
    try:
        payload = base._load_payload(requested)
    except Exception as exc:
        st.error(f"Kyre Sports API could not load the Game Total board: {type(exc).__name__}")
        return

    selected_day = base._selected_date(payload)
    games = [row for row in payload.get("games") or [] if isinstance(row, Mapping)]
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    generated = _clean(payload.get("generated_at_utc")) or "Freshness pending"
    verified = int(summary.get("verified_market_games") or 0)
    pending = int(summary.get("market_unavailable_games") or 0)

    st.markdown(
        '<div class="cfbgt2-shell"><div class="cfbgt2-eyebrow">KYRE SPORTS AI • CFB GAME TOTALS</div>'
        '<div class="cfbgt2-title">Game Total Intelligence</div>'
        '<div class="cfbgt2-sub">Fast market decisions up front. Deep matchup research remains one tap away.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cfbgt2-summary">'
        f'<div><small>GAMES</small><b>{len(games)}</b></div>'
        f'<div class="good"><small>VERIFIED</small><b>{verified}</b></div>'
        f'<div class="{("good" if pending == 0 else "warn")}"><small>PENDING</small><b>{pending}</b></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="cfbgt2-date">📅 {escape(selected_day.strftime("%A • %B %d, %Y"))} • Phoenix</div>', unsafe_allow_html=True)
    picked = st.date_input("Slate date", value=selected_day, key="cfbgt2_date", label_visibility="collapsed")
    if picked != selected_day:
        st.query_params["date"] = picked.isoformat()
        st.query_params["ks_cfb_game_total_date"] = picked.isoformat()
        st.rerun()

    st.markdown(
        '<div class="cfbgt2-board"><b>GAME TOTAL DECISION BOARD</b>'
        f'<span>{len(games)} games • refreshed {escape(generated)} • normalized by Kyre Sports API</span></div>',
        unsafe_allow_html=True,
    )

    if not games:
        st.markdown('<div class="cfbgt2-empty">No qualifying pregame CFB games are currently available for this slate through Kyre Sports API.</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="cfbgt2-search-label">Search matchup</div>', unsafe_allow_html=True)
    search = st.text_input("Search matchup", placeholder="Search team", key="cfbgt2_search", label_visibility="collapsed")
    needle = _clean(search).casefold()
    visible = [game for game in games if not needle or needle in (base._name(game,"away") + " " + base._name(game,"home")).casefold()]
    for index, game in enumerate(visible, start=1):
        _render_card(game, index, selected_day)


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total A-tier V2 cannot render market={market!r}")
    render_game_total_page1()


__all__ = [
    "MARKET",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_page1",
]
