"""WNBA PRA Repair V1 Step 2 — Page-2 canonical team identity overlay.

The frozen WNBA PRA Speed V3 Step-9 runtime remains the parent.  This overlay
changes only the identity handoff between the lightweight Slate and the frozen
Game Center:

* reconcile selected-game team IDs against the canonical 2026 WNBA registry;
* fail closed when numeric/name/tricode identity conflicts;
* leave the frozen Game Center, model, projections, market math and sportsbook
  influence untouched;
* emit a hidden production-proof marker after the frozen Game Center renders.

The wrapper is installed only for the duration of one Streamlit render and is
always restored.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard as frozen_parent
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_slate_v2_step2 as slate
import wnba_pra_repair_v1_step2_team_identity as identity

FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"
MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 2 TEAM IDENTITY"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_PROJECTION_MATH = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
TEAM_IDENTITY_VERSION = identity.VERSION
PROOF_MARKER = "wnba-pra-repair-v1-step2-team-identity"


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _reconciled_slate_loader(original_loader, day_str: str) -> dict[str, Any]:
    payload = original_loader(str(day_str))
    return identity.reconcile_slate_payload(payload)


def _prewarm_game_inputs(
    game_id: str,
    game_date: str,
    away_id: int,
    home_id: int,
) -> None:
    """Warm the exact frozen Page-2 inputs concurrently.

    The frozen Game Center/role engine still owns every returned value and all
    projection math.  This only overlaps independent cached provider reads that
    the frozen path would otherwise perform sequentially.
    """
    try:
        import wnba_availability_v27 as availability
        import wnba_role_v28 as role

        season = int(str(game_date)[:4])
        calls = (
            (availability._verified_pool_for_day, (str(game_date),)),
            (availability._event_summary, (str(game_id),)),
            (availability._team_injury_feed, (int(away_id),)),
            (availability._team_injury_feed, (int(home_id),)),
            (role._advanced_usage_fetch, (season, 0)),
            (role._advanced_usage_fetch, (season, 10)),
            (role._advanced_usage_fetch, (season, 5)),
        )
        with ThreadPoolExecutor(max_workers=len(calls), thread_name_prefix="wnba-page2-warm") as pool:
            futures = [pool.submit(fn, *args) for fn, args in calls]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    # Preserve frozen loader fallback semantics.  A failed warm
                    # must never replace or fabricate the authoritative read.
                    pass
    except Exception:
        # Warmup is latency-only; the unchanged frozen loader remains authority.
        pass


def _team_player_count(payload: Mapping[str, Any], team_id: int) -> int:
    teams = payload.get("teams") if isinstance(payload, Mapping) else None
    if not isinstance(teams, Mapping):
        return 0
    rows = teams.get(str(int(team_id)))
    return len(rows) if isinstance(rows, list) else 0


def _proof_marker(payload: Mapping[str, Any]) -> None:
    snapshot_raw = st.session_state.get(slate.SESSION_SELECTED_GAME)
    if not isinstance(snapshot_raw, Mapping) or not isinstance(payload, Mapping):
        return

    try:
        snapshot = identity.reconcile_game_identity(snapshot_raw)
    except identity.WNBATeamIdentityError:
        return

    away_id = int(snapshot["away_team_id"])
    home_id = int(snapshot["home_team_id"])
    away_count = _team_player_count(payload, away_id)
    home_count = _team_player_count(payload, home_id)
    status = "green" if away_count > 0 and home_count > 0 else "blocked"

    st.markdown(
        '<div style="display:none" '
        f'data-wnba-pra-repair-v1-step2="{escape(PROOF_MARKER)}" '
        f'data-status="{status}" '
        f'data-away-team-id="{away_id}" '
        f'data-home-team-id="{home_id}" '
        f'data-away-player-count="{away_count}" '
        f'data-home-player-count="{home_count}" '
        f'data-away-id-repaired="{str(bool(snapshot.get("away_identity_repaired"))).lower()}" '
        f'data-home-id-repaired="{str(bool(snapshot.get("home_identity_repaired"))).lower()}" '
        f'data-identity-version="{escape(identity.VERSION)}"></div>',
        unsafe_allow_html=True,
    )


def render_app() -> Any:
    original_slate_loader = slate.load_slate
    original_game_loader = game_center.load_game_center
    original_game_renderer = game_center.render_game_center
    original_perf_slate_loader = performance._FROZEN_SLATE_LOADER
    original_perf_game_loader = performance._FROZEN_GAME_LOADER

    def guarded_slate_loader(day_str: str) -> dict[str, Any]:
        return _reconciled_slate_loader(original_slate_loader, day_str)

    if hasattr(original_slate_loader, "clear"):
        guarded_slate_loader.clear = original_slate_loader.clear  # type: ignore[attr-defined]

    def guarded_game_loader(
        game_id: str,
        game_date: str,
        away_id: int,
        home_id: int,
        away_team: str,
        home_team: str,
    ) -> dict[str, Any]:
        _prewarm_game_inputs(game_id, game_date, away_id, home_id)
        payload = original_game_loader(
            game_id,
            game_date,
            away_id,
            home_id,
            away_team,
            home_team,
        )
        # Step 5's static frozen-loader reference used to bypass the Step-9
        # duplicate-key wrapper.  Preserve the already-frozen Step-9 behavior
        # explicitly on this handoff.
        return frozen_parent._dedupe_game_center_payload(payload)

    if hasattr(original_game_loader, "clear"):
        guarded_game_loader.clear = original_game_loader.clear  # type: ignore[attr-defined]

    def guarded_game_renderer(state):
        payload = original_game_renderer(state)
        if isinstance(payload, Mapping):
            _proof_marker(payload)
        return payload

    slate.load_slate = guarded_slate_loader
    game_center.load_game_center = guarded_game_loader
    game_center.render_game_center = guarded_game_renderer

    # Step-5 caches import-time loader references.  Patch those exact seams so
    # Page 2 cannot bypass canonical team identity or the latency-only warmup.
    performance._FROZEN_SLATE_LOADER = guarded_slate_loader
    performance._FROZEN_GAME_LOADER = guarded_game_loader
    try:
        return frozen_parent.render_app()
    finally:
        slate.load_slate = original_slate_loader
        game_center.load_game_center = original_game_loader
        game_center.render_game_center = original_game_renderer
        performance._FROZEN_SLATE_LOADER = original_perf_slate_loader
        performance._FROZEN_GAME_LOADER = original_perf_game_loader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION_MATH",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "PROOF_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TEAM_IDENTITY_VERSION",
    "_prewarm_game_inputs",
    "_proof_marker",
    "_reconciled_slate_loader",
    "record_bootstrap_import_ms",
    "render_app",
]
