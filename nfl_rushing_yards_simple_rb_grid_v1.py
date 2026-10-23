"""Simple league-wide NFL Rushing Yards Page 1 running-back board."""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from urllib.parse import quote
from zoneinfo import ZoneInfo

from nfl_rushing_yards_slate_gateway_v1 import load_rushing_yards_slate

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "NFL RUSHING YARDS SIMPLE RB GRID V1"

CSS = r"""
<style>
.kry1{max-width:1180px;margin:0 auto;padding:2px 4px 32px;color:#edf7fc}.kry1head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:4px 0 12px}.kry1kick{font-size:.66rem;letter-spacing:.14em;color:#68cdf7;font-weight:950}.kry1title{font-size:1.65rem;line-height:1.05;font-weight:950}.kry1sub{font-size:.74rem;color:#a9bdca;margin-top:5px}.kry1grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.kry1card{display:block;text-decoration:none;color:inherit;border:1px solid #25495f;background:#091a27;border-radius:17px;padding:14px;transition:transform .12s ease,border-color .12s ease}.kry1card:hover{transform:translateY(-1px);border-color:#4f9cc4}.kry1top{display:flex;align-items:center;gap:10px}.kry1face{width:52px;height:52px;border-radius:50%;object-fit:cover;border:2px solid #3e80a5;background:#06131d}.kry1faceph{width:52px;height:52px;border-radius:50%;border:2px solid #345f78;background:#071621;display:flex;align-items:center;justify-content:center;font-size:.64rem;font-weight:900;color:#87a9bc}.kry1logo{width:38px;height:38px;object-fit:contain;margin-left:auto}.kry1name{font-size:1.02rem;font-weight:950;line-height:1.05}.kry1meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:.69rem;color:#a9bdca;margin-top:4px}.kry1role{display:inline-flex;border:1px solid #397697;border-radius:999px;padding:2px 6px;color:#79d6ff;font-size:.58rem;font-weight:950;letter-spacing:.06em}.kry1metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:12px}.kry1metric{border:1px solid #294a5e;background:#071621;border-radius:11px;padding:8px 8px;min-width:0}.kry1label{font-size:.50rem;letter-spacing:.08em;color:#92a9b8;font-weight:900}.kry1value{font-size:.92rem;font-weight:950;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kry1tiny{font-size:.58rem;color:#8fa5b4;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kry1row{display:flex;gap:7px;align-items:center;justify-content:space-between;margin-top:10px}.kry1chips{display:flex;gap:6px;flex-wrap:wrap}.kry1chip{display:inline-flex;border:1px solid #31536a;border-radius:999px;padding:4px 7px;font-size:.61rem;font-weight:850;color:#c5d8e3}.kry1action{font-size:.65rem;font-weight:950;color:#80dbff;white-space:nowrap}.kry1empty{border:1px solid #5d5839;background:#1d1a0f;border-radius:14px;padding:14px;color:#efd58e}.kry1sort{margin:0 0 10px}.kry1good{color:#79e1af}.kry1warn{color:#f2cb75}
@media(max-width:850px){.kry1grid{grid-template-columns:1fr}.kry1metrics{grid-template-columns:repeat(4,minmax(80px,1fr));overflow-x:auto;padding-bottom:2px}}
@media(max-width:520px){.kry1title{font-size:1.4rem}.kry1card{padding:12px}.kry1metrics{grid-template-columns:repeat(2,1fr);overflow:visible}.kry1row{align-items:flex-start;flex-direction:column}.kry1action{align-self:flex-end}}
</style>
"""


def _text(value: Any, fallback: str = "Pending verification") -> str:
    text = str(value if value is not None else "").strip()
    return text or fallback


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, digits: int = 1, fallback: str = "Pending") -> str:
    number = _num(value)
    return fallback if number is None else f"{number:.{digits}f}"


