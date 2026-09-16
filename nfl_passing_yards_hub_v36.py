"""NFL Passing Yards V36 — compact dashboard presentation.

Presentation-only wrapper over certified V35. V36 re-composes the already-rendered
V34/V35 Passing Yards cards into a compact player-first dashboard. No projection,
probability, market, identity, transport, settlement, or sportsbook influence math
is recomputed or modified.
"""
from __future__ import annotations

from html import escape, unescape
import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v34 as composition
import nfl_passing_yards_hub_v35 as prior

MODEL_VERSION = "NFL PASSING YARDS V36 • COMPACT DASHBOARD"
FROZEN_PRIOR = "nfl_passing_yards_hub_v35"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
DISPLAY_ONLY = True
COMPACT_DASHBOARD = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_COMPACT_DASHBOARD_CSS = r"""
<style>
.kpass36-shell{
  --monster:#a78bfa;--info:#60a5fa;--good:#4ade80;--bad:#fb7185;--warn:#fbbf24;
  --text:#f8fafc;--muted:#94a3b8;--line:#273449;--panel:#0b1220;--panel2:#101827;
  margin:10px 0 16px;color:var(--text)
}
.kpass36-buildflag{display:flex;align-items:center;justify-content:space-between;gap:10px;
  border:1px solid #2d3748;border-radius:14px;background:#0b1220;padding:8px 10px;margin:4px 0 10px}
.kpass36-buildflag b{font-size:.72rem;color:#e9d5ff}.kpass36-buildflag span{font-size:.46rem;color:#94a3b8}
.kpass36-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:10px;align-items:center;
  border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#0b1220,#0e1626);padding:12px 14px;margin-bottom:10px;
  box-shadow:0 10px 28px rgba(0,0,0,.16)}
.kpass36-team{display:flex;align-items:center;gap:8px;min-width:0}.kpass36-team.home{justify-content:flex-end;text-align:right}
.kpass36-team img{width:34px;height:34px;object-fit:contain;border-radius:9px;background:#111827;padding:3px;box-sizing:border-box}
.kpass36-team b{font-size:.76rem;color:#f8fafc}.kpass36-center{text-align:center;min-width:170px}
.kpass36-kicker{font-size:.42rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase;color:var(--monster)}
.kpass36-matchlabel{font-size:.78rem;font-weight:950;color:#f8fafc;margin-top:2px;white-space:nowrap}
.kpass36-sub{font-size:.43rem;color:var(--muted);margin-top:3px}
.kpass36-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:start}
.kpass36-player{min-width:0;border:1px solid var(--line);border-radius:18px;background:linear-gradient(155deg,#0b1220,#0a111d);
  padding:11px;box-shadow:0 8px 24px rgba(0,0,0,.13)}
.kpass36-id{display:flex;align-items:center;gap:9px}.kpass36-head{width:54px;height:54px;flex:0 0 54px;border-radius:50%;
  overflow:hidden;background:#111827;border:1px solid #334155}.kpass36-head img{width:100%;height:100%;object-fit:cover;object-position:center top}
.kpass36-ident{min-width:0;flex:1}.kpass36-name{font-size:.9rem;font-weight:950;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass36-meta{font-size:.48rem;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass36-logo img{width:36px;height:36px;object-fit:contain;background:#111827;border-radius:9px;padding:3px;box-sizing:border-box}
.kpass36-hero{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;margin-top:9px}
.kpass36-metric{min-width:0;border:1px solid #243147;border-radius:10px;background:#0c1524;padding:7px 6px}
.kpass36-metric b{display:block;font-size:.68rem;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass36-metric span{display:block;font-size:.36rem;font-weight:900;letter-spacing:.035em;text-transform:uppercase;color:#7f8ea3;margin-top:3px}
.kpass36-metric.monster b{color:var(--monster)}.kpass36-metric.info b{color:var(--info)}.kpass36-metric.good b{color:var(--good)}
.kpass36-metric.bad b{color:var(--bad)}.kpass36-metric.warn b{color:var(--warn)}
.kpass36-why{margin-top:9px;border:1px solid #243147;border-radius:12px;background:#0a1321;padding:8px}
.kpass36-whytitle{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:6px}
.kpass36-whytitle b{font-size:.56rem;color:#e9d5ff}.kpass36-whytitle span{font-size:.38rem;color:#718096}
.kpass36-reasons{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px}
.kpass36-reason{min-width:0;border-radius:8px;background:#0e1726;padding:6px;border-left:2px solid var(--info)}
.kpass36-reason.monster{border-left-color:var(--monster)}.kpass36-reason.good{border-left-color:var(--good)}
.kpass36-reason.bad{border-left-color:var(--bad)}.kpass36-reason.warn{border-left-color:var(--warn)}
.kpass36-reason b{display:block;font-size:.39rem;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8}
.kpass36-reason span{display:block;font-size:.48rem;font-weight:850;color:#e5e7eb;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpass36-evidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:9px}
.kpass36-evidence details{min-width:0;border:1px solid #243147;border-radius:10px;background:#0a1320;overflow:hidden}
.kpass36-evidence summary{cursor:pointer;list-style:none;padding:7px 8px;font-size:.46rem;font-weight:900;color:#cbd5e1}
.kpass36-evidence summary::-webkit-details-marker{display:none}.kpass36-evidence summary:after{content:"+";float:right;color:#64748b}
.kpass36-evidence details[open] summary:after{content:"−"}.kpass36-detail{padding:0 7px 7px}
.kpass36-detail .kpass29-card,.kpass36-detail .kpass30-profile,.kpass36-detail .kpy-defense,.kpass36-detail .kpy-pressure,
.kpass36-detail .kpy-personnel,.kpass36-detail .kpy-env,.kpass36-detail .kpy-proj,.kpass36-detail .kpy8-card,
.kpass36-detail .kpy9-card,.kpass36-detail .kpy10-card{margin:0!important;width:auto!important;box-sizing:border-box!important;border-color:#2b3a50!important}
.kpass36-method{font-size:.46rem;line-height:1.55;color:#94a3b8;padding:5px 2px}.kpass36-method strong{color:#e9d5ff}
.kpass36-missing{font-size:.46rem;color:#7f8ea3;border:1px dashed #334155;border-radius:8px;padding:8px}
.kpy-head,.kpy-strip{border-color:#2b3a50!important;background:#0b1220!important}
.kpy-title span{color:#c4b5fd!important}.kpy-chip{border-color:#334155!important;background:#111827!important;color:#bfdbfe!important}
.kpy-stat{border-color:#243147!important;background:#0c1524!important}
@media(max-width:1100px){.kpass36-hero{grid-template-columns:repeat(3,minmax(0,1fr))}.kpass36-reasons{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:860px){.kpass36-grid{grid-template-columns:1fr}.kpass36-matchup{grid-template-columns:1fr auto 1fr}.kpass36-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kpass36-hero .kpass36-metric:first-child{grid-column:1/-1}.kpass36-reasons{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.kpass36-matchup{grid-template-columns:1fr}.kpass36-team,.kpass36-team.home{justify-content:center;text-align:center}.kpass36-center{order:-1}
  .kpass36-evidence{grid-template-columns:1fr}.kpass36-reasons{grid-template-columns:1fr 1fr}.kpass36-player{padding:9px}}
</style>
"""


