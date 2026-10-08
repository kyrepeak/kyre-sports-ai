from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import (
    _hash as frozen_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import (
    _hash as lease_hash,
    _without_hash as lease_without_hash,
    validate_state as validate_scope_lease_state,
)

TASK_ID = "nfl-rb-wr-render-repair-step2-presentation-transport"
WORKSTREAM = "nfl-rb-wr-render-repair-v1"
SOURCE_MAIN_SHA = "32366f629fd7764d99a1f715da26a2305c9f4a18"
CANDIDATE_SHA = "6566751edbb03cb2ff8322078ba93056fe459178"
MERGED_MAIN_SHA = "02f19b7ca4400e69d1c0b193e710e67e45184769"
PR_NUMBER = 1473

PREMERGE_PROOF_ID = (
    "nfl-rb-wr-render-repair-step2-presentation-transport-"
    "6566751edbb03cb2-e82edbf65111725d"
)
PREMERGE_DIGEST = "d0e0a5c27aaf93c4da2076bf32b2b881f32ea458846d091b96fd048b3194b817"
PREMERGE_CHECK_ID = 113551121106

FREEZE_TOKEN = "NFL_RB_WR_RENDER_REPAIR_V1_STEP2_PRESENTATION_TRANSPORT_FROZEN"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
REGISTRY_REVISION = 207
REGISTRY_HASH = "bc62d4ce566970b7da795af54926f85392ff06b9abf9ce05a074efcebccb5614"

RECEIPT_BRANCH = "runless-proof-receipts"
RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PREMERGE_PROOF_ID}.json"

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
PRODUCT_LEASE_ID = "SCOPE-LEASE-NFL-RB-WR-STEP2-214"
FINALIZER_LEASE_ID = "SCOPE-LEASE-NFL-RB-WR-STEP2-FINALIZER-216"
FINALIZER_LEASE_OWNER = "api2-nfl-rb-wr-render-repair-step2-finalizer"
RELEASE_LEASE_IDS = {PRODUCT_LEASE_ID, FINALIZER_LEASE_ID}

LEDGER_PATH = "devsystem/task_ledgers/nfl-rb-wr-render-repair-step2-presentation-transport.json"
RESOLVER_PATH = "devsystem/canonical_completion_resolver_v1.py"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError(label + "_DECODE_FAILED") from exc


def _decode_text(raw: dict | None, label: str) -> str:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    try:
        return base64.b64decode(raw["content"]).decode()
    except Exception as exc:
        raise RuntimeError(label + "_DECODE_FAILED") from exc


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_gate(client) -> dict:
    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + PREMERGE_DIGEST
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            int(run.get("id") or 0) == PREMERGE_CHECK_ID
            and str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("name") or "") == "runless-final-gate"
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == 5204253
            and str(output.get("summary") or "") == expected_summary
        ):
            return {
                "id": int(run["id"]),
                "name": "runless-final-gate",
                "head_sha": CANDIDATE_SHA,
                "conclusion": "success",
                "receipt_digest": PREMERGE_DIGEST,
                "app_id": 5204253,
            }
    raise RuntimeError("NFL_RB_WR_STEP2_RUNLESS_GATE_DRIFT")


def _finalizer_state(client) -> tuple[dict, dict, dict | None]:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "NFL_RB_WR_STEP2_LEASE"))
    holder = next(
        (
            item
            for item in state.get("holders", [])
            if item.get("lease_id") == FINALIZER_LEASE_ID
            and item.get("owner_id") == FINALIZER_LEASE_OWNER
        ),
        None,
    )
    return raw, state, holder


