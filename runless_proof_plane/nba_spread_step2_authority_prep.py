from __future__ import annotations

import base64
import json
import os
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state,
)

from .registry import GithubRegistryBackend, REGISTRY_PATH

ENV = "RPP_NBA_SPREAD_STEP2_AUTHORITY_PREP_ON_START"
TASK_ID = "nba-spread-step2-site-activation-v1"
WORKSTREAM = "nba-spread-two-page-v1"
BRANCH = "nba-spread-step2-site-activation-r1"
CANDIDATE_SHA = "21c31d5971c74ce1ff0ca0a22c2adffc6467d1c7"
PRIOR_CANDIDATE_SHA = "19c366d03e8f219fce4ae237c39e53b36955bcb1"
SOURCE_MAIN_SHA = "9a7afa1fe19d62eed444088a8e77ca6c45e0bfb1"
PR = "1521"
THAW_ID = "THAW-NBA-SPREAD-STEP2-SITE-ACTIVATION-R1"
OWNER_ID = "chatgpt:api2:nba-spread-step2-site-activation-v1"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
THAW_FILES = {
    "app.py": {
        "from_blob": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
        "to_blob": "a8802aa8e32b430e5c33378ab1105ca877b934c1",
    },
    "tests/test_devsystem_change_classifier_v1.py": {
        "from_blob": "265129d2ce89da49426b36059294fcba381cfb7b",
        "to_blob": "d02df05feaab1ac0cfb7b88968807a5090e09010",
    },
}
PRIOR_THAW_FILES = {
    "app.py": {
        "from_blob": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
        "to_blob": "a8802aa8e32b430e5c33378ab1105ca877b934c1",
    },
    "tests/test_devsystem_change_classifier_v1.py": {
        "from_blob": "265129d2ce89da49426b36059294fcba381cfb7b",
        "to_blob": "6b064453b2d79ab933ce58f9d2a504e34f6fbd21",
    },
}
WRITE_PATHS = (
    "app.py",
    "devsystem/devsystem_manifest_v1.json",
    "devsystem/execution_plans/nba-spread-step2-site-activation-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step2-site-activation-v1.json",
    "devsystem/task_ledgers/nba-spread-step2-site-activation-v1.json",
    "nba_spread_page_v1.py",
    "nba_spread_step2_activation_v1.py",
    "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py",
    "tests/test_devsystem_change_classifier_v1.py",
    "tests/test_nba_spread_step2_site_activation_v1.py",
)


class NBASpreadStep2AuthorityFailure(RuntimeError):
    pass


