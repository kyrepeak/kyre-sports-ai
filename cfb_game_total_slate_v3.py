"""CFB Game Total Slate V3 — Step 6 runtime-fresh deterministic handoff.

Uses checked-in certified profiles before any legacy team-data path and keys its
cache to the snapshot revision. Frozen V1 projection/synthesis owners remain the
only model math.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_model_input_v2 as model_input
import cfb_game_total_slate_v1 as frozen

MODEL_VERSION = "CFB GAME TOTAL SLATE V3 • STEP 6 RUNTIME FRESH"
MAX_WORKERS = frozen.MAX_WORKERS
raw_model = frozen.raw_model
final_model = frozen.final_model
team_data = frozen.team_data


def _identity(game: Mapping[str, Any]) -> str:
    return str(game.get("identity_key") or game.get("game_id") or game.get("event_id") or "")


@st.cache_data(ttl=300, show_spinner=False)
def _analyze_game_cached(
    game: Mapping[str, Any],
    as_of_day: str,
    snapshot_revision: str,
) -> dict[str, Any]:
    del snapshot_revision

    local_profiles, local_diag = model_input.local_exact_profiles(game, str(as_of_day))
    if bool(local_diag.get("ready")):
        normalized_profiles = local_profiles
        input_diag = local_diag
        team_diag: dict[str, Any] = {
            "source": "checked-in-certified-runtime-v2-fast-path",
            "external_team_data_bypassed": True,
        }
    else:
        profiles, team_diag = team_data.load_matchup_team_data(game, as_of_day)
        normalized_profiles, input_diag = model_input.enrich_matchup_model_profiles(
            game, str(as_of_day), profiles
        )

    away = normalized_profiles.get("away") or {}
    home = normalized_profiles.get("home") or {}

    raw = raw_model.project_distribution(game, away, home)
    final = final_model.synthesize(game, raw)

    diag = dict(team_diag or {})
    diag["normalized_model_input"] = dict(input_diag or {})
    diag["version_v3"] = MODEL_VERSION

    return {
        "game": dict(game),
        "away": dict(away),
        "home": dict(home),
        "raw": dict(raw),
        "final": dict(final),
        "team_diag": diag,
    }


def analyze_game(game: Mapping[str, Any], as_of_day: str) -> dict[str, Any]:
    return _analyze_game_cached(
        game,
        str(as_of_day),
        model_input.local_snapshot_revision(),
    )


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    max_workers = max(1, min(int(workers), MAX_WORKERS))
    tasks = [
        dict(game) for game in games
        if bool(game.get("identity_verified") and game.get("date_matches_query"))
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(analyze_game, game, str(as_of_day)): game
            for game in tasks
        }
        for future in as_completed(futures):
            game = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append({
                    "identity": _identity(game),
                    "matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                    "error": f"{type(exc).__name__}: {exc}",
                })
    rows.sort(key=lambda row: (
        str((row.get("game") or {}).get("kickoff_iso") or ""),
        str((row.get("game") or {}).get("identity_key") or ""),
    ))
    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_analyzed": len(rows),
        "raw_ready": sum(bool((row.get("raw") or {}).get("ready")) for row in rows),
        "final_ready": sum(bool((row.get("final") or {}).get("ready")) for row in rows),
        "qualified_forecasts": sum(bool((row.get("final") or {}).get("rank_eligible")) for row in rows),
        "errors": errors,
        "worker_count": max_workers,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }


def clear_scan_cache() -> None:
    try:
        _analyze_game_cached.clear()
    except Exception:
        pass


__all__ = [
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "clear_scan_cache",
    "final_model",
    "model_input",
    "raw_model",
    "scan_slate",
    "team_data",
]
