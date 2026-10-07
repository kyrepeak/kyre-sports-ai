from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from urllib.parse import quote

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
REPAIR_BRANCH = "api2-wnba-data-completeness-repair-v1-step2-live-hydration-r1"
EXPECTED_BRANCH_HEAD = "ab7d7fc48b03a32365c21a436fbf84741f195bda"
RUNTIME_PATH = "wnba_players_v25.py"
FROZEN_BLOB = "9960efb20d9e6f3791ed5c3228ca42abd884f828"
STEP2_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-LIVE-HYDRATION-R1"
EXPECTED_REGISTRY_REVISION = 149
EXPECTED_REGISTRY_HASH = "c3a6eb8c37b6aa6e227c70078fa8fabf6c482a943a656e49cdebb6777ce20ff5"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _read_text(client, path: str, ref: str):
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _patch_runtime(source: str) -> str:
    import_needle = "from wnba_data_completeness_repair_v1_step2_stats_gate import gate_primary_production\n"
    import_replacement = (
        "from wnba_data_completeness_repair_v1_step2_live_history import summarize_player_history\n"
        "from wnba_data_completeness_repair_v1_step2_stats_gate import gate_primary_production\n"
    )
    if source.count(import_needle) != 1:
        raise RuntimeError("RUNTIME_IMPORT_ANCHOR_DRIFT")
    source = source.replace(import_needle, import_replacement, 1)

    function_anchor = "\ndef _aggregate_games(games: pd.DataFrame, roster: pd.DataFrame, team_meta: dict) -> pd.DataFrame:\n"
    if source.count(function_anchor) != 1:
        raise RuntimeError("RUNTIME_AGGREGATE_ANCHOR_DRIFT")
    fast_function = r'''

def _aggregate_espn_athlete_gamelogs(roster: pd.DataFrame, team_meta: dict, day_str: str) -> pd.DataFrame:
    """Hydrate current-roster production from the latency-safe ESPN athlete gamelog."""
    if roster is None or roster.empty:
        return _empty_players()
    try:
        from sports_api.wnba_pra_speed_v3_step3_espn_history import (
            get_step3_espn_player_game_log_dataset,
        )
    except Exception:
        return _empty_players()

    current = roster.drop_duplicates(subset=["TEAM_ID", "PLAYER_ID"], keep="first").copy()
    season = int(pd.to_datetime(day_str).year)
    summaries = {}
    jobs = {}
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(current)))) as pool:
        for _, rr in current.iterrows():
            try:
                pid = int(rr.get("PLAYER_ID"))
            except Exception:
                continue
            jobs[pool.submit(get_step3_espn_player_game_log_dataset, pid, season)] = pid
        for future in as_completed(jobs):
            pid = jobs[future]
            try:
                summaries[pid] = summarize_player_history(future.result(), day_str)
            except Exception:
                summaries[pid] = None

    rows = []
    for _, rr in current.iterrows():
        try:
            pid = int(rr.get("PLAYER_ID"))
        except Exception:
            continue
        summary = summaries.get(pid)
        has_history = isinstance(summary, dict) and int(summary.get("GP") or 0) > 0
        base = {
            "PLAYER_ID": pid,
            "PLAYER_NAME": str(rr.get("PLAYER_NAME") or "Player"),
            "TEAM_ID": int(rr.get("TEAM_ID") or 0),
            "TEAM_NAME": str(rr.get("TEAM_NAME") or ""),
            "TEAM_ABBREVIATION": str(rr.get("TEAM_ABBREVIATION") or ""),
            "POSITION": str(rr.get("POSITION") or ""),
            "ROSTER_STATUS": str(rr.get("ROSTER_STATUS") or "ROSTERED"),
            "PLAYER_ID_SOURCE": "ESPN",
        }
        if has_history:
            for col in (
                "GP", "MIN", "PTS", "REB", "AST", "PRA",
                "L10_GP", "L10_MIN", "L10_PTS", "L10_REB", "L10_AST", "L10_PRA",
                "L5_GP", "L5_MIN", "L5_PTS", "L5_REB", "L5_AST", "L5_PRA",
                "LAST_GAME_DATE",
            ):
                base[col] = summary.get(col)
            base["DATA_SOURCE"] = "ESPN WNBA Athlete Gamelog"
        else:
            for col in (
                "GP", "MIN", "PTS", "REB", "AST", "PRA",
                "L10_GP", "L10_MIN", "L10_PTS", "L10_REB", "L10_AST", "L10_PRA",
                "L5_GP", "L5_MIN", "L5_PTS", "L5_REB", "L5_AST", "L5_PRA",
            ):
                base[col] = 0.0
            base["LAST_GAME_DATE"] = "—"
            base["DATA_SOURCE"] = "ESPN WNBA current roster • athlete gamelog unavailable"
        rows.append(base)

    out = pd.DataFrame(rows)
    if out.empty:
        return _empty_players()
    for col in PLAYER_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out.reindex(columns=PLAYER_COLUMNS).sort_values(
        ["TEAM_ID", "MIN"], ascending=[True, False]
    ).reset_index(drop=True)
'''
    source = source.replace(function_anchor, fast_function + function_anchor, 1)

    fallback_anchor = "    # Streamlit fallback: reconstruct season averages from WNBA game summaries.\n"
    if source.count(fallback_anchor) != 1:
        raise RuntimeError("RUNTIME_FALLBACK_ANCHOR_DRIFT")
    fast_path = '''    # Fast Streamlit fallback: one bounded ESPN athlete-gamelog read per current player.\n    # This transport is already used by the hosted PRA detail API because the direct\n    # WNBA Stats hosts are not latency-safe in the live environment.\n    fast_players = _aggregate_espn_athlete_gamelogs(roster, team_meta, day_str)\n    if fast_players is not None and not fast_players.empty:\n        real_rows = pd.to_numeric(fast_players.get("GP"), errors="coerce").fillna(0).gt(0)\n        if bool(real_rows.any()):\n            diag = {\n                "state": "VERIFIED", "selected_date": day_str, "teams": len(team_ids),\n                "rosters_connected": len(roster_frames), "roster_players": len(roster),\n                "stat_rows": len(fast_players),\n                "completed_games_used": int(pd.to_numeric(fast_players.get("GP"), errors="coerce").fillna(0).sum()),\n                "source": "ESPN WNBA Athlete Gamelog",\n                "roster_source": "ESPN WNBA current roster" if len(roster_frames) else "unavailable",\n            }\n            return fast_players.reset_index(drop=True), diag\n\n'''
    source = source.replace(fallback_anchor, fast_path + fallback_anchor, 1)

    compile(source, RUNTIME_PATH, "exec")
    required = (
        "summarize_player_history",
        "get_step3_espn_player_game_log_dataset",
        "_aggregate_espn_athlete_gamelogs",
        "ESPN WNBA Athlete Gamelog",
    )
    if not all(token in source for token in required):
        raise RuntimeError("RUNTIME_PATCH_CONTRACT_INCOMPLETE")
    return source


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("MAIN_SHA_DRIFT")
    if client.branch_sha(REPAIR_BRANCH) != EXPECTED_BRANCH_HEAD:
        raise RuntimeError("REPAIR_BRANCH_HEAD_DRIFT")

    source, current_blob = _read_text(client, RUNTIME_PATH, REPAIR_BRANCH)
    if current_blob != FROZEN_BLOB:
        raise RuntimeError("FROZEN_RUNTIME_BLOB_DRIFT")
    patched = _patch_runtime(source)

    blob = client.request("POST", "/git/blobs", json={"content": patched, "encoding": "utf-8"})
    to_blob = str((blob or {}).get("sha") or "")
    if len(to_blob) != 40 or to_blob == FROZEN_BLOB:
        raise RuntimeError("CANDIDATE_BLOB_INVALID")

    parent = client.request("GET", f"/git/commits/{EXPECTED_BRANCH_HEAD}") or {}
    base_tree = str((parent.get("tree") or {}).get("sha") or "")
    if len(base_tree) != 40:
        raise RuntimeError("REPAIR_BRANCH_TREE_UNRESOLVED")
    tree = client.request(
        "POST", "/git/trees",
        json={
            "base_tree": base_tree,
            "tree": [{"path": RUNTIME_PATH, "mode": "100644", "type": "blob", "sha": to_blob}],
        },
    ) or {}
    tree_sha = str(tree.get("sha") or "")
    commit = client.request(
        "POST", "/git/commits",
        json={
            "message": "fix: hydrate WNBA live stats from athlete gamelog",
            "tree": tree_sha,
            "parents": [EXPECTED_BRANCH_HEAD],
        },
    ) or {}
    candidate_sha = str(commit.get("sha") or "")
    if len(candidate_sha) != 40:
        raise RuntimeError("CANDIDATE_COMMIT_INVALID")

    registry_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not registry_raw or registry_raw.get("encoding") != "base64":
        raise RuntimeError("REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(registry_raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("REGISTRY_HASH_DRIFT")
    frozen = ((registry.get("entries") or {}).get(STEP2_TOKEN) or {}).get("artifacts") or {}
    if str(frozen.get(RUNTIME_PATH) or "") != FROZEN_BLOB:
        raise RuntimeError("STEP2_FROZEN_OWNER_DRIFT")
    original_thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(str(item.get("thaw_id") or "") == THAW_ID for item in original_thaws):
        raise RuntimeError("THAW_ID_ALREADY_EXISTS")
    for item in original_thaws:
        if RUNTIME_PATH in (item.get("files") or {}):
            raise RuntimeError("RUNTIME_ALREADY_THAWED")

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": candidate_sha,
        "files": {
            RUNTIME_PATH: {"from_blob": FROZEN_BLOB, "to_blob": to_blob},
        },
    }
    updated = deepcopy(registry)
    updated.setdefault("active_thaws", []).append(grant)
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: thaw {THAW_ID}",
        str(registry_raw["sha"]),
    )

    readback_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    readback = json.loads(base64.b64decode(readback_raw["content"]).decode())
    validate_registry(readback)
    grants = [item for item in readback.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if grants != [grant]:
        raise RuntimeError("THAW_READBACK_MISMATCH")
    unrelated_before = [item for item in original_thaws if item.get("thaw_id") != THAW_ID]
    unrelated_after = [item for item in readback.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("UNRELATED_THAW_DRIFT")

    client.request(
        "PATCH",
        f"/git/refs/heads/{quote(REPAIR_BRANCH, safe='/')}",
        json={"sha": candidate_sha, "force": False},
    )
    if client.branch_sha(REPAIR_BRANCH) != candidate_sha:
        raise RuntimeError("REPAIR_BRANCH_UPDATE_FAILED")
    tree_blobs = client.tree_blobs(candidate_sha)
    if str(tree_blobs.get(RUNTIME_PATH) or "") != to_blob:
        raise RuntimeError("RUNTIME_BLOB_READBACK_FAILED")

    return {
        "status": "GREEN",
        "branch": REPAIR_BRANCH,
        "candidate_sha": candidate_sha,
        "runtime_from_blob": FROZEN_BLOB,
        "runtime_to_blob": to_blob,
        "thaw_id": THAW_ID,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_live_hydration_thaw_patch = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_live_hydration_thaw_patch = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_live_hydration_thaw_patch = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:800],
            }
        print(
            "WNBA_LIVE_HYDRATION_THAW_PATCH="
            + json.dumps(app.state.wnba_live_hydration_thaw_patch, sort_keys=True),
            flush=True,
        )
    return app
