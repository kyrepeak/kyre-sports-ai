"""Pure NFL Game Totals Page 2 display-context normalizers.

This module contains no external provider transport. Streamlit obtains live
context only through ``nfl_game_totals_page2_context_gateway_v2`` -> Kyre Sports
API. Server-side provider collection lives under ``sports_api.api``.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd

DISPLAY_ONLY = True
MODEL_INFLUENCE = 0.0
HISTORY_SOURCE = "nflverse"
AVAILABILITY_SOURCE = "NFL.com Official Injury Report"

_TEAM_ALIASES = {"JAC": "JAX", "LA": "LAR", "WSH": "WAS"}
_KEY_OFFENSE = frozenset({"QB", "RB", "FB", "WR", "TE", "C", "G", "T", "OT", "OG", "OL", "C/G", "G/T"})
_STATUS_RANK = {"OUT": 0, "DOUBTFUL": 1, "QUESTIONABLE": 2, "PROBABLE": 3, "NO GAME STATUS": 4, "": 5}
_POSITION_RANK = {"QB": 0, "WR": 1, "RB": 2, "TE": 3, "OT": 4, "T": 4, "OG": 5, "G": 5, "C": 6, "OL": 7, "FB": 8, "C/G": 9, "G/T": 9}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _abbr(value: Any) -> str:
    text = _text(value).upper()
    return _TEAM_ALIASES.get(text, text) if len(text) in {2, 3} else ""


def history_empty(state: str, reason: str) -> dict[str, Any]:
    return {"ready": False, "semantic_state": state, "reason": reason, "source": HISTORY_SOURCE, "display_only": DISPLAY_ONLY, "model_influence": MODEL_INFLUENCE, "games": 0, "overs": 0, "unders": 0, "pushes": 0, "line_verified_games": 0, "average_combined_score": None, "meetings": []}


def _ou_result(total: float, line: float | None) -> str:
    if line is None:
        return "—"
    if abs(total - line) < 1e-9:
        return "PUSH"
    return "OVER" if total > line else "UNDER"


def normalize_matchup_history(frame: pd.DataFrame | None, away_abbr: str, home_abbr: str, *, limit: int = 3) -> dict[str, Any]:
    away = _abbr(away_abbr); home = _abbr(home_abbr)
    if not away or not home or away == home:
        return history_empty("MATCHUP_IDENTITY_UNAVAILABLE", "Exact team identity is unavailable.")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return history_empty("HISTORY_SOURCE_UNAVAILABLE", "Verified matchup history is unavailable.")
    required = {"gameday", "away_team", "home_team", "away_score", "home_score"}
    if not required.issubset(frame.columns):
        return history_empty("HISTORY_SCHEMA_UNAVAILABLE", "Verified history fields are incomplete.")
    rows = frame.copy()
    rows["_away"] = rows["away_team"].map(_abbr); rows["_home"] = rows["home_team"].map(_abbr)
    pair = rows[((rows["_away"] == away) & (rows["_home"] == home)) | ((rows["_away"] == home) & (rows["_home"] == away))].copy()
    pair = pair[pair["away_score"].notna() & pair["home_score"].notna()]
    if pair.empty:
        return history_empty("NO_PREVIOUS_MEETINGS", "No previous verified meetings are available for these teams.")
    pair["_date"] = pd.to_datetime(pair["gameday"], errors="coerce")
    pair = pair[pair["_date"].notna()].sort_values("_date", ascending=False)
    meetings: list[dict[str, Any]] = []
    for raw in pair.head(min(max(int(limit), 1), 10)).to_dict("records"):
        away_score = _num(raw.get("away_score")); home_score = _num(raw.get("home_score"))
        if away_score is None or home_score is None:
            continue
        row_away = _abbr(raw.get("away_team")); row_home = _abbr(raw.get("home_team")); combined = float(away_score + home_score); closing = _num(raw.get("total_line"))
        meetings.append({"date": str(raw.get("gameday") or "")[:10], "away_abbr": row_away, "home_abbr": row_home, "away_score": int(away_score), "home_score": int(home_score), "score": f"{row_away} {int(away_score)} – {row_home} {int(home_score)}", "combined_score": combined, "closing_total": closing, "ou_result": _ou_result(combined, closing)})
    if not meetings:
        return history_empty("NO_PREVIOUS_MEETINGS", "No previous verified completed meetings are available.")
    verified = [row for row in meetings if row["closing_total"] is not None]
    return {"ready": True, "semantic_state": "", "reason": "", "source": HISTORY_SOURCE, "display_only": DISPLAY_ONLY, "model_influence": MODEL_INFLUENCE, "games": len(meetings), "overs": sum(row["ou_result"] == "OVER" for row in verified), "unders": sum(row["ou_result"] == "UNDER" for row in verified), "pushes": sum(row["ou_result"] == "PUSH" for row in verified), "line_verified_games": len(verified), "average_combined_score": round(sum(row["combined_score"] for row in meetings) / len(meetings), 1), "meetings": meetings}


def availability_empty(reason: str) -> dict[str, Any]:
    return {"ready": False, "reason": reason, "source": AVAILABILITY_SOURCE, "display_only": DISPLAY_ONLY, "model_influence": MODEL_INFLUENCE, "impact": "UNAVAILABLE", "away": [], "home": []}


def _designation(row: Mapping[str, Any]) -> dict[str, str] | None:
    position = _text(row.get("position")).upper()
    if position not in _KEY_OFFENSE:
        return None
    player = _text(row.get("player_name"))
    if not player:
        return None
    status = _text(row.get("game_status")).upper(); injury = _text(row.get("injury")); practice = _text(row.get("practice_status"))
    if not status and not injury and not practice:
        return None
    return {"player_name": player, "position": position, "game_status": status or "NO GAME STATUS", "injury": injury, "practice_status": practice}


def _rank_designation(row: Mapping[str, Any]) -> tuple[int, int, str]:
    return (_STATUS_RANK.get(_text(row.get("game_status")).upper(), 4), _POSITION_RANK.get(_text(row.get("position")).upper(), 99), _text(row.get("player_name")).casefold())


def _team_designations(team_report: Mapping[str, Any], limit: int) -> list[dict[str, str]]:
    items = [item for raw in (team_report.get("rows") or []) if isinstance(raw, Mapping) and (item := _designation(raw)) is not None]
    items.sort(key=_rank_designation)
    return items[: min(max(int(limit), 1), 5)]


def _impact(rows: list[dict[str, str]]) -> str:
    statuses = {_text(row.get("game_status")).upper() for row in rows}
    if statuses & {"OUT", "DOUBTFUL"}: return "HIGH"
    if "QUESTIONABLE" in statuses: return "MEDIUM"
    return "LOW IMPACT"


def normalize_availability(report: Mapping[str, Any] | None, away_abbr: str, home_abbr: str, *, limit_per_team: int = 2) -> dict[str, Any]:
    away = _abbr(away_abbr); home = _abbr(home_abbr)
    if not away or not home or away == home:
        return availability_empty("Exact team identity is unavailable.")
    if not isinstance(report, Mapping):
        return availability_empty("Official NFL injury report unavailable.")
    away_report = report.get(away) if isinstance(report.get(away), Mapping) else {}; home_report = report.get(home) if isinstance(report.get(home), Mapping) else {}
    if away_report.get("verified") is not True or home_report.get("verified") is not True:
        return availability_empty("Official NFL injury report is not verified for both teams.")
    away_rows = _team_designations(away_report, limit_per_team); home_rows = _team_designations(home_report, limit_per_team)
    return {"ready": True, "reason": "", "source": AVAILABILITY_SOURCE, "display_only": DISPLAY_ONLY, "model_influence": MODEL_INFLUENCE, "impact": _impact(away_rows + home_rows), "away": away_rows, "home": home_rows}


def _gateway_bundle(game: Mapping[str, Any], *, history_limit: int = 3, availability_limit: int = 2) -> dict[str, Any]:
    from nfl_game_totals_page2_context_gateway_v2 import load_game_total_page2_context
    return load_game_total_page2_context(
        away_abbr=_abbr(game.get("away_abbr")),
        home_abbr=_abbr(game.get("home_abbr")),
        history_limit=history_limit,
        availability_limit=availability_limit,
    )


def load_matchup_history(game: Mapping[str, Any], *, limit: int = 3) -> dict[str, Any]:
    bundle = _gateway_bundle(game, history_limit=limit, availability_limit=2)
    history = bundle.get("history")
    return dict(history) if isinstance(history, Mapping) else history_empty("GATEWAY_UNAVAILABLE", "Kyre Sports API matchup history unavailable.")


def load_availability(game: Mapping[str, Any], *, limit_per_team: int = 2) -> dict[str, Any]:
    bundle = _gateway_bundle(game, history_limit=3, availability_limit=limit_per_team)
    availability = bundle.get("availability")
    return dict(availability) if isinstance(availability, Mapping) else availability_empty("Kyre Sports API availability unavailable.")


__all__ = ["AVAILABILITY_SOURCE", "DISPLAY_ONLY", "HISTORY_SOURCE", "MODEL_INFLUENCE", "availability_empty", "history_empty", "load_availability", "load_matchup_history", "normalize_availability", "normalize_matchup_history"]
