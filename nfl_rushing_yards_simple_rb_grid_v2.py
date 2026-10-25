"""Compact projection-first NFL Rushing Yards Page 1 successor.

Presentation-only successor over the frozen V1 board. Data loading, identities,
projection values, market integrity, upcoming-game filtering, sorting and Page 2
analytics remain owned by the existing frozen modules.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping
from urllib.parse import quote

import nfl_rushing_yards_simple_rb_grid_v1 as v1

MODEL_VERSION = "NFL RUSHING YARDS SIMPLE RB GRID V2 • DENSITY R1"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

CSS = r"""
<style>
.kry2{max-width:1180px;margin:0 auto;padding:2px 4px 32px;color:#edf7fc}
.kry2head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:4px 0 10px}
.kry2kick{font-size:.64rem;letter-spacing:.15em;color:#68cdf7;font-weight:950}
.kry2title{font-size:1.58rem;line-height:1.05;font-weight:950}
.kry2sub{font-size:.72rem;color:#9eb3c0;margin-top:5px}
.kry2grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.kry2card{display:block;position:relative;overflow:hidden;text-decoration:none!important;color:inherit;border:1px solid #24495f;background:linear-gradient(135deg,rgba(9,26,39,.99),rgba(7,22,33,.99));border-radius:15px;padding:10px 12px 10px 15px;box-shadow:0 0 0 1px rgba(104,205,247,.025),inset 0 1px 0 rgba(255,255,255,.025);transition:transform .12s ease,border-color .12s ease,box-shadow .12s ease}
.kry2card *{text-decoration:none!important}.kry2card:hover{transform:translateY(-1px);border-color:var(--team-accent);box-shadow:0 6px 22px rgba(0,0,0,.16)}
.kry2accent{position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--team-accent);box-shadow:0 0 11px color-mix(in srgb,var(--team-accent) 50%,transparent)}
.kry2top{display:flex;align-items:center;gap:9px}.kry2face,.kry2faceph{width:44px;height:44px;border-radius:50%;flex:0 0 44px}
.kry2face{object-fit:cover;border:2px solid var(--team-accent);background:#06131d}.kry2faceph{border:2px solid var(--team-accent);background:#071621;display:flex;align-items:center;justify-content:center;font-size:.6rem;font-weight:900;color:#c9dbe5}
.kry2identity{min-width:0;flex:1}.kry2name{font-size:1rem;font-weight:950;line-height:1.08;color:#f2f8fb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kry2meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:.65rem;color:#9eb3c0;margin-top:3px}.kry2role{display:inline-flex;border:1px solid var(--team-accent);border-radius:999px;padding:2px 6px;color:var(--team-accent);background:rgba(6,19,29,.72);font-size:.55rem;font-weight:950;letter-spacing:.06em}
.kry2team{display:flex;align-items:center;gap:5px;margin-left:auto;min-width:max-content}.kry2teamabbr{font-size:.61rem;font-weight:950;letter-spacing:.08em;color:#dceaf2}.kry2logo{width:30px;height:30px;object-fit:contain}
.kry2projection{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-top:9px;padding:8px 10px;border:1px solid #31566b;border-radius:11px;background:linear-gradient(110deg,rgba(10,33,48,.94),rgba(7,22,33,.94))}
.kry2projectionlabel{font-size:.5rem;letter-spacing:.12em;color:#8ea8b8;font-weight:950}.kry2projectionvalue{margin-top:2px;font-size:1.28rem;line-height:1;font-weight:950;color:#f4f9fc}.kry2projectionunit{font-size:.58rem;color:#9eb3c0;font-weight:850;margin-left:4px}.kry2projectionhint{font-size:.57rem;color:#8da5b4;text-align:right;white-space:nowrap}
.kry2decision{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin-top:6px;border:1px solid #294d62;background:#071621;border-radius:10px;overflow:hidden}.kry2decisioncell{padding:6px 8px;min-width:0}.kry2decisioncell+.kry2decisioncell{border-left:1px solid #294d62}.kry2label{font-size:.46rem;letter-spacing:.09em;color:#8da5b4;font-weight:950}.kry2value{font-size:.79rem;font-weight:950;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#eaf6fb}.kry2tiny{font-size:.52rem;color:#8299a8;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kry2positive,.kry2side-positive{color:#7de2b2!important}.kry2negative,.kry2side-negative{color:#ff9a94!important}.kry2pending{color:#f3cf7f!important}.kry2pendingnote{font-size:.56rem;color:#d8bb75;margin-top:5px;padding-left:1px}
.kry2quick{display:flex;align-items:center;gap:0;margin-top:7px;min-width:0;color:#c4d7e1;font-size:.58rem;font-weight:850;overflow:hidden}.kry2quickitem{white-space:nowrap}.kry2quickitem+.kry2quickitem:before{content:'·';display:inline-block;margin:0 6px;color:#577386}
.kry2def-favorable{color:#7de2b2}.kry2def-medium{color:#8bdcff}.kry2def-tough{color:#ffb36d}.kry2def-elite{color:#ff8f8f}.kry2def-check{color:#f3cf7f}
.kry2bottom{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:5px}.kry2action{margin-left:auto;font-size:.6rem;font-weight:950;color:#80dbff;white-space:nowrap;letter-spacing:.035em}.kry2empty{border:1px solid #5d5839;background:#1d1a0f;border-radius:14px;padding:14px;color:#efd58e}
@media(max-width:850px){.kry2grid{grid-template-columns:1fr}.kry2card{padding:10px 11px 9px 15px}}
@media(max-width:520px){.kry2title{font-size:1.38rem}.kry2decision{grid-template-columns:repeat(3,minmax(0,1fr))}.kry2decisioncell{padding:6px 6px}.kry2quick{flex-wrap:wrap;row-gap:3px;overflow:visible}.kry2teamabbr{display:none}.kry2logo{width:28px;height:28px}.kry2name{font-size:.96rem}.kry2projectionvalue{font-size:1.22rem}.kry2projectionhint{font-size:.53rem}.kry2pendingnote{font-size:.54rem}}
</style>
"""


def _market_view(market: Mapping[str, Any]) -> tuple[str, str, str, str]:
    status = v1._text(market.get("status"), "MARKET_NOT_POSTED")
    line = v1._num(market.get("line"))
    if status == "VERIFIED" and line is not None:
        return f"{line:.1f}", v1._text(market.get("sportsbook"), "Verified book"), "", ""
    if status == "LINE_CURRENTLY_OFF_BOARD":
        return "OFF BOARD", "Rushing Yards", "kry2pending", "Line currently off board • projection ready"
    if status == "DATA_UNAVAILABLE":
        return "VERIFYING", "Market check", "kry2pending", "Market verification in progress • projection ready"
    return "PENDING", "Rushing Yards", "kry2pending", "Sportsbook line not posted yet • projection ready"


def _edge_view(card: Mapping[str, Any], *, market_verified: bool) -> tuple[str, str, str]:
    edge = v1._num(card.get("edge_yards"))
    if not market_verified or edge is None:
        return "—", "Awaiting line", ""
    return f"{edge:+.1f}", "Projection − line", "kry2positive" if edge > 0 else "kry2negative" if edge < 0 else ""


def _side_view(card: Mapping[str, Any], *, market_verified: bool) -> tuple[str, str, str]:
    if not market_verified:
        return "PENDING", "Awaiting line", "kry2pending"
    favored = v1._text(card.get("favored_side"), "CHECK").upper()
    confidence = v1._text(card.get("confidence"), "CHECK")
    probability = card.get("over_probability") if favored == "OVER" else card.get("under_probability") if favored == "UNDER" else None
    if favored == "OVER":
        return favored, f"{v1._pct(probability)} · {confidence}", "kry2side-positive"
    if favored == "UNDER":
        return favored, f"{v1._pct(probability)} · {confidence}", "kry2side-negative"
    return "CHECK", confidence, "kry2pending"


def _defense_class(grade: Any) -> str:
    value = v1._text(grade, "CHECK").upper()
    if value in {"FAVORABLE", "SOFT"}:
        return "kry2def-favorable"
    if value in {"MEDIUM", "AVERAGE", "NEUTRAL"}:
        return "kry2def-medium"
    if value == "TOUGH":
        return "kry2def-tough"
    if value in {"ELITE", "VERY TOUGH"}:
        return "kry2def-elite"
    return "kry2def-check"


def build_rb_card_html(card: Mapping[str, Any]) -> str:
    market = card.get("market") if isinstance(card.get("market"), dict) else {}
    market_status = v1._text(market.get("status"), "MARKET_NOT_POSTED")
    market_verified = market_status == "VERIFIED" and v1._num(market.get("line")) is not None
    line_text, book_text, market_class, pending_note = _market_view(market)
    edge_text, edge_note, edge_class = _edge_view(card, market_verified=market_verified)
    side_text, side_note, side_class = _side_view(card, market_verified=market_verified)

    player_id = quote(v1._text(card.get("player_id"), ""), safe="")
    game_id = quote(v1._text(card.get("game_id"), ""), safe="")
    date = quote(v1._text(card.get("game_date"), ""), safe="")
    href = f"?sport=nfl&market=rushing-yards&player_id={player_id}&game_id={game_id}&date={date}&ks_ry_detail={player_id}&ks_ry_game={game_id}&ks_ry_date={date}"

    team = v1._text(card.get("team_abbr"), "NFL").upper()
    theme = v1.team_theme(team)
    team_style = f"--team-primary:{theme['primary']};--team-secondary:{theme['secondary']};--team-accent:{theme['accent']}"
    face = v1._text(card.get("headshot_url"), "")
    logo = v1._text(card.get("team_logo_url"), "")
    face_html = f'<img class="kry2face" src="{escape(face)}" alt="">' if face else '<div class="kry2faceph">RB</div>'
    logo_html = f'<img class="kry2logo" src="{escape(logo)}" alt="">' if logo else ""

    role = v1._text(card.get("role"), "RB")
    opponent = v1._text(card.get("opponent_abbr"), "Opponent")
    home_away = v1._text(card.get("home_away"), "Pregame")
    defense_grade = v1._text(card.get("opponent_rush_defense_grade"), "CHECK").upper()
    defense_class = _defense_class(defense_grade)
    projection = v1._fmt(card.get("projection_yards"))
    pending_html = f'<div class="kry2pendingnote">{escape(pending_note)}</div>' if pending_note else ""
    projection_hint = "Model projection" if market_verified else "Market-independent"

    return (
        f'<a class="kry2card" style="{team_style}" data-team="{escape(team)}" href="{escape(href)}">'
        '<span class="kry2accent"></span>'
        '<div class="kry2top">' + face_html + '<div class="kry2identity">'
        f'<div class="kry2name">{escape(v1._text(card.get("player_name"), "Running back"))}</div>'
        f'<div class="kry2meta"><span class="kry2role">{escape(role)}</span><span>{escape(home_away)} vs {escape(opponent)}</span></div>'
        f'<div class="kry2meta">{escape(v1._kickoff(card.get("game_time")))}</div>'
        '</div>'
        f'<div class="kry2team"><span class="kry2teamabbr">{escape(team)}</span>{logo_html}</div></div>'
        '<div class="kry2projection">'
        '<div><div class="kry2projectionlabel">KYRE PROJECTION</div>'
        f'<div class="kry2projectionvalue">{escape(projection)}<span class="kry2projectionunit">YDS</span></div></div>'
        f'<div class="kry2projectionhint">{escape(projection_hint)}</div></div>'
        '<div class="kry2decision">'
        f'<div class="kry2decisioncell"><div class="kry2label">MARKET</div><div class="kry2value {market_class}">{escape(line_text)}</div><div class="kry2tiny">{escape(book_text)}</div></div>'
        f'<div class="kry2decisioncell"><div class="kry2label">EDGE</div><div class="kry2value {edge_class}">{escape(edge_text)}</div><div class="kry2tiny">{escape(edge_note)}</div></div>'
        f'<div class="kry2decisioncell"><div class="kry2label">MODEL</div><div class="kry2value {side_class}">{escape(side_text)}</div><div class="kry2tiny">{escape(side_note)}</div></div>'
        '</div>' + pending_html +
        '<div class="kry2bottom"><div class="kry2quick">'
        f'<span class="kry2quickitem">L5 {v1._fmt(card.get("last5_average"))}</span>'
        f'<span class="kry2quickitem">{v1._fmt(card.get("carries_per_game"))} ATT/G</span>'
        f'<span class="kry2quickitem">{v1._fmt(card.get("yards_per_carry"),2)} YPC</span>'
        f'<span class="kry2quickitem {defense_class}">{escape(defense_grade)} RUSH D</span>'
        '</div><span class="kry2action">FULL ANALYSIS →</span></div>'
        '</a>'
    )


def render_nfl_rushing_yards_simple_rb_grid_v2() -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
    target_date = st.query_params.get("date") or st.query_params.get("ks_ry_date") or None
    payload = v1.load_rushing_yards_slate(target_date)
    if not payload.get("ready"):
        st.error(v1._text(payload.get("reason"), "Kyre Sports API Rushing Yards slate is not ready"))
        return

    cards = list(payload.get("running_backs") or [])
    selected = st.query_params.get("player_id") or st.query_params.get("ks_ry_detail")
    if selected:
        card = next((row for row in cards if v1._text(row.get("player_id"), "") == str(selected)), None)
        if card:
            v1._render_detail(st, card)
            return

    sort_mode = st.radio("Sort running backs", ["Game Time", "Best Edges"], horizontal=True, label_visibility="collapsed")
    cards = v1.sort_rb_cards(cards, sort_mode)
    header = (
        '<div class="kry2"><div class="kry2head"><div>'
        '<div class="kry2kick">KYRE AI · NFL RUSHING YARDS</div>'
        '<div class="kry2title">RB Market Board</div>'
        f'<div class="kry2sub">{escape(v1._slate_label(payload))} · {len(cards)} active RB1/RB2 · upcoming games only</div>'
        '</div></div>'
    )
    if not cards:
        st.markdown(header + '<div class="kry2empty">No upcoming RB1/RB2 cards currently qualify. The board will automatically roll to the next scheduled NFL slate.</div></div>', unsafe_allow_html=True)
        return
    st.markdown(header + '<div class="kry2grid">' + "".join(build_rb_card_html(card) for card in cards) + '</div></div>', unsafe_allow_html=True)


render_nfl_rushing_yards_simple_rb_grid = render_nfl_rushing_yards_simple_rb_grid_v2
render_nfl_hub = lambda market="Rushing Yards": render_nfl_rushing_yards_simple_rb_grid_v2()

__all__ = [
    "CSS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_rb_card_html",
    "render_nfl_hub",
    "render_nfl_rushing_yards_simple_rb_grid",
    "render_nfl_rushing_yards_simple_rb_grid_v2",
]
