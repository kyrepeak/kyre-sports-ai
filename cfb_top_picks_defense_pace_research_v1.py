"""CFB Top Picks Research V2 Step 5 — defense + pace research.

Descriptive research only. This module cannot modify Top Picks probability,
ranking, selection, projection math, sportsbook influence, or API 2 behavior.

Field routing:
- ESPN exact-event completed-game summaries: defensive allowance metrics.
- ESPN exact-team completed-game schedule: recent points allowed.
- NCAA certified Red Zone Defense: opponent red-zone touchdown rate.
- NCAA certified passing/rushing defense tables: explosive-susceptibility proxy.
- NCAA Total Offense + Time of Possession: plays/game, seconds/play, pace index.
- ESPN Core exact-team current-season statistics: plays/game fallback.

Every material value carries source + observed_at provenance. Missing values are
never invented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean
from typing import Any, Mapping

import cfb_over_under_explosive_engine_v1 as explosive
import cfb_over_under_pace_engine_v1 as pace_identity
import cfb_over_under_red_zone_engine_v1 as red_zone
import cfb_over_under_step3_readable_v2 as readable
import cfb_top_picks_offense_research_v1 as offense_research

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 5 • DEFENSE + PACE"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
DEFENSE_PACE_RESEARCH_PROJECTION_WEIGHT = 0.0
API2_USED = False
RECENT_ALLOWANCE_WINDOW = 3

CORE_FIELDS = (
    "points_allowed_per_game",
    "recent_points_allowed_avg",
    "yards_per_play_allowed",
    "plays_per_game",
)
SUPPORTING_FIELDS = (
    "pass_yards_allowed_per_game",
    "rush_yards_allowed_per_game",
    "red_zone_td_rate_allowed",
    "explosive_susceptibility_proxy",
    "seconds_per_play",
    "pace_index",
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


def _recent_allowance(
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
    recent = list(rows[-RECENT_ALLOWANCE_WINDOW:]) if rows else []
    values = [
        float(row["points_against"])
        for row in recent
        if _float(row.get("points_against")) is not None
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


def _red_zone_defense(
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
    row = pace_identity._lookup(tables.get("red_zone_defense") or {}, profile)
    metrics = red_zone._metrics(row, True) if row else {}
    rate = _float(metrics.get("touchdown_rate"))
    return _metric(
        rate,
        source=f"NCAA {division} Red Zone Defense",
        observed_at=observed_at,
        note="Opponent red-zone touchdown rate allowed",
    ), {
        "ready": rate is not None,
        "division": division,
        "metrics": dict(metrics),
        "attempts": list(diag.get("attempts") or []),
    }


def _explosive_defense(
    profile: Mapping[str, Any],
    division: str,
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if division not in {"FBS", "FCS"}:
        metric = _metric(
            None,
            source="",
            observed_at=observed_at,
            note="NCAA division identity unavailable",
        )
        metric["label"] = "UNAVAILABLE"
        return metric, {"ready": False, "reason": "division identity unavailable"}

    bundle, diag = explosive._load_explosive_division(division)
    tables = bundle.get("tables") or {}
    baselines = bundle.get("baselines") or {}

    pass_row = pace_identity._lookup(tables.get("pass_defense") or {}, profile)
    rush_row = pace_identity._lookup(tables.get("rush_defense") or {}, profile)
    pass_metrics = explosive._pass_defense_metrics(pass_row)
    rush_metrics = explosive._rush_metrics(rush_row, True)

    signals: list[tuple[float, float]] = []
    for value, baseline, full_ratio, weight in (
        (
            pass_metrics.get("yards_per_attempt_allowed"),
            baselines.get("pass_ypa_allowed"),
            explosive.PASS_FULL_SIGNAL_RATIO,
            explosive.PASS_WEIGHT * 0.65,
        ),
        (
            pass_metrics.get("yards_per_completion_allowed"),
            baselines.get("pass_ypc_allowed"),
            explosive.PASS_FULL_SIGNAL_RATIO,
            explosive.PASS_WEIGHT * 0.35,
        ),
        (
            rush_metrics.get("yards_per_rush_allowed"),
            baselines.get("rush_ypr_allowed"),
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
        label = "HIGH VULNERABILITY"
    elif proxy >= 0.08:
        label = "ABOVE-AVG VULNERABILITY"
    elif proxy <= -0.25:
        label = "STRONG SUPPRESSION"
    elif proxy <= -0.08:
        label = "ABOVE-AVG SUPPRESSION"
    else:
        label = "BALANCED"

    metric = _metric(
        proxy,
        source=f"NCAA {division} passing/rushing defense efficiency tables",
        observed_at=observed_at,
        note=(
            "Explosive-susceptibility efficiency proxy; not a literal "
            "20+ pass / 10+ rush explosive-play rate"
        ),
    )
    metric["label"] = label
    metric["pass_yards_per_attempt_allowed"] = _float(
        pass_metrics.get("yards_per_attempt_allowed")
    )
    metric["pass_yards_per_completion_allowed"] = _float(
        pass_metrics.get("yards_per_completion_allowed")
    )
    metric["rush_yards_per_attempt_allowed"] = _float(
        rush_metrics.get("yards_per_rush_allowed")
    )
    return metric, {
        "ready": proxy is not None,
        "division": division,
        "pass_metrics": dict(pass_metrics),
        "rush_metrics": dict(rush_metrics),
        "baselines": dict(baselines),
        "attempts": list(diag.get("attempts") or []),
    }


def _espn_core_plays(
    team_id: str,
    season: int,
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return _metric(
            None,
            source="",
            observed_at=observed_at,
            note="numeric ESPN team ID unavailable",
        ), {"ready": False, "reason": "bad team id"}

    url = (
        f"{readable.deep._CORE_ROOT}/seasons/{int(season)}/types/2/"
        f"teams/{team_id}/statistics?lang=en&region=us"
    )
    payload, attempts = readable.deep._core_json(
        url,
        f"ESPN Core CFB team {team_id} current-season pace statistics",
    )
    stats = readable._flatten_core_stats(payload)
    games = readable._int(readable._stat_value(stats, "gamesPlayed"))
    if games is None:
        games = readable._int(readable._stat_value(stats, "teamGamesPlayed"))
    games = max(0, int(games or 0))

    plays_pg = _float(readable._stat_value(stats, "totalOffensivePlaysPerGame"))
    total_plays = _float(readable._stat_value(stats, "totalOffensivePlays"))
    if plays_pg is None and total_plays is not None and games > 0:
        plays_pg = float(total_plays) / float(games)

    return _metric(
        plays_pg,
        source="ESPN Core exact-team current-season statistics",
        observed_at=observed_at,
        note="Offensive plays per game pace fallback",
    ), {
        "ready": plays_pg is not None,
        "games": games,
        "total_plays": total_plays,
        "attempts": attempts,
    }


def _pace_profile(
    profile: Mapping[str, Any],
    division: str,
    team_id: str,
    season: int,
    observed_at: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    ncaa_bundle: Mapping[str, Any] = {}
    ncaa_diag: Mapping[str, Any] = {}
    ncaa: Mapping[str, Any] = {}
    if division in {"FBS", "FCS"}:
        ncaa_bundle, ncaa_diag = pace_identity._load_pace_division(division)
        ncaa = pace_identity._team_pace(profile, ncaa_bundle, division)

    ncaa_plays = _float(ncaa.get("plays_per_game"))
    if ncaa_plays is not None:
        plays = _metric(
            ncaa_plays,
            source=f"NCAA {division} Total Offense",
            observed_at=observed_at,
            note="Offensive plays per game",
        )
        espn_diag = {}
    else:
        plays, espn_diag = _espn_core_plays(team_id, season, observed_at)
        if plays.get("value") is not None:
            plays["status"] = "VERIFIED_FALLBACK"
            plays["note"] = "NCAA pace row unavailable; exact-team ESPN Core fallback used"

    seconds = _metric(
        ncaa.get("seconds_per_offensive_play"),
        source=f"NCAA {division} Total Offense + Time of Possession" if division else "",
        observed_at=observed_at,
        note="Possession-clock seconds per offensive play",
    )
    pace_index = _metric(
        ncaa.get("pace_index"),
        source=f"NCAA {division} division-relative pace baseline" if division else "",
        observed_at=observed_at,
        note="plays/game relative to same-division median",
    )
    index_value = _float(pace_index.get("value"))
    if index_value is None:
        label = "DATA LIMITED"
    elif index_value >= 1.05:
        label = "FAST"
    elif index_value <= 0.95:
        label = "SLOW"
    else:
        label = "BALANCED"
    pace_index["label"] = label

    return {
        "plays_per_game": plays,
        "seconds_per_play": seconds,
        "pace_index": pace_index,
    }, {
        "ready": plays.get("value") is not None,
        "division": division,
        "ncaa": dict(ncaa),
        "ncaa_diagnostics": dict(ncaa_diag),
        "espn_fallback": dict(espn_diag),
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
    season = offense_research._season(game, slate_day)
    cutoff = offense_research._cutoff(game, slate_day)

    live, live_diag = readable._live_defense(
        team_id,
        season,
        cutoff.astimezone(timezone.utc).isoformat(),
        event_id,
    )
    live = dict(live or {})
    try:
        snapshot = dict((readable._snapshot_team(team_id) or {}).get("defense") or {})
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

    recent_allowed, recent_rows, recent_diag = _recent_allowance(
        team_id,
        season,
        cutoff,
        event_id,
    )

    identity = offense_research._identity_profile(team, slug, division_hint)
    division, division_diag = offense_research._resolve_division(identity)
    red_metric, red_diag = _red_zone_defense(identity, division, observed_at)
    explosive_metric, explosive_diag = _explosive_defense(
        identity,
        division,
        observed_at,
    )
    pace_metrics, pace_diag = _pace_profile(
        identity,
        division,
        team_id,
        season,
        observed_at,
    )

    metrics = {
        "points_allowed_per_game": routed(
            "points_allowed_pg",
            "ESPN exact-event completed-game summaries",
        ),
        "recent_points_allowed_avg": _metric(
            recent_allowed,
            source="ESPN exact-team completed-game schedule",
            observed_at=observed_at,
            note=f"Average across last {len(recent_rows)} completed games before kickoff",
        ),
        "yards_per_play_allowed": routed(
            "yards_per_play_allowed",
            "ESPN exact-event completed-game summaries",
        ),
        "pass_yards_allowed_per_game": routed(
            "pass_yards_allowed_pg",
            "ESPN exact-event completed-game summaries",
        ),
        "rush_yards_allowed_per_game": routed(
            "rush_yards_allowed_pg",
            "ESPN exact-event completed-game summaries",
        ),
        "pass_td_allowed_per_game": routed(
            "pass_td_allowed_pg",
            "ESPN exact-event completed-game summaries",
        ),
        "rush_td_allowed_per_game": routed(
            "rush_td_allowed_pg",
            "ESPN exact-event completed-game summaries",
        ),
        "red_zone_td_rate_allowed": red_metric,
        "explosive_susceptibility_proxy": explosive_metric,
        **pace_metrics,
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
            "espn_defense": {
                "ready": bool(live_diag.get("ready")),
                "attempts": list(live_diag.get("attempts") or []),
                "provider": _clean(live_diag.get("provider")),
            },
            "recent_allowance": recent_diag,
            "division_identity": division_diag,
            "red_zone_defense": red_diag,
            "explosive_defense": explosive_diag,
            "pace": pace_diag,
        },
        "observed_at": observed_at,
    }


def _value(side: Mapping[str, Any], field: str) -> float | None:
    metrics = side.get("metrics") or {}
    item = metrics.get(field) or {}
    return _float(item.get("value")) if isinstance(item, Mapping) else None


def _reasoning(away: Mapping[str, Any], home: Mapping[str, Any]) -> list[str]:
    reads: list[str] = []
    away_allowed = _value(away, "points_allowed_per_game")
    home_allowed = _value(home, "points_allowed_per_game")
    if away_allowed is not None and home_allowed is not None:
        reads.append(
            f"Scoring prevention: {away.get('team')} allows {away_allowed:.1f} PPG; "
            f"{home.get('team')} allows {home_allowed:.1f} PPG."
        )

    away_recent = _value(away, "recent_points_allowed_avg")
    home_recent = _value(home, "recent_points_allowed_avg")
    if away_recent is not None and home_recent is not None:
        reads.append(
            f"Recent defense: {away.get('team')} {away_recent:.1f} allowed/game; "
            f"{home.get('team')} {home_recent:.1f} allowed/game."
        )

    away_ypp = _value(away, "yards_per_play_allowed")
    home_ypp = _value(home, "yards_per_play_allowed")
    if away_ypp is not None and home_ypp is not None:
        reads.append(
            f"Yards/play allowed: {away.get('team')} {away_ypp:.2f}; "
            f"{home.get('team')} {home_ypp:.2f}."
        )

    away_plays = _value(away, "plays_per_game")
    home_plays = _value(home, "plays_per_game")
    if away_plays is not None and home_plays is not None:
        reads.append(
            f"Pace: {away.get('team')} {away_plays:.1f} plays/game; "
            f"{home.get('team')} {home_plays:.1f} plays/game."
        )

    labels = []
    for side in (away, home):
        item = ((side.get("metrics") or {}).get("pace_index") or {})
        label = _clean(item.get("label"))
        if label and label != "DATA LIMITED":
            labels.append(label)
    if labels:
        if all(label == "FAST" for label in labels):
            env = "FAST"
        elif all(label == "SLOW" for label in labels):
            env = "SLOW"
        else:
            env = "BALANCED/MIXED"
        reads.append(f"Verified pace environment: {env}.")

    return reads


def build_defense_pace_research(
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
        "projection_weight": DEFENSE_PACE_RESEARCH_PROJECTION_WEIGHT,
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
    "DEFENSE_PACE_RESEARCH_PROJECTION_WEIGHT",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "RECENT_ALLOWANCE_WINDOW",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "SUPPORTING_FIELDS",
    "build_defense_pace_research",
]
