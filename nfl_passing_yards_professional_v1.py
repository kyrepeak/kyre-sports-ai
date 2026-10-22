"""NFL Passing Yards professional decision-first analytics page."""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_passing_yards_gateway_v1 as gateway

MODEL_VERSION = "NFL PASSING YARDS PROFESSIONAL V1"

_CSS = r"""
<style>
.kpy-pro,.kpy-pro *{box-sizing:border-box}.kpy-pro{--panel:#071521;--panel2:#091b2a;--line:#21435a;--soft:#8aa2b4;--text:#f5f9fc;--cyan:#69d6ff;--green:#79efad;--amber:#f2c96f;--red:#ff8a8a}
.kpy-hero{border:1px solid #2a526a;background:radial-gradient(circle at 15% 0,rgba(52,169,235,.12),transparent 33%),linear-gradient(135deg,#07131e,#081c2b);border-radius:18px;padding:14px 15px;margin:0 0 10px;box-shadow:0 16px 40px rgba(0,0,0,.22)}
.kpy-kicker{font-size:.52rem;font-weight:950;letter-spacing:.14em;color:var(--cyan);text-transform:uppercase}.kpy-title{font-size:1.35rem;font-weight:950;color:var(--text);letter-spacing:-.03em;margin-top:3px}.kpy-sub{font-size:.62rem;color:var(--soft);margin-top:4px}.kpy-match{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:12px;padding-top:10px;border-top:1px solid rgba(105,214,255,.15)}
.kpy-team{display:flex;align-items:center;gap:7px;font-weight:950;color:#fff}.kpy-logo{width:34px;height:34px;border-radius:10px;border:1px solid #31536a;display:grid;place-items:center;background:#0a1b29;font-size:.65rem}.kpy-vs{font-size:.65rem;color:#7290a5;font-weight:900}.kpy-kick{font-size:.52rem;color:#849bad;text-align:right}
.kpy-board{border:1px solid var(--line);background:#06121c;border-radius:16px;padding:11px;margin-bottom:10px}.kpy-sectionhead{display:flex;align-items:end;justify-content:space-between;gap:8px;margin-bottom:8px}.kpy-sectiontitle{font-size:.82rem;font-weight:950;color:#f4f9fc}.kpy-sectionsub{font-size:.49rem;color:#728b9e;margin-top:2px}.kpy-source{font-size:.45rem;color:#77a8c7}
.kpy-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.kpy-qb{border:1px solid #264a61;background:linear-gradient(145deg,#081724,#07131d);border-radius:14px;padding:10px;min-width:0}.kpy-qbtop{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.kpy-name{font-size:.9rem;font-weight:950;color:#fff}.kpy-teamline{font-size:.47rem;color:#7f98aa;margin-top:2px}.kpy-grade{border-radius:999px;padding:4px 7px;font-size:.43rem;font-weight:950;border:1px solid #4b6271;color:#b9c7d1;white-space:nowrap}.kpy-grade.a,.kpy-grade.b,.kpy-grade.favorable{color:var(--green);border-color:#317b58;background:#08281b}.kpy-grade.c,.kpy-grade.medium{color:var(--amber);border-color:#76623a;background:#2a2311}.kpy-grade.tough{color:var(--red);border-color:#814545;background:#2b1315}.kpy-grade.pass{color:#9ed6ff;border-color:#3d6c8d;background:#092236}
.kpy-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:8px}.kpy-metric{border:1px solid #193a50;background:#05111a;border-radius:10px;padding:8px 7px;min-width:0}.kpy-metric b{font-size:.9rem;color:#fff;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-metric span{font-size:.38rem;color:#6f8799;text-transform:uppercase;display:block;margin-top:3px}.kpy-verdict{margin-top:7px;border-top:1px solid #193348;padding-top:7px;display:flex;justify-content:space-between;align-items:center;gap:7px}.kpy-lean{font-size:.66rem;font-weight:950;color:#eaf6fc}.kpy-marketmeta{font-size:.43rem;color:#748da0;margin-top:2px}
.kpy-compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0 0 10px}.kpy-card{border:1px solid #20465e;background:#07131e;border-radius:14px;padding:10px}.kpy-cardtitle{font-size:.66rem;font-weight:950;color:#f1f7fa;margin-bottom:7px}.kpy-statrow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.kpy-small{border:1px solid #17364a;border-radius:9px;padding:7px;background:#061019}.kpy-small b{display:block;color:#f7fbfd;font-size:.72rem}.kpy-small span{display:block;color:#71899b;font-size:.37rem;margin-top:2px;text-transform:uppercase}.kpy-note{font-size:.47rem;line-height:1.45;color:#7b93a5;margin-top:7px}.kpy-drivers{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.kpy-driver{border:1px solid #1c4258;border-radius:10px;padding:8px;background:#06121c}.kpy-driver b{display:block;color:#f7fbfd;font-size:.72rem}.kpy-driver span{display:block;color:#7590a3;font-size:.39rem;margin-top:2px}.kpy-ladder{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}.kpy-rung{border:1px solid #1b3b50;border-radius:9px;padding:7px 5px;text-align:center;background:#06121b}.kpy-rung b{display:block;color:#fff;font-size:.68rem}.kpy-rung span{font-size:.38rem;color:#7190a5}.kpy-method{font-size:.55rem;line-height:1.55;color:#93a6b4}.kpy-method strong{color:#edf7fc}
@media(max-width:760px){.kpy-grid2,.kpy-compare{grid-template-columns:1fr}.kpy-drivers{grid-template-columns:repeat(2,minmax(0,1fr))}.kpy-ladder{grid-template-columns:repeat(3,minmax(0,1fr))}.kpy-title{font-size:1.16rem}}
.kpy-ident{display:flex;align-items:center;gap:8px;margin:0 0 8px;padding:7px 8px;border:1px solid rgba(105,214,255,.16);border-radius:11px;background:#071724}.kpy-face{width:38px;height:38px;border-radius:50%;object-fit:cover;border:1px solid #31536a;background:#0a1b29}.kpy-identmeta{min-width:0}.kpy-identname{font-size:.62rem;font-weight:950;color:#fff}.kpy-identid{font-size:.42rem;color:#7894a8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-mini-logo{width:22px;height:22px;object-fit:contain;margin-left:auto}.kpy-logo img{width:29px;height:29px;object-fit:contain}</style>
"""


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    number = _num(value)
    return f"{number:.{digits}f}{suffix}" if number is not None else "—"


