"""S-tier simple Page 1 for NFL Passing Yards: every starting QB, one glance."""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote

from nfl_passing_yards_slate_gateway_v1 import load_passing_yards_slate

TEAM_COLORS: dict[str, tuple[str, str]] = {
    "ARI": ("#97233F", "#FFB612"), "ATL": ("#A71930", "#000000"), "BAL": ("#241773", "#9E7C0C"),
    "BUF": ("#00338D", "#C60C30"), "CAR": ("#0085CA", "#101820"), "CHI": ("#0B162A", "#C83803"),
    "CIN": ("#FB4F14", "#000000"), "CLE": ("#311D00", "#FF3C00"), "DAL": ("#003594", "#869397"),
    "DEN": ("#FB4F14", "#002244"), "DET": ("#0076B6", "#B0B7BC"), "GB": ("#203731", "#FFB612"),
    "HOU": ("#03202F", "#A71930"), "IND": ("#002C5F", "#A2AAAD"), "JAX": ("#006778", "#D7A22A"),
    "KC": ("#E31837", "#FFB81C"), "LV": ("#000000", "#A5ACAF"), "LAC": ("#0080C6", "#FFC20E"),
    "LAR": ("#003594", "#FFA300"), "MIA": ("#008E97", "#FC4C02"), "MIN": ("#4F2683", "#FFC62F"),
    "NE": ("#002244", "#C60C30"), "NO": ("#101820", "#D3BC8D"), "NYG": ("#0B2265", "#A71930"),
    "NYJ": ("#125740", "#000000"), "PHI": ("#004C54", "#A5ACAF"), "PIT": ("#101820", "#FFB612"),
    "SEA": ("#002244", "#69BE28"), "SF": ("#AA0000", "#B3995D"), "TB": ("#D50A0A", "#FF7900"),
    "TEN": ("#0C2340", "#4B92DB"), "WAS": ("#5A1414", "#FFB612"),
}

CSS = r"""
<style>
.kpy-simple-wrap{max-width:1220px;margin:0 auto;padding:4px 4px 34px}.kpy-simple-head{display:flex;justify-content:space-between;gap:12px;align-items:end;margin:4px 0 14px}.kpy-simple-kicker{font-size:.72rem;font-weight:900;letter-spacing:.14em;color:#78d7ff}.kpy-simple-title{font-size:1.55rem;font-weight:950;color:#f7fbff;line-height:1.05}.kpy-simple-sub{font-size:.75rem;color:#94a7b5;margin-top:4px}.kpy-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.kpy-qb-card{--team-primary:#0b2235;--team-accent:#5dd8ff;position:relative;overflow:hidden;border:1px solid color-mix(in srgb,var(--team-accent) 46%,#263747);background:linear-gradient(145deg,color-mix(in srgb,var(--team-primary) 46%,#07111a),#07111a 62%);border-radius:18px;padding:14px;box-shadow:0 12px 34px rgba(0,0,0,.22)}.kpy-qb-card:before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--team-accent),var(--team-primary))}.kpy-idrow{display:flex;align-items:center;gap:10px}.kpy-face{width:52px;height:52px;border-radius:50%;object-fit:cover;background:#111c26;border:2px solid var(--team-accent)}.kpy-logo{width:30px;height:30px;object-fit:contain;margin-left:auto}.kpy-name{font-size:1.02rem;font-weight:950;color:#fff}.kpy-meta{font-size:.67rem;color:#b5c5d0;margin-top:2px}.kpy-time{font-size:.67rem;font-weight:900;color:#e9f7ff;margin-top:3px}.kpy-main{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.kpy-stat{border:1px solid #253949;background:rgba(4,12,18,.54);border-radius:12px;padding:9px}.kpy-label{font-size:.55rem;letter-spacing:.08em;color:#8499a8;font-weight:900}.kpy-value{font-size:1.08rem;color:#fff;font-weight:950;margin-top:2px}.kpy-edge{font-size:.6rem;color:#7fe0ac;font-weight:900;margin-top:2px}.kpy-probs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.kpy-prob{padding:8px 9px;border-radius:11px;background:#08141e;border:1px solid #213545}.kpy-prob.hot{border-color:#3c8c64;background:rgba(23,79,53,.22)}.kpy-probtop{display:flex;justify-content:space-between;gap:8px;font-size:.64rem;font-weight:950;color:#d9e8f1}.kpy-bar{height:5px;background:#172735;border-radius:99px;margin-top:6px;overflow:hidden}.kpy-fill{height:100%;background:var(--team-accent)}.kpy-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px}.kpy-badge{font-size:.56rem;font-weight:950;padding:4px 7px;border-radius:99px;border:1px solid #31526a;color:#d8effd}.kpy-link{font-size:.64rem;font-weight:950;text-decoration:none;color:#fff;border:1px solid var(--team-accent);border-radius:9px;padding:6px 9px}.kpy-na{color:#8295a3!important;font-size:.86rem!important}@media(max-width:760px){.kpy-grid{grid-template-columns:1fr}.kpy-simple-title{font-size:1.28rem}.kpy-qb-card{padding:12px}}
</style>
"""