def _plain(value: Any, default: str = "—") -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    return text or default


def _class_inner(fragment: str, class_name: str) -> str:
    pattern = re.compile(
        rf'<(?P<tag>[a-zA-Z0-9]+)[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(?P<body>.*?)</(?P=tag)>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(str(fragment or ""))
    return match.group("body") if match else ""


def _class_text(fragment: str, class_name: str, default: str = "—") -> str:
    return _plain(_class_inner(fragment, class_name), default)


def _img_from(fragment: str, *, class_name: str | None = None) -> str:
    text = str(fragment or "")
    if class_name:
        match = re.search(
            rf'<img\b[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>',
            text,
            re.IGNORECASE,
        )
        return match.group(0) if match else ""
    match = re.search(r"<img\b[^>]*>", text, re.IGNORECASE)
    return match.group(0) if match else ""


def _metric_value(fragment: str, label: str, default: str = "—") -> str:
    escaped_label = re.escape(label)
    patterns = (
        rf"<div[^>]*>\s*<b[^>]*>(?P<value>.*?)</b>\s*<span[^>]*>\s*{escaped_label}\s*</span>\s*</div>",
        rf"<div[^>]*>\s*<b[^>]*>(?P<value>.*?)</b>\s*{escaped_label}\s*</div>",
    )
    for pattern in patterns:
        match = re.search(pattern, str(fragment or ""), re.IGNORECASE | re.DOTALL)
        if match:
            return _plain(match.group("value"), default)
    return default


def _weather_value(fragment: str) -> str:
    match = re.search(r"weather:\s*<b[^>]*>(.*?)</b>", str(fragment or ""), re.IGNORECASE | re.DOTALL)
    return _plain(match.group(1), "CHECK") if match else "CHECK"


def _tone_for_context(value: str) -> str:
    upper = str(value or "").upper()
    if any(token in upper for token in ("RED", "NEGATIVE", "POOR", "OUT", "HIGH PRESSURE")):
        return "bad"
    if any(token in upper for token in ("WATCH", "CHECK", "CAUTION", "LIMITED", "QUESTIONABLE")):
        return "warn"
    if any(token in upper for token in ("GREEN", "FAVORABLE", "READY", "CLEAR", "GOOD")):
        return "good"
    return "info"


def _grade_tone(market_fragment: str) -> str:
    grade_text = _class_text(market_fragment, "kpy10-grade", "CHECK").upper()
    grade = grade_text.split("•", 1)[0].strip()
    if grade in {"A", "B"}:
        return "good"
    if grade == "C":
        return "warn"
    if grade in {"PASS", "CHECK"}:
        return "info"
    return "monster"


def _confidence_tone(value: str) -> str:
    upper = str(value or "").upper()
    if "HIGH" in upper:
        return "good"
    if "MEDIUM" in upper:
        return "warn"
    if "LOW" in upper:
        return "bad"
    return "info"


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _team_token(identity_fragment: str) -> str:
    meta = _class_text(identity_fragment, "kpass29-meta", "NFL")
    parts = [part.strip() for part in meta.split("•")]
    if len(parts) >= 2:
        matchup = parts[1].split()
        if matchup:
            return matchup[0].upper()
    return "NFL"


def _headshot(identity_fragment: str) -> str:
    return _img_from(_class_inner(identity_fragment, "kpass29-head"))


def _team_logo(identity_fragment: str) -> str:
    return _img_from(identity_fragment, class_name="kpass29-logo")


def _selected_matchup_label() -> str:
    try:
        label = str(st.session_state.get("nfl_passing_yards_v8_matchup") or "").strip()
    except Exception:
        label = ""
    return label or "Verified NFL matchup"


def _compact_build_banner_v36() -> str:
    return (
        '<div class="kpass36-buildflag">'
        '<b>👹 Passing Yards • Compact Dashboard</b>'
        '<span>Certified values preserved • V28 engine frozen • sportsbook projection influence 0.0%</span>'
        '</div>'
    )


def _detail(label: str, body: str) -> str:
    body = body or '<div class="kpass36-missing">Certified evidence is unavailable for this selected matchup.</div>'
    return f'<details><summary>{escape(label)}</summary><div class="kpass36-detail">{body}</div></details>'


def _methodology_detail() -> str:
    return _detail(
        "Methodology",
        '<div class="kpass36-method"><strong>Presentation-only.</strong> This compact dashboard reuses the exact '
        'certified identity, profile, defense, pressure, personnel, environment, projection, uncertainty, '
        'distribution, probability, and market outputs already produced by V35/V34/V33/V28. No analytical '
        'value is recomputed here. Sportsbook projection influence remains <strong>0.0%</strong>; stake sizing '
        'remains <strong>OFF</strong>.</div>',
    )


def _player_dashboard(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index)
    projection = _piece(captured, "projection", index)
    market = _piece(captured, "market", index)
    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)

    name = _class_text(identity, "kpass29-name", f"Quarterback {index + 1}")
    meta = _class_text(identity, "kpass29-meta", "Verified quarterback")
    headshot = _headshot(identity)
    logo = _team_logo(identity)

    projection_yards = _metric_value(projection, "Baseline Pass Yards")
    market_line = _metric_value(market, "Market Line")
    edge = _metric_value(market, "Model edge Over / Under")
    lean = _metric_value(market, "Final Lean", "PASS")
    confidence = _metric_value(market, "Model Confidence", "CHECK")
    attempts = _metric_value(projection, "Expected Attempts")
    ypa = _metric_value(projection, "Expected YPA")
    pressure_context = _metric_value(projection, "Pressure context • not numerically adjusted", "CHECK")
    personnel_context = _metric_value(projection, "Personnel context • not numerically adjusted", "CHECK")
    weather = _weather_value(projection)

    market_tone = _grade_tone(market)
    confidence_tone = _confidence_tone(confidence)

    head_html = f'<div class="kpass36-head">{headshot}</div>' if headshot else '<div class="kpass36-head"></div>'
    logo_html = f'<div class="kpass36-logo">{logo}</div>' if logo else ""

    reasons = (
        f'<div class="kpass36-reason monster"><b>Volume</b><span>{escape(attempts)} exp. attempts</span></div>'
        f'<div class="kpass36-reason monster"><b>Efficiency</b><span>{escape(ypa)} exp. YPA</span></div>'
        f'<div class="kpass36-reason {_tone_for_context(pressure_context)}"><b>Pressure</b><span>{escape(pressure_context)}</span></div>'
        f'<div class="kpass36-reason {_tone_for_context(personnel_context)}"><b>Personnel</b><span>{escape(personnel_context)}</span></div>'
        f'<div class="kpass36-reason {_tone_for_context(weather)}"><b>Weather</b><span>{escape(weather)}</span></div>'
    )

    evidence = "".join(
        (
            _detail("Passing Profile", profile),
            _detail("Opponent Defense", defense),
            _detail("Pressure", pressure),
            _detail("Weapons/Injuries", personnel),
            _detail("Environment", environment),
            _detail("Projection Engine", projection + context),
            _detail("Distribution", distribution),
            _detail("Market Math", market),
            _methodology_detail(),
        )
    )

    return (
        f'<article class="kpass36-player" data-player-card-index="{index}">'
        '<div class="kpass36-id">'
        f'{head_html}<div class="kpass36-ident"><div class="kpass36-name">{escape(name)}</div>'
        f'<div class="kpass36-meta">{escape(meta)}</div></div>{logo_html}</div>'
        '<div class="kpass36-hero">'
        f'<div class="kpass36-metric monster"><b>{escape(projection_yards)}</b><span>Monster Projection</span></div>'
        f'<div class="kpass36-metric info"><b>{escape(market_line)}</b><span>Market Line</span></div>'
        f'<div class="kpass36-metric {market_tone}"><b>{escape(edge)}</b><span>Edge O/U</span></div>'
        f'<div class="kpass36-metric {market_tone}"><b>{escape(lean)}</b><span>Lean</span></div>'
        f'<div class="kpass36-metric {confidence_tone}"><b>{escape(confidence)}</b><span>Confidence</span></div>'
        '</div>'
        '<div class="kpass36-why"><div class="kpass36-whytitle"><b>Why This Projection</b>'
        '<span>Certified context • no sportsbook adjustment</span></div>'
        f'<div class="kpass36-reasons">{reasons}</div></div>'
        f'<div class="kpass36-evidence">{evidence}</div>'
        '</article>'
    )