def _pct(value: Any) -> str:
    number = _num(value)
    return f"{100.0 * number:.1f}%" if number is not None else "—"


def _rank(value: Any) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "Rank unavailable"
    suffix = "th" if 10 <= n % 100 <= 20 else {1:"st",2:"nd",3:"rd"}.get(n % 10,"th")
    return f"{n}{suffix} in NFL"


def _grade_class(value: Any) -> str:
    token = _safe(value, "check").lower().split()[0]
    return token if token in {"a","b","c","pass","favorable","medium","tough"} else ""



def _team_badge(*, team_name: str, team_abbr: str, logo_url: str | None) -> str:
    name = escape(_safe(team_name, team_abbr or "Team"))
    abbr = escape(_safe(team_abbr, ""))
    if logo_url:
        visual = f'<span class="kpy-logo"><img src="{escape(str(logo_url), quote=True)}" alt="{name} logo"></span>'
    else:
        visual = f'<span class="kpy-logo">{abbr}</span>'
    return f'<div class="kpy-team">{visual}{name}</div>'


def _identity_strip(player: dict[str, Any], *, opponent: bool = False) -> str:
    identity = player.get("identity_visuals") or {}
    player_id = _safe(identity.get("canonical_player_id") or player.get("player_id"), "ID unavailable")
    qb_name = escape(_safe(player.get("qb_name"), "Quarterback"))
    headshot = identity.get("headshot_url") if identity.get("identity_verified") else None
    if headshot:
        face = f'<img class="kpy-face" src="{escape(str(headshot), quote=True)}" alt="{qb_name} headshot">'
    else:
        face = '<span class="kpy-face"></span>'
    team_logo = identity.get("team_logo_url")
    opponent_logo = identity.get("opponent_logo_url") if opponent else None
    logos = []
    if team_logo:
        logos.append(f'<img class="kpy-mini-logo" src="{escape(str(team_logo), quote=True)}" alt="team logo">')
    if opponent_logo:
        logos.append(f'<img class="kpy-mini-logo" src="{escape(str(opponent_logo), quote=True)}" alt="opponent logo">')
    return f'<div class="kpy-ident">{face}<div class="kpy-identmeta"><div class="kpy-identname">{qb_name}</div><div class="kpy-identid">{escape(player_id)}</div></div>{"".join(logos)}</div>'

