from __future__ import annotations

import base64
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import (
    _hash as frozen_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.runless_terminal_proof_receipt_v1 import validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

from . import task17_step5_atomic_closeout as core
from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-v2-step4-prediction-market"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json"
SOURCE_MAIN_SHA = "8ad570f765daf0884fe6f963f10982b05a414b60"
SOURCE_CANDIDATE_SHA = "6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b"
MAIN_SHA = "091226472ad03d11d86fa2843fc37c3dc2830023"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-prediction-market-6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b"
PREMERGE_DIGEST = "9829d7b5bcc735f42cccdf86ededcb09e6434435e8cf037f59533c4bcabc1710"
PREMERGE_CHECK_ID = 113165457178
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step4-prediction-market-091226472ad03d11-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PREDICTION_MARKET_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_page1_step4_prediction_market_v1.py",
    "cfb_game_total_page1_step4_side_market_v1.py",
    "cfb_game_total_clean_page_v37.py",
    "cfb_game_total_page1_v2_step4_activation.py",
    "kyre_universal_components_v1.py",
    "tests/test_cfb_game_total_page1_v2_step4_prediction_market.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json",
)
LEASE_ID = "SCOPE-LEASE-68C177FAE1838F91703FC3CF"
LEASE_OWNER = "cfb-game-total-page1-v2-step4-closeout"
EXPECTED_REGISTRY_REVISION = 196
EXPECTED_REGISTRY_HASH = "b6779f297868cae2388f18bc60bc43ae42ee181742bb5f55ff87f43d1668d8c1"
EXPECTED_EVENT_HASH = "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"

NFL_RB_WR_SUBMIT_FLAG = "RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"
NFL_RB_WR_CLOSEOUT_FLAG = "RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"
NFL_TASK_ID = "nfl-rb-wr-render-repair-step1-root-cause"
NFL_WORKSTREAM = "nfl-rb-wr-render-repair-v1"
NFL_SOURCE_MAIN_SHA = "a1dfac558c76253f99e2279dd7cb45e944d913a6"
NFL_CANDIDATE_SHA = "67146c8f00e828b1944689426e376e3e99484ae0"
NFL_MERGED_MAIN_SHA = "32366f629fd7764d99a1f715da26a2305c9f4a18"
NFL_PR_NUMBER = 1472
NFL_PREMERGE_PROOF_ID = "nfl-rb-wr-render-repair-step1-root-cause-67146c8f00e828b1-5f4d87a24704f94a"
NFL_PREMERGE_DIGEST = "a48f2793c1b099534e9c2456f2be6e9522784c2078616461a2e9dda2dae8f363"
NFL_PREMERGE_CHECK_ID = 113537869417
NFL_FREEZE_TOKEN = "NFL_RB_WR_RENDER_REPAIR_V1_STEP1_ROOT_CAUSE_FROZEN"
NFL_REGISTRY_BRANCH = "monster-frozen-artifact-registry"
NFL_REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
NFL_REGISTRY_REVISION = 206
NFL_REGISTRY_HASH = "cca4b20727ef97ef8e720c2bd0b1905e85b3de383331fc862a6fda4b273b7cd6"
NFL_RECEIPT_BRANCH = "runless-proof-receipts"
NFL_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{NFL_PREMERGE_PROOF_ID}.json"
NFL_FINALIZER_LEASE_ID = "SCOPE-LEASE-39405BD84A7BDAAEAEF410EE"
NFL_FINALIZER_LEASE_OWNER = "api2-nfl-rb-wr-step1-finalizer"
NFL_LEASE_BRANCH = "monster-scope-aware-execution-leases"
NFL_LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
NFL_RELEASE_LEASE_IDS = {
    "SCOPE-LEASE-28512CFB5B1FCAD2EF7399E6",
    "SCOPE-LEASE-075B6B1B6FD0208D555467D0",
    NFL_FINALIZER_LEASE_ID,
}
NFL_CANONICAL_RESOLVER_PATH = "devsystem/canonical_completion_resolver_v1.py"
NFL_LEDGER_PATH = "devsystem/task_ledgers/nfl-rb-wr-render-repair-step1-root-cause.json"


