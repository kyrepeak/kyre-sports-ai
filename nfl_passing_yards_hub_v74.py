"""NFL Passing Yards V74 — Availability + Game-Day Conditions Step 5.

Additive evidence/presentation wrapper over frozen V73. Step 5 consolidates the
already-certified Passing Yards personnel and environment evidence, then adds an
exact-event game-day inactive state from the existing frozen
nfl_game_day_availability_v1 provider.

Truth boundary:
- QB/skill/OL/opponent-secondary values are read from the frozen rendered
  personnel card; they are not recalculated here.
- venue/surface/weather/temperature/wind are read from the frozen rendered game
  environment card; they are not synthesized here.
- exact-event inactive state is CONFIRMED/PENDING/UNVERIFIED from the frozen
  game-day availability provider. PENDING is a truthful pre-kick state, not a
  failure and not a claim that final inactives have been published.
- no Step 5 value modifies projection, context math, probability, market math,
  or sportsbook handling.

Sportsbook projection influence remains exactly 0.0%. Stake sizing stays OFF.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any, Callable

import streamlit as st

import nfl_game_day_availability_v1 as game_day
import nfl_passing_yards_hub_v73 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v73

MODEL_VERSION = "NFL PASSING YARDS V74 • AVAILABILITY + GAME-DAY CONDITIONS STEP 5"
FROZEN_PRIOR = "nfl_passing_yards_hub_v73"
FROZEN_AVAILABILITY_PROVIDER = "nfl_game_day_availability_v1"
AVAILABILITY_VERSION = "v74"
NEW_PHASE_STEP = 5
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PERSONNEL_MATH = False
MAY_MODIFY_ENVIRONMENT_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_AVAILABILITY_CSS = r"""
<style data-passing-yards-availability-game-day-css="v74">
.ks-py74,.ks-py74 *{box-sizing:border-box}
.ks-py74{
  margin:9px 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:14px;background:linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt))
}
.ks-py74-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}
.ks-py74-kicker{font-size:.54rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py74-title{margin-top:3px;font-size:.96rem;font-weight:950;color:var(--kyre-sem-text-primary)}
.ks-py74-state{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py74-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.ks-py74-cell{min-width:0;padding:9px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;background:rgba(255,255,255,.014)}
.ks-py74-cell b{display:block;font-size:.78rem;line-height:1.2;color:var(--kyre-sem-text-primary);overflow-wrap:anywhere}
.ks-py74-cell span{display:block;margin-top:4px;font-size:.45rem;font-weight:900;text-transform:uppercase;color:var(--kyre-sem-text-muted)}
.ks-py74-report{margin-top:9px;padding:9px 10px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;font-size:.56rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
.ks-py74-report strong{color:var(--kyre-sem-text-primary)}
.ks-py74-foot{margin-top:8px;padding-top:8px;border-top:1px solid var(--kyre-sem-border-soft);font-size:.51rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
@media(max-width:760px){.ks-py74-head{flex-direction:column}.ks-py74-state{align-self:flex-start}.ks-py74-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:420px){.ks-py74{padding:10px}.ks-py74-grid{grid-template-columns:1fr}}
</style>
"""


def _plain(value: Any, fallback: str = "") -> str:
    text = re.sub(r"<[^>]+>", "", str(value if value is not None else ""), flags=re.S)
    text = text.replace("&nbsp;", " ").strip()
    return text or fallback


def _metric(body: str, label: str) -> str:
    pattern = re.compile(
        rf"<b[^>]*>\s*(.*?)\s*</b>\s*<span[^>]*>\s*{re.escape(label)}\s*</span>",
        flags=re.I | re.S,
    )
    match = pattern.search(str(body or ""))
    return _plain(match.group(1)) if match else ""


def _count_metric(body: str, label: str) -> int | None:
    value = _metric(body, label)
    match = re.search(r"-?\d+", value)
    return int(match.group(0)) if match else None


def _selected_matchup_identity(body: str) -> dict:
    match = re.search(
        r'class="kpass29-meta"[^>]*>\s*QB\s*•\s*([A-Z]{2,4})\s*(vs|@)\s*([A-Z]{2,4})\s*•',
        str(body or ""),
        flags=re.I,
    )
    if not match:
        return {"ready": False, "selected_abbr": "", "opponent_abbr": "", "away_abbr": "", "home_abbr": "", "selected_side": ""}
    selected = match.group(1).upper()
    token = match.group(2).lower()
    opponent = match.group(3).upper()
    if token == "@":
        away, home, side = selected, opponent, "away"
    else:
        away, home, side = opponent, selected, "home"
    return {
        "ready": True,
        "selected_abbr": selected,
        "opponent_abbr": opponent,
        "away_abbr": away,
        "home_abbr": home,
        "selected_side": side,
    }


def resolve_game_day_snapshot(
    body: str,
    game_date: str,
    *,
    scoreboard_rows: list[dict] | None = None,
    scoreboard_diag: dict | None = None,
    event_loader: Callable[[str], tuple[dict, dict]] | None = None,
) -> dict:
    identity = _selected_matchup_identity(body)
    base = {
        **identity,
        "game_id": "",
        "game_state": "",
        "state": "UNVERIFIED",
        "provider_ok": False,
        "prop_gate_open": False,
        "selected_unavailable": [],
        "opponent_unavailable": [],
        "selected_explicit_inactive": [],
        "opponent_explicit_inactive": [],
        "reason": "",
    }
    if not identity.get("ready"):
        base["reason"] = "selected matchup identity unavailable"
        return base

    if scoreboard_rows is None or scoreboard_diag is None:
        scoreboard_rows, scoreboard_diag = game_day.load_game_day_scoreboard(game_date)
    scoreboard_rows = list(scoreboard_rows or [])
    scoreboard_diag = dict(scoreboard_diag or {})
    if not scoreboard_diag.get("ok"):
        base["reason"] = "exact-date scoreboard provider unavailable"
        return base

    matched = next(
        (
            row for row in scoreboard_rows
            if str(row.get("away_abbr") or "").upper() == identity["away_abbr"]
            and str(row.get("home_abbr") or "").upper() == identity["home_abbr"]
        ),
        None,
    )
    if not matched:
        base["reason"] = "exact matchup not found on verified date scoreboard"
        return base

    game_id = str(matched.get("game_id") or "").strip()
    state = str(matched.get("state") or "").strip().lower()
    if event_loader is None:
        event_loader = game_day.load_event_injury_map
    event_map, event_diag = event_loader(game_id)
    snap = game_day.event_availability_snapshot(
        game_id,
        identity["away_abbr"],
        identity["home_abbr"],
        state,
        event_map=event_map,
        event_diag=event_diag,
    )
    side = identity["selected_side"]
    other = "home" if side == "away" else "away"
    base.update({
        "game_id": game_id,
        "game_state": state,
        "state": str(snap.get("state") or "UNVERIFIED").upper(),
        "provider_ok": bool(snap.get("provider_ok")),
        "prop_gate_open": bool(snap.get("prop_gate_open")),
        "selected_unavailable": list(snap.get(f"{side}_unavailable") or []),
        "opponent_unavailable": list(snap.get(f"{other}_unavailable") or []),
        "selected_explicit_inactive": list(snap.get(f"{side}_explicit_inactive") or []),
        "opponent_explicit_inactive": list(snap.get(f"{other}_explicit_inactive") or []),
        "reason": "" if snap.get("provider_ok") else "exact-event availability provider unavailable",
    })
    return base


def _query_date() -> str:
    try:
        return str(st.query_params.get("ks_py_date") or "").strip()
    except Exception:
        return ""


def _runtime_game_day_snapshot(body: str) -> dict:
    date = _query_date()
    if not date:
        return resolve_game_day_snapshot(body, "")
    try:
        return resolve_game_day_snapshot(body, date)
    except Exception as exc:
        identity = _selected_matchup_identity(body)
        return {
            **identity,
            "game_id": "",
            "game_state": "",
            "state": "UNVERIFIED",
            "provider_ok": False,
            "prop_gate_open": False,
            "selected_unavailable": [],
            "opponent_unavailable": [],
            "selected_explicit_inactive": [],
            "opponent_explicit_inactive": [],
            "reason": f"availability lookup failed closed: {type(exc).__name__}",
        }


def _row_names(rows: list[dict]) -> str:
    names = []
    for row in rows or []:
        name = _plain(row.get("name"))
        status = _plain(row.get("status"))
        if name:
            names.append(f"{name} ({status or 'status unavailable'})")
    return ", ".join(names) if names else "None explicitly published"


def _report_label(snapshot: dict) -> str:
    state = str(snapshot.get("state") or "UNVERIFIED").upper()
    if state == "CONFIRMED":
        return "FINAL INACTIVES CONFIRMED"
    if state == "PENDING":
        return "FINAL INACTIVES PENDING"
    return "INACTIVE REPORT UNVERIFIED"


def build_availability_panel(body: str, snapshot: dict) -> str:
    qb_status = _metric(body, "QB Status") or "—"
    skill_hard = _count_metric(body, "Skill Hard")
    ol_hard = _count_metric(body, "OL Hard")
    secondary_hard = _count_metric(body, "Opp Secondary Hard")
    venue_type = _metric(body, "Venue Type") or "—"
    surface = _metric(body, "Surface") or "—"
    weather = _metric(body, "Weather") or "—"
    temperature = _metric(body, "Temperature") or "—"
    wind = _metric(body, "Wind") or "—"

    personnel_ready = qb_status != "—" and None not in (skill_hard, ol_hard, secondary_hard)
    environment_ready = venue_type != "—" and surface != "—" and weather != "—"
    game_day_state = str(snapshot.get("state") or "UNVERIFIED").upper()
    game_day_ready = bool(snapshot.get("provider_ok") and game_day_state in {"PENDING", "CONFIRMED"})
    ready = bool(personnel_ready and environment_ready and game_day_ready)

    state_label = _report_label(snapshot)
    selected_inactive = _row_names(list(snapshot.get("selected_explicit_inactive") or []))
    opponent_inactive = _row_names(list(snapshot.get("opponent_explicit_inactive") or []))
    selected_unavailable_count = len(list(snapshot.get("selected_unavailable") or []))
    opponent_unavailable_count = len(list(snapshot.get("opponent_unavailable") or []))
    game_id = _plain(snapshot.get("game_id"), "—")

    return (
        '<section class="ks-py74" data-passing-yards-availability-game-day="v74" '
        f'data-passing-yards-availability-ready="{"true" if ready else "false"}" '
        f'data-game-day-state="{escape(game_day_state, quote=True)}" '
        'data-passing-yards-v225-runtime="availability-game-day-step5">'
        '<div class="ks-py74-head"><div>'
        '<div class="ks-py74-kicker">Availability + game-day conditions • evidence only</div>'
        '<div class="ks-py74-title">Who is available, and what conditions are they playing in?</div>'
        f'</div><div class="ks-py74-state">{escape(state_label)}</div></div>'
        '<div class="ks-py74-grid">'
        f'<div class="ks-py74-cell" data-step5-field="qb-status"><b>{escape(qb_status)}</b><span>QB Status</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="skill-hard"><b>{skill_hard if skill_hard is not None else "—"}</b><span>Skill Hard</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="ol-hard"><b>{ol_hard if ol_hard is not None else "—"}</b><span>OL Hard</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="secondary-hard"><b>{secondary_hard if secondary_hard is not None else "—"}</b><span>Opp Secondary Hard</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="venue"><b>{escape(venue_type)}</b><span>Venue Type</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="surface"><b>{escape(surface)}</b><span>Surface</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="weather"><b>{escape(weather)}</b><span>Weather</span></div>'
        f'<div class="ks-py74-cell" data-step5-field="wind"><b>{escape(wind)}</b><span>Wind</span></div>'
        '</div>'
        '<div class="ks-py74-report" data-step5-game-day-report="v74">'
        f'<strong>Final inactive report:</strong> {escape(state_label)} • ESPN event {escape(game_id)} • '
        f'selected-team unavailable: {selected_unavailable_count} • opponent unavailable: {opponent_unavailable_count}.<br>'
        f'<strong>Selected-team explicit inactives:</strong> {escape(selected_inactive)}.<br>'
        f'<strong>Opponent explicit inactives:</strong> {escape(opponent_inactive)}.<br>'
        f'<strong>Environment:</strong> {escape(temperature)} • {escape(wind)} • {escape(weather)} • {escape(surface)}.'
        '</div>'
        '<div class="ks-py74-foot">'
        'PENDING means the exact-event provider is healthy but final inactive confirmation is not complete; '
        'UNVERIFIED fails closed and never fabricates an inactive list. Personnel/environment values are inherited '
        'from the frozen Passing Yards evidence stack. Projection/model/context/probability/market math unchanged • '
        'Sportsbook projection influence 0.0% • stake sizing OFF.'
        '</div></section>'
    )


def _insert_after_live_market(body: str, panel: str) -> str:
    text = str(body or "")
    start = text.find('<section class="ks-py73-market"')
    if start < 0:
        return text
    end = text.find("</section>", start)
    if end < 0:
        return text
    end += len("</section>")
    return text[:end] + panel + text[end:]


def _inject_availability_game_day(body: str, slot: int) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-live-market="v73"' not in text
        or 'data-passing-yards-availability-game-day="v74"' in text
    ):
        return text
    snapshot = _runtime_game_day_snapshot(text)
    panel = build_availability_panel(text, snapshot)
    text = _insert_after_live_market(text, panel)
    ready = 'data-passing-yards-live-market-ready="v73"'
    if ready in text and 'data-passing-yards-availability-game-day-ready="v74"' not in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-availability-game-day-ready="v74"',
            1,
        )
    return _AVAILABILITY_CSS + text


def _selected_analysis_v74(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_availability_game_day(
        _FROZEN_SELECTED_ANALYSIS(captured, slot),
        slot,
    )


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v73
    prior._selected_analysis_v73 = _selected_analysis_v74
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v73 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V74 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "AVAILABILITY_VERSION",
    "FROZEN_AVAILABILITY_PROVIDER",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_ENVIRONMENT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PERSONNEL_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_availability_game_day",
    "_selected_analysis_v74",
    "build_availability_panel",
    "resolve_game_day_snapshot",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