def _market_board(player: dict[str, Any]) -> str:
    identity = _identity_strip(player, opponent=False)
    ctx = player.get("context_projection") or {}
    dist = player.get("distribution") or {}
    market = player.get("market") or {}
    ev = player.get("market_evaluation") or {}
    defense = player.get("pass_defense") or {}
    projection = ctx.get("context_projection_yards")
    line = market.get("line")
    under = ev.get("model_under_probability")
    over = ev.get("model_over_probability")
    lean = _safe(ev.get("lean"), "MARKET PENDING")
    grade = _safe(ev.get("grade"), "CHECK")
    confidence = _safe(dist.get("confidence"), "CHECK")
    matchup_grade = _safe(defense.get("grade"), "CHECK")
    return identity + f'''<article class="kpy-qb">
      <div class="kpy-qbtop"><div><div class="kpy-name">{escape(_safe(player.get("qb_name"),"Quarterback"))}</div><div class="kpy-teamline">{escape(_safe(player.get("team_abbr")))} vs {escape(_safe(player.get("opponent_abbr")))} • {escape(confidence)} confidence</div></div><span class="kpy-grade {_grade_class(grade)}">{escape(grade)}</span></div>
      <div class="kpy-metrics"><div class="kpy-metric"><b>{_fmt(projection)}</b><span>Kyre Projection</span></div><div class="kpy-metric"><b>{_fmt(line)}</b><span>Market Line</span></div><div class="kpy-metric"><b>{_pct(under)}</b><span>Under Probability</span></div></div>
      <div class="kpy-verdict"><div><div class="kpy-lean">{escape(lean)}</div><div class="kpy-marketmeta">Over {_pct(over)} • Under {_pct(under)} • {_rank(defense.get("rank"))}</div></div><span class="kpy-grade {_grade_class(matchup_grade)}">{escape(matchup_grade)} MATCHUP</span></div>
    </article>'''


def _profile_card(player: dict[str, Any]) -> str:
    identity = _identity_strip(player, opponent=False)
    p = player.get("profile") or {}
    return identity + f'''<article class="kpy-card"><div class="kpy-cardtitle">{escape(_safe(player.get("qb_name")))} • PASSING PROFILE</div><div class="kpy-statrow"><div class="kpy-small"><b>{_fmt(p.get("passing_yards_per_game"))}</b><span>Yards / Game</span></div><div class="kpy-small"><b>{_fmt(p.get("attempts_per_game"))}</b><span>Attempts / Game</span></div><div class="kpy-small"><b>{_fmt(p.get("yards_per_attempt"),2)}</b><span>Yards / Attempt</span></div></div><div class="kpy-note">Recent 3: {_fmt((p.get("recent3_yards") or 0) / min(3,p.get("games") or 1) if p.get("recent3_yards") is not None else None)} yds/game • {_fmt(p.get("completion_pct"),1,"%")} completion • {_safe(p.get("games"),"0")} verified games.</div></article>'''


def _matchup_card(player: dict[str, Any]) -> str:
    identity = _identity_strip(player, opponent=True)
    d = player.get("pass_defense") or {}
    h = player.get("qb_vs_team_history") or {}
    grade = _safe(d.get("grade"), "CHECK")
    if h.get("available"):
        history = f'{h.get("games")} meetings • {_fmt(h.get("avg_passing_yards"))} avg yds • {_fmt(h.get("avg_attempts"))} avg attempts • {_fmt(h.get("completion_pct"),1,"%")} completion'
    else:
        history = escape(_safe(h.get("message"), "No verified prior matchup history"))
    return identity + f'''<article class="kpy-card"><div class="kpy-cardtitle">PASS DEFENSE RANK • <span class="kpy-grade {_grade_class(grade)}">{escape(grade)}</span></div><div class="kpy-statrow"><div class="kpy-small"><b>{escape(_rank(d.get("rank")))}</b><span>Pass Yards Rank</span></div><div class="kpy-small"><b>{_fmt(d.get("pass_yards_allowed_per_game"))}</b><span>Yds Allowed / Game</span></div><div class="kpy-small"><b>{_fmt(d.get("recent3_pass_yards_allowed"))}</b><span>Recent 3 Allowed</span></div></div><div class="kpy-note"><strong>QB VS TEAM HISTORY:</strong> {history}</div></article>'''


def _drivers(player: dict[str, Any]) -> str:
    identity = _identity_strip(player, opponent=False)
    why = player.get("why") or {}
    pieces = []
    for key in ("volume","efficiency","pressure","defense"):
        row = why.get(key) or {}
        value = row.get("value")
        shown = _fmt(value,2) if key == "efficiency" else _fmt(value)
        pieces.append(f'<div class="kpy-driver"><b>{shown}</b><span>{escape(_safe(row.get("label"),key.title()))}</span></div>')
    return identity + "".join(pieces)


def _ladder(player: dict[str, Any]) -> str:
    identity = _identity_strip(player, opponent=False)
    rows = (player.get("distribution") or {}).get("thresholds") or []
    useful = [row for row in rows if row.get("ready") and int(float(row.get("threshold") or 0)) in {200,225,250,275,300}]
    if not useful:
        return identity + '<div class="kpy-note">Probability ladder unavailable until at least three verified recent games establish observed variance.</div>'
    return identity + '<div class="kpy-ladder">' + ''.join(f'<div class="kpy-rung"><b>{_pct(row.get("over_probability"))}</b><span>{int(float(row.get("threshold")))}+ yards</span></div>' for row in useful) + '</div>'