def _validate_finalizer_lease(client) -> tuple[dict, dict]:
    raw, state, holder = _finalizer_state(client)
    if holder is None or datetime.now(timezone.utc) >= _utc(holder["expires_at_utc"]):
        raise RuntimeError("NFL_RB_WR_STEP2_FINALIZER_LEASE_NOT_LIVE")

    scope = holder.get("scope") or {}
    required_paths = {
        REGISTRY_PATH,
        LEASE_PATH,
        "runless_proof_plane/bootstrap.py",
        "runless_proof_plane/nfl_rb_wr_step2_closeout.py",
        "tests/test_runless_nfl_rb_wr_step2_closeout.py",
    }
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("NFL_RB_WR_STEP2_FINALIZER_SCOPE_DRIFT")

    identity = scope.get("resource_identity") or {}
    if (
        str(identity.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(identity.get("merged_main_sha") or "") != MERGED_MAIN_SHA
        or str(identity.get("proof_digest") or "") != PREMERGE_DIGEST
        or str(identity.get("registry_revision") or "") != str(REGISTRY_REVISION)
        or str(identity.get("registry_state_hash") or "") != REGISTRY_HASH
    ):
        raise RuntimeError("NFL_RB_WR_STEP2_FINALIZER_IDENTITY_DRIFT")

    product = next(
        (item for item in state.get("holders", []) if item.get("lease_id") == PRODUCT_LEASE_ID),
        None,
    )
    if product is None:
        raise RuntimeError("NFL_RB_WR_STEP2_PRODUCT_LEASE_MISSING")
    return raw, state


def _release_authorities(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(
        _decode_json(raw, "NFL_RB_WR_STEP2_LEASE_RELEASE")
    )
    remaining_before = [
        item for item in state.get("holders", [])
        if str(item.get("lease_id") or "") in RELEASE_LEASE_IDS
    ]
    if not remaining_before:
        return {
            "decision": "AUTHORITY_GC_ALREADY_CLEAN",
            "remaining_target_mutation_authority": 0,
            "state_revision": int(state["revision"]),
            "state_hash": str(state["state_hash"]),
        }

    updated = deepcopy(state)
    updated["revision"] = int(state["revision"]) + 1
    updated["holders"] = [
        deepcopy(item)
        for item in state.get("holders", [])
        if str(item.get("lease_id") or "") not in RELEASE_LEASE_IDS
    ]
    updated["state_hash"] = lease_hash(lease_without_hash(updated))
    validate_scope_lease_state(updated)
    client.update_content(
        LEASE_PATH,
        json.dumps(updated, indent=2, sort_keys=True) + "\n",
        LEASE_BRANCH,
        "lease: release NFL RB WR Step2 terminal authorities",
        raw["sha"],
    )
    readback = validate_scope_lease_state(
        _decode_json(
            client.content(LEASE_PATH, ref=LEASE_BRANCH),
            "NFL_RB_WR_STEP2_LEASE_RELEASE_READBACK",
        )
    )
    remaining = sorted(
        str(item.get("lease_id") or "")
        for item in readback.get("holders", [])
        if str(item.get("lease_id") or "") in RELEASE_LEASE_IDS
    )
    if remaining:
        raise RuntimeError(
            "NFL_RB_WR_STEP2_AUTHORITY_GC_READBACK_MISMATCH:" + ",".join(remaining)
        )
    return {
        "decision": "AUTHORITY_GC_COLLECTED",
        "remaining_target_mutation_authority": 0,
        "released_lease_count": len(remaining_before),
        "state_revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def execute(app) -> dict:
    client = app.state.github_client

    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("NFL_RB_WR_STEP2_MAIN_DRIFT")

    receipt = _decode_json(
        client.content(RECEIPT_PATH, ref=RECEIPT_BRANCH),
        "NFL_RB_WR_STEP2_PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if (
        str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID
        or str(receipt.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(receipt.get("digest") or "") != PREMERGE_DIGEST
        or str(receipt.get("task_id") or "") != TASK_ID
        or str(receipt.get("workstream") or "") != WORKSTREAM
        or str(receipt.get("failure_class") or "") != "NONE"
    ):
        raise RuntimeError("NFL_RB_WR_STEP2_PREMERGE_RECEIPT_DRIFT")

    gate = _read_gate(client)
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        not pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != SOURCE_MAIN_SHA
        or str(pr.get("merge_commit_sha") or "") != MERGED_MAIN_SHA
    ):
        raise RuntimeError("NFL_RB_WR_STEP2_SQUASH_MERGE_PROVENANCE_DRIFT")

    _validate_finalizer_lease(client)

    source_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    main_tree = client.tree_blobs(MERGED_MAIN_SHA)

    for label, mapping in (
        ("ARTIFACT", receipt.get("artifact_map") or {}),
        ("DEPENDENCY", receipt.get("dependency_map") or {}),
    ):
        for path, blob in mapping.items():
            if (
                str(candidate_tree.get(path) or "") != str(blob)
                or str(main_tree.get(path) or "") != str(blob)
            ):
                raise RuntimeError(
                    f"NFL_RB_WR_STEP2_SQUASH_{label}_IDENTITY_DRIFT:{path}"
                )

    registry_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    registry = _decode_json(registry_raw, "NFL_RB_WR_STEP2_REGISTRY")
    validated = validate_registry(registry)

    existing_entry = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    inherited_frozen_paths: list[str] = []
    freeze_artifacts = dict(sorted((receipt.get("artifact_map") or {}).items()))
    if not freeze_artifacts:
        raise RuntimeError("NFL_RB_WR_STEP2_FREEZE_ARTIFACTS_MISSING")

    if existing_entry is None:
        if (
            int(registry.get("revision") or -1) != REGISTRY_REVISION
            or str(registry.get("state_hash") or "") != REGISTRY_HASH
            or str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA
        ):
            raise RuntimeError("NFL_RB_WR_STEP2_REGISTRY_BASELINE_DRIFT")

        for path, expected in validated["artifacts"].items():
            source_blob = str(source_tree.get(path) or "")
            candidate_blob = str(candidate_tree.get(path) or "")
            main_blob = str(main_tree.get(path) or "")
            if not source_blob or not candidate_blob or not main_blob:
                raise RuntimeError("NFL_RB_WR_STEP2_EXISTING_FROZEN_MISSING:" + path)
            if not (source_blob == candidate_blob == main_blob):
                raise RuntimeError("NFL_RB_WR_STEP2_EXISTING_FROZEN_DELTA:" + path)
            if main_blob != str(expected):
                inherited_frozen_paths.append(path)

        thaw_paths = {
            path
            for grant in registry.get("active_thaws", [])
            for path in (grant.get("files") or {})
        }
        overlap = sorted(set(freeze_artifacts) & thaw_paths)
        if overlap:
            raise RuntimeError(
                "NFL_RB_WR_STEP2_FREEZE_THAW_CONFLICT:" + ",".join(overlap)
            )
        baseline_conflicts = sorted(
            path
            for path, blob in freeze_artifacts.items()
            if path in validated["artifacts"]
            and str(validated["artifacts"][path]) != str(blob)
        )
        if baseline_conflicts:
            raise RuntimeError(
                "NFL_RB_WR_STEP2_FREEZE_BASELINE_CONFLICT:"
                + ",".join(baseline_conflicts)
            )

        updated = deepcopy(registry)
        updated["revision"] = int(registry["revision"]) + 1
        updated["source_main_sha"] = MERGED_MAIN_SHA
        updated["entries"][FREEZE_TOKEN] = {
            "status": "FROZEN",
            "checkpoint_id": FREEZE_TOKEN,
            "source_main_sha": MERGED_MAIN_SHA,
            "artifacts": freeze_artifacts,
        }
        updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
        validate_registry(updated)
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True) + "\n",
            REGISTRY_BRANCH,
            "registry: freeze NFL RB WR render repair Step 2 presentation transport",
            registry_raw["sha"],
        )
    else:
        if (
            existing_entry.get("status") != "FROZEN"
            or str(existing_entry.get("source_main_sha") or "") != MERGED_MAIN_SHA
            or existing_entry.get("artifacts") != freeze_artifacts
        ):
            raise RuntimeError("NFL_RB_WR_STEP2_FREEZE_TOKEN_COLLISION")

    readback = _decode_json(
        client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH),
        "NFL_RB_WR_STEP2_REGISTRY_READBACK",
    )
    validate_registry(readback)
    frozen = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    if (
        not frozen
        or frozen.get("status") != "FROZEN"
        or str(frozen.get("source_main_sha") or "") != MERGED_MAIN_SHA
        or frozen.get("artifacts") != freeze_artifacts
        or str(readback.get("source_main_sha") or "") != MERGED_MAIN_SHA
    ):
        raise RuntimeError("NFL_RB_WR_STEP2_REGISTRY_READBACK_MISMATCH")

    ledger = _decode_json(
        client.content(LEDGER_PATH, ref=MERGED_MAIN_SHA),
        "NFL_RB_WR_STEP2_LEDGER",
    )
    resolver_source = _decode_text(
        client.content(RESOLVER_PATH, ref=MERGED_MAIN_SHA),
        "NFL_RB_WR_STEP2_CANONICAL_RESOLVER",
    )
    resolver_ns = {"__name__": "nfl_rb_wr_step2_runtime_canonical_resolver"}
    exec(compile(resolver_source, RESOLVER_PATH, "exec"), resolver_ns)

    merge_evidence = {
        "contains_candidate": True,
        "candidate_sha": CANDIDATE_SHA,
        "merged_main_sha": MERGED_MAIN_SHA,
        "method": "GITHUB_SQUASH_PR_EXACT_CONTENT_IDENTITY",
        "pr_number": PR_NUMBER,
        "artifact_count": len(receipt.get("artifact_map") or {}),
        "dependency_count": len(receipt.get("dependency_map") or {}),
    }
    canonical = resolver_ns["resolve_completion"](
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=ledger,
        registry=readback,
        receipt=receipt,
        gate=gate,
        merge_evidence=merge_evidence,
    )
    if canonical.get("complete") is not True or canonical.get("status") != "GREEN_FROZEN":
        raise RuntimeError(
            "NFL_RB_WR_STEP2_CANONICAL_COMPLETION_BLOCKED:"
            + str(canonical.get("reason") or "UNKNOWN")
        )

    authority_gc = _release_authorities(client)
    if int(authority_gc.get("remaining_target_mutation_authority", -1)) != 0:
        raise RuntimeError("NFL_RB_WR_STEP2_AUTHORITY_GC_NOT_TERMINAL")

    return {
        "status": "GREEN",
        "decision": "NFL_RB_WR_STEP2_GREEN_FROZEN",
        "step": "2/5",
        "main_sha": MERGED_MAIN_SHA,
        "source_candidate_sha": CANDIDATE_SHA,
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "premerge_gate_id": PREMERGE_CHECK_ID,
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws") or []),
        "frozen_artifact_count": len(frozen.get("artifacts") or {}),
        "inherited_frozen_path_count": len(inherited_frozen_paths),
        "canonical_completion": canonical,
        "merge_evidence": merge_evidence,
        "authority_gc": authority_gc,
        "product_runtime_mutation_files": 2,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.nfl_rb_wr_step2_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run_nfl_rb_wr_step2_closeout():
        try:
            _, _, holder = _finalizer_state(app.state.github_client)
            if holder is None:
                app.state.nfl_rb_wr_step2_closeout = {
                    "status": "NOT_RUN",
                    "decision": "NFL_RB_WR_STEP2_NO_FINALIZER_LEASE",
                }
            else:
                app.state.nfl_rb_wr_step2_closeout = execute(app)
        except Exception as exc:
            app.state.nfl_rb_wr_step2_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "NFL_RB_WR_STEP2_FINAL_CLOSEOUT="
            + json.dumps(app.state.nfl_rb_wr_step2_closeout, sort_keys=True),
            flush=True,
        )

    return app
