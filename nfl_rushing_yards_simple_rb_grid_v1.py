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
LEGACY_PAGE_TITLE = "Running Back Board"
LEGACY_ACTION_LABEL = "View Full Analysis"

FALLBACK_TEAM_THEME = {
    "primary": "#0B1B2A",
    "secondary": "#8AD8FF",
    "accent": "#68CDF7",
}

TEAM_THEMES: dict[str, dict[str, str]] = {
    "ARI": {"primary": "#97233F", "secondary": "#000000", "accent": "#FFB612"},
    "ATL": {"primary": "#A71930", "secondary": "#000000", "accent": "#A71930"},
    "BAL": {"primary": "#241773", "secondary": "#000000", "accent": "#9E7C0C"},
    "BUF": {"primary": "#00338D", "secondary": "#C60C30", "accent": "#C60C30"},
    "CAR": {"primary": "#0085CA", "secondary": "#101820", "accent": "#0085CA"},
    "CHI": {"primary": "#0B162A", "secondary": "#C83803", "accent": "#C83803"},
    "CIN": {"primary": "#FB4F14", "secondary": "#000000", "accent": "#FB4F14"},
    "CLE": {"primary": "#311D00", "secondary": "#FF3C00", "accent": "#FF3C00"},
    "DAL": {"primary": "#003594", "secondary": "#041E42", "accent": "#869397"},
    "DEN": {"primary": "#FB4F14", "secondary": "#002244", "accent": "#FB4F14"},
    "DET": {"primary": "#0076B6", "secondary": "#B0B7BC", "accent": "#0076B6"},
    "GB": {"primary": "#203731", "secondary": "#FFB612", "accent": "#FFB612"},
    "HOU": {"primary": "#03202F", "secondary": "#A71930", "accent": "#A71930"},
    "IND": {"primary": "#002C5F", "secondary": "#A2AAAD", "accent": "#4F9CD3"},
    "JAX": {"primary": "#006778", "secondary": "#D7A22A", "accent": "#D7A22A"},
    "KC": {"primary": "#E31837", "secondary": "#FFB81C", "accent": "#E31837"},
    "LV": {"primary": "#000000", "secondary": "#A5ACAF", "accent": "#A5ACAF"},
    "LAC": {"primary": "#0080C6", "secondary": "#FFC20E", "accent": "#0080C6"},
    "LAR": {"primary": "#003594", "secondary": "#FFA300", "accent": "#FFA300"},
    "MIA": {"primary": "#008E97", "secondary": "#FC4C02", "accent": "#008E97"},
    "MIN": {"primary": "#4F2683", "secondary": "#FFC62F", "accent": "#FFC62F"},
    "NE": {"primary": "#002244", "secondary": "#C60C30", "accent": "#C60C30"},
    "NO": {"primary": "#D3BC8D", "secondary": "#101820", "accent": "#D3BC8D"},
    "NYG": {"primary": "#0B2265", "secondary": "#A71930", "accent": "#A71930"},
    "NYJ": {"primary": "#125740", "secondary": "#000000", "accent": "#3B8C6E"},
    "PHI": {"primary": "#004C54", "secondary": "#A5ACAF", "accent": "#00A6B2"},
    "PIT": {"primary": "#FFB612", "secondary": "#101820", "accent": "#FFB612"},
    "SF": {"primary": "#AA0000", "secondary": "#B3995D", "accent": "#AA0000"},
    "SEA": {"primary": "#002244", "secondary": "#69BE28", "accent": "#69BE28"},
    "TB": {"primary": "#D50A0A", "secondary": "#34302B", "accent": "#D50A0A"},
    "TEN": {"primary": "#0C2340", "secondary": "#4B92DB", "accent": "#4B92DB"},
    "WAS": {"primary": "#5A1414", "secondary": "#FFB612", "accent": "#FFB612"},
}

