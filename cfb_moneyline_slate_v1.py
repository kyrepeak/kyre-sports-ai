"""College Football Moneyline Slate Scanner V1 — Step 6.

Additive full-slate orchestration for the frozen Step-5 raw model and Step-6
final synthesis.

The scanner never uses sportsbook prices. It analyzes only games whose team
profiles and frozen raw model are ready, then ranks by final model P(win).

Network-heavy team data is cached by the existing providers. The scanner uses
a small worker pool to keep Saturday slates practical without flooding NCAA.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_moneyline_final_v1 as final_model
import cfb_moneyline_model_v1 as raw_model
import cfb_team_data_v2 as team_data

MODEL_VERSION = "CFB MONEYLINE SLATE V1 • STEP 6"
MAX_WORKERS = 2


@st.cache_data(ttl=300, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
) -> dict[str, Any]:
    """Analyze one verified game through frozen raw model -> final synthesis."""
    profiles, team_diag = team_data.load_matchup_team_data(game, as_of_day)
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}
    raw = raw_model.project_matchup(game, away, home)
    final = final_model.synthesize(game, away, home, raw)
    return {
        "game": dict(game),
        "away": dict(away),
        "home": dict(home),
        "raw": dict(raw),
        "final": dict(final),
        "team_diag": dict(team_diag),
    }


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Analyze a full verified slate and return every result plus diagnostics."""
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    max_workers = max(1, min(int(workers), MAX_WORKERS))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(analyze_game, dict(game), str(as_of_day)): dict(game)
            for game in games
            if bool(game.get("identity_verified") and game.get("date_matches_query"))
        }
        for future in as_completed(futures):
            game = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append({
                    "identity": str(game.get("identity_key") or game.get("game_id") or ""),
                    "matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                    "error": f"{type(exc).__name__}: {exc}",
                })

    rows.sort(
        key=lambda row: (
            str((row.get("game") or {}).get("kickoff_iso") or ""),
            str((row.get("game") or {}).get("identity_key") or ""),
        )
    )
    ready = sum(bool((row.get("final") or {}).get("ready")) for row in rows)
    gated = len(rows) - ready
    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_analyzed": len(rows),
        "games_ready": ready,
        "games_gated": gated,
        "errors": errors,
        "worker_count": max_workers,
        "market_price_used": False,
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
