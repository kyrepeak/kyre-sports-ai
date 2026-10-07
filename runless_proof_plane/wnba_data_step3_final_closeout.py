from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable, Mapping

MAIN_SHA = "7e1d91948caf36e45535259bb5547689f211ce9a"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
EXPECTED_REGISTRY_HEAD = "3749c51ed5ded32987e8cec2f3fd6ddb7a4f6b1f"
EXPECTED_REGISTRY_BLOB = "9dda8e6c300ff9886f820145f354e65c1d78aa42"
EXPECTED_REGISTRY_REVISION = 182
EXPECTED_REGISTRY_HASH = "d0fb9193ca76394e7537bf3779fc2476c61841db8af17d937c6d76601e279218"
FREEZE_TOKEN = "WNBA_PRA_REPAIR_V1_STEP3_FROZEN"

REPAIR_HEAD = "72fb0ca7eaad3827f7a9721c193cd59a5acb7f99"
REPAIR_RECEIPT = "67b46ded9a1a4fc9df56799e98bf10842a90310dccca67188270968cb0e48503"
REFRESH_HEAD = "eae0f0d0839712f199f093c67873dc11c83e2416"
REFRESH_RECEIPT = "5eb01dbe8255ad2fb090148b45ca81cf0984fb7258de9b0b5c97692455a628ed"
RUNLESS_APP_ID = 5204253

PLAYER_THAW_ID = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
REFRESH_THAW_ID = "THAW-API2-WNBA-DATA-STEP3-STREAMLIT-REFRESH-R1"
UNRELATED_THAW_IDS = {
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
}

PLAYER_PATH = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
PLAYER_FROM = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
PLAYER_TO = "a82a0d374c0fc1de9346e0d62f92831e39ddd9f7"
REQUIREMENTS_PATH = "requirements.txt"
REQUIREMENTS_FROM = "7f5cf407662a79cb4c56781195e7bbcaca38d315"
REQUIREMENTS_TO = "2904ed539d5a2e8a195675b96b756fb6ba6a3c74"

FREEZE_ARTIFACTS = {
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py": "84ae2e8eacd785e29547cbc92b435c9483994417",
    "tests/test_wnba_pra_repair_v1_step3.py": "98b2809c31b6b012331c18dc977a54add259ab07",
    "wnba_pra_repair_v1_step3_data.py": "d7c90bda07a5a32a53e14f87973ca6d1596fd1a5",
}

BASELINE_UPDATES = {
    PLAYER_PATH: {"from_blob": PLAYER_FROM, "to_blob": PLAYER_TO},
    REQUIREMENTS_PATH: {"from_blob": REQUIREMENTS_FROM, "to_blob": REQUIREMENTS_TO},
}

EXPECTED_UPDATED_OWNERS = {
    ("WNBA_PRA_REPAIR_V1_STEP7_FROZEN", PLAYER_PATH),
    ("WNBA_PUSHSTATE_REPAIR_V1_STEP3_FROZEN", PLAYER_PATH),
    ("WNBA_PUSHSTATE_REPAIR_V1_STEP4_FROZEN", PLAYER_PATH),
    ("WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN", REQUIREMENTS_PATH),
    ("WNBA_PRA_REPAIR_V1_STEP8_FROZEN", REQUIREMENTS_PATH),
}


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _exact_entry(registry: Mapping[str, Any]) -> bool:
    entry = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    return bool(
        isinstance(entry, Mapping)
        and entry.get("status") == "FROZEN"
        and entry.get("checkpoint_id") == FREEZE_TOKEN
        and entry.get("source_main_sha") == MAIN_SHA
        and dict(entry.get("artifacts") or {}) == FREEZE_ARTIFACTS
    )


def _relevant_thaws_absent(registry: Mapping[str, Any]) -> bool:
    ids = {str(item.get("thaw_id") or "") for item in registry.get("active_thaws", [])}
    return not ({PLAYER_THAW_ID, REFRESH_THAW_ID} & ids)