CSS = r"""
<style>
.kry1{max-width:1180px;margin:0 auto;padding:2px 4px 32px;color:#edf7fc}.kry1head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:4px 0 11px}.kry1kick{font-size:.64rem;letter-spacing:.15em;color:#68cdf7;font-weight:950}.kry1title{font-size:1.58rem;line-height:1.05;font-weight:950}.kry1sub{font-size:.72rem;color:#9eb3c0;margin-top:5px}.kry1grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.kry1card{display:block;position:relative;overflow:hidden;text-decoration:none!important;color:inherit;border:1px solid #24495f;background:linear-gradient(135deg,rgba(9,26,39,.99),rgba(7,22,33,.99));border-radius:16px;padding:12px 13px 11px 16px;box-shadow:0 0 0 1px rgba(104,205,247,.025),inset 0 1px 0 rgba(255,255,255,.025);transition:transform .12s ease,border-color .12s ease,box-shadow .12s ease}.kry1card *{text-decoration:none!important}.kry1card:hover{transform:translateY(-1px);border-color:var(--team-accent);box-shadow:0 6px 22px rgba(0,0,0,.16)}.kry1accent{position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--team-accent);box-shadow:0 0 12px color-mix(in srgb,var(--team-accent) 55%,transparent)}.kry1top{display:flex;align-items:center;gap:9px}.kry1face,.kry1faceph{width:46px;height:46px;border-radius:50%;flex:0 0 46px}.kry1face{object-fit:cover;border:2px solid var(--team-accent);background:#06131d;box-shadow:0 0 0 2px rgba(255,255,255,.025)}.kry1faceph{border:2px solid var(--team-accent);background:#071621;display:flex;align-items:center;justify-content:center;font-size:.61rem;font-weight:900;color:#c9dbe5}.kry1identity{min-width:0;flex:1}.kry1name{font-size:1rem;font-weight:950;line-height:1.08;color:#f2f8fb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kry1meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:.67rem;color:#9eb3c0;margin-top:4px}.kry1role{display:inline-flex;border:1px solid var(--team-accent);border-radius:999px;padding:2px 6px;color:var(--team-accent);background:rgba(6,19,29,.72);font-size:.56rem;font-weight:950;letter-spacing:.06em}.kry1team{display:flex;align-items:center;gap:5px;margin-left:auto;min-width:max-content}.kry1teamabbr{font-size:.62rem;font-weight:950;letter-spacing:.08em;color:#dceaf2}.kry1logo{width:31px;height:31px;object-fit:contain}.kry1analytics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:10px;border:1px solid #294d62;background:#071621;border-radius:12px;overflow:hidden}.kry1cell{padding:8px 9px;min-width:0}.kry1cell+.kry1cell{border-left:1px solid #294d62}.kry1label{font-size:.48rem;letter-spacing:.09em;color:#8da5b4;font-weight:950}.kry1value{font-size:.91rem;font-weight:950;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#eaf6fb}.kry1tiny{font-size:.56rem;color:#8299a8;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kry1positive,.kry1side-positive{color:#7de2b2!important}.kry1negative,.kry1side-negative{color:#ff9a94!important}.kry1pending{color:#f3cf7f!important}.kry1pendingnote{font-size:.59rem;color:#d8bb75;margin-top:6px;padding-left:1px}.kry1scout{display:flex;align-items:center;gap:0;margin-top:8px;min-width:0;color:#c4d7e1;font-size:.61rem;font-weight:850;overflow:hidden}.kry1scoutitem{white-space:nowrap}.kry1scoutitem+.kry1scoutitem:before{content:'·';display:inline-block;margin:0 7px;color:#577386}.kry1def-favorable{color:#7de2b2}.kry1def-medium{color:#8bdcff}.kry1def-tough{color:#ffb36d}.kry1def-elite{color:#ff8f8f}.kry1def-check{color:#f3cf7f}.kry1bottom{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:7px}.kry1action{margin-left:auto;font-size:.62rem;font-weight:950;color:#80dbff;white-space:nowrap;letter-spacing:.035em}.kry1empty{border:1px solid #5d5839;background:#1d1a0f;border-radius:14px;padding:14px;color:#efd58e}
@media(max-width:850px){.kry1grid{grid-template-columns:1fr}.kry1card{padding:12px 12px 10px 16px}}
@media(max-width:520px){.kry1title{font-size:1.38rem}.kry1analytics{grid-template-columns:repeat(2,1fr)}.kry1cell:nth-child(3),.kry1cell:nth-child(4){border-top:1px solid #294d62}.kry1cell:nth-child(3){border-left:0}.kry1scout{flex-wrap:wrap;row-gap:4px;overflow:visible}.kry1teamabbr{display:none}.kry1logo{width:28px;height:28px}.kry1name{font-size:.96rem}.kry1pendingnote{font-size:.57rem}}
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


def team_theme(team_abbr: Any) -> dict[str, str]:
    key = _text(team_abbr, "").upper()
    return dict(TEAM_THEMES.get(key, FALLBACK_TEAM_THEME))


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


def _market_view(market: Mapping[str, Any]) -> tuple[str, str, str, str]:
    status = _text(market.get("status"), "MARKET_NOT_POSTED")
    line = _num(market.get("line"))
    if status == "VERIFIED" and line is not None:
        return f"{line:.1f}", _text(market.get("sportsbook"), "Verified book"), "", ""
    if status == "LINE_CURRENTLY_OFF_BOARD":
        return "OFF BOARD", "Rushing Yards", "kry1pending", "Projection ready • line currently off board"
    if status == "DATA_UNAVAILABLE":
        return "VERIFYING", "Rushing Yards", "kry1pending", "Projection ready • market verification pending"
    return "LINE PENDING", "Rushing Yards", "kry1pending", "Projection ready • sportsbook market not posted"


def _edge_view(card: Mapping[str, Any], *, market_verified: bool) -> tuple[str, str]:
    edge = _num(card.get("edge_yards"))
    if not market_verified or edge is None:
        return "WAIT", "kry1pending"
    return f"{edge:+.1f}", "kry1positive" if edge > 0 else "kry1negative" if edge < 0 else ""


def _side_view(card: Mapping[str, Any], *, market_verified: bool) -> tuple[str, str, str]:
    if not market_verified:
        return "WAIT", "Market pending", "kry1pending"
    favored = _text(card.get("favored_side"), "CHECK").upper()
    confidence = _text(card.get("confidence"), "CHECK")
    side_probability = card.get("over_probability") if favored == "OVER" else card.get("under_probability") if favored == "UNDER" else None
    if favored == "OVER":
        return favored, f"{_pct(side_probability)} · {confidence}", "kry1side-positive"
    if favored == "UNDER":
        return favored, f"{_pct(side_probability)} · {confidence}", "kry1side-negative"
    return "WAIT", confidence, "kry1pending"


def _defense_class(grade: Any) -> str:
    value = _text(grade, "CHECK").upper()
    if value in {"FAVORABLE", "SOFT"}:
        return "kry1def-favorable"
    if value in {"MEDIUM", "AVERAGE", "NEUTRAL"}:
        return "kry1def-medium"
    if value == "TOUGH":
        return "kry1def-tough"
    if value in {"ELITE", "VERY TOUGH"}:
        return "kry1def-elite"
    return "kry1def-check"


def build_rb_card_html(card: Mapping[str, Any]) -> str:
    market = card.get("market") if isinstance(card.get("market"), dict) else {}
    market_status = _text(market.get("status"), "MARKET_NOT_POSTED")
    market_verified = market_status == "VERIFIED" and _num(market.get("line")) is not None
    line_text, book_text, market_class, pending_note = _market_view(market)
    edge_text, edge_class = _edge_view(card, market_verified=market_verified)
    side_text, side_note, side_class = _side_view(card, market_verified=market_verified)

    player_id = quote(_text(card.get("player_id"), ""), safe="")
    game_id = quote(_text(card.get("game_id"), ""), safe="")
    date = quote(_text(card.get("game_date"), ""), safe="")
    href = f"?sport=nfl&market=rushing-yards&player_id={player_id}&game_id={game_id}&date={date}&ks_ry_detail={player_id}&ks_ry_game={game_id}&ks_ry_date={date}"

    team = _text(card.get("team_abbr"), "NFL").upper()
    theme = team_theme(team)
    team_style = f"--team-primary:{theme['primary']};--team-secondary:{theme['secondary']};--team-accent:{theme['accent']}"
    face = _text(card.get("headshot_url"), "")
    logo = _text(card.get("team_logo_url"), "")
    face_html = f'<img class="kry1face" src="{escape(face)}" alt="">' if face else '<div class="kry1faceph">RB</div>'
    logo_html = f'<img class="kry1logo" src="{escape(logo)}" alt="">' if logo else ""

    role = _text(card.get("role"), "RB")
    opponent = _text(card.get("opponent_abbr"), "Opponent")
    home_away = _text(card.get("home_away"), "Pregame")
    defense_grade = _text(card.get("opponent_rush_defense_grade"), "CHECK").upper()
    defense_class = _defense_class(defense_grade)
    projection = _fmt(card.get("projection_yards"))
    pending_html = f'<div class="kry1pendingnote">{escape(pending_note)}</div>' if pending_note else ""

    return (
        f'<a class="kry1card" style="{team_style}" data-team="{escape(team)}" href="{escape(href)}">'
        '<span class="kry1accent"></span>'
        '<div class="kry1top">' + face_html + '<div class="kry1identity">'
        f'<div class="kry1name">{escape(_text(card.get("player_name"), "Running back"))}</div>'
        f'<div class="kry1meta"><span class="kry1role">{escape(role)}</span><span>{escape(home_away)} vs {escape(opponent)}</span></div>'
        f'<div class="kry1meta">{escape(_kickoff(card.get("game_time")))}</div>'
        '</div>'
        f'<div class="kry1team"><span class="kry1teamabbr">{escape(team)}</span>{logo_html}</div></div>'
        '<div class="kry1analytics">'
        f'<div class="kry1cell"><div class="kry1label">MARKET</div><div class="kry1value {market_class}">{escape(line_text)}</div><div class="kry1tiny">{escape(book_text)}</div></div>'
        f'<div class="kry1cell"><div class="kry1label">KYRE</div><div class="kry1value">{escape(projection)}</div><div class="kry1tiny">Rush yds</div></div>'
        f'<div class="kry1cell"><div class="kry1label">EDGE</div><div class="kry1value {edge_class}">{escape(edge_text)}</div><div class="kry1tiny">Projection − line</div></div>'
        f'<div class="kry1cell"><div class="kry1label">MODEL</div><div class="kry1value {side_class}">{escape(side_text)}</div><div class="kry1tiny">{escape(side_note)}</div></div>'
        '</div>'
        + pending_html +
        '<div class="kry1bottom"><div class="kry1scout">'
        f'<span class="kry1scoutitem">L5 {_fmt(card.get("last5_average"))}</span>'
        f'<span class="kry1scoutitem">{_fmt(card.get("carries_per_game"))} ATT/G</span>'
        f'<span class="kry1scoutitem">{_fmt(card.get("yards_per_carry"),2)} YPC</span>'
        f'<span class="kry1scoutitem {defense_class}">{escape(defense_grade)} RUSH D</span>'
        '</div><span class="kry1action">FULL ANALYSIS →</span></div>'
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
        '<div class="kry1kick">KYRE AI · NFL RUSHING YARDS</div>'
        '<div class="kry1title">RB Market Board</div>'
        f'<div class="kry1sub">{escape(_slate_label(payload))} · {len(cards)} active RB1/RB2 · upcoming games only</div>'
        '</div></div>'
    )
    if not cards:
        st.markdown(header + '<div class="kry1empty">No upcoming RB1/RB2 cards currently qualify. The board will automatically roll to the next scheduled NFL slate.</div></div>', unsafe_allow_html=True)
        return
    st.markdown(header + '<div class="kry1grid">' + "".join(build_rb_card_html(card) for card in cards) + '</div></div>', unsafe_allow_html=True)


render_nfl_hub = lambda market="Rushing Yards": render_nfl_rushing_yards_simple_rb_grid()

__all__ = [
    "CSS",
    "FALLBACK_TEAM_THEME",
    "MODEL_VERSION",
    "TEAM_THEMES",
    "build_rb_card_html",
    "load_rushing_yards_slate",
    "render_nfl_hub",
    "render_nfl_rushing_yards_simple_rb_grid",
    "sort_rb_cards",
    "team_theme",
]
