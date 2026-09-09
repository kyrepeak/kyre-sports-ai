"""CFB Over/Under Intelligence V2 — Upgrade Step 10 historical context engine.

Additive audit layer above permanently frozen Upgrade Step 9.

Purpose
-------
Step 10 gathers pre-kickoff team scoring history and true head-to-head results
from ESPN team schedules. It improves matchup context without pretending that
old games automatically predict a new roster.

Integrity policy
----------------
- Only completed games strictly before the target kickoff/date are accepted.
- Future scheduled games and the target event itself are excluded.
- Head-to-head rows require exact ESPN team IDs; no name-only guessing.
- Recent team history is descriptive only in Step 10.
- Historical roster continuity and opponent-strength normalization are not yet
  certified, so history has exactly 0% projection, selection, and analysis-line
  weight.
- Step-9 projected points, projected total, structural sigma, reliability, and
  final qualification rules remain unchanged.
- No sportsbook input, market-implied probability, EV, price, or Monte Carlo is
  introduced.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean, pstdev
from typing import Any, Iterable, Mapping

import streamlit as st

import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_schedule_v3 as schedule

MODEL_VERSION = "CFB O/U HISTORICAL CONTEXT ENGINE V1 • UPGRADE STEP 10"
FROZEN_STEP9_ENGINE = "cfb_over_under_environment_engine_v1"

ESPN_TEAM_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/"
    "teams/{team_id}/schedule"
)
RECENT_GAME_WINDOW = 8
LOOKBACK_SEASONS = 3
H2H_LOOKBACK_SEASONS = 6
MIN_RECENT_GAMES_FOR_CONTEXT = 3

PROJECTED_TOTAL_HISTORY_WEIGHT = 0.0
ANALYSIS_LINE_HISTORY_WEIGHT = 0.0
SELECTION_HISTORY_WEIGHT = 0.0
HISTORICAL_ROSTER_CONTINUITY_CERTIFIED = False
OPPONENT_STRENGTH_ADJUSTED_HISTORY = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, Mapping):
        for key in ("value", "displayValue", "score"):
            if key in value:
                found = _float(value.get(key))
                if found is not None:
                    return found
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _target_cutoff(game: Mapping[str, Any]) -> datetime:
    kickoff = _parse_dt(game.get("kickoff_iso") or game.get("date"))
    if kickoff is not None:
        return kickoff
    day = _clean(game.get("game_date"))
    try:
        return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def _season_year(game: Mapping[str, Any]) -> int:
    day = _clean(game.get("game_date"))
    try:
        return int(day[:4])
    except Exception:
        return datetime.now(timezone.utc).year


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_team_schedule(
    team_id: str,
    season: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    team_id = _clean(team_id)
    if not team_id.isdigit() or int(season) < 1900:
        return {}, []
    return schedule.frozen.frozen._fetch_json_with_fallback(
        ESPN_TEAM_SCHEDULE_URL.format(team_id=team_id),
        {"season": int(season)},
        f"ESPN CFB team {team_id} schedule season {int(season)}",
    )


def _competition(event: Mapping[str, Any]) -> Mapping[str, Any]:
    comps = event.get("competitions") or []
    if comps and isinstance(comps[0], Mapping):
        return comps[0]
    return {}


def _completed(event: Mapping[str, Any]) -> bool:
    comp = _competition(event)
    status = event.get("status") or comp.get("status") or {}
    if not isinstance(status, Mapping):
        status = {}
    typ = status.get("type") or {}
    if not isinstance(typ, Mapping):
        typ = {}
    if typ.get("completed") is True:
        return True
    name = _clean(typ.get("name") or typ.get("state")).lower()
    return name in {"status_final", "final", "post"}


def _event_row(event: Mapping[str, Any], team_id: str) -> dict[str, Any] | None:
    if not _completed(event):
        return None
    comp = _competition(event)
    competitors = comp.get("competitors") or []
    mine: Mapping[str, Any] | None = None
    opp: Mapping[str, Any] | None = None
    for competitor in competitors:
        if not isinstance(competitor, Mapping):
            continue
        team = competitor.get("team") or {}
        if not isinstance(team, Mapping):
            team = {}
        if _clean(team.get("id")) == _clean(team_id):
            mine = competitor
        else:
            opp = competitor
    if mine is None or opp is None:
        return None

    my_team = mine.get("team") or {}
    opp_team = opp.get("team") or {}
    if not isinstance(my_team, Mapping):
        my_team = {}
    if not isinstance(opp_team, Mapping):
        opp_team = {}

    points_for = _float(mine.get("score"))
    points_against = _float(opp.get("score"))
    if points_for is None or points_against is None:
        return None

    dt = _parse_dt(event.get("date") or comp.get("date"))
    return {
        "event_id": _clean(event.get("id") or comp.get("id")),
        "date": _clean(event.get("date") or comp.get("date")),
        "date_dt": dt,
        "team_id": _clean(team_id),
        "team_name": _clean(
            my_team.get("displayName") or my_team.get("shortDisplayName")
        ),
        "opponent_id": _clean(opp_team.get("id")),
        "opponent_name": _clean(
            opp_team.get("displayName") or opp_team.get("shortDisplayName")
        ),
        "home_away": _clean(mine.get("homeAway")).lower(),
        "points_for": float(points_for),
        "points_against": float(points_against),
        "combined_total": float(points_for + points_against),
        "won": bool(points_for > points_against),
    }


def _iter_events(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for event in payload.get("events") or []:
        if isinstance(event, Mapping):
            yield event


def _load_history(
    team_id: str,
    seasons: Iterable[int],
    cutoff: datetime,
    excluded_event_id: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    for season in seasons:
        payload, these_attempts = _fetch_team_schedule(team_id, int(season))
        attempts.extend(list(these_attempts or []))
        for event in _iter_events(payload):
            row = _event_row(event, team_id)
            if not row:
                continue
            event_id = _clean(row.get("event_id"))
            if excluded_event_id and event_id == _clean(excluded_event_id):
                continue
            dt = row.get("date_dt")
            if isinstance(dt, datetime) and dt >= cutoff:
                continue
            key = event_id or f"{row.get('date')}|{row.get('opponent_id')}"
            rows[key] = row
    ordered = sorted(
        rows.values(),
        key=lambda row: row.get("date_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return ordered, attempts


def _summary(rows: list[Mapping[str, Any]], limit: int = RECENT_GAME_WINDOW) -> dict[str, Any]:
    sample = [dict(row) for row in rows[: max(0, int(limit))]]
    n = len(sample)
    if not n:
        return {
            "ready": False,
            "games": 0,
            "avg_points_for": None,
            "avg_points_against": None,
            "avg_combined_total": None,
            "combined_total_sigma": None,
            "wins": 0,
            "losses": 0,
            "sample": [],
        }
    pf = [float(row["points_for"]) for row in sample]
    pa = [float(row["points_against"]) for row in sample]
    totals = [float(row["combined_total"]) for row in sample]
    wins = sum(bool(row.get("won")) for row in sample)
    return {
        "ready": n >= MIN_RECENT_GAMES_FOR_CONTEXT,
        "games": n,
        "avg_points_for": float(fmean(pf)),
        "avg_points_against": float(fmean(pa)),
        "avg_combined_total": float(fmean(totals)),
        "combined_total_sigma": float(pstdev(totals)) if n > 1 else 0.0,
        "wins": int(wins),
        "losses": int(n - wins),
        "sample": sample,
    }


def _h2h_summary(rows: list[Mapping[str, Any]], opponent_id: str) -> dict[str, Any]:
    sample = [
        dict(row) for row in rows
        if _clean(row.get("opponent_id")) == _clean(opponent_id)
    ]
    n = len(sample)
    if not n:
        return {
            "ready": False,
            "meetings": 0,
            "avg_combined_total": None,
            "latest": {},
            "sample": [],
        }
    totals = [float(row["combined_total"]) for row in sample]
    return {
        "ready": True,
        "meetings": n,
        "avg_combined_total": float(fmean(totals)),
        "combined_total_sigma": float(pstdev(totals)) if n > 1 else 0.0,
        "latest": dict(sample[0]),
        "sample": sample,
    }


def build_history_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    step9_environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(step9_environment or {})
    if not env:
        env = environment_engine.build_environment_engine(game, away, home)

    away_id = _clean(env.get("away_espn_team_id"))
    home_id = _clean(env.get("home_espn_team_id"))
    event_id = _clean(env.get("event_id"))
    if not away_id.isdigit() or not home_id.isdigit():
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "reason": "verified ESPN team IDs are unavailable from Step 9",
            "away_recent": {},
            "home_recent": {},
            "head_to_head": {},
            "coverage": 0.0,
            "projected_total_history_weight": PROJECTED_TOTAL_HISTORY_WEIGHT,
            "analysis_line_history_weight": ANALYSIS_LINE_HISTORY_WEIGHT,
            "selection_history_weight": SELECTION_HISTORY_WEIGHT,
            "sportsbook_input_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    year = _season_year(game)
    cutoff = _target_cutoff(game)
    recent_seasons = list(range(year, year - LOOKBACK_SEASONS, -1))
    h2h_seasons = list(range(year, year - H2H_LOOKBACK_SEASONS, -1))

    away_rows, away_attempts = _load_history(
        away_id, h2h_seasons, cutoff, excluded_event_id=event_id
    )
    home_rows, home_attempts = _load_history(
        home_id, recent_seasons, cutoff, excluded_event_id=event_id
    )
    # Away rows use the longer H2H horizon. Recent summary still caps to the last 8.
    away_recent = _summary(away_rows)
    home_recent = _summary(home_rows)
    h2h = _h2h_summary(away_rows, home_id)

    recent_coverage = (
        min(1.0, float(away_recent.get("games") or 0) / RECENT_GAME_WINDOW)
        + min(1.0, float(home_recent.get("games") or 0) / RECENT_GAME_WINDOW)
    ) / 2.0
    model_ready = bool(away_recent.get("ready") and home_recent.get("ready"))
    reason = "" if model_ready else "insufficient completed pre-kickoff recent-game history"

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "model_ready": model_ready,
        "reason": reason,
        "event_id": event_id,
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "away_recent": away_recent,
        "home_recent": home_recent,
        "head_to_head": h2h,
        "coverage": float(recent_coverage),
        "future_event_leakage_allowed": False,
        "target_event_excluded": True,
        "historical_roster_continuity_certified": HISTORICAL_ROSTER_CONTINUITY_CERTIFIED,
        "opponent_strength_adjusted_history": OPPONENT_STRENGTH_ADJUSTED_HISTORY,
        "projected_total_history_weight": PROJECTED_TOTAL_HISTORY_WEIGHT,
        "analysis_line_history_weight": ANALYSIS_LINE_HISTORY_WEIGHT,
        "selection_history_weight": SELECTION_HISTORY_WEIGHT,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "diagnostics": {
            "recent_seasons": recent_seasons,
            "h2h_seasons": h2h_seasons,
            "away_attempts": away_attempts,
            "home_attempts": home_attempts,
        },
    }


def apply_to_raw(
    base_raw: Mapping[str, Any],
    engine: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach Step-10 history without changing any Step-9 model outputs."""
    out = dict(base_raw)
    out["base_step9_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step10_history_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step10_applied"] = bool(base_raw.get("ready") and engine.get("model_ready"))
    out["history_engine_coverage"] = float(engine.get("coverage") or 0.0)
    out["projected_total_history_weight"] = PROJECTED_TOTAL_HISTORY_WEIGHT
    out["analysis_line_history_weight"] = ANALYSIS_LINE_HISTORY_WEIGHT
    out["selection_history_weight"] = SELECTION_HISTORY_WEIGHT
    if not engine.get("model_ready"):
        out["history_engine_reason"] = _clean(engine.get("reason"))

    components = dict(base_raw.get("components") or {})
    components.update({
        "step10_history_coverage": float(engine.get("coverage") or 0.0),
        "step10_away_recent_games": int(
            (engine.get("away_recent") or {}).get("games") or 0
        ),
        "step10_home_recent_games": int(
            (engine.get("home_recent") or {}).get("games") or 0
        ),
        "step10_h2h_meetings": int(
            (engine.get("head_to_head") or {}).get("meetings") or 0
        ),
        "step10_projected_total_adjustment": 0.0,
        "step10_structural_sigma_adjustment": 0.0,
        "step10_selection_adjustment": 0.0,
    })
    out["components"] = components
    out["historical_roster_continuity_certified"] = False
    out["opponent_strength_adjusted_history"] = False
    out["future_event_leakage_allowed"] = False
    out["sportsbook_input_used"] = False
    out["market_price_used"] = False
    out["market_probability_used"] = False
    out["edge_or_ev_used"] = False
    out["monte_carlo_used"] = False
    return out


def clear_history_engine_cache() -> None:
    try:
        _fetch_team_schedule.clear()
    except Exception:
        pass


__all__ = [
    "ANALYSIS_LINE_HISTORY_WEIGHT",
    "FROZEN_STEP9_ENGINE",
    "H2H_LOOKBACK_SEASONS",
    "HISTORICAL_ROSTER_CONTINUITY_CERTIFIED",
    "LOOKBACK_SEASONS",
    "MODEL_VERSION",
    "OPPONENT_STRENGTH_ADJUSTED_HISTORY",
    "PROJECTED_TOTAL_HISTORY_WEIGHT",
    "RECENT_GAME_WINDOW",
    "SELECTION_HISTORY_WEIGHT",
    "_event_row",
    "_fetch_team_schedule",
    "_h2h_summary",
    "_load_history",
    "_summary",
    "apply_to_raw",
    "build_history_engine",
    "clear_history_engine_cache",
]