def _text(value: Any, default: str = "Not Available") -> str:
    text = str(value or "").strip()
    return text or default


def _pct(value: Any) -> str:
    try:
        return f"{round(float(value) * 100):d}%"
    except (TypeError, ValueError):
        return "N/A"


def _pct_width(value: Any) -> int:
    try:
        return max(0, min(100, round(float(value) * 100)))
    except (TypeError, ValueError):
        return 0


def _game_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Time Not Available"
    try:
        hour, minute = [int(part) for part in text[:5].split(":")]
        suffix = "AM" if hour < 12 else "PM"
        shown = hour % 12 or 12
        return f"{shown}:{minute:02d} {suffix} ET"
    except Exception:
        return text



def _slate_label(payload: dict[str, Any]) -> str:
    week = payload.get("week")
    start = _text(payload.get("slate_start"), "")
    end = _text(payload.get("slate_end"), "")
    try:
        from datetime import date
        a = date.fromisoformat(start)
        b = date.fromisoformat(end)
        span = f"{a.strftime('%b')} {a.day}" if a == b else (f"{a.strftime('%b')} {a.day}–{b.day}" if a.month == b.month else f"{a.strftime('%b')} {a.day}–{b.strftime('%b')} {b.day}")
    except Exception:
        span = start or end or "Current slate"
    return f"Week {week} · {span}" if week is not None else span

def build_qb_card_html(card: dict[str, Any]) -> str:
    team = _text(card.get("team_abbr"), "NFL")
    primary, accent = TEAM_COLORS.get(team, ("#0B2235", "#59D8FF"))
    market = card.get("market") or {}
    line = market.get("line")
    projection = card.get("projection_yards")
    edge = card.get("edge_yards")
    over = card.get("over_probability")
    under = card.get("under_probability")
    favored = _text(card.get("favored_side"), "NO_STRONG_SIDE")
    headshot = card.get("headshot_url") or ""
    logo = card.get("team_logo_url") or ""
    head = f'<img class="kpy-face" src="{escape(str(headshot))}" alt="{escape(_text(card.get("qb_name")))}">' if headshot else '<div class="kpy-face"></div>'
    team_logo = f'<img class="kpy-logo" src="{escape(str(logo))}" alt="{escape(team)} logo">' if logo else ""
    line_text = f"{float(line):.1f}" if line is not None else "N/A"
    proj_text = f"{float(projection):.1f}" if projection is not None else "N/A"
    edge_text = f"{float(edge):+.1f} yd edge" if edge is not None else "Market unavailable"
    date = quote(_text(card.get("game_date"), ""), safe="")
    player = quote(_text(card.get("player_id"), ""), safe="")
    game = quote(_text(card.get("game_id"), ""), safe="")
    href = f"?ks_py_detail={player}&ks_py_game={game}&ks_py_date={date}"
    over_hot = " hot" if favored == "OVER" else ""
    under_hot = " hot" if favored == "UNDER" else ""
    starter = "Market listed" if card.get("starter_status") == "MARKET_LISTED" else "Projected starter"
    return f'''<article class="kpy-qb-card" style="--team-primary:{primary};--team-accent:{accent}">
      <div class="kpy-idrow">{head}<div><div class="kpy-name">{escape(_text(card.get('qb_name')))}</div><div class="kpy-meta">{escape(_text(card.get('team_name'), team))} · vs {escape(_text(card.get('opponent_abbr')))} · {escape(starter)}</div><div class="kpy-time">{escape(_game_time(card.get('game_time')))}</div></div>{team_logo}</div>
      <div class="kpy-main"><div class="kpy-stat"><div class="kpy-label">MARKET LINE</div><div class="kpy-value{' kpy-na' if line is None else ''}">{line_text}</div><div class="kpy-edge">{escape(_text(market.get('sportsbook'), 'Not Available'))}</div></div><div class="kpy-stat"><div class="kpy-label">KYRE PROJECTION</div><div class="kpy-value{' kpy-na' if projection is None else ''}">{proj_text}</div><div class="kpy-edge">{escape(edge_text)}</div></div></div>
      <div class="kpy-probs"><div class="kpy-prob{over_hot}"><div class="kpy-probtop"><span>OVER {line_text}</span><span>{_pct(over)}</span></div><div class="kpy-bar"><div class="kpy-fill" style="width:{_pct_width(over)}%"></div></div></div><div class="kpy-prob{under_hot}"><div class="kpy-probtop"><span>UNDER {line_text}</span><span>{_pct(under)}</span></div><div class="kpy-bar"><div class="kpy-fill" style="width:{_pct_width(under)}%"></div></div></div></div>
      <div class="kpy-foot"><span class="kpy-badge">{escape(favored.replace('_',' '))} · {escape(_text(card.get('confidence'), 'CHECK'))}</span><a class="kpy-link" href="{href}">View Full Analysis →</a></div>
    </article>'''


