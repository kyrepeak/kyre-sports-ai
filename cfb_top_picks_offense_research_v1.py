"""CFB Top Picks Research V2 Step 4 — offensive scoring research.

Presentation/research only. This module cannot modify Top Picks probability,
ranking, selection, sportsbook influence, projection math, or API 2 behavior.

Field routing:
- ESPN Core exact-team current-season statistics: points/game, pass yards/game,
  rush yards/game, yards/play, pass TD/game, rush TD/game.
- ESPN exact-team completed-game schedule: recent scoring average.
- NCAA certified red-zone table: offensive red-zone touchdown rate.
- NCAA certified explosive-efficiency tables: passing/rushing efficiency proxy.

Missing values are never invented. Every material field carries source and
observed_at provenance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean
from typing import Any, Mapping

import cfb_over_under_explosive_engine_v1 as explosive
import cfb_over_under_pace_engine_v1 as pace_identity
import cfb_over_under_red_zone_engine_v1 as red_zone
import cfb_over_under_step3_readable_v2 as readable

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 4 • OFFENSIVE SCORING RESEARCH"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
OFFENSE_RESEARCH_PROJECTION_WEIGHT = 0.0
API2_USED = False
RECENT_SCORING_WINDOW = 3

# NCAA stat tables abbreviate a small number of schools differently from the
# schedule/ESPN identity. Keep these deterministic aliases local to the
# research layer rather than weakening the shared fuzzy matcher.
_NCAA_TEAM_SLUG_ALIASES = {
    "south florida": "south-fla",
    "south florida bulls": "south-fla",
    "usf": "south-fla",
}

CORE_FIELDS = (
    "points_per_game",
    "recent_scoring_avg",
    "yards_per_play",
    "pass_yards_per_game",
    "rush_yards_per_game",
)
SUPPORTING_FIELDS = (
    "pass_td_per_game",
    "rush_td_per_game",
    "red_zone_td_rate",
    "explosive_efficiency_proxy",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _season(game: Mapping[str, Any], slate_day: str = "") -> int:
    for value in (
        game.get("game_date"),
        game.get("kickoff_iso"),
        slate_day,
    ):
        text = _clean(value)
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return datetime.now(timezone.utc).year


def _cutoff(game: Mapping[str, Any], slate_day: str = "") -> datetime:
    for value in (game.get("kickoff_iso"), game.get("date")):
        text = _clean(value)
        if not text:
            continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    day = _clean(game.get("game_date") or slate_day)
    try:
        return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def _metric(
    value: Any,
    *,
    source: str,
    observed_at: str,
    status: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    number = _float(value)
    return {
        "value": number,
        "status": status or ("VERIFIED" if number is not None else "UNAVAILABLE"),
        "source": source if number is not None else "",
        "observed_at": observed_at,
        "note": note,
    }


def _source_attempts_healthy(diag: Mapping[str, Any]) -> bool:
    attempts = diag.get("attempts") or []
    for attempt in attempts if isinstance(attempts, list) else []:
        if not isinstance(attempt, Mapping):
            continue
        if not _clean(attempt.get("error")) and (
            _float(attempt.get("bytes")) or _float(attempt.get("http"))
        ):
            return True
    return False


def _recent_scoring(
    team_id: str,
    season: int,
    cutoff: datetime,
    excluded_event_id: str,
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    rows, attempts = readable._completed_rows(
        _clean(team_id),
        int(season),
        cutoff,
        _clean(excluded_event_id),
    )
    recent = list(rows[-RECENT_SCORING_WINDOW:]) if rows else []
    values = [
        float(row["points_for"])
        for row in recent
        if _float(row.get("points_for")) is not None
    ]
    average = float(fmean(values)) if values else None
    evidence = [
        {
            "event_id": _clean(row.get("event_id")),
            "date": _clean(row.get("date"))[:10],
            "opponent": _clean(row.get("opponent_name")),
            "points_for": _float(row.get("points_for")),
            "points_against": _float(row.get("points_against")),
        }
        for row in recent
    ]
    return average, evidence, {
        "provider": "ESPN exact-team completed-game schedule",
        "attempts": attempts,
        "games_available": len(rows),
        "recent_games_used": len(values),
        "ready": bool(values),
    }


def _identity_profile(
    team: str,
    slug: str = "",
    division_context: str = "",
) -> dict[str, Any]:
    clean_team = _clean(team)
    alias_slug = _NCAA_TEAM_SLUG_ALIASES.get(clean_team.casefold(), "")
    return {
        "team": clean_team,
        "team_slug": alias_slug or _clean(slug),
        "division_context": _clean(division_context),
    }


def _resolve_division(profile: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    fbs, fbs_diag = pace_identity._load_pace_division("FBS")
    fcs, fcs_diag = pace_identity._load_pace_division("FCS")
    division, _ = pace_identity._resolve_division(profile, fbs, fcs)
    return division, {
        "FBS": fbs_diag,
        "FCS": fcs_diag,
    }


def _red_zone_offense(
    profile: Mapping[str, Any],
    division: str,
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if division not in {"FBS", "FCS"}:
        return _metric(
            None,
            source="",
            observed_at=observed_at,
            note="NCAA division identity unavailable",
        ), {"ready": False, "reason": "division identity unavailable"}

    bundle, diag = red_zone._load_red_zone_division(division)
    tables = bundle.get("tables") or {}
    row = pace_identity._lookup(tables.get("red_zone_offense") or {}, profile)
    metrics = red_zone._metrics(row, False) if row else {}
    rate = _float(metrics.get("touchdown_rate"))
    return _metric(
        rate,
        source=f"NCAA {division} Red Zone Offense",
        observed_at=observed_at,
        note="Offensive red-zone touchdown rate",
    ), {
        "ready": rate is not None,
        "division": division,
        "metrics": dict(metrics),
        "attempts": list(diag.get("attempts") or []),
    }


def _explosive_offense(
    profile: Mapping[str, Any],
    division: str,
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if division not in {"FBS", "FCS"}:
        return _metric(
            None,
            source="",
            observed_at=observed_at,
            note="NCAA division identity unavailable",
        ), {"ready": False, "reason": "division identity unavailable"}

    bundle, diag = explosive._load_explosive_division(division)
    tables = bundle.get("tables") or {}
    baselines = bundle.get("baselines") or {}

    pass_row = pace_identity._lookup(tables.get("pass_offense") or {}, profile)
    ypc_row = pace_identity._lookup(
        tables.get("pass_yards_per_completion") or {},
        profile,
    )
    rush_row = pace_identity._lookup(tables.get("rush_offense") or {}, profile)

    pass_metrics = explosive._pass_offense_metrics(pass_row, ypc_row)
    rush_metrics = explosive._rush_metrics(rush_row, False)

    signals: list[tuple[float, float]] = []
    for value, baseline, full_ratio, weight in (
        (
            pass_metrics.get("yards_per_attempt"),
            baselines.get("pass_ypa"),
            explosive.PASS_FULL_SIGNAL_RATIO,
            explosive.PASS_WEIGHT * 0.60,
        ),
        (
            pass_metrics.get("yards_per_completion"),
            baselines.get("pass_ypc"),
            explosive.PASS_FULL_SIGNAL_RATIO,
            explosive.PASS_WEIGHT * 0.40,
        ),
        (
            rush_metrics.get("yards_per_rush"),
            baselines.get("rush_ypr"),
            explosive.RUSH_FULL_SIGNAL_RATIO,
            explosive.RUSH_WEIGHT,
        ),
    ):
        signal = explosive._ratio_signal(value, baseline, full_ratio)
        if signal is not None:
            signals.append((float(signal), float(weight)))

    weight_sum = sum(weight for _, weight in signals)
    proxy = (
        sum(signal * weight for signal, weight in signals) / weight_sum
        if weight_sum > 0
        else None
    )

    if proxy is None:
        label = "UNAVAILABLE"
    elif proxy >= 0.25:
        label = "HIGH"
    elif proxy >= 0.08:
        label = "ABOVE AVERAGE"
    elif proxy <= -0.25:
        label = "LOW"
    elif proxy <= -0.08:
        label = "BELOW AVERAGE"
    else:
        label = "BALANCED"

    metric = _metric(
        proxy,
        source=f"NCAA {division} passing/rushing efficiency tables",
        observed_at=observed_at,
        note=(
            "Explosive-efficiency proxy; not a literal 20+ pass / 10+ rush play rate"
        ),
    )
    metric["label"] = label
    metric["pass_yards_per_attempt"] = _float(pass_metrics.get("yards_per_attempt"))
    metric["pass_yards_per_completion"] = _float(
        pass_metrics.get("yards_per_completion")
    )
    metric["rush_yards_per_attempt"] = _float(rush_metrics.get("yards_per_rush"))

    return metric, {
        "ready": proxy is not None,
        "division": division,
        "pass_metrics": dict(pass_metrics),
        "rush_metrics": dict(rush_metrics),
        "baselines": dict(baselines),
        "attempts": list(diag.get("attempts") or []),
    }


def _side_profile(
    side: str,
    row: Mapping[str, Any],
    game: Mapping[str, Any],
    slate_day: str,
) -> dict[str, Any]:
    observed_at = _now()
    team = _clean(game.get(f"{side}_team") or row.get(side))
    team_id = _clean(
        game.get(f"{side}_espn_team_id")
        or row.get(f"{side}_team_id")
    )
    slug = _clean(game.get(f"{side}_team_slug"))
    division_hint = _clean(
        game.get(f"{side}_division")
        or game.get(f"{side}_division_context")
    )
    event_id = _clean(
        game.get("espn_event_id")
        or game.get("game_id")
        or row.get("event_id")
    )
    season = _season(game, slate_day)
    cutoff = _cutoff(game, slate_day)

    live, live_diag = readable._live_offense(team_id, season)
    live = dict(live or {})

    snapshot = {}
    try:
        snapshot = dict((readable._snapshot_team(team_id) or {}).get("offense") or {})
    except Exception:
        snapshot = {}

    def routed(key: str, source_label: str) -> dict[str, Any]:
        live_value = _float(live.get(key))
        if live_value is not None:
            return _metric(
                live_value,
                source=source_label,
                observed_at=observed_at,
            )
        snap_value = _float(snapshot.get(key))
        if snap_value is not None:
            return _metric(
                snap_value,
                source="Checked-in 2026 CFB Step-3 verified snapshot fallback",
                observed_at=observed_at,
                status="VERIFIED_FALLBACK",
                note="Live ESPN field unavailable; verified snapshot fallback used",
            )
        return _metric(
            None,
            source="",
            observed_at=observed_at,
            note="No verified live or snapshot value available",
        )

    recent_avg, recent_rows, recent_diag = _recent_scoring(
        team_id,
        season,
        cutoff,
        event_id,
    )

    profile_identity = _identity_profile(team, slug, division_hint)
    division, division_diag = _resolve_division(profile_identity)
    red_metric, red_diag = _red_zone_offense(
        profile_identity,
        division,
        observed_at,
    )
    explosive_metric, explosive_diag = _explosive_offense(
        profile_identity,
        division,
        observed_at,
    )

    metrics = {
        "points_per_game": routed(
            "points_pg",
            "ESPN Core exact-team current-season statistics",
        ),
        "recent_scoring_avg": _metric(
            recent_avg,
            source="ESPN exact-team completed-game schedule",
            observed_at=observed_at,
            note=f"Average across last {len(recent_rows)} completed games before kickoff",
        ),
        "yards_per_play": routed(
            "yards_per_play",
            "ESPN Core exact-team current-season statistics",
        ),
        "pass_yards_per_game": routed(
            "pass_yards_pg",
            "ESPN Core exact-team current-season statistics",
        ),
        "rush_yards_per_game": routed(
            "rush_yards_pg",
            "ESPN Core exact-team current-season statistics",
        ),
        "pass_td_per_game": routed(
            "pass_td_pg",
            "ESPN Core exact-team current-season statistics",
        ),
        "rush_td_per_game": routed(
            "rush_td_pg",
            "ESPN Core exact-team current-season statistics",
        ),
        "red_zone_td_rate": red_metric,
        "explosive_efficiency_proxy": explosive_metric,
    }

    core_ready = sum(metrics[field]["value"] is not None for field in CORE_FIELDS)
    supporting_ready = sum(
        metrics[field]["value"] is not None for field in SUPPORTING_FIELDS
    )

    return {
        "side": side,
        "team": team,
        "team_id": team_id,
        "season": season,
        "division": division,
        "metrics": metrics,
        "recent_games": recent_rows,
        "core_ready": core_ready,
        "core_total": len(CORE_FIELDS),
        "supporting_ready": supporting_ready,
        "supporting_total": len(SUPPORTING_FIELDS),
        "complete_core": core_ready == len(CORE_FIELDS),
        "source_router": {
            "espn_core": {
                "ready": bool(live_diag.get("ready")),
                "attempts": list(live_diag.get("attempts") or []),
                "provider": _clean(live_diag.get("provider")),
            },
            "recent_scoring": recent_diag,
            "division_identity": division_diag,
            "red_zone": red_diag,
            "explosive": explosive_diag,
        },
        "observed_at": observed_at,
    }


def _value(side: Mapping[str, Any], field: str) -> float | None:
    metrics = side.get("metrics") or {}
    row = metrics.get(field) or {}
    return _float(row.get("value")) if isinstance(row, Mapping) else None


def _reasoning(away: Mapping[str, Any], home: Mapping[str, Any]) -> list[str]:
    reads: list[str] = []
    appg = _value(away, "points_per_game")
    hppg = _value(home, "points_per_game")
    if appg is not None and hppg is not None:
        combined = appg + hppg
        reads.append(
            f"{away.get('team')} scores {appg:.1f} PPG and {home.get('team')} scores "
            f"{hppg:.1f} PPG; combined season scoring average {combined:.1f}."
        )

    ar = _value(away, "recent_scoring_avg")
    hr = _value(home, "recent_scoring_avg")
    if ar is not None and hr is not None:
        reads.append(
            f"Recent scoring: {away.get('team')} {ar:.1f} and {home.get('team')} "
            f"{hr:.1f} points/game across their last verified completed games."
        )

    aypp = _value(away, "yards_per_play")
    hypp = _value(home, "yards_per_play")
    if aypp is not None and hypp is not None:
        reads.append(
            f"Offensive efficiency: {away.get('team')} {aypp:.2f} YPP; "
            f"{home.get('team')} {hypp:.2f} YPP."
        )

    arz = _value(away, "red_zone_td_rate")
    hrz = _value(home, "red_zone_td_rate")
    if arz is not None or hrz is not None:
        pieces = []
        if arz is not None:
            pieces.append(f"{away.get('team')} {arz * 100:.1f}%")
        if hrz is not None:
            pieces.append(f"{home.get('team')} {hrz * 100:.1f}%")
        reads.append("Red-zone TD finishing: " + "; ".join(pieces) + ".")

    return reads


def build_offense_research(
    row: Mapping[str, Any],
    game: Mapping[str, Any],
    slate_day: str = "",
) -> dict[str, Any]:
    away = _side_profile("away", row, game, slate_day)
    home = _side_profile("home", row, game, slate_day)
    return {
        "version": MODEL_VERSION,
        "status": "READY" if away["complete_core"] and home["complete_core"] else "PARTIAL",
        "away": away,
        "home": home,
        "reasoning": _reasoning(away, home),
        "combined_points_per_game": (
            _value(away, "points_per_game") + _value(home, "points_per_game")
            if _value(away, "points_per_game") is not None
            and _value(home, "points_per_game") is not None
            else None
        ),
        "projection_weight": OFFENSE_RESEARCH_PROJECTION_WEIGHT,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "may_modify_probability": MAY_MODIFY_PROBABILITY,
        "may_modify_ranking": MAY_MODIFY_RANKING,
        "may_modify_selection": MAY_MODIFY_SELECTION,
        "api2_used": API2_USED,
        "observed_at": _now(),
    }


__all__ = [
    "API2_USED",
    "CORE_FIELDS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "OFFENSE_RESEARCH_PROJECTION_WEIGHT",
    "RECENT_SCORING_WINDOW",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "SUPPORTING_FIELDS",
    "build_offense_research",
]
