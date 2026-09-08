"""College Football Over/Under Slate V1 — Step 9.

Additive full-slate orchestration for permanently frozen Step-8 projected-total
model plus Step-9 selection/ranking.

Each game receives its own user-entered analysis line. The line is a comparison
threshold only and has exactly 0% projection weight. No sportsbook feed,
sportsbook price, market-implied probability, edge/EV, or Monte Carlo is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_final_v1 as final_model
import cfb_over_under_model_v1 as raw_model
import cfb_team_data_v2 as team_data

MODEL_VERSION = "CFB OVER/UNDER SLATE V1 • STEP 9"
MAX_WORKERS = 2


def _identity(game: Mapping[str, Any]) -> str:
    return str(game.get("identity_key") or game.get("game_id") or "")


@st.cache_data(ttl=300, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
    analysis_line: float,
) -> dict[str, Any]:
    """Analyze one verified pregame matchup through frozen Step 8 -> Step 9."""
    profiles, team_diag = team_data.load_matchup_team_data(game, as_of_day)
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}
    raw = raw_model.project_matchup(game, away, home, float(analysis_line))
    final = final_model.synthesize(game, raw)
    return {
        "game": dict(game),
        "away": dict(away),
        "home": dict(home),
        "raw": dict(raw),
        "final": dict(final),
        "team_diag": dict(team_diag),
        "analysis_line": float(analysis_line),
    }


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    analysis_lines: Mapping[str, Any],
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Analyze games that have explicit per-game analysis lines."""
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_missing_line = 0
    max_workers = max(1, min(int(workers), MAX_WORKERS))

    tasks: list[tuple[dict[str, Any], float]] = []
    for game in games:
        if not bool(game.get("identity_verified") and game.get("date_matches_query")):
            continue
        identity = _identity(game)
        if not identity or identity not in analysis_lines:
            skipped_missing_line += 1
            continue
        try:
            line = float(analysis_lines[identity])
        except Exception:
            skipped_missing_line += 1
            continue
        tasks.append((dict(game), line))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                analyze_game,
                game,
                str(as_of_day),
                line,
            ): (game, line)
            for game, line in tasks
        }
        for future in as_completed(futures):
            game, line = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append({
                    "identity": _identity(game),
                    "matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                    "analysis_line": str(line),
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

    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_with_lines": len(tasks),
        "games_analyzed": len(rows),
        "raw_ready": raw_ready,
        "final_ready": final_ready,
        "qualified_plays": qualified,
        "games_gated": len(rows) - final_ready,
        "skipped_missing_line": skipped_missing_line,
        "errors": errors,
        "worker_count": max_workers,
        "analysis_line_projection_weight": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
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
    "scan_slate",
]
