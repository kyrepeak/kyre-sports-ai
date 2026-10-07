from __future__ import annotations

import json
from urllib.parse import quote

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry

from .registry import GithubRegistryBackend, REGISTRY_BRANCH, REGISTRY_PATH

EXPECTED_MAIN_SHA = "4036459c8c8cde0ac8f3034b560d7948ad9a5015"
EXPECTED_CANDIDATE_SHA = "97ac0eda464004c2debe45f84060b7830d2f8419"
STEP17_THAW_ID = "THAW-RUNLESS-TASK17-STEP1-REAL-PROVE-R1"
EXPECTED_API_FROM = "185c07cb05fb5dc4937011330c6da6b7d5e8d1c5"
EXPECTED_API_TO = "3734146408aefba224f3ceed7c9385fc91eca68a"
MIGRATION_NOT_BEFORE = "2026-10-05T00:00:00Z"
MAX_MISMATCHES = 30


class Task17RegistryRecoveryFailure(RuntimeError):
    pass


def _step17_thaw(registry):
    matches = [
        grant
        for grant in registry.get("active_thaws", [])
        if grant.get("thaw_id") == STEP17_THAW_ID
    ]
    if len(matches) != 1:
        raise Task17RegistryRecoveryFailure("STEP17_EXACT_THAW_MISSING_OR_AMBIGUOUS")
    grant = matches[0]
    pair = (grant.get("files") or {}).get("runless_proof_plane/api.py") or {}
    if (
        grant.get("target_head_sha") != EXPECTED_CANDIDATE_SHA
        or pair.get("from_blob") != EXPECTED_API_FROM
        or pair.get("to_blob") != EXPECTED_API_TO
    ):
        raise Task17RegistryRecoveryFailure("STEP17_EXACT_THAW_IDENTITY_DRIFT")
    return grant


def _latest_main_change(client, path: str) -> dict:
    encoded = quote(path, safe="")
    rows = client.request(
        "GET",
        f"/commits?sha={EXPECTED_MAIN_SHA}&path={encoded}&per_page=1",
    )
    if not rows:
        raise Task17RegistryRecoveryFailure(f"NO_MAIN_HISTORY:{path}")
    row = rows[0]
    commit = row.get("commit") or {}
    message = str(commit.get("message") or "")
    authored = str((commit.get("author") or {}).get("date") or "")
    if "runless" not in message.casefold():
        raise Task17RegistryRecoveryFailure(
            f"NON_RUNLESS_DRIFT:{path}:{message[:120]}"
        )
    if authored and authored < MIGRATION_NOT_BEFORE:
        raise Task17RegistryRecoveryFailure(
            f"PRE_MIGRATION_DRIFT:{path}:{authored}"
        )
    return {
        "commit_sha": str(row.get("sha") or ""),
        "message": message.splitlines()[0][:180],
        "authored_at": authored,
    }


def execute(client):
    main_sha = client.branch_sha("main")
    if main_sha != EXPECTED_MAIN_SHA:
        raise Task17RegistryRecoveryFailure(
            f"WAIT_MAIN_IDENTITY_MOVED:{main_sha}"
        )

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if registry.get("source_main_sha") != EXPECTED_MAIN_SHA:
        raise Task17RegistryRecoveryFailure(
            "WAIT_REGISTRY_SOURCE_MAIN_DRIFT"
        )
    _step17_thaw(registry)

    tree = client.tree_blobs(EXPECTED_MAIN_SHA)
    flattened = validate_registry(registry)["artifacts"]
    mismatches = []
    updates = {}
    lineage = {}
    for path, expected_blob in sorted(flattened.items()):
        actual_blob = tree.get(path)
        if actual_blob == expected_blob:
            continue
        if actual_blob is None:
            raise Task17RegistryRecoveryFailure(f"FROZEN_ARTIFACT_DELETED:{path}")
        if not path.startswith(".github/workflows/"):
            raise Task17RegistryRecoveryFailure(f"NON_WORKFLOW_FROZEN_DRIFT:{path}")
        history = _latest_main_change(client, path)
        lineage[path] = history
        mismatches.append(
            {
                "path": path,
                "from_blob": expected_blob,
                "to_blob": actual_blob,
                **history,
            }
        )
        updates[path] = {"from_blob": expected_blob, "to_blob": actual_blob}

    if not mismatches:
        return {
            "status": "GREEN",
            "decision": "REGISTRY_ALREADY_ALIGNED",
            "revision": int(registry["revision"]),
            "state_hash": registry["state_hash"],
            "mismatch_count": 0,
        }
    if len(mismatches) > MAX_MISMATCHES:
        raise Task17RegistryRecoveryFailure(
            f"MISMATCH_BUDGET_EXCEEDED:{len(mismatches)}"
        )

    planned = plan_baseline_forward_port(
        registry,
        updates=updates,
        source_main_sha=EXPECTED_MAIN_SHA,
    )
    planned_registry = planned["registry"]
    _step17_thaw(planned_registry)

    text = json.dumps(
        planned_registry,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    ) + "\n"
    try:
        client.update_content(
            REGISTRY_PATH,
            text,
            REGISTRY_BRANCH,
            "registry: reconcile merged Runless workflow quarantine baselines",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17RegistryRecoveryFailure(
            "WAIT_REGISTRY_CAS_CONFLICT"
        ) from exc

    readback = backend.read_registry()
    validate_registry(readback)
    _step17_thaw(readback)
    if (
        readback.get("revision") != planned_registry.get("revision")
        or readback.get("state_hash") != planned_registry.get("state_hash")
        or readback.get("source_main_sha") != EXPECTED_MAIN_SHA
    ):
        raise Task17RegistryRecoveryFailure("REGISTRY_RECOVERY_READBACK_MISMATCH")

    readback_tree = client.tree_blobs(EXPECTED_MAIN_SHA)
    readback_flattened = validate_registry(readback)["artifacts"]
    residual = [
        path
        for path, expected_blob in readback_flattened.items()
        if readback_tree.get(path) != expected_blob
    ]
    if residual:
        raise Task17RegistryRecoveryFailure(
            "REGISTRY_RECOVERY_RESIDUAL_DRIFT:" + ",".join(residual)
        )

    return {
        "status": "GREEN",
        "decision": "RUNLESS_MIGRATION_REGISTRY_RECONCILED",
        "previous_revision": int(registry["revision"]),
        "revision": int(readback["revision"]),
        "previous_state_hash": registry["state_hash"],
        "state_hash": readback["state_hash"],
        "source_main_sha": readback["source_main_sha"],
        "mismatch_count": len(mismatches),
        "paths": [item["path"] for item in mismatches],
        "lineage": lineage,
        "step17_thaw_preserved": True,
        "active_thaw_count": len(readback.get("active_thaws", [])),
    }


def install_startup(app):
    app.state.task17_step1_registry_recovery = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step1_registry_recovery = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step1_registry_recovery = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        print(
            "RUNLESS_TASK17_STEP1_REGISTRY_RECOVERY="
            + json.dumps(
                app.state.task17_step1_registry_recovery,
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )

    @app.get("/task17-step1-registry-recovery/status")
    def _status():
        return app.state.task17_step1_registry_recovery

    return app