def sort_qb_cards(cards: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    ordered = list(cards)
    if mode == "Best Edges":
        ordered.sort(key=lambda row: (-(abs(float(row.get("edge_yards"))) if row.get("edge_yards") is not None else -1), _text(row.get("qb_name"))))
    else:
        ordered.sort(key=lambda row: (_text(row.get("game_date"), "9999-99-99"), _text(row.get("game_time"), "99:99"), _text(row.get("qb_name"))))
    return ordered


def _render_detail(st: Any, card: dict[str, Any]) -> None:
    import nfl_passing_yards_professional_v1 as deep
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<a class="kpy-link" href="?">← All Quarterbacks</a>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpy-simple-wrap"><div class="kpy-grid">{build_qb_card_html(card)}</div></div>', unsafe_allow_html=True)
    player = card.get("detail") or {}
    if not player:
        st.info("Full analysis is not available for this quarterback yet.")
        return
    st.markdown(deep.CSS, unsafe_allow_html=True)
    game_date = _text(card.get("game_date"), "")
    sections = [
        deep._decision_support(player, slot=0, game_date=game_date),
        deep._profile_card(player),
        deep._matchup_card(player),
        deep._drivers(player),
        deep._ladder(player),
    ]
    st.markdown('<div class="kpy-shell">' + "".join(sections) + "</div>", unsafe_allow_html=True)


def render_nfl_passing_yards_simple_qb_grid() -> None:
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)
    target_date = st.query_params.get("ks_py_date") or None
    payload = load_passing_yards_slate(target_date)
    if not payload.get("ready"):
        st.error(_text(payload.get("reason"), "Kyre Sports API Passing Yards slate unavailable"))
        return
    cards = list(payload.get("quarterbacks") or [])
    selected = st.query_params.get("ks_py_detail")
    if selected:
        card = next((row for row in cards if _text(row.get("player_id"), "") == str(selected)), None)
        if card:
            _render_detail(st, card)
            return
    sort_mode = st.radio("Sort quarterbacks", ["Game Time", "Best Edges"], horizontal=True, label_visibility="collapsed")
    cards = sort_qb_cards(cards, sort_mode)
    header = f'''<div class="kpy-simple-wrap"><div class="kpy-simple-head"><div><div class="kpy-simple-kicker">KYRE AI · PASSING YARDS</div><div class="kpy-simple-title">Quarterback Board</div><div class="kpy-simple-sub">{escape(_slate_label(payload))} · {len(cards)} QB cards · simple market scan</div></div></div><div class="kpy-grid">'''
    st.markdown(header + "".join(build_qb_card_html(card) for card in cards) + "</div></div>", unsafe_allow_html=True)


render_nfl_hub = lambda market="Passing Yards": render_nfl_passing_yards_simple_qb_grid()