def _decode(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise NBASpreadStep2AuthorityFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise NBASpreadStep2AuthorityFailure(label + "_DECODE_FAILED") from exc


def _prepare_thaw(client) -> dict:
    if client.branch_sha("main") != SOURCE_MAIN_SHA:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_CANDIDATE_DRIFT")

    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    validated = validate_registry(current)
    if str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_REGISTRY_MAIN_DRIFT")

    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    main_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    for path, pair in THAW_FILES.items():
        expected = str(validated["artifacts"].get(path) or "")
        if expected != pair["from_blob"]:
            raise NBASpreadStep2AuthorityFailure("NBA_STEP2_FROZEN_BASELINE_DRIFT:" + path)
        if str(main_tree.get(path) or "") != pair["from_blob"]:
            raise NBASpreadStep2AuthorityFailure("NBA_STEP2_MAIN_BLOB_DRIFT:" + path)
        if str(candidate_tree.get(path) or "") != pair["to_blob"]:
            raise NBASpreadStep2AuthorityFailure("NBA_STEP2_CANDIDATE_BLOB_DRIFT:" + path)

    exact_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": deepcopy(THAW_FILES),
    }
    existing_indexes = [
        index for index, item in enumerate(current.get("active_thaws", []))
        if item.get("thaw_id") == THAW_ID
    ]
    if len(existing_indexes) > 1:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_DUPLICATE_THAW_ID")
    if existing_indexes:
        existing = current["active_thaws"][existing_indexes[0]]
        if existing == exact_grant:
            return current
        if (
            str(existing.get("target_head_sha") or "") != PRIOR_CANDIDATE_SHA
            or existing.get("files") != PRIOR_THAW_FILES
            or existing.get("status") != "ACTIVE"
        ):
            raise NBASpreadStep2AuthorityFailure("NBA_STEP2_THAW_ID_COLLISION")
        updated = deepcopy(current)
        updated["active_thaws"][existing_indexes[0]] = exact_grant
        message = "registry: rebind NBA Spread Step2 thaw to generation 2"
    else:
        updated = deepcopy(current)
        updated["active_thaws"].append(exact_grant)
        message = "registry: authorize NBA Spread Step2 exact-head thaw"

    updated["revision"] = int(current["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        backend.branch,
        message,
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    grants = [item for item in readback.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if grants != [exact_grant]:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_THAW_READBACK_MISMATCH")
    return readback


def _prepare_lease(client, registry: dict) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_state(_decode(raw, "NBA_STEP2_SCOPE_LEASE"))
    now = datetime.now(timezone.utc)

    working = state
    stale_ids = [
        str(h["lease_id"])
        for h in working.get("holders", [])
        if h.get("owner_id") == OWNER_ID
        and str((h.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") or "") != CANDIDATE_SHA
    ]
    for stale_id in stale_ids:
        released = release_scope(
            working,
            owner_id=OWNER_ID,
            lease_id=stale_id,
            expected_revision=int(working["revision"]),
            expected_state_hash=str(working["state_hash"]),
        )
        if released["result"].get("allowed") is not True:
            raise NBASpreadStep2AuthorityFailure("NBA_STEP2_STALE_LEASE_RELEASE_FAILED")
        working = released["state"]

    live = [
        h for h in working.get("holders", [])
        if now < datetime.fromisoformat(str(h["expires_at_utc"]).replace("Z", "+00:00"))
    ]
    matches = [
        h for h in live
        if h.get("owner_id") == OWNER_ID
        and str((h.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") or "") == CANDIDATE_SHA
    ]
    if len(matches) > 1:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_DUPLICATE_LIVE_LEASE")
    if matches and not stale_ids:
        return {
            "lease_id": str(matches[0]["lease_id"]),
            "lease_revision": int(working["revision"]),
            "lease_state_hash": str(working["state_hash"]),
            "reused": True,
            "released_stale_lease_ids": [],
        }

    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("workstream:nba-spread-two-page-v1",),
        shared_resources=("entrypoint:app.py",),
        resource_identity={
            "candidate_sha": CANDIDATE_SHA,
            "pr": PR,
            "source_main_sha": SOURCE_MAIN_SHA,
            "registry_state_hash": str(registry["state_hash"]),
        },
    )
    claimed = claim_scope(
        working,
        owner_id=OWNER_ID,
        now_utc=now.isoformat().replace("+00:00", "Z"),
        scope=scope,
        expected_revision=int(working["revision"]),
        expected_state_hash=str(working["state_hash"]),
        ttl_seconds=900,
        frozen_paths=tuple(validate_registry(registry)["artifacts"].keys()),
        thawed_paths=tuple(THAW_FILES.keys()),
    )
    result = claimed["result"]
    if result.get("allowed") is not True:
        raise NBASpreadStep2AuthorityFailure(
            "NBA_STEP2_SCOPE_LEASE_BLOCKED:" + str(result.get("decision") or "UNKNOWN")
        )
    updated = claimed["state"]
    client.update_content(
        LEASE_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: rebind NBA Spread Step2 generation 2 exact scope",
        str(raw.get("sha") or ""),
    )
    rb_raw = client.content(LEASE_PATH, ref=LEASE_REF)
    readback = validate_state(_decode(rb_raw, "NBA_STEP2_SCOPE_LEASE_READBACK"))
    lease_id = str(result["lease_id"])
    holders = [h for h in readback.get("holders", []) if h.get("lease_id") == lease_id]
    if len(holders) != 1:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_SCOPE_LEASE_READBACK_MISMATCH")
    old_remaining = [h for h in readback.get("holders", []) if str(h.get("lease_id") or "") in stale_ids]
    if old_remaining:
        raise NBASpreadStep2AuthorityFailure("NBA_STEP2_STALE_LEASE_STILL_PRESENT")
    return {
        "lease_id": lease_id,
        "lease_revision": int(readback["revision"]),
        "lease_state_hash": str(readback["state_hash"]),
        "reused": False,
        "released_stale_lease_ids": stale_ids,
    }


def execute(client) -> dict:
    registry = _prepare_thaw(client)
    lease = _prepare_lease(client, registry)
    return {
        "status": "GREEN",
        "task_id": TASK_ID,
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": SOURCE_MAIN_SHA,
        "thaw_id": THAW_ID,
        "thaw_paths": sorted(THAW_FILES),
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        **lease,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    @app.on_event("startup")
    def _run() -> None:
        trigger = os.environ.pop(ENV, "").strip()
        if trigger != "1":
            return
        try:
            result = execute(app.state.github_client)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:1800]}
        app.state.nba_spread_step2_authority_prep = result
        print("NBA_SPREAD_STEP2_AUTHORITY_PREP=" + json.dumps(result, sort_keys=True), flush=True)

    return app