def _bindings() -> dict[str, object]:
    return {
        "TASK_ID": TASK_ID,
        "WORKSTREAM": WORKSTREAM,
        "PLAN_PATH": PLAN_PATH,
        "SOURCE_MAIN_SHA": SOURCE_MAIN_SHA,
        "SOURCE_CANDIDATE_SHA": SOURCE_CANDIDATE_SHA,
        "MAIN_SHA": MAIN_SHA,
        "PREMERGE_PROOF_ID": PREMERGE_PROOF_ID,
        "PREMERGE_DIGEST": PREMERGE_DIGEST,
        "PREMERGE_CHECK_ID": PREMERGE_CHECK_ID,
        "MERGED_PROOF_ID": MERGED_PROOF_ID,
        "FREEZE_TOKEN": FREEZE_TOKEN,
        "FREEZE_PATHS": FREEZE_PATHS,
        "LEASE_ID": LEASE_ID,
        "LEASE_OWNER": LEASE_OWNER,
        "EXPECTED_REGISTRY_REVISION": EXPECTED_REGISTRY_REVISION,
        "EXPECTED_REGISTRY_HASH": EXPECTED_REGISTRY_HASH,
        "EXPECTED_EVENT_HASH": EXPECTED_EVENT_HASH,
    }


def execute(client):
    saved = {name: getattr(core, name) for name in _bindings()}
    original_build_receipt = core.build_runless_receipt

    def _build_receipt(**kwargs):
        kwargs["step"] = "cfb-game-total-page1-v2-step4-prediction-market"
        return original_build_receipt(**kwargs)

    try:
        for name, value in _bindings().items():
            setattr(core, name, value)
        core.build_runless_receipt = _build_receipt
        result = dict(core.execute(client))
    finally:
        core.build_runless_receipt = original_build_receipt
        for name, value in saved.items():
            setattr(core, name, value)

    decision = str(result.get("decision") or "")
    result["decision"] = decision.replace(
        "RUNLESS_TASK17_STEP5", "CFB_GAME_TOTAL_PAGE1_V2_STEP4"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "4/9"
    return result


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


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _scope_state_hash(value: dict) -> str:
    payload = deepcopy(value)
    payload.pop("state_hash", None)
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_gate(client) -> dict:
    runs = client.request(
        "GET",
        f"/commits/{NFL_CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + NFL_PREMERGE_DIGEST
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            int(run.get("id") or 0) == NFL_PREMERGE_CHECK_ID
            and str(run.get("head_sha") or "") == NFL_CANDIDATE_SHA
            and str(run.get("name") or "") == "runless-final-gate"
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == 5204253
            and str(output.get("summary") or "") == expected_summary
        ):
            return {
                "id": int(run["id"]),
                "name": "runless-final-gate",
                "head_sha": NFL_CANDIDATE_SHA,
                "conclusion": "success",
                "receipt_digest": NFL_PREMERGE_DIGEST,
                "app_id": 5204253,
            }
    raise RuntimeError("NFL_RB_WR_STEP1_RUNLESS_GATE_DRIFT")


def _validate_finalizer_lease(client) -> tuple[dict, dict]:
    raw = client.content(NFL_LEASE_PATH, ref=NFL_LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "NFL_RB_WR_STEP1_LEASE"))
    holder = next(
        (
            item
            for item in state.get("holders", [])
            if item.get("lease_id") == NFL_FINALIZER_LEASE_ID
            and item.get("owner_id") == NFL_FINALIZER_LEASE_OWNER
        ),
        None,
    )
    if not holder or datetime.now(timezone.utc) >= _utc(holder["expires_at_utc"]):
        raise RuntimeError("NFL_RB_WR_STEP1_FINALIZER_LEASE_NOT_LIVE")
    scope = holder.get("scope") or {}
    required_paths = {NFL_REGISTRY_PATH, NFL_LEASE_PATH}
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("NFL_RB_WR_STEP1_FINALIZER_SCOPE_DRIFT")
    identity = scope.get("resource_identity") or {}
    if (
        str(identity.get("main_sha") or "") != NFL_MERGED_MAIN_SHA
        or str(identity.get("premerge_receipt_digest") or "") != NFL_PREMERGE_DIGEST
        or str(identity.get("registry_state_hash") or "") != NFL_REGISTRY_HASH
    ):
        raise RuntimeError("NFL_RB_WR_STEP1_FINALIZER_IDENTITY_DRIFT")
    return raw, state


