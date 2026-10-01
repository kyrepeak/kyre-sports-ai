"""CFB Top Picks Research V2 Step 3 — multi-source matchup history router.

History is descriptive context only. It cannot change projection, ranking,
selection, reliability, sportsbook influence, or the Top-10 order.

Independent source lanes:
1. ESPN exact-team-ID schedule history.
2. Winsipedia all-time game-by-game history with alias/slug resolution.

A provider miss/failure is never converted into a claim that two teams have
never played. "Verified no history" is legal only after healthy source
exhaustion. Otherwise the terminal state is SOURCE_CONFLICT_REVIEW.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from statistics import fmean
from typing import Any, Mapping

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_history_engine_v1 as espn_history

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 3 • MULTI-SOURCE HISTORY"
HISTORY_PROJECTION_WEIGHT = 0.0
HISTORY_SELECTION_WEIGHT = 0.0
HISTORY_RANKING_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
API2_USED = False
MIN_INDEPENDENT_SOURCES = 2
MAX_RECENT_MEETINGS = 5

VERIFIED_HISTORY = "VERIFIED_HISTORY"
VERIFIED_NO_HISTORY = "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION"
SOURCE_CONFLICT_REVIEW = "SOURCE_CONFLICT_REVIEW"
TERMINAL_STATUSES = {
    VERIFIED_HISTORY,
    VERIFIED_NO_HISTORY,
    SOURCE_CONFLICT_REVIEW,
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _winsipedia_lookup_name(name: Any, espn_team_id: Any = "") -> str:
    """Normalize display abbreviations only for the Winsipedia lookup lane.

    ESPN identity remains authoritative and untouched.  Many CFB display names
    end in "St." while Winsipedia uses the full "State" slug (for example,
    Florida St. -> florida-state).
    """
    text = _clean(name)
    if not text:
        return ""
    if _clean(espn_team_id) == "52":
        return "Florida State"
    return re.sub(r"\bSt\.?$", "State", text, flags=re.IGNORECASE)


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _line(row: Mapping[str, Any]) -> float | None:
    pick = _clean(row.get("pick"))
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*$", pick)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _successful_espn_transport(engine: Mapping[str, Any]) -> bool:
    diagnostics = engine.get("diagnostics") or {}
    if not isinstance(diagnostics, Mapping):
        return False
    attempts = list(diagnostics.get("away_attempts") or []) + list(
        diagnostics.get("home_attempts") or []
    )
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            continue
        if not _clean(attempt.get("error")) and int(_f(attempt.get("bytes"), 0.0)) > 0:
            return True
    return False


def _espn_rows(h2h: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in h2h.get("sample") or []:
        if not isinstance(raw, Mapping):
            continue
        away_points = int(round(_f(raw.get("points_for"), 0.0)))
        home_points = int(round(_f(raw.get("points_against"), 0.0)))
        rows.append({
            "event_id": _clean(raw.get("event_id")),
            "date": _clean(raw.get("date"))[:10],
            "away_points": away_points,
            "home_points": home_points,
            "combined_total": away_points + home_points,
            "source": "ESPN exact-team schedule history",
            "source_url": "",
        })
    return rows


def _winsipedia_rows(series: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in series.get("sample") or []:
        if not isinstance(raw, Mapping):
            continue
        rows.append({
            "event_id": "",
            "date": _clean(raw.get("date"))[:10],
            "away_points": int(round(_f(raw.get("away_points"), 0.0))),
            "home_points": int(round(_f(raw.get("home_points"), 0.0))),
            "combined_total": int(round(_f(raw.get("combined_total"), 0.0))),
            "source": _clean(raw.get("source")) or "Winsipedia game-by-game",
            "source_url": _clean(raw.get("source_url") or series.get("source_url")),
        })
    return rows


def _merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, int]] = set()
    merged: list[dict[str, Any]] = []
    for group in groups:
        for row in group:
            key = (
                _clean(row.get("date")),
                int(_f(row.get("away_points"), 0.0)),
                int(_f(row.get("home_points"), 0.0)),
            )
            if not key[0] or key in seen:
                continue
            seen.add(key)
            merged.append(dict(row))
    merged.sort(key=lambda item: _clean(item.get("date")), reverse=True)
    return merged


def _series_from_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "meetings": 0,
            "away_wins": 0,
            "home_wins": 0,
            "ties": 0,
            "avg_combined_total": 0.0,
        }
    away_wins = sum(_f(r.get("away_points")) > _f(r.get("home_points")) for r in rows)
    home_wins = sum(_f(r.get("home_points")) > _f(r.get("away_points")) for r in rows)
    ties = len(rows) - away_wins - home_wins
    totals = [_f(r.get("combined_total")) for r in rows]
    return {
        "meetings": len(rows),
        "away_wins": int(away_wins),
        "home_wins": int(home_wins),
        "ties": int(ties),
        "avg_combined_total": float(fmean(totals)) if totals else 0.0,
    }


def _line_hit_context(row: Mapping[str, Any], history_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    market = _clean(row.get("market")).upper()
    pick = _clean(row.get("pick")).upper()
    line = _line(row)
    if market != "OVER/UNDER" or line is None or not history_rows:
        return {
            "market": market,
            "line": line,
            "sample_games": len(history_rows),
            "hits": 0,
            "misses": 0,
            "pushes": 0,
            "summary": "No totals-line history comparison applies to this pick.",
        }
    totals = [_f(item.get("combined_total")) for item in history_rows]
    if pick.startswith("OVER"):
        hits = sum(total > line for total in totals)
        misses = sum(total < line for total in totals)
    elif pick.startswith("UNDER"):
        hits = sum(total < line for total in totals)
        misses = sum(total > line for total in totals)
    else:
        hits = misses = 0
    pushes = sum(total == line for total in totals)
    return {
        "market": market,
        "line": float(line),
        "sample_games": len(totals),
        "hits": int(hits),
        "misses": int(misses),
        "pushes": int(pushes),
        "summary": f"{hits}/{len(totals)} verified historical meetings cleared this pick direction.",
    }


def resolve_matchup_history(
    row: Mapping[str, Any],
    game: Mapping[str, Any],
) -> dict[str, Any]:
    away = _clean(game.get("away_team") or row.get("away"))
    home = _clean(game.get("home_team") or row.get("home"))
    away_id = _clean(game.get("away_espn_team_id") or row.get("away_team_id"))
    home_id = _clean(game.get("home_espn_team_id") or row.get("home_team_id"))
    event_id = _clean(game.get("espn_event_id") or game.get("game_id") or row.get("event_id"))
    observed_at = _now()

    aliases = {
        "away": {
            "canonical_name": away,
            "espn_team_id": away_id,
            "winsipedia_lookup_name": _winsipedia_lookup_name(away, away_id),
            "winsipedia_slug": recovery._slug_guess(_winsipedia_lookup_name(away, away_id)) if away else "",
        },
        "home": {
            "canonical_name": home,
            "espn_team_id": home_id,
            "winsipedia_lookup_name": _winsipedia_lookup_name(home, home_id),
            "winsipedia_slug": recovery._slug_guess(_winsipedia_lookup_name(home, home_id)) if home else "",
        },
    }

    attempts: list[dict[str, Any]] = []
    espn_engine: dict[str, Any] = {}
    espn_h2h: dict[str, Any] = {}
    espn_error = ""
    if away_id.isdigit() and home_id.isdigit():
        try:
            env = {
                "event_id": event_id,
                "away_espn_team_id": away_id,
                "home_espn_team_id": home_id,
            }
            espn_engine = dict(
                espn_history.build_history_engine(
                    game,
                    {},
                    {},
                    step9_environment=env,
                )
                or {}
            )
            espn_h2h = dict(espn_engine.get("head_to_head") or {})
        except Exception as exc:
            espn_error = f"{type(exc).__name__}: {exc}"[:260]
    else:
        espn_error = "exact ESPN team IDs unavailable"

    espn_meetings = int(_f(espn_h2h.get("meetings"), 0.0))
    espn_healthy = _successful_espn_transport(espn_engine)
    attempts.append({
        "source_id": "espn_exact_team_schedule_history",
        "source": "ESPN",
        "independent": True,
        "attempted": True,
        "verified": espn_meetings > 0,
        "result": (
            "HISTORY"
            if espn_meetings > 0
            else ("CHECKED_NO_RECENT_HISTORY" if espn_healthy else "SOURCE_UNAVAILABLE")
        ),
        "meetings": espn_meetings,
        "error": espn_error,
        "observed_at": observed_at,
    })

    wins: dict[str, Any] = {}
    wins_error = ""
    wins_away_lookup = _winsipedia_lookup_name(away, away_id)
    wins_home_lookup = _winsipedia_lookup_name(home, home_id)
    try:
        wins = dict(
            recovery._fetch_winsipedia_games(
                wins_away_lookup,
                wins_home_lookup,
            )
            or {}
        )
    except Exception as exc:
        wins_error = f"{type(exc).__name__}: {exc}"[:260]
    wins_meetings = int(_f(wins.get("meetings"), 0.0))
    wins_explicit_no_history = _clean(wins.get("source_status")).upper() == "NO_HISTORY"
    attempts.append({
        "source_id": "winsipedia_all_time_game_by_game",
        "source": "Winsipedia",
        "independent": True,
        "attempted": True,
        "verified": wins_meetings > 0,
        "result": (
            "HISTORY"
            if wins_meetings > 0
            else ("CHECKED_NO_HISTORY" if wins_explicit_no_history else "UNVERIFIED_NO_RESULT")
        ),
        "meetings": wins_meetings,
        "error": wins_error,
        "source_url": _clean(wins.get("source_url")),
        "lookup_names": {
            "away": wins_away_lookup,
            "home": wins_home_lookup,
        },
        "observed_at": observed_at,
    })

    espn_rows = _espn_rows(espn_h2h)
    wins_rows = _winsipedia_rows(wins)
    merged_rows = _merge_rows(wins_rows, espn_rows)

    sources_verified = [
        attempt["source"]
        for attempt in attempts
        if attempt.get("verified") is True
    ]
    if sources_verified:
        status = VERIFIED_HISTORY
    elif (
        espn_healthy
        and wins_explicit_no_history
        and len(attempts) >= MIN_INDEPENDENT_SOURCES
    ):
        status = VERIFIED_NO_HISTORY
    else:
        status = SOURCE_CONFLICT_REVIEW

    if wins_meetings > 0:
        series = {
            "meetings": wins_meetings,
            "away_wins": int(_f(wins.get("away_wins"), 0.0)),
            "home_wins": int(_f(wins.get("home_wins"), 0.0)),
            "ties": int(_f(wins.get("ties"), 0.0)),
            "avg_combined_total": _f(wins.get("avg_combined_total"), 0.0),
        }
        primary_source = "Winsipedia all-time + ESPN exact-ID verification" if espn_meetings else "Winsipedia all-time"
        primary_url = _clean(wins.get("source_url"))
    else:
        series = _series_from_rows(espn_rows)
        primary_source = "ESPN exact-team schedule history" if espn_meetings else ""
        primary_url = ""

    recent = merged_rows[:MAX_RECENT_MEETINGS]
    return {
        "version": MODEL_VERSION,
        "status": status,
        "history_ready": status == VERIFIED_HISTORY,
        "event_id": event_id,
        "away_team": away,
        "home_team": home,
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "canonical_aliases": aliases,
        "meetings": int(series["meetings"]),
        "away_wins": int(series["away_wins"]),
        "home_wins": int(series["home_wins"]),
        "ties": int(series["ties"]),
        "series_record": {
            "away_wins": int(series["away_wins"]),
            "home_wins": int(series["home_wins"]),
            "ties": int(series["ties"]),
        },
        "avg_combined_total": float(series["avg_combined_total"]),
        "recent_meetings": recent,
        "sample": recent,
        "latest": dict(recent[0]) if recent else {},
        "line_hit_context": _line_hit_context(row, merged_rows),
        "sources_attempted": attempts,
        "sources_verified": sources_verified,
        "source_count_attempted": len(attempts),
        "source_count_verified": len(sources_verified),
        "sources_exhausted": status == VERIFIED_NO_HISTORY,
        "source": primary_source,
        "source_url": primary_url,
        "observed_at": observed_at,
        "no_history_claim_allowed": status == VERIFIED_NO_HISTORY,
        "projection_weight": HISTORY_PROJECTION_WEIGHT,
        "selection_weight": HISTORY_SELECTION_WEIGHT,
        "ranking_weight": HISTORY_RANKING_WEIGHT,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "api2_used": API2_USED,
    }


__all__ = [
    "API2_USED",
    "HISTORY_PROJECTION_WEIGHT",
    "HISTORY_RANKING_WEIGHT",
    "HISTORY_SELECTION_WEIGHT",
    "MAX_RECENT_MEETINGS",
    "MIN_INDEPENDENT_SOURCES",
    "MODEL_VERSION",
    "SOURCE_CONFLICT_REVIEW",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "TERMINAL_STATUSES",
    "VERIFIED_HISTORY",
    "VERIFIED_NO_HISTORY",
    "resolve_matchup_history",
]
