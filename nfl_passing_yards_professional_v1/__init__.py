"""NFL Passing Yards Page 1 S-tier V2 renderer successor overlay."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_passing_yards_professional_v1.py"
_SPEC = importlib.util.spec_from_file_location("_nfl_passing_yards_professional_v1_frozen", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Passing Yards frozen renderer unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)

_FROZEN_MARKET_BOARD = _legacy._market_board
_FROZEN_PROFILE_CARD = _legacy._profile_card
_FROZEN_MATCHUP_CARD = _legacy._matchup_card
_FROZEN_DRIVERS = _legacy._drivers
_FROZEN_LADDER = _legacy._ladder

_EXTRA_CSS = r"""
.kpy-playerunit{min-width:0}.kpy-playerunit>.kpy-ident{margin-bottom:5px;padding:5px 7px;min-height:48px}.kpy-playerunit>.kpy-ident .kpy-face{width:32px;height:32px}.kpy-playerunit>.kpy-ident .kpy-identid{max-width:190px}.kpy-playerunit>.kpy-ident .kpy-mini-logo{width:19px;height:19px}.kpy-playerunit>.kpy-qb,.kpy-playerunit>.kpy-card{height:auto}
.kpy-decision{margin-top:7px;border:1px solid #29516a;background:linear-gradient(145deg,#071724,#06111a);border-radius:13px;padding:9px;min-width:0}.kpy-decision-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.kpy-decision-title{font-size:.58rem;font-weight:950;color:#fff}.kpy-pill{display:inline-flex;align-items:center;border:1px solid #315972;border-radius:999px;padding:3px 6px;font-size:.38rem;font-weight:950;color:#dff6ff;background:#091d2b}.kpy-pill.good{border-color:#2c7550;color:#79e4a5}.kpy-pill.warn{border-color:#7b6226;color:#ffd878}.kpy-pill.under{border-color:#6b4d78;color:#e0b9ff}.kpy-quick{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.kpy-quick>div,.kpy-supportbox{border:1px solid #1c4258;border-radius:9px;background:#06121c;padding:6px}.kpy-quick b,.kpy-supportbox b{display:block;color:#fff;font-size:.62rem}.kpy-quick span,.kpy-supportbox span{display:block;color:#7890a2;font-size:.34rem;text-transform:uppercase;margin-top:2px}.kpy-thesis{border:1px solid rgba(105,214,255,.18);border-radius:10px;background:#071925;padding:8px;margin-top:6px}.kpy-thesis h4{font-size:.58rem;color:#fff;margin:0 0 4px;font-weight:950}.kpy-thesis p{font-size:.45rem;color:#a6b8c5;line-height:1.5;margin:0}.kpy-chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.kpy-chip{border:1px solid #264b61;border-radius:999px;padding:3px 6px;font-size:.34rem;color:#9fb4c2}.kpy-chip.good{border-color:#2b6548;color:#87e9ae}.kpy-supportgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:6px}.kpy-supporttitle{font-size:.4rem;font-weight:950;color:#d9edf7;letter-spacing:.04em;margin-bottom:4px}.kpy-form{display:flex;align-items:end;gap:3px;height:38px;margin-bottom:11px}.kpy-formbar{flex:1;min-width:0;background:linear-gradient(180deg,#3f9cca,#175271);border-radius:3px 3px 1px 1px;position:relative}.kpy-formbar em{position:absolute;bottom:-11px;left:50%;transform:translateX(-50%);font-style:normal;font-size:.28rem;color:#7890a2}.kpy-books{display:grid;gap:3px}.kpy-book{display:grid;grid-template-columns:1.15fr .65fr .8fr .8fr;gap:3px;border-top:1px solid rgba(105,214,255,.1);padding-top:3px;font-size:.35rem;color:#9fb4c2}.kpy-book strong{color:#edf7fc}.kpy-cta{display:flex;justify-content:space-between;align-items:center;gap:8px;border-top:1px solid rgba(105,214,255,.13);margin-top:7px;padding-top:7px}.kpy-cta a{text-decoration:none;border:1px solid #2d607d;border-radius:9px;padding:6px 8px;font-size:.4rem;font-weight:950;color:#9ee8ff;background:#071d2a}
@media(max-width:760px){.kpy-quick{grid-template-columns:repeat(2,minmax(0,1fr))}.kpy-supportgrid{grid-template-columns:1fr}.kpy-book{grid-template-columns:1.1fr .7fr .75fr .75fr}}
"""
if "</style>" in _legacy._CSS:
    _legacy._CSS = _legacy._CSS.replace("</style>", _EXTRA_CSS + "</style>", 1)
CSS = _legacy._CSS


def _player_unit(content: str) -> str:
    return f'<div class="kpy-playerunit">{content}</div>'


def _decision_support(player: dict[str, Any], *, slot: int, game_date: str) -> str:
    support = player.get("page1_decision_support") or {}
    quick = support.get("quick_verdict") or {}
    thesis = support.get("thesis") or {}
    movement = support.get("line_movement") or {}
    recent = list((support.get("recent_form") or {}).get("yards") or [])[:5]
    environment = support.get("environment") or {}
    availability = support.get("availability") or {}
    books = list(support.get("book_comparison") or [])
    risks = list(support.get("risk_flags") or [])
    side = _legacy._safe(quick.get("side"), "NO STRONG SIDE").upper()
    strength = _legacy._safe(quick.get("strength"), "CHECK").upper()
    line = _legacy._num(quick.get("line"))
    sportsbook = _legacy._safe(quick.get("sportsbook"), "Market pending")
    projection = quick.get("projection")
    edge = _legacy._num(quick.get("edge_yards"))
    confidence = _legacy._safe(quick.get("confidence"), "CHECK")
    side_class = "under" if side == "UNDER" else ""
    strength_class = "good" if strength == "STRONG" else ("warn" if strength == "MODERATE" else "")
    why_title = f"WHY {side} {_legacy._fmt(line)}" if side in {"OVER", "UNDER"} and line is not None else "WHY — NO STRONG SIDE"
    factors = []
    for factor in thesis.get("factors") or []:
        cls = " good" if factor.get("positive") else ""
        factors.append(f'<span class="kpy-chip{cls}">{_legacy.escape(_legacy._safe(factor.get("label"), "Evidence"))} · {_legacy.escape(_legacy._safe(factor.get("detail")))}</span>')
    if not factors:
        factors.append('<span class="kpy-chip">No verified supporting factors yet</span>')
    if movement.get("ready"):
        movement_html = f'<b>{_legacy._fmt(movement.get("open_line"))} → {_legacy._fmt(movement.get("current_line"))}</b><span>{_legacy.escape(_legacy._safe(movement.get("sportsbook")))} · Δ {_legacy._fmt(movement.get("delta"))}</span>'
    else:
        movement_html = '<b>BUILDING</b><span>Same-book history required</span>'
    numeric_recent = [value for value in (_legacy._num(value) for value in recent) if value is not None]
    top = max(numeric_recent + ([line] if line is not None else []) + [1.0])
    bars = ''.join(f'<div class="kpy-formbar" style="height:{max(16,min(100,int((value/top)*100)))}%"><em>{value:.0f}</em></div>' for value in numeric_recent)
    if not bars:
        bars = '<span>Verified recent form unavailable</span>'
    if environment.get("verified"):
        env_bits = [
            _legacy._safe(environment.get("venue"), "Venue CHECK"),
            _legacy._safe(environment.get("roof"), "Roof CHECK"),
            _legacy._safe(environment.get("surface"), "Surface CHECK"),
            _legacy._safe(environment.get("weather"), "Weather CHECK"),
        ]
        if _legacy._num(environment.get("rest_days")) is not None:
            env_bits.append(f'{_legacy._fmt(environment.get("rest_days"),0)} days rest')
        if _legacy._num(environment.get("temperature_f")) is not None:
            env_bits.append(f'{_legacy._fmt(environment.get("temperature_f"),0)}°F')
        if _legacy._num(environment.get("wind_mph")) is not None:
            env_bits.append(f'{_legacy._fmt(environment.get("wind_mph"),0)} mph wind')
        env_html = '<b>VERIFIED</b><span>' + _legacy.escape(' • '.join(env_bits)) + '</span>'
    else:
        env_html = '<b>CHECK</b><span>' + _legacy.escape(_legacy._safe(environment.get("reason"), "Verified game conditions unavailable")) + '</span>'
    if availability.get("verified"):
        avail_bits = [
            f'QB {_legacy._safe(availability.get("qb_status"), "CHECK")}',
            f'OL {_legacy._safe(availability.get("offensive_line"), "CHECK")}',
            f'Receivers {_legacy._safe(availability.get("receivers"), "CHECK")}',
            f'Secondary {_legacy._safe(availability.get("opponent_secondary"), "CHECK")}',
        ]
        availability_html = '<b>VERIFIED</b><span>' + _legacy.escape(' • '.join(avail_bits)) + '</span>'
    else:
        availability_html = '<b>CHECK</b><span>' + _legacy.escape(_legacy._safe(availability.get("reason"), "Verified availability unavailable")) + '</span>'
    book_rows = ''.join(
        '<div class="kpy-book">'
        f'<strong>{_legacy.escape(_legacy._safe(row.get("sportsbook"), "Book"))}</strong>'
        f'<span>{_legacy._fmt(row.get("line"))}</span><span>O {_legacy._fmt(row.get("over_odds"),0)}</span><span>U {_legacy._fmt(row.get("under_odds"),0)}</span>'
        '</div>' for row in books
    ) or '<span>No verified sportsbook comparison available</span>'
    risk_html = ''.join(f'<span class="kpy-chip">{_legacy.escape(_legacy._safe(risk))}</span>' for risk in risks) or '<span class="kpy-chip good">No material verified flags</span>'
    defense = player.get("pass_defense") or {}
    matchup_html = f'<b>{_legacy.escape(_legacy._safe(defense.get("grade"), "CHECK"))}</b><span>{_legacy.escape(_legacy._rank(defense.get("rank")))} · {_legacy._fmt(defense.get("pass_yards_allowed_per_game"))} pass yds allowed/game</span>'
    confidence_reason = _legacy._safe((player.get("distribution") or {}).get("confidence_basis"), "Verified sample and context determine confidence")
    href = "?" + urlencode({"ks_py_date": game_date, "ks_qb_slot": str(slot)})
    line_label = _legacy._fmt(line) if line is not None else "—"
    edge_label = f'{edge:+.1f}' if edge is not None else "—"
    return f'''<article class="kpy-decision">
      <div class="kpy-decision-head"><div class="kpy-decision-title">QUICK VERDICT · {_legacy.escape(_legacy._safe(player.get("qb_name"), "Quarterback"))}</div><div><span class="kpy-pill {side_class}">{_legacy.escape(side)}</span> <span class="kpy-pill {strength_class}">{_legacy.escape(strength)}</span></div></div>
      <div class="kpy-quick"><div><b>{_legacy._fmt(projection)}</b><span>Kyre projection</span></div><div><b>{line_label}</b><span>{_legacy.escape(sportsbook)} line</span></div><div><b>{edge_label}</b><span>Projection edge yds</span></div><div><b>{_legacy.escape(confidence)}</b><span>Confidence</span></div></div>
      <div class="kpy-thesis"><h4>{_legacy.escape(why_title)} PASSING YARDS</h4><p>{_legacy.escape(_legacy._safe(thesis.get("narrative"), "Verified market evidence is still building."))}</p><div class="kpy-chips">{''.join(factors)}</div></div>
      <div class="kpy-supportgrid">
        <div class="kpy-supportbox"><div class="kpy-supporttitle">LINE MOVEMENT</div>{movement_html}</div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">MATCHUP ADVANTAGE</div>{matchup_html}</div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">RECENT FORM</div><div class="kpy-form">{bars}</div><span>Last {len(numeric_recent)} verified games · line {line_label}</span></div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">CONFIDENCE</div><b>{_legacy.escape(confidence)}</b><span>{_legacy.escape(confidence_reason)}</span></div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">GAME ENVIRONMENT</div>{env_html}</div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">AVAILABILITY</div>{availability_html}</div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">BOOK COMPARISON</div><div class="kpy-books">{book_rows}</div></div>
        <div class="kpy-supportbox"><div class="kpy-supporttitle">RISK FLAGS</div><div class="kpy-chips">{risk_html}</div></div>
      </div>
      <div class="kpy-cta"><span class="kpy-note">Fast Page 1 read; deeper splits stay on Page 2.</span><a href="{_legacy.escape(href, quote=True)}">FULL QB ANALYSIS →</a></div>
    </article>'''


def _market_board(player: dict[str, Any]) -> str:
    content = _FROZEN_MARKET_BOARD(player)
    support = player.get("page1_decision_support") or {}
    game_date = _legacy._safe((support.get("page2") or {}).get("date"))
    slot = 1 if _legacy._safe(player.get("side")).casefold() == "away" else 2
    return _player_unit(content + _decision_support(player, slot=slot, game_date=game_date))


def _profile_card(player: dict[str, Any]) -> str:
    return _player_unit(_FROZEN_PROFILE_CARD(player))


def _matchup_card(player: dict[str, Any]) -> str:
    return _player_unit(_FROZEN_MATCHUP_CARD(player))


def _drivers(player: dict[str, Any]) -> str:
    return _player_unit(_FROZEN_DRIVERS(player))


def _ladder(player: dict[str, Any]) -> str:
    return _player_unit(_FROZEN_LADDER(player))


# Frozen render function resolves these names from its module globals at runtime.
_legacy._market_board = _market_board
_legacy._profile_card = _profile_card
_legacy._matchup_card = _matchup_card
_legacy._drivers = _drivers
_legacy._ladder = _ladder
_legacy._CSS = CSS
render_nfl_passing_yards_professional = _legacy.render_nfl_passing_yards_professional
