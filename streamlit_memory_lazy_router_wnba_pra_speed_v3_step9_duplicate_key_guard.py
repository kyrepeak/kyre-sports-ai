"""WNBA PRA Speed V3 Step 9 — duplicate Streamlit key runtime guard.

This overlay preserves every frozen WNBA Navigation V2 / PRA Speed V3 artifact.
It wraps the frozen Game Center loader only while the frozen Step-8 router
renders, removing duplicate (team, player_id) identity rows before Streamlit
constructs player buttons. Projection values and model math are unchanged.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step8 as frozen_parent
import wnba_pra_game_center_v2_step3 as game_center


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 9 DUPLICATE KEY GUARD"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step8"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _dedupe_game_center_payload(payload: Any) -> Any:
    """Suppress duplicate player identities without changing surviving values."""
    if not isinstance(payload, Mapping):
        return payload

    teams_obj = payload.get("teams")
    if not isinstance(teams_obj, Mapping):
        return payload

    clean_payload = dict(payload)
    clean_teams: dict[str, list[Any]] = {}
    suppressed = 0

    for team_key, rows_obj in teams_obj.items():
        rows = list(rows_obj or []) if isinstance(rows_obj, (list, tuple)) else []
        seen_player_ids: set[int] = set()
        clean_rows: list[Any] = []

        for row in rows:
            if not isinstance(row, Mapping):
                clean_rows.append(row)
                continue

            pid = game_center._integer(row.get("player_id"))
            if pid is not None:
                if pid in seen_player_ids:
                    suppressed += 1
                    continue
                seen_player_ids.add(pid)

            clean_rows.append(dict(row))

        clean_teams[str(team_key)] = clean_rows

    clean_payload["teams"] = clean_teams
    clean_payload["players"] = sum(len(rows) for rows in clean_teams.values())
    clean_payload["duplicate_player_rows_suppressed"] = suppressed
    clean_payload["duplicate_key_guard_active"] = True
    return clean_payload


def render_app() -> Any:
    """Render the frozen Step-8 tree with one identity-dedupe compatibility guard."""
    original_loader = game_center.load_game_center

    def guarded_loader(*args: Any, **kwargs: Any) -> Any:
        return _dedupe_game_center_payload(original_loader(*args, **kwargs))

    if hasattr(original_loader, "clear"):
        guarded_loader.clear = original_loader.clear  # type: ignore[attr-defined]

    game_center.load_game_center = guarded_loader
    try:
        return frozen_parent.render_app()
    finally:
        game_center.load_game_center = original_loader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_dedupe_game_center_payload",
    "record_bootstrap_import_ms",
    "render_app",
]