def _pct(value: Any) -> str:
    number = _num(value)
    return "Pending" if number is None else f"{round(number * 100):d}%"


def _kickoff(value: Any) -> str:
    raw = _text(value, "")
    if not raw:
        return "Kickoff pending"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ET)
        dt = dt.astimezone(ET)
        return dt.strftime("%a %-m/%-d · %-I:%M %p ET")
    except Exception:
        return raw


def _market_label(market: Mapping[str, Any]) -> tuple[str, str]:
    status = _text(market.get("status"), "MARKET_NOT_POSTED")
    line = _num(market.get("line"))
    if status == "VERIFIED" and line is not None:
        return f"{line:.1f}", _text(market.get("sportsbook"), "Verified book")
    labels = {
        "MARKET_NOT_POSTED": "Not posted yet",
        "LINE_CURRENTLY_OFF_BOARD": "Off board",
        "DATA_UNAVAILABLE": "Verification pending",
    }
    return labels.get(status, status.replace("_", " ").title()), "Rushing Yards"


def _edge_label(card: Mapping[str, Any]) -> str:
    edge = _num(card.get("edge_yards"))
    return "Pending" if edge is None else f"{edge:+.1f}"


def build_rb_card_html(card: Mapping[str, Any]) -> str:
    market = card.get("market") if isinstance(card.get("market"), dict) else {}
    line_text, book_text = _market_label(market)
    player_id = quote(_text(card.get("player_id"), ""), safe="")
    game_id = quote(_text(card.get("game_id"), ""), safe="")
    date = quote(_text(card.get("game_date"), ""), safe="")
    # Compatibility key is retained while canonical route params drive the same player handoff.
    href = f"?sport=nfl&market=rushing-yards&player_id={player_id}&game_id={game_id}&date={date}&ks_ry_detail={player_id}&ks_ry_game={game_id}&ks_ry_date={date}"
    face = _text(card.get("headshot_url"), "")
    logo = _text(card.get("team_logo_url"), "")
    face_html = f'<img class="kry1face" src="{escape(face)}" alt="">' if face else '<div class="kry1faceph">RB</div>'
    logo_html = f'<img class="kry1logo" src="{escape(logo)}" alt="">' if logo else ""
    role = _text(card.get("role"), "RB")
    opponent = _text(card.get("opponent_abbr"), "Opponent")
    home_away = _text(card.get("home_away"), "Pregame")
    favored = _text(card.get("favored_side"), "CHECK")
    confidence = _text(card.get("confidence"), "MARKET PENDING")
    side_probability = card.get("over_probability") if favored == "OVER" else card.get("under_probability") if favored == "UNDER" else None
    defense_grade = _text(card.get("opponent_rush_defense_grade"), "CHECK")
    projection = _fmt(card.get("projection_yards"))
    return (
        f'<a class="kry1card" href="{escape(href)}">'
        '<div class="kry1top">' + face_html + '<div>'
        f'<div class="kry1name">{escape(_text(card.get("player_name"), "Running back"))}</div>'
        f'<div class="kry1meta"><span class="kry1role">{escape(role)}</span><span>{escape(_text(card.get("team_abbr"), "NFL"))} · {escape(home_away)} vs {escape(opponent)}</span></div>'
        f'<div class="kry1meta">{escape(_kickoff(card.get("game_time")))}</div>'
        '</div>' + logo_html + '</div>'
        '<div class="kry1metrics">'
        f'<div class="kry1metric"><div class="kry1label">MARKET LINE</div><div class="kry1value">{escape(line_text)}</div><div class="kry1tiny">{escape(book_text)}</div></div>'
        f'<div class="kry1metric"><div class="kry1label">KYRE PROJECTION</div><div class="kry1value">{escape(projection)}</div><div class="kry1tiny">Rushing yards</div></div>'
        f'<div class="kry1metric"><div class="kry1label">EDGE</div><div class="kry1value">{escape(_edge_label(card))}</div><div class="kry1tiny">Projection − line</div></div>'
        f'<div class="kry1metric"><div class="kry1label">MODEL SIDE</div><div class="kry1value">{escape(favored)}</div><div class="kry1tiny">{escape(_pct(side_probability))} · {escape(confidence)}</div></div>'
        '</div>'
        '<div class="kry1row"><div class="kry1chips">'
        f'<span class="kry1chip">L5 {_fmt(card.get("last5_average"))}</span>'
        f'<span class="kry1chip">ATT/G {_fmt(card.get("carries_per_game"))}</span>'
        f'<span class="kry1chip">YPC {_fmt(card.get("yards_per_carry"),2)}</span>'
        f'<span class="kry1chip">Rush D {escape(defense_grade)}</span>'
        '</div><span class="kry1action">View Full Analysis →</span></div>'
        '</a>'
    )


