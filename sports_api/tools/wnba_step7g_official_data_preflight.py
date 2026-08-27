"""Read-only Step 7G preflight for official WNBA public-data replacement paths.

This probe exists because stats.wnba.com is timing out from both GitHub Actions
and the Render-hosted backend. It does NOT change any frozen WNBA provider,
scheduler, model, feed, Supabase, or production-runtime behavior.

The probe answers a narrower question: can the already-supported official WNBA
public CDN + official WNBA web pages supply the *raw evidence* needed to build a
Step-7G-only replacement for the blocked Stats API core path?

It intentionally does not claim that a replacement adapter is complete. In
particular, exact historical rotation stints still need deterministic
reconstruction/validation from official starters + liveData substitutions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import httpx

from sports_api.wnba_live_game import (
    WNBALiveNotFoundError,
    WNBALiveUpstreamError,
    get_live_game_state_dataset,
    get_play_by_play_dataset,
)
from sports_api.wnba_schedule_context import _season_schedule_dataset

SEASON = 2026
REPORT_PATH = Path("step7g-official-data-preflight.json")
OFFICIAL_WEB_BASE = "https://www.wnba.com"

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _minutes(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    match = re.fullmatch(
        r"PT(?:(?P<hours>\d+(?:\.\d+)?)H)?"
        r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
        r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?",
        text,
        re.I,
    )
    if match:
        hours = float(match.group("hours") or 0.0)
        minutes = float(match.group("minutes") or 0.0)
        seconds = float(match.group("seconds") or 0.0)
        return hours * 60.0 + minutes + seconds / 60.0
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            try:
                return float(parts[0]) + float(parts[1]) / 60.0
            except ValueError:
                return None
    try:
        return float(text)
    except ValueError:
        return None


def _side_for_team(game: dict[str, Any], team_key: str) -> str | None:
    for side in ("away", "home"):
        if isinstance(game.get(side), dict) and game[side].get("team_key") == team_key:
            return side
    return None


def _player_from_state(
    state: dict[str, Any], player_id: int
) -> tuple[str, dict[str, Any]] | None:
    for side in ("away", "home"):
        team = state.get(side)
        if not isinstance(team, dict):
            continue
        players = team.get("players")
        if not isinstance(players, list):
            continue
        for player in players:
            if isinstance(player, dict) and player.get("player_id") == player_id:
                return side, player
    return None


def _sample_regular_player(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for side in ("away", "home"):
        team = state.get(side)
        if not isinstance(team, dict):
            continue
        for player in team.get("players") or []:
            if not isinstance(player, dict) or not isinstance(player.get("player_id"), int):
                continue
            if player.get("played") is not True:
                continue
            minutes = _minutes((player.get("statistics") or {}).get("minutes"))
            if minutes is None:
                continue
            candidates.append((minutes, side, player))
    if not candidates:
        raise RuntimeError("No played player with parseable minutes was found in the CDN box score.")
    candidates.sort(key=lambda row: (row[0], row[2].get("player_id") or 0), reverse=True)
    _, side, player = candidates[0]
    return side, player


def _final_games(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        game
        for game in schedule.get("games", [])
        if isinstance(game, dict)
        and (game.get("status") or {}).get("category") == "final"
        and isinstance(game.get("game_id"), str)
    ]
    rows.sort(
        key=lambda game: (
            game.get("official_schedule_date") or "",
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        ),
        reverse=True,
    )
    return rows


def _find_probe_game(
    final_games: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    errors: list[dict[str, str]] = []
    for game in final_games[:12]:
        game_id = game["game_id"]
        try:
            state = get_live_game_state_dataset(game_id, SEASON)
            pbp = get_play_by_play_dataset(game_id, SEASON)
        except (WNBALiveNotFoundError, WNBALiveUpstreamError) as exc:
            errors.append({"game_id": game_id, "error": str(exc)})
            continue
        if state.get("status", {}).get("category") != "final":
            continue
        if not isinstance(pbp.get("actions"), list) or not pbp.get("actions"):
            continue
        return game, state, pbp
    raise RuntimeError(
        "Could not find a recent final 2026 WNBA game with both official CDN box score "
        f"and play-by-play. Recent errors: {errors[:5]}"
    )


def _history_probe(
    *,
    final_games: list[dict[str, Any]],
    player_id: int,
    team_key: str,
    through_date: str,
    max_rows: int = 5,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    eligible = [
        game
        for game in final_games
        if (game.get("official_schedule_date") or "") <= through_date
        and _side_for_team(game, team_key) is not None
    ]
    for game in eligible[:14]:
        game_id = game["game_id"]
        try:
            state = get_live_game_state_dataset(game_id, SEASON)
        except (WNBALiveNotFoundError, WNBALiveUpstreamError) as exc:
            errors.append({"game_id": game_id, "error": str(exc)})
            continue
        match = _player_from_state(state, player_id)
        if match is None:
            continue
        side, player = match
        if player.get("played") is not True:
            continue
        stats = player.get("statistics") if isinstance(player.get("statistics"), dict) else {}
        rows.append(
            {
                "game_id": game_id,
                "game_date": game.get("official_schedule_date"),
                "side": side,
                "opponent_team_key": (
                    state["home"].get("team_key") if side == "away" else state["away"].get("team_key")
                ),
                "minutes": stats.get("minutes"),
                "points": stats.get("points"),
                "rebounds": stats.get("rebounds"),
                "assists": stats.get("assists"),
                "field_goals_attempted": stats.get("field_goals_attempted"),
                "three_pointers_attempted": stats.get("three_pointers_attempted"),
                "free_throws_attempted": stats.get("free_throws_attempted"),
                "turnovers": stats.get("turnovers"),
            }
        )
        if len(rows) >= max_rows:
            break
    return {
        "requested_rows": max_rows,
        "observed_rows": len(rows),
        "coverage": round(len(rows) / max_rows, 4),
        "rows": rows,
        "errors": errors[:5],
        "raw_evidence_supports_player_game_log_reconstruction": len(rows) >= 3,
    }


def _team_workload_probe(state: dict[str, Any], side: str) -> dict[str, Any]:
    team = state.get(side) or {}
    parsed: list[float] = []
    for player in team.get("players") or []:
        if not isinstance(player, dict) or player.get("played") is not True:
            continue
        value = _minutes((player.get("statistics") or {}).get("minutes"))
        if value is not None:
            parsed.append(value)
    total = round(sum(parsed), 3)
    return {
        "team_key": team.get("team_key"),
        "played_player_count_with_parseable_minutes": len(parsed),
        "summed_player_minutes": total,
        "at_least_regulation_team_minutes": total >= 199.0,
        "raw_evidence_supports_team_workload_reconstruction": len(parsed) >= 5 and total >= 199.0,
    }


def _rotation_raw_evidence_probe(state: dict[str, Any], pbp: dict[str, Any]) -> dict[str, Any]:
    starters: dict[str, list[int]] = {}
    for side in ("away", "home"):
        ids = []
        for player in (state.get(side) or {}).get("players") or []:
            if not isinstance(player, dict):
                continue
            starter = (_clean(player.get("starter")) or "").casefold()
            if starter in {"1", "true", "yes"} and isinstance(player.get("player_id"), int):
                ids.append(player["player_id"])
        starters[side] = ids

    substitutions = [
        action for action in pbp.get("actions", [])
        if isinstance(action, dict) and action.get("event_category") == "substitution"
    ]
    subtypes = sorted(
        {
            _clean(action.get("sub_type"))
            for action in substitutions
            if _clean(action.get("sub_type")) is not None
        }
    )
    participant_ids = sorted(
        {
            action.get("person_id")
            for action in substitutions
            if isinstance(action.get("person_id"), int)
        }
    )
    return {
        "away_starter_ids": starters["away"],
        "home_starter_ids": starters["home"],
        "away_starter_count": len(starters["away"]),
        "home_starter_count": len(starters["home"]),
        "substitution_event_count": len(substitutions),
        "substitution_subtypes": subtypes,
        "substitution_participant_count": len(participant_ids),
        "substitution_participant_ids": participant_ids,
        "raw_evidence_available": (
            len(starters["away"]) == 5
            and len(starters["home"]) == 5
            and len(substitutions) > 0
            and len(participant_ids) > 0
        ),
        "exact_rotation_reconstruction_certified": False,
        "certification_note": (
            "This preflight only verifies official starter + substitution evidence. "
            "Exact historical stint reconstruction remains a separate implementation/test step."
        ),
    }


def _official_roster_web_probe(team_key: str, sample_player_name: str | None) -> dict[str, Any]:
    url = f"{OFFICIAL_WEB_BASE}/team/{team_key}/roster"
    started = datetime.now(timezone.utc)
    try:
        response = httpx.get(url, headers=HTTP_HEADERS, timeout=20.0, follow_redirects=True)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        response.raise_for_status()
        html = response.text
        needle = (_clean(sample_player_name) or "").casefold()
        return {
            "url": str(response.url),
            "http_status": response.status_code,
            "elapsed_seconds": round(elapsed, 3),
            "html_bytes": len(response.content),
            "sample_player_name_present": bool(needle and needle in html.casefold()),
            "reachable": True,
        }
    except httpx.HTTPError as exc:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return {
            "url": url,
            "http_status": getattr(getattr(exc, "response", None), "status_code", None),
            "elapsed_seconds": round(elapsed, 3),
            "reachable": False,
            "error_type": type(exc).__name__,
        }


def build_report() -> dict[str, Any]:
    schedule = _season_schedule_dataset(SEASON)
    final_games = _final_games(schedule)
    if not final_games:
        raise RuntimeError("Official 2026 WNBA schedule contained no final games for the preflight.")

    probe_game, state, pbp = _find_probe_game(final_games)
    sample_side, sample_player = _sample_regular_player(state)
    sample_team = state[sample_side]
    player_id = sample_player["player_id"]
    player_name = sample_player.get("name")
    team_key = sample_team["team_key"]

    history = _history_probe(
        final_games=final_games,
        player_id=player_id,
        team_key=team_key,
        through_date=probe_game["official_schedule_date"],
    )
    workload = _team_workload_probe(state, sample_side)
    rotation = _rotation_raw_evidence_probe(state, pbp)
    roster_web = _official_roster_web_probe(team_key, player_name)

    source_url = str(schedule.get("source_url") or "")
    schedule_on_public_cdn = source_url.startswith("https://cdn.wnba.com/")
    live_sources_on_public_cdn = (
        str(state.get("source_url") or "").startswith("https://cdn.wnba.com/")
        and str(pbp.get("source_url") or "").startswith("https://cdn.wnba.com/")
    )

    return {
        "data_type": "wnba_step7g_official_data_preflight_v1",
        "created_at_utc": _utc_now_iso(),
        "season": SEASON,
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "schedule": {
            "source": schedule.get("source"),
            "source_url": schedule.get("source_url"),
            "source_variant": schedule.get("source_variant"),
            "game_count": schedule.get("game_count"),
            "final_game_count": len(final_games),
            "official_public_cdn": schedule_on_public_cdn,
        },
        "probe_game": {
            "game_id": probe_game.get("game_id"),
            "date": probe_game.get("official_schedule_date"),
            "away_team_key": (state.get("away") or {}).get("team_key"),
            "home_team_key": (state.get("home") or {}).get("team_key"),
            "box_score_source_url": state.get("source_url"),
            "play_by_play_source_url": pbp.get("source_url"),
            "official_public_cdn": live_sources_on_public_cdn,
            "box_score_player_count": (
                int((state.get("away") or {}).get("player_count") or 0)
                + int((state.get("home") or {}).get("player_count") or 0)
            ),
            "play_by_play_action_count": pbp.get("source_action_count"),
        },
        "sample_player": {
            "player_id": player_id,
            "player_name": player_name,
            "team_key": team_key,
            "side": sample_side,
            "minutes": (sample_player.get("statistics") or {}).get("minutes"),
        },
        "player_history_raw_evidence": history,
        "team_workload_raw_evidence": workload,
        "rotation_raw_evidence": rotation,
        "official_roster_web": roster_web,
        "feasibility": {
            "schedule_raw_evidence_available_without_stats_host": schedule_on_public_cdn,
            "boxscore_and_pbp_raw_evidence_available_without_stats_host": live_sources_on_public_cdn,
            "player_game_log_reconstruction_raw_evidence_available": history[
                "raw_evidence_supports_player_game_log_reconstruction"
            ],
            "team_workload_reconstruction_raw_evidence_available": workload[
                "raw_evidence_supports_team_workload_reconstruction"
            ],
            "rotation_reconstruction_raw_evidence_available": rotation["raw_evidence_available"],
            "official_roster_web_reachable": roster_web["reachable"],
            "exact_rotation_reconstruction_certified": False,
            "production_activation_safe_now": False,
        },
        "next_required_step": (
            "Build and regression-test a Step-7G-only adapter that reconstructs player/team "
            "history from official CDN box scores and exact rotation stints from official "
            "starter + substitution evidence. Do not activate production until reconstructed "
            "outputs pass frozen-schema and historical parity tests."
        ),
    }


def main() -> int:
    report = build_report()
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    feasibility = report["feasibility"]
    required = (
        "schedule_raw_evidence_available_without_stats_host",
        "boxscore_and_pbp_raw_evidence_available_without_stats_host",
        "player_game_log_reconstruction_raw_evidence_available",
        "team_workload_reconstruction_raw_evidence_available",
        "rotation_reconstruction_raw_evidence_available",
        "official_roster_web_reachable",
    )
    missing = [name for name in required if feasibility.get(name) is not True]
    if missing:
        raise RuntimeError(
            "Step 7G official-data preflight is not yet source-feasible: " + ", ".join(missing)
        )
    if feasibility.get("production_activation_safe_now") is not False:
        raise RuntimeError("Preflight must never certify production activation directly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
