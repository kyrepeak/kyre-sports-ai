"""Additive CFB Game Total Slate V2 — normalized model-input routing.

Preserves the frozen V1 Step-11/Step-12 math and only upgrades the team-profile
input routing when the legacy FBS profile is incomplete.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_model_input_v1 as model_input
import cfb_game_total_slate_v1 as frozen

MODEL_VERSION = "CFB GAME TOTAL SLATE V2 • PAGE CLEANUP STEP 1"
MAX_WORKERS = frozen.MAX_WORKERS

# Explicit immutable math owners.
raw_model = frozen.raw_model
final_model = frozen.final_model
team_data = frozen.team_data


def _identity(game: Mapping[str, Any]) -> str:
    return str(game.get("identity_key") or game.get("game_id") or game.get("event_id") or "")


@st.cache_data(ttl=300, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
) -> dict[str, Any]:
    profiles, team_diag = team_data.load_matchup_team_data(game, as_of_day)
    normalized_profiles, input_diag = model_input.enrich_matchup_model_profiles(
        game,
        str(as_of_day),
        profiles,
    )
    away = normalized_profiles.get("away") or {}
    home = normalized_profiles.get("home") or {}

    # Frozen math boundary: same exact V1 functions.
    raw = raw_model.project_distribution(game, away, home)
    final = final_model.synthesize(game, raw)

    diag = dict(team_diag or {})
    diag["normalized_model_input"] = dict(input_diag or {})
    diag["version_v2"] = MODEL_VERSION

    return {
        "game": dict(game),
        "away": dict(away),
        "home": dict(home),
        "raw": dict(raw),
        "final": dict(final),
        "team_diag": diag,
    }


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    max_workers = max(1, min(int(workers), MAX_WORKERS))

    tasks = [
        dict(game)
        for game in games
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

    rows.sort(
        key=lambda row: (
            str((row.get("game") or {}).get("kickoff_iso") or ""),
            str((row.get("game") or {}).get("identity_key") or ""),
        )
    )

    raw_ready = sum(bool((row.get("raw") or {}).get("ready")) for row in rows)
    final_ready = sum(bool((row.get("final") or {}).get("ready")) for row in rows)
    qualified = sum(bool((row.get("final") or {}).get("rank_eligible")) for row in rows)
    fallbacks = sum(bool(
        (((row.get("team_diag") or {}).get("normalized_model_input") or {}).get("fallback_used"))
    ) for row in rows)

    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_analyzed": len(rows),
        "raw_ready": raw_ready,
        "final_ready": final_ready,
        "qualified_forecasts": qualified,
        "games_gated": len(rows) - final_ready,
        "normalized_input_fallbacks": fallbacks,
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
        analyze_game.clear()
    except Exception:
        pass


__all__ = [
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "clear_scan_cache",
    "final_model",
    "raw_model",
    "scan_slate",
    "team_data",
]