def render_nfl_passing_yards_professional() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    raw_date = st.query_params.get("date")
    if isinstance(raw_date, (list, tuple)):
        raw_date = raw_date[-1] if raw_date else None
    payload = gateway.load_passing_yards_page(str(raw_date) if raw_date else None)
    if not payload.get("ready"):
        st.error(_safe(payload.get("reason"), "NFL Passing Yards data is temporarily unavailable."))
        return
    game = payload.get("game") or {}
    players = list(payload.get("players") or [])
    provenance = payload.get("provenance") or {}
    source_time = _safe(payload.get("source_timestamp"), "timestamp unavailable")
    st.markdown(f'''<div class="kpy-pro"><section class="kpy-hero"><div class="kpy-kicker">KYRE SPORTS AI • NFL PLAYER PROPS</div><div class="kpy-title">KYRE AI PASSING YARDS</div><div class="kpy-sub">Decision-first quarterback analytics • projection math completes before sportsbook comparison</div><div class="kpy-match">{_team_badge(team_name=_safe(game.get("away_name")), team_abbr=_safe(game.get("away")), logo_url=game.get("away_logo_url"))}<div class="kpy-vs">@</div>{_team_badge(team_name=_safe(game.get("home_name")), team_abbr=_safe(game.get("home")), logo_url=game.get("home_logo_url"))}<div class="kpy-kick">{escape(_safe(game.get("date")))}<br>{escape(_safe(game.get("kickoff"),"Kickoff TBD"))}</div></div></section></div>''', unsafe_allow_html=True)
    st.markdown('<div class="kpy-pro"><section class="kpy-board"><div class="kpy-sectionhead"><div><div class="kpy-sectiontitle">KYRE AI MARKET BOARD</div><div class="kpy-sectionsub">Projection • market line • probability • confidence • matchup</div></div><div class="kpy-source">Freshness '+escape(source_time)+'</div></div><div class="kpy-grid2">'+''.join(_market_board(p) for p in players)+'</div></section></div>', unsafe_allow_html=True)
    st.markdown('<div class="kpy-pro"><div class="kpy-compare">'+''.join(_profile_card(p) for p in players)+'</div><div class="kpy-compare">'+''.join(_matchup_card(p) for p in players)+'</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="kpy-pro"><section class="kpy-board"><div class="kpy-sectiontitle">WHY THIS PROJECTION</div><div class="kpy-sectionsub">The strongest model drivers, without the raw engineering tables</div></section></div>', unsafe_allow_html=True)
    for player in players:
        st.markdown(f'<div class="kpy-pro"><section class="kpy-card"><div class="kpy-cardtitle">{escape(_safe(player.get("qb_name")))}</div><div class="kpy-drivers">{_drivers(player)}</div></section></div>', unsafe_allow_html=True)
    st.markdown('<div class="kpy-pro"><section class="kpy-board"><div class="kpy-sectiontitle">PROBABILITY LADDER</div><div class="kpy-sectionsub">Model probability of reaching common passing-yard thresholds</div></section></div>', unsafe_allow_html=True)
    for player in players:
        st.markdown(f'<div class="kpy-pro"><section class="kpy-card"><div class="kpy-cardtitle">{escape(_safe(player.get("qb_name")))}</div>{_ladder(player)}</section></div>', unsafe_allow_html=True)
    with st.expander("MODEL DETAILS & METHODOLOGY", expanded=False):
        st.markdown('<div class="kpy-pro kpy-method"><strong>Model structure.</strong> Passing volume and passing efficiency are blended independently, then multiplied. Opponent defense and recent form use verified normalized data only. Pressure is the only bounded numerical context adjustment; personnel/weather/rest remain qualitative unless a future certified coefficient exists.<br><br><strong>Market separation.</strong> Sportsbook line and price are read only after the projection and probability distribution are complete. Sportsbook projection influence is permanently 0.0%. Missing values remain unavailable rather than becoming zeros.<br><br><strong>Sources.</strong> The application talks only to Kyre Sports API. Provider routing, canonical identity, fallback, provenance, and freshness are server-owned.</div>', unsafe_allow_html=True)
        st.json({"game_id":game.get("game_id"),"provenance":provenance,"routing":payload.get("routing"),"source_timestamp":source_time}, expanded=False)


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("Professional Passing Yards page renders Passing Yards only")
    return render_nfl_passing_yards_professional()


__all__ = ["MODEL_VERSION","render_nfl_hub","render_nfl_passing_yards_professional"]