def build_closeout_registry(
    registry: Mapping[str, Any],
    *,
    planner: Callable[..., dict[str, Any]] | None = None,
    validator: Callable[[Mapping[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    if planner is None:
        from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
        planner = plan_baseline_forward_port
    if validator is None:
        from devsystem.frozen_artifact_registry_v1 import validate_registry
        validator = validate_registry

    validator(registry)
    if _exact_entry(registry):
        if not _relevant_thaws_absent(registry):
            raise RuntimeError("WNBA_STEP3_CLOSEOUT_TOKEN_WITH_ACTIVE_THAW")
        return {"status": "GREEN", "decision": "ALREADY_COMPLETE", "registry": deepcopy(dict(registry))}
    if FREEZE_TOKEN in (registry.get("entries") or {}):
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_TOKEN_CONFLICT")

    plan = planner(registry, updates=BASELINE_UPDATES, source_main_sha=MAIN_SHA)
    updated = deepcopy(plan["registry"])
    retired = set(plan.get("retired_empty_thaw_grants") or [])
    if retired != {PLAYER_THAW_ID, REFRESH_THAW_ID}:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_THAW_RETIREMENT_DRIFT")

    updated["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(FREEZE_ARTIFACTS.items())),
    }
    updated["state_hash"] = _state_hash(updated)
    validator(updated)
    return {
        "status": "GREEN",
        "decision": "READY_TO_COMMIT",
        "registry": updated,
        "updated_entries": plan.get("updated_entries") or [],
        "retired_empty_thaw_grants": sorted(retired),
        "retained_thaw_count": int(plan.get("retained_thaw_count") or 0),
    }


def _require_runless_gate(client, head: str, receipt: str) -> int:
    checks = client.request("GET", f"/commits/{head}/check-runs") or {}
    matches = []
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == head
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={receipt}"
        ):
            matches.append(int(check["id"]))
    if len(matches) != 1:
        raise RuntimeError(f"WNBA_STEP3_CLOSEOUT_RUNLESS_GATE_MISSING:{head}")
    return matches[0]


def _require_ancestor(client, ancestor: str, descendant: str) -> None:
    comparison = client.request("GET", f"/compare/{ancestor}...{descendant}") or {}
    merge_base = str(((comparison.get("merge_base_commit") or {}).get("sha") or ""))
    if merge_base != ancestor or int(comparison.get("behind_by") or 0) != 0:
        raise RuntimeError(f"WNBA_STEP3_CLOSEOUT_ANCESTRY_DRIFT:{ancestor}")


def _require_exact_main_tree(client) -> None:
    tree = client.tree_blobs(MAIN_SHA)
    expected = {
        **FREEZE_ARTIFACTS,
        PLAYER_PATH: PLAYER_TO,
        REQUIREMENTS_PATH: REQUIREMENTS_TO,
    }
    drift = [f"{path}:{tree.get(path)}!={blob}" for path, blob in sorted(expected.items()) if tree.get(path) != blob]
    if drift:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_MAIN_BLOB_DRIFT:" + ",".join(drift))


def _require_exact_thaws(registry: Mapping[str, Any]) -> None:
    expected = {
        PLAYER_THAW_ID: {
            "thaw_id": PLAYER_THAW_ID,
            "status": "ACTIVE",
            "target_head_sha": REPAIR_HEAD,
            "files": {PLAYER_PATH: {"from_blob": PLAYER_FROM, "to_blob": PLAYER_TO}},
        },
        REFRESH_THAW_ID: {
            "thaw_id": REFRESH_THAW_ID,
            "status": "ACTIVE",
            "target_head_sha": REFRESH_HEAD,
            "files": {REQUIREMENTS_PATH: {"from_blob": REQUIREMENTS_FROM, "to_blob": REQUIREMENTS_TO}},
        },
    }
    by_id = {str(item.get("thaw_id") or ""): item for item in registry.get("active_thaws", [])}
    for thaw_id, grant in expected.items():
        if by_id.get(thaw_id) != grant:
            raise RuntimeError(f"WNBA_STEP3_CLOSEOUT_THAW_DRIFT:{thaw_id}")
    ids = set(by_id)
    if ids != (set(expected) | UNRELATED_THAW_IDS):
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_ACTIVE_THAW_SET_DRIFT")


def execute(client) -> dict[str, Any]:
    from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
    from devsystem.frozen_artifact_registry_v1 import validate_registry
    from .registry import GithubRegistryBackend

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    if _exact_entry(registry) and _relevant_thaws_absent(registry):
        validate_registry(registry)
        return {
            "status": "GREEN",
            "decision": "ALREADY_COMPLETE",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "frozen_token": FREEZE_TOKEN,
        }

    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_MAIN_DRIFT")
    if client.branch_sha(REGISTRY_BRANCH) != EXPECTED_REGISTRY_HEAD:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REGISTRY_HEAD_DRIFT")
    if int(registry["revision"]) != EXPECTED_REGISTRY_REVISION or str(registry["state_hash"]) != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REGISTRY_STATE_DRIFT")
    if str(getattr(backend, "_blob_sha", "")) != EXPECTED_REGISTRY_BLOB:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REGISTRY_BLOB_DRIFT")

    _require_exact_thaws(registry)
    repair_check = _require_runless_gate(client, REPAIR_HEAD, REPAIR_RECEIPT)
    refresh_check = _require_runless_gate(client, REFRESH_HEAD, REFRESH_RECEIPT)
    _require_ancestor(client, REPAIR_HEAD, MAIN_SHA)
    _require_ancestor(client, REFRESH_HEAD, MAIN_SHA)
    _require_exact_main_tree(client)

    built = build_closeout_registry(registry, planner=plan_baseline_forward_port, validator=validate_registry)
    updated = built["registry"]
    owners = {(str(item.get("checkpoint")), str(item.get("path"))) for item in built["updated_entries"]}
    if owners != EXPECTED_UPDATED_OWNERS:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_OWNER_SET_DRIFT")
    remaining_ids = {str(item.get("thaw_id") or "") for item in updated.get("active_thaws", [])}
    if remaining_ids != UNRELATED_THAW_IDS:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_UNRELATED_THAW_DRIFT")
    if int(updated["revision"]) != EXPECTED_REGISTRY_REVISION + 1:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REVISION_DRIFT")

    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_MAIN_MOVED_BEFORE_WRITE")
    if client.branch_sha(REGISTRY_BRANCH) != EXPECTED_REGISTRY_HEAD:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REGISTRY_MOVED_BEFORE_WRITE")

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    response = client.update_content(
        backend.path,
        text,
        backend.branch,
        f"registry: freeze {FREEZE_TOKEN}",
        EXPECTED_REGISTRY_BLOB,
    )
    write_sha = str(((response or {}).get("commit") or {}).get("sha") or "")
    if not write_sha:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_WRITE_SHA_MISSING")
    if client.branch_sha(REGISTRY_BRANCH) != write_sha:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REF_READBACK_MISMATCH")
    commit = client.commit(write_sha)
    parents = [str(item.get("sha") or "") for item in (commit.get("parents") or [])]
    if parents != [EXPECTED_REGISTRY_HEAD]:
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_CAS_PARENT_MISMATCH")

    readback = GithubRegistryBackend(client).read_registry()
    validate_registry(readback)
    if (
        int(readback["revision"]) != int(updated["revision"])
        or str(readback["state_hash"]) != str(updated["state_hash"])
        or not _exact_entry(readback)
        or not _relevant_thaws_absent(readback)
        or {str(item.get("thaw_id") or "") for item in readback.get("active_thaws", [])} != UNRELATED_THAW_IDS
    ):
        raise RuntimeError("WNBA_STEP3_CLOSEOUT_REGISTRY_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "decision": "FROZEN",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "frozen_token": FREEZE_TOKEN,
        "registry_commit_sha": write_sha,
        "repair_check_id": repair_check,
        "refresh_check_id": refresh_check,
        "retained_thaw_ids": sorted(UNRELATED_THAW_IDS),
        "updated_owner_count": len(owners),
        "artifact_count": len(FREEZE_ARTIFACTS),
    }


def install_startup(app):
    app.state.wnba_data_step3_final_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_final_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_final_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1200],
            }
        print(
            "WNBA_DATA_STEP3_FINAL_CLOSEOUT="
            + json.dumps(app.state.wnba_data_step3_final_closeout, sort_keys=True),
            flush=True,
        )

    return app
