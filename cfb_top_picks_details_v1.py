"""CFB Top Picks Step 4 detail context.

Adds tap-to-expand explanation content above the frozen Step-3 ranked board.
Historical matchup evidence is context only and carries exactly 0.0% projection,
selection, ranking, and sportsbook weight.

Identity rules:
- the target matchup must resolve to exactly one verified ESPN event ID;
- both ESPN team IDs must be present before external historical context is shown;
- no fuzzy event identity and no synthetic IDs are allowed;
- Winsipedia is used only as an all-time game-by-game historical context fallback.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import cfb_over_under_data_recovery_v1 as history_recovery
import cfb_schedule_v7_future_slate as schedule

MODEL_VERSION = "CFB TOP PICKS DETAILS V1 • STEP 4 WHY HISTORY BENEFITS"
HISTORY_PROJECTION_WEIGHT = 0.0
HISTORY_SELECTION_WEIGHT = 0.0
HISTORY_RANKING_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MAX_HISTORY_ROWS = 3


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _verified_target_game(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    event_id = _clean(row.get("event_id"))
    if not event_id.isdigit():
        return {}
    games = schedule.games_for_date(str(slate_day))
    exact = [
        dict(game)
        for game in games
        if (
            _clean(game.get("espn_event_id") or game.get("game_id")) == event_id
            and game.get("identity_verified") is True
            and game.get("date_matches_query") is True
        )
    ]
    if len(exact) != 1:
        return {}
    game = exact[0]
    away_id = _clean(game.get("away_espn_team_id"))
    home_id = _clean(game.get("home_espn_team_id"))
    if not (away_id.isdigit() and home_id.isdigit()):
        return {}
    return game


def _selected_team(row: Mapping[str, Any]) -> tuple[str, str]:
    pick = _clean(row.get("pick"))
    away = _clean(row.get("away"))
    home = _clean(row.get("home"))
    if away and pick.casefold().startswith(away.casefold()):
        return "away", away
    if home and pick.casefold().startswith(home.casefold()):
        return "home", home
    return "", ""


def _total_line(row: Mapping[str, Any]) -> float | None:
    pick = _clean(row.get("pick"))
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*$", pick)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _why(row: Mapping[str, Any]) -> str:
    market = _clean(row.get("market")).upper()
    pick = _clean(row.get("pick"))
    probability = int(round(_f(row.get("probability"), 0.0)))
    reliability = max(0.0, min(1.0, _f(row.get("reliability"), 0.0)))
    reliability_text = f"{reliability * 100.0:.0f}% reliability" if reliability else "verified model inputs"

    if market == "MONEYLINE":
        lead = f"The frozen CFB Moneyline model makes {pick} the winning side at {probability}%."
    elif market == "SPREAD":
        lead = f"The frozen projected-margin distribution gives {pick} an estimated {probability}% cover probability."
    elif market == "OVER/UNDER":
        lead = f"The certified CFB Over/Under model gives {pick} an estimated {probability}% probability."
    else:
        lead = f"The certified CFB model ranks {pick} at {probability}%."

    return (
        f"{lead} The ranking also carries {reliability_text}. "
        "Sportsbook lines are comparison thresholds only and have 0.0% projection weight."
    )


def _history_rows(series: Mapping[str, Any]) -> list[dict[str, Any]]:
    sample = series.get("sample")
    if not isinstance(sample, list):
        return []
    rows: list[dict[str, Any]] = []
    for raw in sample[:MAX_HISTORY_ROWS]:
        if not isinstance(raw, Mapping):
            continue
        rows.append({
            "date": _clean(raw.get("date")),
            "away_points": int(_f(raw.get("away_points"), 0.0)),
            "home_points": int(_f(raw.get("home_points"), 0.0)),
            "combined_total": int(_f(raw.get("combined_total"), 0.0)),
        })
    return rows


def _benefit(row: Mapping[str, Any], series: Mapping[str, Any]) -> str:
    meetings = int(_f(series.get("meetings"), 0.0))
    if meetings <= 0:
        return "No verified historical matchup edge is being claimed for this pick."

    market = _clean(row.get("market")).upper()
    side, team = _selected_team(row)
    if side:
        wins = int(_f(series.get(f"{side}_wins"), 0.0))
        other_wins = int(_f(series.get("home_wins" if side == "away" else "away_wins"), 0.0))
        latest = series.get("latest") if isinstance(series.get("latest"), Mapping) else {}
        latest_for = _f(latest.get(f"{side}_points"), 0.0)
        latest_against = _f(latest.get("home_points" if side == "away" else "away_points"), 0.0)

        if wins > other_wins:
            return (
                f"Historical benefit for {team}: it leads this verified series "
                f"{wins}-{other_wins} across {meetings} meetings."
            )
        if latest and latest_for > latest_against:
            return (
                f"Recent historical benefit for {team}: it won the latest verified meeting "
                f"{int(latest_for)}-{int(latest_against)}."
            )
        return (
            f"The verified series does not currently show a clear historical edge for {team}. "
            "The pick remains model-driven rather than history-driven."
        )

    if market == "OVER/UNDER":
        line = _total_line(row)
        avg_total = _f(series.get("avg_combined_total"), 0.0)
        pick = _clean(row.get("pick")).upper()
        if line is not None and avg_total > 0:
            if pick.startswith("OVER") and avg_total > line:
                return (
                    f"Historical benefit for the Over: the series averages {avg_total:.1f} total points, "
                    f"above the current {line:.1f} threshold."
                )
            if pick.startswith("UNDER") and avg_total < line:
                return (
                    f"Historical benefit for the Under: the series averages {avg_total:.1f} total points, "
                    f"below the current {line:.1f} threshold."
                )
            return (
                f"Series history averages {avg_total:.1f} total points and does not clearly support "
                f"the current {line:.1f} threshold. The model remains the reason for the pick."
            )

    return "Historical context is shown for transparency and does not change the ranked pick."


def build_pick_detail(row: Mapping[str, Any], slate_day: str) -> dict[str, Any]:
    """Build one read-only Step-4 dropdown payload."""
    game = _verified_target_game(row, slate_day)
    why = _why(row)
    if not game:
        return {
            "version": MODEL_VERSION,
            "ready": False,
            "why": why,
            "history_ready": False,
            "history_source": "",
            "meetings": 0,
            "history_rows": [],
            "benefit": "Verified matchup identity was unavailable, so no historical claim is shown.",
            "reason": "exact ESPN event/team identity unavailable",
            "history_projection_weight": HISTORY_PROJECTION_WEIGHT,
            "history_selection_weight": HISTORY_SELECTION_WEIGHT,
            "history_ranking_weight": HISTORY_RANKING_WEIGHT,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    away = _clean(game.get("away_team") or row.get("away"))
    home = _clean(game.get("home_team") or row.get("home"))
    series = history_recovery._fetch_winsipedia_games(away, home)
    history_ready = bool(series.get("ready"))
    rows = _history_rows(series) if history_ready else []

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "event_id": _clean(game.get("espn_event_id") or game.get("game_id")),
        "away_espn_team_id": _clean(game.get("away_espn_team_id")),
        "home_espn_team_id": _clean(game.get("home_espn_team_id")),
        "why": why,
        "history_ready": history_ready,
        "history_source": _clean(series.get("source")) if history_ready else "",
        "history_source_url": _clean(series.get("source_url")) if history_ready else "",
        "meetings": int(_f(series.get("meetings"), 0.0)) if history_ready else 0,
        "away_wins": int(_f(series.get("away_wins"), 0.0)) if history_ready else 0,
        "home_wins": int(_f(series.get("home_wins"), 0.0)) if history_ready else 0,
        "ties": int(_f(series.get("ties"), 0.0)) if history_ready else 0,
        "avg_combined_total": _f(series.get("avg_combined_total"), 0.0) if history_ready else 0.0,
        "history_rows": rows,
        "benefit": _benefit(row, series) if history_ready else (
            "No verified head-to-head series was available, so no historical benefit is claimed."
        ),
        "reason": "" if history_ready else "verified all-time matchup history unavailable",
        "history_projection_weight": HISTORY_PROJECTION_WEIGHT,
        "history_selection_weight": HISTORY_SELECTION_WEIGHT,
        "history_ranking_weight": HISTORY_RANKING_WEIGHT,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "HISTORY_PROJECTION_WEIGHT",
    "HISTORY_RANKING_WEIGHT",
    "HISTORY_SELECTION_WEIGHT",
    "MAX_HISTORY_ROWS",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "_benefit",
    "_selected_team",
    "_verified_target_game",
    "build_pick_detail",
]
