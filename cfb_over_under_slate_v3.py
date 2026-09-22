"""CFB Over/Under Slate V3 — Upgrade Step 4 pace orchestration.

Pipeline:
frozen Step 8 -> frozen Step 3 offense-vs-defense -> Step 4 pace ->
unchanged Step 9 synthesis.

The analysis line remains a comparison threshold only and has 0% influence on
Step-4 pace evidence or projection adjustment.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_final_v1 as final_model
import cfb_over_under_pace_engine_v1 as pace_engine
import cfb_over_under_slate_v2 as frozen

MODEL_VERSION = "CFB OVER/UNDER SLATE V3 • UPGRADE STEP 4 PACE"
FROZEN_SLATE = "cfb_over_under_slate_v2"
MAX_WORKERS = frozen.MAX_WORKERS


def _identity(game: Mapping[str, Any]) -> str:
    return str(game.get("identity_key") or game.get("game_id") or "")


@st.cache_data(ttl=300, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
    analysis_line: float,
) -> dict[str, Any]:
    base = frozen.analyze_game(game, as_of_day, float(analysis_line))
    away = dict(base.get("away") or {})
    home = dict(base.get("home") or {})
    base_raw = dict(base.get("raw") or {})

    pace = pace_engine.build_pace_engine(game, away, home)
    raw = pace_engine.apply_to_raw(base_raw, pace)
    final = final_model.synthesize(game, raw)

    out = dict(base)
    out.update({
        "version": MODEL_VERSION,
        "raw": dict(raw),
        "final": dict(final),
        "step3_raw": base_raw,
        "pace_engine": dict(pace),
        "analysis_line": float(analysis_line),
        "analysis_line_pace_weight": 0.0,
    })
    return out


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    analysis_lines: Mapping[str, Any],
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
            pool.submit(analyze_game, game, str(as_of_day), line): (game, line)
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
    pace_ready = sum(
        bool((row.get("pace_engine") or {}).get("model_ready"))
        for row in rows
    )
    pace_applied = sum(
        bool((row.get("raw") or {}).get("upgrade_step4_applied"))
        for row in rows
    )

    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_with_lines": len(tasks),
        "games_analyzed": len(rows),
        "raw_ready": raw_ready,
        "final_ready": final_ready,
        "qualified_plays": qualified,
        "pace_engine_ready": pace_ready,
        "pace_engine_applied": pace_applied,
        "games_gated": len(rows) - final_ready,
        "skipped_missing_line": skipped_missing_line,
        "errors": errors,
        "worker_count": max_workers,
        "analysis_line_projection_weight": 0.0,
        "analysis_line_matchup_weight": 0.0,
        "analysis_line_pace_weight": 0.0,
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
    "FROZEN_SLATE",
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "clear_scan_cache",
    "scan_slate",
]
