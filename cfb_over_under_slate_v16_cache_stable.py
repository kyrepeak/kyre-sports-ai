"""CFB Over/Under Slate V16 — cache-stable market metadata bridge.

Performance-only wrapper over certified Slate V15 identity recovery and frozen
Slate V14 analysis.

Why this exists
---------------
The live market adapter attaches display/context fields such as sportsbook,
market timestamps, provider IDs and freshness metadata to each schedule row.
Those fields have certified 0.0% projection influence, but Streamlit cache keys
hash the full game mapping. A harmless market timestamp refresh could therefore
invalidate expensive current-team-data and selected-game analysis caches.

V16 removes only top-level ``market_*`` fields before the frozen V14 analysis
cache boundary, while preserving the explicit ``analysis_line`` argument that
already owns the comparison threshold. After the frozen result is returned, the
latest market fields are restored onto the result's display game mapping.

No schedule identity, team-data evidence, projection formula, ranking,
qualification, selection threshold, sportsbook semantics or market line is
changed. Official ESPN identity recovery remains owned by certified V15.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import cfb_over_under_slate_v14_runtime as frozen
import cfb_over_under_slate_v15_identity_bridge as prior

MODEL_VERSION = "KYRE CFB O/U SLATE V16 • CACHE-STABLE MARKET METADATA"
FROZEN_ANALYZER = "cfb_over_under_slate_v14_runtime"
FROZEN_IDENTITY_BRIDGE = "cfb_over_under_slate_v15_identity_bridge"
MARKET_PROJECTION_WEIGHT = 0.0
MAX_WORKERS = frozen.MAX_WORKERS


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _identity(game: Mapping[str, Any]) -> str:
    return _clean(game.get("identity_key") or game.get("game_id"))


def _market_metadata(game: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return display-only/context-only market fields from one schedule row."""
    return {
        str(key): value
        for key, value in dict(game or {}).items()
        if str(key).startswith("market_")
    }


def cache_stable_game(game: Mapping[str, Any] | None) -> dict[str, Any]:
    """Remove only certified 0%-weight market context from cache input.

    Identity, schedule facts, team IDs, venue, broadcast, rankings, status and
    every non-market field remain byte-for-byte represented in the mapping sent
    to frozen V14. The analysis threshold is not stored in this mapping; it is a
    separate required argument to ``analyze_game`` and therefore remains part of
    the frozen Streamlit cache key.
    """
    return {
        str(key): value
        for key, value in dict(game or {}).items()
        if not str(key).startswith("market_")
    }


def _restore_market_metadata(
    result: Mapping[str, Any],
    source_game: Mapping[str, Any],
) -> dict[str, Any]:
    """Restore latest display-only market context after cached analysis."""
    out = dict(result or {})
    game_out = dict(out.get("game") or {})
    game_out.update(_market_metadata(source_game))
    out["game"] = game_out
    out["cache_stable_market_metadata"] = True
    out["cache_stable_market_prefix"] = "market_"
    out["sportsbook_projection_weight"] = MARKET_PROJECTION_WEIGHT
    return out


def analyze_game(
    game: Mapping[str, Any],
    as_of_day: date | str,
    analysis_line: float,
) -> dict[str, Any]:
    """Hydrate official identity, stabilize cache input, then run frozen V14."""
    hydrated_game, _ = prior.hydrate_game_identity(game, as_of_day)
    stable_game = cache_stable_game(hydrated_game)
    result = frozen.analyze_game(
        stable_game,
        str(as_of_day),
        float(analysis_line),
    )
    return _restore_market_metadata(result, hydrated_game)


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: date | str,
    analysis_lines: Mapping[str, Any],
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use cache-stable inputs for frozen full-slate work, then restore context."""
    hydrated_games: list[dict[str, Any]] = []
    display_by_identity: dict[str, dict[str, Any]] = {}

    for game in games:
        hydrated, _ = prior.hydrate_game_identity(game, as_of_day)
        hydrated_games.append(cache_stable_game(hydrated))
        identity = _identity(hydrated)
        if identity:
            display_by_identity[identity] = dict(hydrated)

    rows, diag = frozen.scan_slate(
        hydrated_games,
        str(as_of_day),
        analysis_lines,
        workers=workers,
    )

    restored: list[dict[str, Any]] = []
    for row in rows:
        result_game = dict((row or {}).get("game") or {})
        source = display_by_identity.get(_identity(result_game))
        if source:
            restored.append(_restore_market_metadata(row, source))
        else:
            restored.append(dict(row))

    diag_out = dict(diag or {})
    diag_out.update({
        "version": MODEL_VERSION,
        "cache_stable_market_metadata": True,
        "cache_stable_market_prefix": "market_",
        "sportsbook_projection_weight": MARKET_PROJECTION_WEIGHT,
        "projection_math": "frozen_v14_unchanged",
        "identity_bridge": FROZEN_IDENTITY_BRIDGE,
    })
    return restored, diag_out


def clear_scan_cache() -> None:
    """Preserve inherited cache-clear API."""
    frozen.clear_scan_cache()


__all__ = [
    "FROZEN_ANALYZER",
    "FROZEN_IDENTITY_BRIDGE",
    "MARKET_PROJECTION_WEIGHT",
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "cache_stable_game",
    "clear_scan_cache",
    "scan_slate",
]
