"""CFB Over/Under Slate V12 Data Recovery — post-12 hotfix.

Replays only the orchestration for frozen Steps 9-12 so the new multi-source
recovery layer can supply identity/history data. All frozen engine math and final
selection rules remain unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_over_under_final_v1 as final_model
import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_slate_v7 as frozen_step8
import cfb_over_under_slate_v11 as frozen_step12

MODEL_VERSION = "CFB OVER/UNDER SLATE V12 • POST-12 MULTI-SOURCE DATA RECOVERY"
FROZEN_STEP12_SLATE = "cfb_over_under_slate_v11"
MAX_WORKERS = frozen_step8.MAX_WORKERS


def _identity(game: Mapping[str, Any]) -> str:
    return str(game.get("identity_key") or game.get("game_id") or "")


@st.cache_data(ttl=120, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
    analysis_line: float,
) -> dict[str, Any]:
    # Frozen Step 8 is the last stage before the environment/history chain.
    base8 = frozen_step8.analyze_game(game, as_of_day, float(analysis_line))
    away = dict(base8.get("away") or {})
    home = dict(base8.get("home") or {})
    raw8 = dict(base8.get("raw") or {})

    # Step 9 — frozen math, recovered provider inputs.
    environment = recovery.build_environment_engine(game, away, home)
    raw9 = environment_engine.apply_to_raw(raw8, environment)
    final9 = final_model.synthesize(game, raw9)

    # Step 10 — frozen history application plus external all-time context.
    history = recovery.build_history_engine(
        game,
        away,
        home,
        step9_environment=environment,
    )
    raw10 = history_engine.apply_to_raw(raw9, history)
    final10 = final_model.synthesize(game, raw10)

    # Step 11 — unchanged current-season form + schedule-strength rules.
    form = form_engine.build_form_strength_engine(
        game,
        away,
        home,
        step10_history=history,
    )
    raw11 = form_engine.apply_to_raw(raw10, form)
    final11 = final_model.synthesize(game, raw11)

    assembled = dict(base8)
    assembled.update({
        "version": MODEL_VERSION,
        "raw": dict(raw11),
        "final": dict(final11),
        "step8_raw": raw8,
        "environment_engine": dict(environment),
        "step9_raw": raw9,
        "history_engine": dict(history),
        "step10_raw": raw10,
        "form_strength_engine": dict(form),
        "analysis_line": float(analysis_line),
        "analysis_line_environment_weight": 0.0,
        "projected_total_environment_weight": 0.0,
        "injury_model_weight": 0.0,
        "analysis_line_history_weight": 0.0,
        "projected_total_history_weight": 0.0,
        "selection_history_weight": 0.0,
        "analysis_line_form_weight": 0.0,
        "direct_selection_form_weight": 0.0,
        "data_recovery_hotfix": True,
        "data_recovery_version": recovery.MODEL_VERSION,
    })

    # Reuse the permanently frozen Step-12 certification attachment exactly.
    out = frozen_step12._attach_certificate(assembled)
    out["version"] = MODEL_VERSION
    out["data_recovery_hotfix"] = True
    out["data_recovery_version"] = recovery.MODEL_VERSION
    out["recovery_summary"] = {
        "environment_recovered": bool(environment.get("recovery_used")),
        "environment_source": str(environment.get("recovery_source") or ""),
        "external_h2h_ready": bool(
            (history.get("all_time_head_to_head") or {}).get("ready")
        ),
        "external_h2h_source": str(
            (history.get("all_time_head_to_head") or {}).get("source") or ""
        ),
    }
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

    max_workers = max(1, min(int(workers), MAX_WORKERS))
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

    rows.sort(key=lambda row: (
        str((row.get("game") or {}).get("kickoff_iso") or ""),
        str((row.get("game") or {}).get("identity_key") or ""),
    ))

    certified = sum(
        (row.get("certification") or {}).get("status") == "CERTIFIED"
        for row in rows
    )
    integrity_failed = sum(
        (row.get("certification") or {}).get("status") == "INTEGRITY_FAIL"
        for row in rows
    )
    environment_recovered = sum(
        bool((row.get("environment_engine") or {}).get("recovery_used"))
        for row in rows
    )
    external_h2h_ready = sum(
        bool(
            ((row.get("history_engine") or {}).get("all_time_head_to_head") or {})
            .get("ready")
        )
        for row in rows
    )

    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_with_lines": len(tasks),
        "games_analyzed": len(rows),
        "certified_games": int(certified),
        "integrity_failed_games": int(integrity_failed),
        "environment_recovered_games": int(environment_recovered),
        "external_h2h_ready_games": int(external_h2h_ready),
        "skipped_missing_line": skipped_missing_line,
        "errors": errors,
        "worker_count": max_workers,
        "analysis_line_projection_weight": 0.0,
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
    try:
        recovery.clear_recovery_cache()
    except Exception:
        pass


__all__ = [
    "FROZEN_STEP12_SLATE",
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "clear_scan_cache",
    "scan_slate",
]