def sort_rb_cards(cards: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    rows = list(cards)
    if mode == "Best Edges":
        return sorted(rows, key=lambda row: (-(abs(_num(row.get("edge_yards")) or -1.0)), row.get("game_time") or "", row.get("player_name") or ""))
    return sorted(rows, key=lambda row: (row.get("game_time") or "", row.get("team_abbr") or "", 0 if row.get("role") == "RB1" else 1, row.get("player_name") or ""))


def _render_detail(st: Any, card: Mapping[str, Any]) -> None:
    from nfl_rushing_yards_professional_v1 import render_page2
    render_page2(st, card)


def _slate_label(payload: Mapping[str, Any]) -> str:
    start = _text(payload.get("slate_start"), "")
    end = _text(payload.get("slate_end"), "")
    week = payload.get("week")
    if start and end:
        span = start if start == end else f"{start} → {end}"
        return f"Week {week} · {span}" if week else span
    reason = _text(payload.get("reason"), "")
    return "Next upcoming NFL slate" if not reason else reason.replace("_", " ").title()


def render_nfl_rushing_yards_simple_rb_grid() -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
    target_date = st.query_params.get("date") or st.query_params.get("ks_ry_date") or None
    payload = load_rushing_yards_slate(target_date)
    if not payload.get("ready"):
        st.error(_text(payload.get("reason"), "Kyre Sports API Rushing Yards slate is not ready"))
        return

    cards = list(payload.get("running_backs") or [])
    selected = st.query_params.get("player_id") or st.query_params.get("ks_ry_detail")
    if selected:
        card = next((row for row in cards if _text(row.get("player_id"), "") == str(selected)), None)
        if card:
            _render_detail(st, card)
            return

    sort_mode = st.radio("Sort running backs", ["Game Time", "Best Edges"], horizontal=True, label_visibility="collapsed")
    cards = sort_rb_cards(cards, sort_mode)
    header = (
        '<div class="kry1"><div class="kry1head"><div>'
        '<div class="kry1kick">KYRE AI · RUSHING YARDS</div>'
        '<div class="kry1title">Running Back Board</div>'
        f'<div class="kry1sub">{escape(_slate_label(payload))} · {len(cards)} RB1/RB2 cards · upcoming games only</div>'
        '</div></div>'
    )
    if not cards:
        st.markdown(header + '<div class="kry1empty">No upcoming RB1/RB2 cards currently qualify. The board will automatically roll to the next scheduled NFL slate.</div></div>', unsafe_allow_html=True)
        return
    st.markdown(header + '<div class="kry1grid">' + "".join(build_rb_card_html(card) for card in cards) + '</div></div>', unsafe_allow_html=True)


render_nfl_hub = lambda market="Rushing Yards": render_nfl_rushing_yards_simple_rb_grid()

__all__ = ["CSS", "MODEL_VERSION", "build_rb_card_html", "load_rushing_yards_slate", "render_nfl_hub", "render_nfl_rushing_yards_simple_rb_grid", "sort_rb_cards"]
