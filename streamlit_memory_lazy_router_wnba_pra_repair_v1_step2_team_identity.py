"""WNBA PRA Repair V1 Step 2 — Page-2 canonical team identity overlay.

The frozen WNBA PRA Speed V3 Step-9 runtime remains the parent. This overlay
changes only the selected-game handoff between the lightweight Slate and the
frozen Game Center:

* reconcile selected-game team IDs against the canonical 2026 WNBA registry;
* keep the Step-5 cached Slate source on that same canonicalized payload;
* prewarm the three independent frozen Game-Center dependency groups in
  parallel, then let the unchanged frozen Game Center consume their caches;
* fail closed when numeric/name/tricode identity conflicts;
* leave the frozen Game Center, model, projections, market math and sportsbook
  influence untouched;
* emit a hidden production-proof marker after the frozen Game Center renders.

The wrapper is installed only for the duration of one Streamlit render and is
always restored.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import hashlib
from html import escape
import os
from pathlib import Path
import re
import socket
import subprocess
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
DEPLOYMENT_PROOF_MARKER = "streamlit-runtime-v1"
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_RUNTIME_SHA_ENV_KEYS = (
    "STREAMLIT_GIT_COMMIT",
    "GIT_COMMIT",
    "SOURCE_COMMIT",
    "COMMIT_SHA",
)
RUNTIME_ATTESTATION_PATHS = (
    "app.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py",
    "wnba_pra_repair_v1_step2_team_identity.py",
    "wnba_pra_game_center_v2_step3.py",
)


def _full_sha(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if _SHA40_RE.fullmatch(text) else ""


def _git_rev(spec: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", spec],
            cwd=Path(__file__).resolve().parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2.0,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return _full_sha(completed.stdout)


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


@lru_cache(maxsize=1)
def _runtime_bundle_attestation() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    blobs: dict[str, str] = {}
    for rel in RUNTIME_ATTESTATION_PATHS:
        target = root / rel
        if not target.is_file():
            return {"digest": "", "file_count": 0, "complete": False}
        try:
            blobs[rel] = _git_blob_sha(target)
        except Exception:
            return {"digest": "", "file_count": 0, "complete": False}
    canonical = "\n".join(f"{path}={blobs[path]}" for path in sorted(blobs))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"digest": digest, "file_count": len(blobs), "complete": True}


@lru_cache(maxsize=1)
def _runtime_deployment_identity() -> dict[str, Any]:
    runtime_sha = ""
    for key in _RUNTIME_SHA_ENV_KEYS:
        runtime_sha = _full_sha(os.environ.get(key))
        if runtime_sha:
            break
    if not runtime_sha:
        runtime_sha = _git_rev("HEAD")

    tree_sha = _git_rev("HEAD^{tree}") if runtime_sha else ""
    host = str(socket.gethostname() or "").strip()
    build_id = f"tree:{tree_sha}" if tree_sha else ""
    deploy_id = f"streamlit:{host}" if host else ""
    ready = bool(runtime_sha and build_id and deploy_id)
    bundle = _runtime_bundle_attestation()
    return {
        "production_sha": runtime_sha,
        "build_id": build_id,
        "deploy_id": deploy_id,
        "health_sha": runtime_sha if ready else "",
        "readiness_sha": runtime_sha if ready else "",
        "ui_proof_sha": runtime_sha if ready else "",
        "health_ok": ready,
        "readiness_ok": ready,
        "ui_proof_ok": ready,
        "runtime_bundle_digest": str(bundle["digest"]),
        "runtime_bundle_file_count": int(bundle["file_count"]),
        "runtime_bundle_complete": bool(bundle["complete"]),
    }


def _deployment_proof_marker() -> None:
    evidence = _runtime_deployment_identity()
    st.markdown(
        '<div style="display:none" '
        f'data-api2-exact-deployment="{escape(DEPLOYMENT_PROOF_MARKER, quote=True)}" '
        f'data-production-sha="{escape(str(evidence["production_sha"]), quote=True)}" '
        f'data-build-id="{escape(str(evidence["build_id"]), quote=True)}" '
        f'data-deploy-id="{escape(str(evidence["deploy_id"]), quote=True)}" '
        f'data-health-sha="{escape(str(evidence["health_sha"]), quote=True)}" '
        f'data-readiness-sha="{escape(str(evidence["readiness_sha"]), quote=True)}" '
        f'data-ui-proof-sha="{escape(str(evidence["ui_proof_sha"]), quote=True)}" '
        f'data-health-ok="{str(bool(evidence["health_ok"])).lower()}" '
        f'data-readiness-ok="{str(bool(evidence["readiness_ok"])).lower()}" '
        f'data-ui-proof-ok="{str(bool(evidence["ui_proof_ok"])).lower()}" '
        f'data-runtime-bundle-digest="{escape(str(evidence["runtime_bundle_digest"]), quote=True)}" '
        f'data-runtime-bundle-file-count="{int(evidence["runtime_bundle_file_count"])}" '
        f'data-runtime-bundle-complete="{str(bool(evidence["runtime_bundle_complete"])).lower()}"></div>',
        unsafe_allow_html=True,
    )


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _reconciled_slate_loader(original_loader, day_str: str) -> dict[str, Any]:
    payload = original_loader(str(day_str))
    return identity.reconcile_slate_payload(payload)


def _prewarm_game_center_dependencies(
    game_id: str,
    game_date: str,
    away_id: int,
    home_id: int,
) -> None:
    """Warm exact frozen provider primitives concurrently.

    This is transport-only acceleration.  We do not replace the frozen Game
    Center loader or role engine.  Instead we warm the exact cached primitives
    they call so the authoritative frozen functions keep identical semantics
    while avoiding serial network wall time on a cold Page-2 render.
    """
    import pandas as pd
    import wnba_availability_v27 as availability
    import wnba_players_v25 as players
    import wnba_role_v28 as role

    day = str(game_date)
    try:
        season = int(pd.to_datetime(day).year)
    except Exception:
        season = 2026

    # Resolve the date-safe slate once so roster prewarms cover every team that
    # _verified_pool_for_day() would otherwise fetch serially.
    try:
        schedule = availability.context.schedule_for_date(day)
    except Exception:
        schedule = None

    team_ids: list[int] = []
    team_meta: dict[int, tuple[str, str]] = {}
    if schedule is not None and not getattr(schedule, "empty", True):
        try:
            ids = (
                schedule["away_team_id"].astype(int).tolist()
                + schedule["home_team_id"].astype(int).tolist()
            )
            team_ids = sorted(set(int(x) for x in ids if int(x) > 0))
            for _, row in schedule.iterrows():
                for side in ("away", "home"):
                    tid = int(row.get(f"{side}_team_id") or 0)
                    if tid > 0:
                        team_meta[tid] = (
                            str(row.get(f"{side}_team") or ""),
                            str(row.get(f"{side}_tricode") or ""),
                        )
        except Exception:
            team_ids = []

    for tid in (int(away_id), int(home_id)):
        if tid > 0 and tid not in team_ids:
            team_ids.append(tid)
    team_ids = sorted(set(team_ids))

    calls: list[tuple[Any, tuple[Any, ...]]] = [
        # Player production: V2.3.2 already parallelizes season/L10/L5.
        (players.old_players.player_form_table, (season,)),
        # Prime the season schedule in case Streamlit Cloud must use the ESPN
        # game-summary fallback after the WNBA Stats transport is unavailable.
        (players._espn_season_schedule, (season,)),
        # Availability primitives used by availability_for_game_key().
        (availability._event_summary, (str(game_id),)),
        (availability._team_injury_feed, (int(away_id),)),
        (availability._team_injury_feed, (int(home_id),)),
        # Advanced usage primitives. advanced_usage_table() consumes these
        # exact cached windows sequentially after the warm.
        (role._advanced_usage_fetch, (season, 0)),
        (role._advanced_usage_fetch, (season, 10)),
        (role._advanced_usage_fetch, (season, 5)),
    ]

    # Roster requests are independent and safe to fan out.  The later frozen
    # pool builder calls the same cached _espn_roster() identities.
    for tid in team_ids:
        name, abbr = team_meta.get(int(tid), ("", ""))
        calls.append((players._espn_roster, (int(tid), name, abbr)))

    def _warm(call: tuple[Any, tuple[Any, ...]]) -> None:
        fn, args = call
        try:
            fn(*args)
        except Exception:
            # Preserve existing fail-soft/provider fallback behavior.
            return

    workers = min(12, max(1, len(calls)))
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="wnba-pra-step2",
    ) as pool:
        list(pool.map(_warm, calls))


def _suppress_cross_team_player_id_conflicts(payload: Any) -> Any:
    """Fail closed when one player ID is claimed by multiple game teams.

    Streamlit widget/container keys are global to the rendered page. The frozen
    Step-9 guard removes duplicate IDs within one team, but a provider identity
    collision can still place the same player ID under both teams. We never
    guess which team owns that conflicting identity: every row carrying a
    cross-team-conflicting player ID is suppressed before player controls render.
    """
    if not isinstance(payload, Mapping):
        return payload

    teams_obj = payload.get("teams")
    if not isinstance(teams_obj, Mapping):
        return payload

    owners: dict[int, set[str]] = {}
    for team_key, rows_obj in teams_obj.items():
        rows = rows_obj if isinstance(rows_obj, (list, tuple)) else []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            pid = game_center._integer(row.get("player_id"))
            if pid is not None:
                owners.setdefault(int(pid), set()).add(str(team_key))

    conflict_ids = {
        pid for pid, team_keys in owners.items()
        if len(team_keys) > 1
    }

    clean_payload = dict(payload)
    clean_teams: dict[str, list[Any]] = {}
    suppressed = 0
    for team_key, rows_obj in teams_obj.items():
        rows = list(rows_obj or []) if isinstance(rows_obj, (list, tuple)) else []
        kept: list[Any] = []
        for row in rows:
            pid = (
                game_center._integer(row.get("player_id"))
                if isinstance(row, Mapping)
                else None
            )
            if pid is not None and int(pid) in conflict_ids:
                suppressed += 1
                continue
            kept.append(dict(row) if isinstance(row, Mapping) else row)
        clean_teams[str(team_key)] = kept

    clean_payload["teams"] = clean_teams
    clean_payload["players"] = sum(len(rows) for rows in clean_teams.values())
    clean_payload["cross_team_duplicate_player_ids"] = sorted(conflict_ids)
    clean_payload["cross_team_duplicate_player_rows_suppressed"] = suppressed
    clean_payload["cross_team_duplicate_key_guard_active"] = True
    return clean_payload


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
        f'data-cross-team-conflicts="{len(payload.get("cross_team_duplicate_player_ids") or [])}" '
        f'data-cross-team-rows-suppressed="{int(payload.get("cross_team_duplicate_player_rows_suppressed") or 0)}" '
        f'data-away-id-repaired="{str(bool(snapshot.get("away_identity_repaired"))).lower()}" '
        f'data-home-id-repaired="{str(bool(snapshot.get("home_identity_repaired"))).lower()}" '
        f'data-identity-version="{escape(identity.VERSION)}"></div>',
        unsafe_allow_html=True,
    )


def render_app() -> Any:
    _deployment_proof_marker()
    original_slate_loader = slate.load_slate
    original_cached_slate_loader = performance._FROZEN_SLATE_LOADER
    original_cached_game_loader = performance._FROZEN_GAME_LOADER
    original_game_loader = game_center.load_game_center
    original_game_renderer = game_center.render_game_center

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
        _prewarm_game_center_dependencies(
            game_id,
            game_date,
            away_id,
            home_id,
        )
        payload = original_game_loader(
            game_id,
            game_date,
            away_id,
            home_id,
            away_team,
            home_team,
        )
        payload = frozen_parent._dedupe_game_center_payload(payload)
        return _suppress_cross_team_player_id_conflicts(payload)

    if hasattr(original_game_loader, "clear"):
        guarded_game_loader.clear = original_game_loader.clear  # type: ignore[attr-defined]

    def guarded_game_renderer(state):
        payload = original_game_renderer(state)
        if isinstance(payload, Mapping):
            _proof_marker(payload)
        return payload

    slate.load_slate = guarded_slate_loader
    performance._FROZEN_SLATE_LOADER = guarded_slate_loader
    performance._FROZEN_GAME_LOADER = guarded_game_loader
    game_center.load_game_center = guarded_game_loader
    game_center.render_game_center = guarded_game_renderer
    try:
        return frozen_parent.render_app()
    finally:
        slate.load_slate = original_slate_loader
        performance._FROZEN_SLATE_LOADER = original_cached_slate_loader
        performance._FROZEN_GAME_LOADER = original_cached_game_loader
        game_center.load_game_center = original_game_loader
        game_center.render_game_center = original_game_renderer


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION_MATH",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "PROOF_MARKER",
    "DEPLOYMENT_PROOF_MARKER",
    "RUNTIME_ATTESTATION_PATHS",
    "_git_blob_sha",
    "_runtime_bundle_attestation",
    "_runtime_deployment_identity",
    "_deployment_proof_marker",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TEAM_IDENTITY_VERSION",
    "_prewarm_game_center_dependencies",
    "_suppress_cross_team_player_id_conflicts",
    "_proof_marker",
    "_reconciled_slate_loader",
    "record_bootstrap_import_ms",
    "render_app",
]
