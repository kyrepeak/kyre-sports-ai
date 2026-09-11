"""CFB Over/Under Slate V15 — downstream official-identity bridge.

This additive wrapper hydrates only verified game identity/presentation metadata
before delegating analysis to frozen Slate V14. It reuses Schedule V7's strict
official identity rules, so it does not perform fuzzy game matching, synthesize
ESPN event IDs, alter sportsbook influence, or mutate frozen projection math.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import cfb_over_under_slate_v14_runtime as frozen
import cfb_schedule_v7_future_slate as schedule_v7

MODEL_VERSION = "KYRE CFB O/U SLATE V15 • DOWNSTREAM IDENTITY BRIDGE"
FROZEN_ANALYZER = "cfb_over_under_slate_v14_runtime"
MARKET_PROJECTION_WEIGHT = 0.0
MAX_WORKERS = frozen.MAX_WORKERS


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _identity_diag(
    game: Mapping[str, Any],
    *,
    matched: bool,
    method: str,
    official_rows: int,
    source: str = "",
) -> dict[str, Any]:
    return {
        "version": MODEL_VERSION,
        "matched": bool(matched),
        "match_method": str(method or "none"),
        "official_rows": int(official_rows),
        "source": str(source or ""),
        "espn_event_id": _clean(game.get("espn_event_id")),
        "away_espn_team_id": _clean(game.get("away_espn_team_id")),
        "home_espn_team_id": _clean(game.get("home_espn_team_id")),
        "fuzzy_matching": False,
        "synthetic_ids": False,
        "sportsbook_projection_weight": MARKET_PROJECTION_WEIGHT,
        "projection_math": "frozen_v14_unchanged",
    }


def hydrate_game_identity(
    game: Mapping[str, Any] | None,
    as_of_day: date | str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Hydrate verified identity metadata, or fail closed to the original game.

    Schedule V7 owns the identity policy. This bridge merely reapplies that
    already-certified policy immediately before frozen V14 analysis so verified
    event/team IDs cannot be lost between schedule selection and downstream
    runtime reconciliation.
    """
    original = dict(game or {})
    mutable = dict(original)
    day = _clean(as_of_day)[:10]
    if not day:
        return original, _identity_diag(
            original,
            matched=False,
            method="date_unavailable",
            official_rows=0,
        )

    try:
        official_rows = schedule_v7._official_rows_for_date(day)
    except Exception as exc:
        diag = _identity_diag(
            original,
            matched=False,
            method="official_identity_unavailable",
            official_rows=0,
        )
        diag["error_type"] = type(exc).__name__
        return original, diag

    match, method = schedule_v7._unique_official_match(mutable, official_rows)
    if not match:
        return original, _identity_diag(
            original,
            matched=False,
            method=method,
            official_rows=len(official_rows),
        )

    official_event_id = _clean(match.get("event_id"))
    if not official_event_id or not official_event_id.isdigit():
        return original, _identity_diag(
            original,
            matched=False,
            method="invalid_official_event_id",
            official_rows=len(official_rows),
        )

    schedule_v7._merge_official_row(mutable, match)
    merged_event_id = _clean(mutable.get("espn_event_id"))
    if merged_event_id != official_event_id:
        return original, _identity_diag(
            original,
            matched=False,
            method="official_event_id_mismatch",
            official_rows=len(official_rows),
        )

    source = _clean(match.get("_official_snapshot_kind"))
    return mutable, _identity_diag(
        mutable,
        matched=True,
        method=method,
        official_rows=len(official_rows),
        source=source,
    )


def analyze_game(
    game: Mapping[str, Any],
    as_of_day: date | str,
    analysis_line: float,
) -> dict[str, Any]:
    """Hydrate identity, then delegate projection work unchanged to frozen V14."""
    hydrated_game, _ = hydrate_game_identity(game, as_of_day)
    return frozen.analyze_game(hydrated_game, as_of_day, analysis_line)


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: date | str,
    analysis_lines: Mapping[str, Any],
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Hydrate every slate game, then preserve frozen V14 scan behavior exactly.

    Analysis-line identity keys, qualification rules, concurrency, sorting,
    diagnostics, ranking inputs, and projection math remain owned by V14. If an
    official identity cannot be recovered, ``hydrate_game_identity`` fails
    closed to that game's original mapping before V14 receives it.
    """
    hydrated_games = [
        hydrate_game_identity(game, as_of_day)[0]
        for game in games
    ]
    return frozen.scan_slate(
        hydrated_games,
        str(as_of_day),
        analysis_lines,
        workers=workers,
    )


def clear_scan_cache() -> None:
    """Preserve the frozen runtime-slate cache API for inherited page controls."""
    frozen.clear_scan_cache()


__all__ = [
    "FROZEN_ANALYZER",
    "MARKET_PROJECTION_WEIGHT",
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "clear_scan_cache",
    "hydrate_game_identity",
    "scan_slate",
]