def _matchup_header(captured: dict[str, list[str]], matchup_label: str) -> str:
    away_identity = _piece(captured, "identity", 0)
    home_identity = _piece(captured, "identity", 1)
    away = _team_token(away_identity)
    home = _team_token(home_identity)
    away_logo = _team_logo(away_identity)
    home_logo = _team_logo(home_identity)
    away_logo_html = away_logo if away_logo else ""
    home_logo_html = home_logo if home_logo else ""
    return (
        '<div class="kpass36-matchup">'
        f'<div class="kpass36-team">{away_logo_html}<b>{escape(away)}</b></div>'
        '<div class="kpass36-center"><div class="kpass36-kicker">NFL Passing Yards</div>'
        f'<div class="kpass36-matchlabel">{escape(matchup_label)}</div>'
        '<div class="kpass36-sub">Compact model + market dashboard</div></div>'
        f'<div class="kpass36-team home"><b>{escape(home)}</b>{home_logo_html}</div>'
        '</div>'
    )


def _compact_dashboard_html(
    captured: dict[str, list[str]],
    *,
    matchup_label: str | None = None,
) -> str:
    label = str(matchup_label or _selected_matchup_label()).strip() or "Verified NFL matchup"
    return (
        '<section class="kpass36-shell" data-passing-dashboard="compact-v36">'
        f'{_matchup_header(captured, label)}'
        '<div class="kpass36-grid">'
        f'{_player_dashboard(captured, 0)}'
        f'{_player_dashboard(captured, 1)}'
        '</div></section>'
    )


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V35 through a compact presentation-only V34 composition hook."""
    original_css = composition._PLAYER_CARD_CSS
    original_builder = composition._combined_player_cards_html
    original_banner = composition._visual_build_banner_v34

    composition._PLAYER_CARD_CSS = _COMPACT_DASHBOARD_CSS
    composition._combined_player_cards_html = _compact_dashboard_html
    composition._visual_build_banner_v34 = _compact_build_banner_v36
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        composition._PLAYER_CARD_CSS = original_css
        composition._combined_player_cards_html = original_builder
        composition._visual_build_banner_v34 = original_banner


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V36 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "COMPACT_DASHBOARD",
    "DISPLAY_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_COMPACT_DASHBOARD_CSS",
    "_compact_dashboard_html",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