def _release_nfl_authorities(client) -> dict:
    raw = client.content(NFL_LEASE_PATH, ref=NFL_LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "NFL_RB_WR_STEP1_LEASE_RELEASE"))
    if not any(item.get("lease_id") == NFL_FINALIZER_LEASE_ID for item in state.get("holders", [])):
        remaining = sorted(
            str(item.get("lease_id") or "")
            for item in state.get("holders", [])
            if str(item.get("lease_id") or "") in NFL_RELEASE_LEASE_IDS
        )
        if remaining:
            raise RuntimeError("NFL_RB_WR_STEP1_PARTIAL_AUTHORITY_GC")
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
        if str(item.get("lease_id") or "") not in NFL_RELEASE_LEASE_IDS
    ]
    updated["state_hash"] = _scope_state_hash(updated)
    validate_scope_lease_state(updated)
    client.update_content(
        NFL_LEASE_PATH,
        json.dumps(updated, indent=2, sort_keys=True) + "\n",
        NFL_LEASE_BRANCH,
        "lease: release NFL RB WR Step1 terminal authorities",
        raw["sha"],
    )
    readback = validate_scope_lease_state(
        _decode_json(
            client.content(NFL_LEASE_PATH, ref=NFL_LEASE_BRANCH),
            "NFL_RB_WR_STEP1_LEASE_RELEASE_READBACK",
        )
    )
    remaining = sorted(
        str(item.get("lease_id") or "")
        for item in readback.get("holders", [])
        if str(item.get("lease_id") or "") in NFL_RELEASE_LEASE_IDS
    )
    if remaining:
        raise RuntimeError("NFL_RB_WR_STEP1_AUTHORITY_GC_READBACK_MISMATCH")
    return {
        "decision": "AUTHORITY_GC_COLLECTED",
        "remaining_target_mutation_authority": 0,
        "released_lease_count": len(NFL_RELEASE_LEASE_IDS),
        "state_revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def _execute_nfl_rb_wr_step1_closeout(app) -> dict:
    client = app.state.github_client
    if client.branch_sha("main") != NFL_MERGED_MAIN_SHA:
        raise RuntimeError("NFL_RB_WR_STEP1_MAIN_DRIFT")

    receipt = _decode_json(
        client.content(NFL_RECEIPT_PATH, ref=NFL_RECEIPT_BRANCH),
        "NFL_RB_WR_STEP1_PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if (
        str(receipt.get("proof_id") or "") != NFL_PREMERGE_PROOF_ID
        or str(receipt.get("candidate_sha") or "") != NFL_CANDIDATE_SHA
        or str(receipt.get("digest") or "") != NFL_PREMERGE_DIGEST
        or str(receipt.get("task_id") or "") != NFL_TASK_ID
        or str(receipt.get("workstream") or "") != NFL_WORKSTREAM
        or str(receipt.get("failure_class") or "") != "NONE"
    ):
        raise RuntimeError("NFL_RB_WR_STEP1_PREMERGE_RECEIPT_DRIFT")

    gate = _read_gate(client)
    pr = client.request("GET", f"/pulls/{NFL_PR_NUMBER}") or {}
    if (
        not pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != NFL_CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != NFL_SOURCE_MAIN_SHA
        or str(pr.get("merge_commit_sha") or "") != NFL_MERGED_MAIN_SHA
    ):
        raise RuntimeError("NFL_RB_WR_STEP1_SQUASH_MERGE_PROVENANCE_DRIFT")

    source_tree = client.tree_blobs(NFL_SOURCE_MAIN_SHA)
    main_tree = client.tree_blobs(NFL_MERGED_MAIN_SHA)
    candidate_tree = client.tree_blobs(NFL_CANDIDATE_SHA)
    for label, mapping in (
        ("ARTIFACT", receipt.get("artifact_map") or {}),
        ("DEPENDENCY", receipt.get("dependency_map") or {}),
    ):
        for path, blob in mapping.items():
            if str(candidate_tree.get(path) or "") != str(blob) or str(main_tree.get(path) or "") != str(blob):
                raise RuntimeError(f"NFL_RB_WR_STEP1_SQUASH_{label}_IDENTITY_DRIFT:{path}")

    registry_raw = client.content(NFL_REGISTRY_PATH, ref=NFL_REGISTRY_BRANCH)
    registry = _decode_json(registry_raw, "NFL_RB_WR_STEP1_REGISTRY")
    validated = validate_registry(registry)

    existing_entry = (registry.get("entries") or {}).get(NFL_FREEZE_TOKEN)
    inherited_frozen_paths = []
    if existing_entry is None:
        _validate_finalizer_lease(client)
        if (
            int(registry.get("revision") or -1) != NFL_REGISTRY_REVISION
            or str(registry.get("state_hash") or "") != NFL_REGISTRY_HASH
            or str(registry.get("source_main_sha") or "") != NFL_SOURCE_MAIN_SHA
        ):
            raise RuntimeError("NFL_RB_WR_STEP1_REGISTRY_BASELINE_DRIFT")

        for path, expected in validated["artifacts"].items():
            source_blob = str(source_tree.get(path) or "")
            candidate_blob = str(candidate_tree.get(path) or "")
            main_blob = str(main_tree.get(path) or "")
            if not source_blob or not candidate_blob or not main_blob:
                raise RuntimeError("NFL_RB_WR_STEP1_EXISTING_FROZEN_MISSING:" + path)
            if not (source_blob == candidate_blob == main_blob):
                raise RuntimeError("NFL_RB_WR_STEP1_EXISTING_FROZEN_DELTA:" + path)
            if main_blob != str(expected):
                inherited_frozen_paths.append(path)

        freeze_artifacts = dict(sorted((receipt.get("artifact_map") or {}).items()))
        if not freeze_artifacts:
            raise RuntimeError("NFL_RB_WR_STEP1_FREEZE_ARTIFACTS_MISSING")
        thaw_paths = {
            path
            for grant in registry.get("active_thaws", [])
            for path in (grant.get("files") or {})
        }
        overlap = sorted(set(freeze_artifacts) & thaw_paths)
        if overlap:
            raise RuntimeError("NFL_RB_WR_STEP1_FREEZE_THAW_CONFLICT:" + ",".join(overlap))
        baseline_conflicts = sorted(
            path
            for path, blob in freeze_artifacts.items()
            if path in validated["artifacts"] and validated["artifacts"][path] != blob
        )
        if baseline_conflicts:
            raise RuntimeError("NFL_RB_WR_STEP1_FREEZE_BASELINE_CONFLICT:" + ",".join(baseline_conflicts))

        preserved_thaws = deepcopy(registry.get("active_thaws") or [])
        updated = deepcopy(registry)
        updated["revision"] = int(registry["revision"]) + 1
        updated["source_main_sha"] = NFL_MERGED_MAIN_SHA
        updated["entries"][NFL_FREEZE_TOKEN] = {
            "status": "FROZEN",
            "checkpoint_id": NFL_FREEZE_TOKEN,
            "source_main_sha": NFL_MERGED_MAIN_SHA,
            "artifacts": freeze_artifacts,
        }
        updated["active_thaws"] = preserved_thaws
        updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
        validate_registry(updated)
        client.update_content(
            NFL_REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True) + "\n",
            NFL_REGISTRY_BRANCH,
            "registry: freeze NFL RB WR render repair Step 1 root cause",
            registry_raw["sha"],
        )
    else:
        freeze_artifacts = dict(sorted((receipt.get("artifact_map") or {}).items()))
        if (
            str(existing_entry.get("source_main_sha") or "") != NFL_MERGED_MAIN_SHA
            or existing_entry.get("artifacts") != freeze_artifacts
        ):
            raise RuntimeError("NFL_RB_WR_STEP1_FREEZE_TOKEN_COLLISION")

    readback = _decode_json(
        client.content(NFL_REGISTRY_PATH, ref=NFL_REGISTRY_BRANCH),
        "NFL_RB_WR_STEP1_REGISTRY_READBACK",
    )
    validate_registry(readback)
    frozen = (readback.get("entries") or {}).get(NFL_FREEZE_TOKEN)
    if (
        not frozen
        or frozen.get("status") != "FROZEN"
        or str(frozen.get("source_main_sha") or "") != NFL_MERGED_MAIN_SHA
        or frozen.get("artifacts") != dict(sorted((receipt.get("artifact_map") or {}).items()))
        or str(readback.get("source_main_sha") or "") != NFL_MERGED_MAIN_SHA
    ):
        raise RuntimeError("NFL_RB_WR_STEP1_REGISTRY_READBACK_MISMATCH")

    ledger = _decode_json(
        client.content(NFL_LEDGER_PATH, ref=NFL_MERGED_MAIN_SHA),
        "NFL_RB_WR_STEP1_LEDGER",
    )
    resolver_source = _decode_text(
        client.content(NFL_CANONICAL_RESOLVER_PATH, ref=NFL_MERGED_MAIN_SHA),
        "NFL_RB_WR_STEP1_CANONICAL_RESOLVER",
    )
    resolver_ns = {"__name__": "nfl_rb_wr_step1_runtime_canonical_resolver"}
    exec(compile(resolver_source, NFL_CANONICAL_RESOLVER_PATH, "exec"), resolver_ns)
    merge_evidence = {
        "contains_candidate": True,
        "candidate_sha": NFL_CANDIDATE_SHA,
        "merged_main_sha": NFL_MERGED_MAIN_SHA,
        "method": "GITHUB_SQUASH_PR_EXACT_CONTENT_IDENTITY",
        "pr_number": NFL_PR_NUMBER,
        "artifact_count": len(receipt.get("artifact_map") or {}),
        "dependency_count": len(receipt.get("dependency_map") or {}),
    }
    canonical = resolver_ns["resolve_completion"](
        task_id=NFL_TASK_ID,
        freeze_token=NFL_FREEZE_TOKEN,
        ledger=ledger,
        registry=readback,
        receipt=receipt,
        gate=gate,
        merge_evidence=merge_evidence,
    )
    if canonical.get("complete") is not True or canonical.get("status") != "GREEN_FROZEN":
        raise RuntimeError("NFL_RB_WR_STEP1_CANONICAL_COMPLETION_BLOCKED:" + str(canonical.get("reason") or "UNKNOWN"))

    authority_gc = _release_nfl_authorities(client)
    if int(authority_gc.get("remaining_target_mutation_authority") or -1) != 0:
        raise RuntimeError("NFL_RB_WR_STEP1_AUTHORITY_GC_NOT_TERMINAL")

    return {
        "status": "GREEN",
        "decision": "NFL_RB_WR_STEP1_GREEN_FROZEN",
        "step": "1/5",
        "main_sha": NFL_MERGED_MAIN_SHA,
        "source_candidate_sha": NFL_CANDIDATE_SHA,
        "premerge_proof_id": NFL_PREMERGE_PROOF_ID,
        "premerge_receipt_digest": NFL_PREMERGE_DIGEST,
        "premerge_gate_id": NFL_PREMERGE_CHECK_ID,
        "freeze_token": NFL_FREEZE_TOKEN,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws") or []),
        "frozen_artifact_count": len(frozen.get("artifacts") or {}),
        "inherited_frozen_path_count": len(inherited_frozen_paths),
        "canonical_completion": canonical,
        "merge_evidence": merge_evidence,
        "authority_gc": authority_gc,
        "product_runtime_mutations": 0,
        "github_actions_fallback": 0,
    }


