"""CFB Game Total Page 2 Step 6 — Trends + Scoring Breakdown.

Presentation-only rendering for already-owned game-total trend and scoring
values. The caller supplies recent totals, market reference, half/quarter
scoring, explosive scoring, scoring opportunities, red-zone finishing, and
optionally the already-owned away/home team profiles. This module adds no
fetching and does not calculate sports/model meaning.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from math import isfinite
from statistics import fmean
from typing import Any

STEP3_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
STEP4_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
STEP5_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_FROZEN"
STEP6_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP6_TRENDS_SCORING_BREAKDOWN_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP6_TRENDS_SCORING_BREAKDOWN_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

PAGE2_STEP6_CSS = r"""
<style>
.gtp2s6-wrap{max-width:1180px;margin:0 auto 20px;color:#f7fbff;scroll-margin-top:18px}
.gtp2s6-card{overflow:hidden;border:1px solid rgba(75,197,255,.32);border-radius:20px;background:radial-gradient(circle at 15% 0,rgba(36,184,243,.11),transparent 36%),linear-gradient(180deg,rgba(7,27,41,.98),rgba(4,15,24,.99));box-shadow:0 16px 38px rgba(0,0,0,.25),0 0 28px rgba(46,190,255,.05)}
.gtp2s6-head{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:17px 18px 13px;border-bottom:1px solid rgba(82,174,211,.17)}
.gtp2s6-kicker{display:block;margin-bottom:5px;color:#66d9ff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}
.gtp2s6-head h3{margin:0;color:#fff;font-size:20px;line-height:1.05;font-weight:1000;letter-spacing:-.02em}
.gtp2s6-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:750}
.gtp2s6-owned{padding:5px 9px;border:1px solid rgba(86,202,246,.24);border-radius:999px;background:rgba(11,67,94,.26);color:#83dfff;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.gtp2s6-body{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr);gap:12px;padding:14px}
.gtp2s6-panel{border:1px solid rgba(82,163,197,.19);border-radius:16px;background:rgba(8,29,43,.72);padding:13px}
.gtp2s6-panel-title{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:11px}
.gtp2s6-panel-title strong{color:#eaf9ff;font-size:10px;font-weight:1000;letter-spacing:.03em}
.gtp2s6-market{color:#6edfff;font-size:8px;font-weight:950;white-space:nowrap}
.gtp2s6-team-trends{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.gtp2s6-team-trend{padding:9px;border:1px solid rgba(82,160,191,.16);border-radius:12px;background:rgba(6,25,37,.58)}
.gtp2s6-team-name{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px;color:#eef9ff;font-size:8px;font-weight:1000}.gtp2s6-team-name span{color:#7c9db0;font-size:6px;text-transform:uppercase;letter-spacing:.06em}
.gtp2s6-trends{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;align-items:end;min-height:118px}
.gtp2s6-trend{display:flex;flex-direction:column;justify-content:end;gap:6px;height:112px;padding:8px 5px;border:1px solid rgba(80,154,184,.14);border-radius:11px;background:rgba(6,25,37,.66);text-align:center}
.gtp2s6-bar{display:block;width:100%;min-height:8px;border-radius:7px 7px 4px 4px;background:linear-gradient(180deg,rgba(91,223,255,.92),rgba(28,123,192,.48));box-shadow:0 0 14px rgba(72,202,255,.09)}
.gtp2s6-trend strong{color:#f7fcff;font-size:11px;font-weight:1000}.gtp2s6-trend span{color:#7393a6;font-size:6px;font-weight:900;text-transform:uppercase;letter-spacing:.07em}
.gtp2s6-empty{display:grid;place-items:center;grid-column:1/-1;min-height:100px;color:#7b97a8;font-size:11px;font-weight:900;text-align:center;line-height:1.35}
.gtp2s6-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.gtp2s6-metric{padding:7px 4px;border:1px solid rgba(75,151,181,.15);border-radius:8px;background:rgba(8,31,44,.7);text-align:center}.gtp2s6-metric span{display:block;color:#7997a9;font-size:5.5px;font-weight:900;text-transform:uppercase}.gtp2s6-metric strong{display:block;margin-top:3px;color:#eaf9ff;font-size:9px;font-weight:1000}
.gtp2s6-breakdown{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}
.gtp2s6-score{min-width:0;padding:10px 8px;border:1px solid rgba(82,160,191,.16);border-radius:11px;background:rgba(7,27,41,.72);text-align:center}
.gtp2s6-score span{display:block;color:#7395a9;font-size:6px;font-weight:950;letter-spacing:.07em;text-transform:uppercase}.gtp2s6-score strong{display:block;margin-top:5px;color:#f7fbff;font-size:12px;font-weight:1000;overflow-wrap:anywhere}
.gtp2s6-split-empty{display:grid;place-items:center;min-height:132px;padding:16px;border:1px dashed rgba(102,178,207,.25);border-radius:11px;background:rgba(5,24,36,.54);color:#8aa6b7;font-size:9px;font-weight:900;text-align:center;line-height:1.45}
.gtp2s6-drivers{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.gtp2s6-driver{padding:13px;border:1px solid rgba(78,181,216,.20);border-radius:14px;background:linear-gradient(145deg,rgba(10,49,66,.66),rgba(7,28,42,.78))}
.gtp2s6-driver span{display:block;color:#78a4b9;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.gtp2s6-driver strong{display:block;margin-top:7px;color:#72e0ff;font-size:15px;font-weight:1000;overflow-wrap:anywhere}.gtp2s6-driver.red strong{color:#78efbd}
@media(max-width:760px){.gtp2s6-head{align-items:start;flex-direction:column;gap:9px}.gtp2s6-owned{align-self:flex-start}.gtp2s6-body{grid-template-columns:1fr}.gtp2s6-team-trends{grid-template-columns:1fr}.gtp2s6-trends{min-height:104px}.gtp2s6-trend{height:98px}.gtp2s6-drivers{grid-template-columns:1fr 1fr 1fr}}
@media(max-width:480px){.gtp2s6-card{border-radius:17px}.gtp2s6-head{padding:14px 13px 11px}.gtp2s6-head h3{font-size:18px}.gtp2s6-body{padding:10px;gap:8px}.gtp2s6-panel{padding:10px}.gtp2s6-trends{gap:5px}.gtp2s6-trend{padding:7px 3px}.gtp2s6-trend strong{font-size:9px}.gtp2s6-breakdown{grid-template-columns:repeat(2,minmax(0,1fr))}.gtp2s6-drivers{grid-template-columns:1fr}.gtp2s6-driver{padding:11px}.gtp2s6-driver strong{font-size:13px}}
</style>
"""


def _number(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


def _display(value: Any) -> str:
    if isinstance(value, float) and not isfinite(value):
        return "—"
    text = "" if value is None else str(value).strip()
    return escape(text) if text else "—"


def _display_number(value: Any) -> str:
    numeric = _number(value)
    if numeric is None:
        return "—"
    if float(numeric).is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}"


def _bar_height(value: Any) -> int:
    """Return a visual-only bar height; never changes the supplied sports value."""
    numeric = _number(value)
    if numeric is None:
        return 12
    return max(12, min(86, int(round(numeric))))


def _recent_html(values: Sequence[Any] | None) -> str:
    items = list(values or [])[:5]
    if not items:
        return '<div class="gtp2s6-empty">No verified recent scoring history available</div>'
    return "".join(
        f'<div class="gtp2s6-trend"><span>Game {index}</span><i class="gtp2s6-bar" style="height:{_bar_height(value)}%"></i><strong>{_display_number(value)}</strong></div>'
        for index, value in enumerate(items, start=1)
    )


def _profile_history(profile: Mapping[str, Any] | None, as_of_day: Any) -> list[dict[str, Any]]:
    row = profile if isinstance(profile, Mapping) else {}
    cutoff = str(as_of_day or "").strip()[:10]
    history: list[dict[str, Any]] = []
    for raw in row.get("completed_games") or []:
        if not isinstance(raw, Mapping):
            continue
        day = str(raw.get("date") or "").strip()[:10]
        if cutoff and day and day >= cutoff:
            continue
        points_for = _number(raw.get("points_for"))
        points_against = _number(raw.get("points_against"))
        if points_for is None or points_against is None:
            continue
        history.append({
            "date": day,
            "event_id": str(raw.get("event_id") or "").strip(),
            "points_for": points_for,
            "points_against": points_against,
            "total": points_for + points_against,
        })
    history.sort(key=lambda item: (item["date"], item["event_id"]))
    return history[-5:]


def _profile_metric(profile: Mapping[str, Any] | None, key: str, values: list[float]) -> float | None:
    row = profile if isinstance(profile, Mapping) else {}
    direct = _number(row.get(key))
    if direct is not None:
        return direct
    return float(fmean(values)) if values else None


def _team_trend_html(team: Any, profile: Mapping[str, Any] | None, as_of_day: Any) -> str:
    history = _profile_history(profile, as_of_day)
    totals = [float(item["total"]) for item in history]
    points_for = [float(item["points_for"]) for item in history]
    points_against = [float(item["points_against"]) for item in history]
    recent_scoring = _profile_metric(profile, "recent_ppg", points_for)
    recent_allowed = _profile_metric(profile, "recent_points_allowed_pg", points_against)
    environment = float(fmean(totals)) if totals else None
    return (
        '<div class="gtp2s6-team-trend">'
        f'<div class="gtp2s6-team-name"><strong>{_display(team)}</strong><span>Last five completed</span></div>'
        f'<div class="gtp2s6-trends">{_recent_html(totals)}</div>'
        '<div class="gtp2s6-metrics">'
        f'<div class="gtp2s6-metric"><span>Recent scoring</span><strong>{_display_number(recent_scoring)}</strong></div>'
        f'<div class="gtp2s6-metric"><span>Recent allowed</span><strong>{_display_number(recent_allowed)}</strong></div>'
        f'<div class="gtp2s6-metric"><span>Scoring environment</span><strong>{_display_number(environment)}</strong></div>'
        '</div></div>'
    )


def _score_cell(label: str, value: Any) -> str:
    return f'<div class="gtp2s6-score"><span>{escape(label)}</span><strong>{_display(value)}</strong></div>'


def _has_split_value(scoring: Mapping[str, Any]) -> bool:
    return any(
        scoring.get(key) not in (None, "")
        for key in ("away_1h", "home_1h", "away_2h", "home_2h", "q1", "q2", "q3", "q4")
    )


def build_trends_scoring_breakdown_html(
    *,
    recent_totals: Sequence[Any] | None,
    market_line: Any,
    scoring_breakdown: Mapping[str, Any] | None,
    explosive_scoring: Any,
    scoring_opportunities: Any,
    red_zone_finishing: Any,
    away_team: Any = None,
    home_team: Any = None,
    away_profile: Mapping[str, Any] | None = None,
    home_profile: Mapping[str, Any] | None = None,
    as_of_day: Any = None,
) -> str:
    """Render Step 6 from already-owned display values without model recomputation."""
    scoring = scoring_breakdown if isinstance(scoring_breakdown, Mapping) else {}
    half_cells = "".join((
        _score_cell("1H Away", scoring.get("away_1h")),
        _score_cell("1H Home", scoring.get("home_1h")),
        _score_cell("2H Away", scoring.get("away_2h")),
        _score_cell("2H Home", scoring.get("home_2h")),
    ))
    quarter_cells = "".join(
        _score_cell(label.upper(), scoring.get(label)) for label in ("q1", "q2", "q3", "q4")
    )

    profile_mode = isinstance(away_profile, Mapping) or isinstance(home_profile, Mapping)
    if profile_mode:
        recent_block = (
            '<div class="gtp2s6-team-trends">'
            f'{_team_trend_html(away_team, away_profile, as_of_day)}'
            f'{_team_trend_html(home_team, home_profile, as_of_day)}'
            '</div>'
        )
    else:
        recent_block = f'<div class="gtp2s6-trends">{_recent_html(recent_totals)}</div>'

    if _has_split_value(scoring):
        split_block = (
            '<div class="gtp2s6-panel-title"><strong>Half Scoring</strong><span class="gtp2s6-market">Verified splits</span></div>'
            f'<div class="gtp2s6-breakdown">{half_cells}</div>'
            '<div class="gtp2s6-panel-title" style="margin-top:12px"><strong>Quarter Scoring</strong><span class="gtp2s6-market">Q1–Q4</span></div>'
            f'<div class="gtp2s6-breakdown">{quarter_cells}</div>'
        )
    else:
        split_block = '<div class="gtp2s6-split-empty">No verified half/quarter scoring splits available</div>'

    return f"""
{PAGE2_STEP6_CSS}
<section id="gtp2-trends" class="gtp2s6-wrap" data-step6="{STEP6_MARKER}" data-testid="gtp2s6-trends" data-value-ownership="precomputed-inputs">
  <div class="gtp2s6-card">
    <header class="gtp2s6-head">
      <div>
        <span class="gtp2s6-kicker">Stage 3 • Trends</span>
        <h3>Trends + Scoring Breakdown</h3>
        <p>Verified recent scoring environment from completed-game evidence.</p>
      </div>
      <span class="gtp2s6-owned">Display only • no recompute</span>
    </header>
    <div class="gtp2s6-body">
      <div class="gtp2s6-panel">
        <div class="gtp2s6-panel-title"><strong>Recent Totals</strong><span class="gtp2s6-market">Market Line: {_display(market_line)}</span></div>
        {recent_block}
      </div>
      <div class="gtp2s6-panel">
        {split_block}
      </div>
      <div class="gtp2s6-drivers">
        <div class="gtp2s6-driver"><span>Explosive Scoring</span><strong>{_display(explosive_scoring)}</strong></div>
        <div class="gtp2s6-driver"><span>Scoring Opportunities</span><strong>{_display(scoring_opportunities)}</strong></div>
        <div class="gtp2s6-driver red"><span>Red-Zone Finishing</span><strong>{_display(red_zone_finishing)}</strong></div>
      </div>
    </div>
  </div>
</section>
"""


__all__ = [
    "FREEZE_TOKEN",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STEP6_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_FREEZE_TOKEN",
    "STEP4_FREEZE_TOKEN",
    "STEP5_FREEZE_TOKEN",
    "STEP6_MARKER",
    "build_trends_scoring_breakdown_html",
]
