"""NFL Game Totals Page 1 S-tier V1.

Presentation-only successor over the certified V10 + compact stack. It removes
engineering/debug hierarchy from the visible Page 1 and keeps the certified deep
analytics behind one collapsed Full Analysis disclosure. Model math, market
routing, and sportsbook projection influence are unchanged.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import pandas as pd
import streamlit as st

import nfl_game_totals_compact_layout_v1 as compact
import nfl_game_totals_hub_v10 as v10

MODEL_VERSION = "NFL GAME TOTALS PAGE1 S-TIER V1"
SPORTSBOOK_PROJECTION_INFLUENCE = v10.SPORTSBOOK_PROJECTION_INFLUENCE
STAKE_SIZING_ENABLED = v10.STAKE_SIZING_ENABLED
WAGER_ACTIONS_ENABLED = v10.WAGER_ACTIONS_ENABLED

v9 = v10.v9
v8 = v9.v8
v7 = v8.v7
v6 = v7.v6
v5 = v6.v5
v4 = v5.v4
v3 = v4.v3
v2 = v3.v2
foundation = v2.foundation
mobile = v9.mobile

_CSS = r'''
<style>
.kgt-s1{max-width:980px;margin:0 auto;color:#edf5fa}.kgt-s1 *{box-sizing:border-box}
.kgt-s1-head{display:flex;justify-content:space-between;gap:14px;align-items:end;margin:4px 0 12px}.kgt-s1-title{font-size:1.65rem;font-weight:950;letter-spacing:.04em}.kgt-s1-sub{color:#91a8b8;font-size:.74rem;margin-top:3px}
.kgt-s1-card{border:1px solid #22516b;border-radius:20px;background:linear-gradient(180deg,#071a25,#08141c);padding:16px;margin:12px 0;box-shadow:0 16px 38px rgba(0,0,0,.22)}
.kgt-s1-match{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding-bottom:12px;border-bottom:1px solid #1e4052}.kgt-s1-team{display:flex;align-items:center;gap:10px}.kgt-s1-team.right{justify-content:flex-end;text-align:right}.kgt-s1-team img{width:58px;height:58px;object-fit:contain}.kgt-s1-team b{display:block;font-size:.88rem}.kgt-s1-team span{display:block;color:#7890a0;font-size:.60rem;margin-top:2px}.kgt-s1-at{color:#4daee2;font-weight:950}.kgt-s1-meta{text-align:center;color:#91a8b8;font-size:.61rem;margin:8px 0 12px}
.kgt-s1-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.kgt-s1-stat{border:1px solid #274c60;border-radius:13px;background:#081720;padding:10px;min-height:83px}.kgt-s1-stat span{display:block;color:#7895a7;font-size:.49rem;font-weight:950;letter-spacing:.08em}.kgt-s1-stat b{display:block;font-size:1.15rem;margin-top:5px}.kgt-s1-stat.kyre{border-color:#625393}.kgt-s1-stat.kyre b{color:#c0a9ff}.kgt-s1-stat.edge b{color:#61e6bd}.kgt-s1-stat.lean.over b{color:#ffb85f}.kgt-s1-stat.lean.under b{color:#75e5c6}.kgt-s1-stat.lean.pass b{color:#d0c7dd}
.kgt-s1-market{display:grid;grid-template-columns:1.3fr .9fr;gap:8px;margin-top:8px}.kgt-s1-strip{border:1px solid #274c60;border-radius:12px;background:#07151d;padding:9px 11px;color:#a9bac5;font-size:.63rem}.kgt-s1-strip b{color:#f1f6f9}.kgt-s1-over{color:#ffb35e!important}.kgt-s1-under{color:#67dfbd!important}.kgt-s1-weather{margin-top:8px}
.kgt-s1-why{border:1px solid #274c60;border-radius:13px;background:#07151d;padding:11px;margin-top:9px}.kgt-s1-why h4{margin:0 0 7px;font-size:.70rem;letter-spacing:.05em}.kgt-s1-reason{display:flex;gap:9px;align-items:center;border-top:1px solid #163747;padding:7px 0;font-size:.62rem}.kgt-s1-reason:first-of-type{border-top:0}.kgt-s1-n{display:grid;place-items:center;width:23px;height:23px;border:1px solid #2aa3e8;border-radius:50%;color:#7dd4ff;font-size:.55rem;font-weight:950;flex:0 0 auto}
.kgt-s1-meter{border:1px solid #274c60;border-radius:13px;background:#07151d;padding:10px 11px;margin-top:9px}.kgt-s1-meter-top{display:flex;justify-content:space-between;color:#8ca6b5;font-size:.53rem;font-weight:900}.kgt-s1-track{height:7px;border-radius:999px;margin:9px 0 4px;background:linear-gradient(90deg,#3297d3,#66727c 48%,#f8a943)}.kgt-s1-dot{width:17px;height:17px;border-radius:50%;background:#ffad4f;border:2px solid #3b2a13;transform:translate(-50%,-12px)}.kgt-s1-axis{display:flex;justify-content:space-between;color:#7890a0;font-size:.50rem}
.kgt-s1-details{margin-top:10px;border:1px solid #2aa3e8;border-radius:12px;overflow:hidden}.kgt-s1-details summary{cursor:pointer;list-style:none;text-align:center;padding:11px;color:#eff8fc;font-weight:950;font-size:.69rem}.kgt-s1-details summary::-webkit-details-marker{display:none}.kgt-s1-deep{padding:0 11px 11px}.kgt-s1-deep-card{border-top:1px solid #173846;padding:8px 0}.kgt-s1-deep-card b{display:block;font-size:.59rem;color:#b9d7e5}.kgt-s1-deep-card span{display:block;font-size:.52rem;color:#829baa;margin-top:3px;line-height:1.45}
[data-testid="stRadio"] label{font-size:.68rem!important}[data-testid="stRadio"]{margin-top:-6px;margin-bottom:4px}
@media(max-width:760px){.kgt-s1-head{align-items:flex-start}.kgt-s1-title{font-size:1.35rem}.kgt-s1-card{padding:12px}.kgt-s1-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kgt-s1-market{grid-template-columns:1fr}.kgt-s1-match{grid-template-columns:1fr}.kgt-s1-team.right{justify-content:flex-start;text-align:left}.kgt-s1-at{text-align:left;padding-left:68px}.kgt-s1-team img{width:48px;height:48px}}
</style>
'''


def _text(value: Any, default: str = "—") -> str:
    raw = str(value if value is not None else "").strip()
    return raw or default


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return f"{number:.{digits}f}" if number is not None else "—"


def _american(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _market(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = snapshot or {}
    markets = payload.get("markets") if isinstance(payload.get("markets"), list) else []
    row = markets[0] if payload.get("ready") is True and payload.get("market_available") is True and len(markets) == 1 and isinstance(markets[0], Mapping) else {}
    return dict(row)


def _weather(environment: Mapping[str, Any] | None) -> tuple[str, str]:
    env = environment or {}
    if env.get("indoor") is True:
        return "INDOOR · weather impact none", "LOW"
    temp = _num(env.get("temperature_f"))
    precip = _num(env.get("precip_probability_pct"))
    gust = _num(env.get("wind_gust_mph"))
    pressure = _text(env.get("weather_pressure"), "UNVERIFIED").upper()
    parts = []
    if temp is not None:
        parts.append(f"{temp:.0f}°F")
    if precip is not None:
        parts.append(f"{precip:.0f}% precip")
    if gust is not None:
        parts.append(f"{gust:.0f} mph")
    return " · ".join(parts) if parts else "Weather unavailable", pressure


def _reason_lines(projection: Mapping[str, Any] | None, environment: Mapping[str, Any] | None) -> list[str]:
    proj = projection or {}
    baseline = _num(proj.get("baseline_total"))
    adjustments = proj.get("adjustments") if isinstance(proj.get("adjustments"), Mapping) else {}
    lines = [f"{baseline:.1f} scoring baseline" if baseline is not None else "Scoring baseline verified"]
    candidates = []
    labels = {"pace": "Pace", "explosive": "Explosives", "sustainability": "Drive sustainability", "environment": "Environment"}
    for key, label in labels.items():
        value = _num(adjustments.get(key))
        if value is not None:
            candidates.append((abs(value), key, label, value))
    candidates.sort(reverse=True)
    if candidates:
        _abs, _key, label, value = candidates[0]
        if abs(value) < 0.05:
            lines.append(f"{label} is neutral")
        else:
            verb = "adds" if value > 0 else "suppresses"
            lines.append(f"{label} {verb} total {abs(value):.1f} pts")
    else:
        lines.append("Context adjustments verified")
    weather, pressure = _weather(environment)
    lines.append(f"Weather impact {pressure}" if pressure != "UNVERIFIED" else weather)
    return lines[:3]


def _confidence(read: Mapping[str, Any] | None) -> str:
    payload = read or {}
    if payload.get("ready") is not True:
        return "WAIT"
    final_read = _text(payload.get("final_read"), "PASS").upper()
    if final_read == "PASS":
        return "PASS"
    clearance = abs(_num(payload.get("range_clearance")) or 0.0)
    if clearance >= 3.0:
        return "HIGH"
    if clearance >= 1.5:
        return "MEDIUM"
    return "WATCH"


def build_decision_card_model(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None,
    scoring_context: Mapping[str, Any] | None,
    pace_context: Mapping[str, Any] | None,
    explosive_context: Mapping[str, Any] | None,
    red_zone_drive_context: Mapping[str, Any] | None,
    environment_context: Mapping[str, Any] | None,
    projection: Mapping[str, Any] | None,
    market_read: Mapping[str, Any] | None,
) -> dict[str, Any]:
    market = _market(snapshot)
    read = market_read or {}
    proj = projection or {}
    market_total = _num(read.get("market_total"))
    if market_total is None:
        market_total = _num(market.get("total"))
    kyre_total = _num(read.get("model_total"))
    if kyre_total is None:
        kyre_total = _num(proj.get("projected_total"))
    edge = _num(read.get("edge_points"))
    if edge is None and market_total is not None and kyre_total is not None:
        edge = kyre_total - market_total
    lean = _text(read.get("final_read"), "WAIT").upper() if read.get("ready") is True else "WAIT"
    low = _num(read.get("range_low"))
    high = _num(read.get("range_high"))
    if low is None:
        low = _num(proj.get("range_low"))
    if high is None:
        high = _num(proj.get("range_high"))
    weather, weather_pressure = _weather(environment_context)
    return {
        "away_team": _text(row.get("away_team"), "Away"),
        "home_team": _text(row.get("home_team"), "Home"),
        "away_record": _text(row.get("away_record")),
        "home_record": _text(row.get("home_record")),
        "away_logo": _text(row.get("away_logo"), ""),
        "home_logo": _text(row.get("home_logo"), ""),
        "venue": _text(row.get("venue"), "Venue TBD"),
        "clock": _text(row.get("tip_et"), "TBD"),
        "market_total": market_total,
        "kyre_total": kyre_total,
        "edge": edge,
        "lean": lean,
        "model_range": f"{_fmt(low)}–{_fmt(high)}" if low is not None and high is not None else "—",
        "confidence": _confidence(read),
        "sportsbook": _text(market.get("sportsbook"), "Verified book"),
        "over_price": market.get("over_price") if market else read.get("over_price"),
        "under_price": market.get("under_price") if market else read.get("under_price"),
        "weather": weather,
        "weather_pressure": weather_pressure,
        "reasons": _reason_lines(proj, environment_context),
        "sportsbook_projection_weight": _num(proj.get("sportsbook_projection_weight")) if _num(proj.get("sportsbook_projection_weight")) is not None else SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def _logo(url: str, team: str) -> str:
    if not url:
        return '<div></div>'
    return f'<img src="{escape(url, quote=True)}" alt="{escape(team, quote=True)} logo">'


def _deep_analysis_html(
    scoring: Mapping[str, Any] | None,
    pace: Mapping[str, Any] | None,
    explosive: Mapping[str, Any] | None,
    red_zone: Mapping[str, Any] | None,
    environment: Mapping[str, Any] | None,
) -> str:
    score = scoring or {}; away = score.get("away") if isinstance(score.get("away"), Mapping) else {}; home = score.get("home") if isinstance(score.get("home"), Mapping) else {}
    pace_match = (pace or {}).get("matchup") if isinstance((pace or {}).get("matchup"), Mapping) else {}
    boom = (explosive or {}).get("matchup") if isinstance((explosive or {}).get("matchup"), Mapping) else {}
    rz = (red_zone or {}).get("matchup") if isinstance((red_zone or {}).get("matchup"), Mapping) else {}
    weather, pressure = _weather(environment)
    return (
        '<div class="kgt-s1-deep">'
        f'<div class="kgt-s1-deep-card"><b>Offense vs Defense</b><span>{escape(_text(away.get("team_name"), "Away"))}: {_fmt(away.get("offense_ppg"))} PF/G vs {_fmt(away.get("opponent_defense_papg"))} opponent PA/G · {escape(_text(home.get("team_name"), "Home"))}: {_fmt(home.get("offense_ppg"))} PF/G vs {_fmt(home.get("opponent_defense_papg"))} opponent PA/G</span></div>'
        f'<div class="kgt-s1-deep-card"><b>Pace + Possession</b><span>{_fmt(pace_match.get("average_plays_per_game"))} average team plays/game · {escape(_text(pace_match.get("grade"), "Verified"))}</span></div>'
        f'<div class="kgt-s1-deep-card"><b>Explosive Scoring</b><span>{_fmt(boom.get("average_explosive_plays_per_game"))} average explosive plays/game · {escape(_text(boom.get("grade"), "Verified"))}</span></div>'
        f'<div class="kgt-s1-deep-card"><b>Red Zone + Drive Sustainability</b><span>{_fmt(rz.get("average_red_zone_td_pct"))}% RZ TD · {_fmt(rz.get("average_third_down_conv_pct"))}% third down · {_fmt(rz.get("average_first_downs_per_game"))} first downs/game</span></div>'
        f'<div class="kgt-s1-deep-card"><b>Game Environment</b><span>{escape(weather)} · {escape(pressure)} impact</span></div>'
        '</div>'
    )


def build_decision_card_html(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None,
    scoring_context: Mapping[str, Any] | None,
    pace_context: Mapping[str, Any] | None,
    explosive_context: Mapping[str, Any] | None,
    red_zone_drive_context: Mapping[str, Any] | None,
    environment_context: Mapping[str, Any] | None,
    projection: Mapping[str, Any] | None,
    market_read: Mapping[str, Any] | None,
) -> str:
    model = build_decision_card_model(row, snapshot, scoring_context, pace_context, explosive_context, red_zone_drive_context, environment_context, projection, market_read)
    edge = model["edge"]
    edge_text = f"{edge:+.1f}" if edge is not None else "—"
    lean = model["lean"]
    lean_class = lean.lower() if lean in {"OVER", "UNDER", "PASS"} else "pass"
    edge_for_meter = max(-6.0, min(6.0, float(edge or 0.0)))
    meter = max(0.0, min(100.0, 50.0 + edge_for_meter / 12.0 * 100.0))
    labels = foundation._phoenix_kickoff(row)
    clock = labels["clock"] if labels else model["clock"]
    deep = _deep_analysis_html(scoring_context, pace_context, explosive_context, red_zone_drive_context, environment_context)
    reasons = ''.join(f'<div class="kgt-s1-reason"><span class="kgt-s1-n">{idx}</span><span>{escape(reason)}</span></div>' for idx, reason in enumerate(model["reasons"], 1))
    meter_label = "PASS / INSIDE RANGE" if lean == "PASS" else (f"LEANS {lean}" if lean in {"OVER", "UNDER"} else "WAIT")
    return (
        '<article class="kgt-s1-card">'
        '<div class="kgt-s1-match">'
        f'<div class="kgt-s1-team">{_logo(model["away_logo"], model["away_team"])}<div><b>{escape(model["away_team"])}</b><span>{escape(model["away_record"])}</span></div></div>'
        '<div class="kgt-s1-at">@</div>'
        f'<div class="kgt-s1-team right"><div><b>{escape(model["home_team"])}</b><span>{escape(model["home_record"])}</span></div>{_logo(model["home_logo"], model["home_team"])}</div>'
        '</div>'
        f'<div class="kgt-s1-meta">{escape(clock)} · {escape(model["venue"])}</div>'
        '<div class="kgt-s1-grid">'
        f'<div class="kgt-s1-stat"><span>MARKET TOTAL</span><b>{_fmt(model["market_total"])}</b></div>'
        f'<div class="kgt-s1-stat kyre"><span>KYRE TOTAL</span><b>{_fmt(model["kyre_total"])}</b></div>'
        f'<div class="kgt-s1-stat edge"><span>EDGE</span><b>{escape(edge_text)}</b></div>'
        f'<div class="kgt-s1-stat lean {lean_class}"><span>LEAN</span><b>{escape(lean)}</b></div>'
        f'<div class="kgt-s1-stat"><span>MODEL RANGE</span><b>{escape(model["model_range"])}</b></div>'
        f'<div class="kgt-s1-stat"><span>CONFIDENCE</span><b>{escape(model["confidence"])}</b></div>'
        '</div>'
        '<div class="kgt-s1-market">'
        f'<div class="kgt-s1-strip"><b>{escape(model["sportsbook"])}</b> · O <b class="kgt-s1-over">{escape(_american(model["over_price"]))}</b> · U <b class="kgt-s1-under">{escape(_american(model["under_price"]))}</b></div>'
        f'<div class="kgt-s1-strip kgt-s1-weather">{escape(model["weather"])} · <b>{escape(model["weather_pressure"])} impact</b></div>'
        '</div>'
        f'<div class="kgt-s1-why"><h4>💡 WHY KYRE {"WAITS" if lean == "PASS" else "LEANS " + escape(lean) if lean in {"OVER","UNDER"} else "WAITS"}</h4>{reasons}</div>'
        '<div class="kgt-s1-meter">'
        f'<div class="kgt-s1-meter-top"><span>TOTAL ENVIRONMENT</span><span>{escape(meter_label)}</span></div>'
        '<div class="kgt-s1-track"></div>'
        f'<div class="kgt-s1-dot" style="margin-left:{meter:.1f}%"></div>'
        '<div class="kgt-s1-axis"><span>Under</span><span>Neutral</span><span>Over</span></div>'
        '</div>'
        f'<details class="kgt-s1-details"><summary>FULL ANALYSIS →</summary>{deep}</details>'
        '</article>'
    )


def _collect(games: pd.DataFrame, day_str: str) -> list[dict[str, Any]]:
    snapshots = v2._market_snapshots(games)
    scoring = v3._matchup_contexts(games, day_str)
    pace = v4._pace_contexts(games, day_str)
    explosive = v5._explosive_contexts(games, day_str)
    red_zone = v6._red_zone_drive_contexts(games, day_str)
    environment = v7._environment_contexts(games, day_str)
    projections = v8._projection_contexts(games, scoring, pace, explosive, red_zone, environment)
    reads = v9._market_read_contexts(projections, snapshots)
    items = []
    for _, raw in games.iterrows():
        row = raw.to_dict() if hasattr(raw, "to_dict") else dict(raw)
        key = _text(row.get("game_id"), "")
        model = build_decision_card_model(row, snapshots.get(key), scoring.get(key), pace.get(key), explosive.get(key), red_zone.get(key), environment.get(key), projections.get(key), reads.get(key))
        items.append({"row": row, "snapshot": snapshots.get(key), "scoring": scoring.get(key), "pace": pace.get(key), "explosive": explosive.get(key), "red_zone": red_zone.get(key), "environment": environment.get(key), "projection": projections.get(key), "read": reads.get(key), "model": model})
    return items


def render_nfl_game_totals_hub() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    today = pd.Timestamp.now(tz=foundation.ET).date()
    mobile._apply_pending_date(today)
    selected = mobile._initial_date(today)
    selected = mobile._auto_surface_next_slate(selected, today)
    c1, c2, c3 = st.columns([3.2, .6, .6])
    with c1:
        selected = st.date_input("NFL Game Totals date", value=selected, key=mobile._WIDGET_DATE_KEY, label_visibility="collapsed")
    selected = mobile._as_date(selected, today); mobile._sync_game_totals_date(selected)
    with c2:
        if st.button("→", key="kgt_s1_next", use_container_width=True): mobile._queue_next_game_day(selected)
    with c3:
        if st.button("↻", key="kgt_s1_reload", use_container_width=True): mobile._reload_game_totals_data()
    day_str = selected.isoformat()
    with st.spinner("Loading verified NFL Game Totals…"):
        games, diag = foundation.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or diag.get("request_ok") is not True:
        st.error("Verified NFL slate unavailable. No games were fabricated."); return
    if games.empty:
        st.markdown(f'<div class="kgt-s1"><div class="kgt-s1-head"><div><div class="kgt-s1-title">NFL GAME TOTALS</div><div class="kgt-s1-sub">{escape(day_str)} · No upcoming verified games</div></div></div></div>', unsafe_allow_html=True)
        st.info("No verified NFL games were returned for this date. Use → for the next game day."); return
    mode = st.radio("Sort", ["GAME TIME", "BEST EDGES"], horizontal=True, label_visibility="collapsed", key="kgt_s1_sort")
    items = _collect(games, day_str)
    if mode == "BEST EDGES":
        items.sort(key=lambda item: abs(float(item["model"].get("edge") or 0.0)), reverse=True)
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum())
    st.markdown(f'<div class="kgt-s1"><div class="kgt-s1-head"><div><div class="kgt-s1-title">NFL GAME TOTALS</div><div class="kgt-s1-sub">{escape(day_str)} · {upcoming} Upcoming · {len(games)} verified game{"s" if len(games) != 1 else ""}</div></div></div></div>', unsafe_allow_html=True)
    cards = ''.join(build_decision_card_html(item["row"], item["snapshot"], item["scoring"], item["pace"], item["explosive"], item["red_zone"], item["environment"], item["projection"], item["read"]) for item in items)
    st.markdown(f'<div class="kgt-s1">{cards}</div>', unsafe_allow_html=True)


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals Page 1 S-tier only renders Game Total.")
    return render_nfl_game_totals_hub()


__all__ = ["MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED", "build_decision_card_model", "build_decision_card_html", "render_nfl_game_totals_hub", "render_nfl_hub"]