def _run_nfl_rb_wr_step1_submit(app) -> None:
    app.state.nfl_rb_wr_step1_submit = {"status": "NOT_RUN"}
    if os.getenv(NFL_RB_WR_SUBMIT_FLAG, "").strip() != "1":
        return
    try:
        request = ProofRequest(
            task_id=os.environ["RPP_NFL_RB_WR_STEP1_TASK_ID"],
            workstream=os.environ["RPP_NFL_RB_WR_STEP1_WORKSTREAM"],
            candidate_sha=os.environ["RPP_NFL_RB_WR_STEP1_CANDIDATE_SHA"],
            lease_id=os.environ["RPP_NFL_RB_WR_STEP1_LEASE_ID"],
            authorization_id=os.environ["RPP_NFL_RB_WR_STEP1_AUTHORIZATION_ID"],
            expected_main_sha=os.environ["RPP_NFL_RB_WR_STEP1_EXPECTED_MAIN_SHA"],
        )
        app.state.nfl_rb_wr_step1_submit = execute_proof_request(
            request,
            settings=app.state.settings,
            github_client=app.state.github_client,
            orchestrator=app.state.orchestrator,
            receipts=app.state.receipts,
        )
    except Exception as exc:
        app.state.nfl_rb_wr_step1_submit = {
            "status": "FAIL",
            "error": type(exc).__name__,
            "detail": str(exc)[:1800],
        }
    print(
        "NFL_RB_WR_STEP1_RUNLESS_SUBMIT="
        + json.dumps(app.state.nfl_rb_wr_step1_submit, sort_keys=True),
        flush=True,
    )


def _run_nfl_rb_wr_step1_closeout(app) -> None:
    app.state.nfl_rb_wr_step1_closeout = {"status": "NOT_RUN"}
    if os.getenv(NFL_RB_WR_CLOSEOUT_FLAG, "").strip() != "1":
        return
    try:
        app.state.nfl_rb_wr_step1_closeout = _execute_nfl_rb_wr_step1_closeout(app)
    except Exception as exc:
        app.state.nfl_rb_wr_step1_closeout = {
            "status": "FAIL",
            "error": type(exc).__name__,
            "detail": str(exc)[:1800],
        }
    print(
        "NFL_RB_WR_STEP1_FINAL_CLOSEOUT="
        + json.dumps(app.state.nfl_rb_wr_step1_closeout, sort_keys=True),
        flush=True,
    )


def install_startup(app):
    app.state.cfb_game_total_page1_v2_step4_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step4_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step4_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP4_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_page1_v2_step4_closeout, sort_keys=True),
            flush=True,
        )
        _run_nfl_rb_wr_step1_submit(app)
        _run_nfl_rb_wr_step1_closeout(app)

    return app
