from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import release_scope, validate_state as validate_lease_state

from .gate import publish_gate
from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend, _state_hash

TASK_ID = "cfb-game-total-page2-step2-matchup-hero-phx"
WORKSTREAM = "cfb-game-total-page2-v1"
MAIN_SHA = "b7f54cd695b05674ed7d1947167196bb75d28969"
PREMERGE_SHA = "ffcbd1fd767c30a5ed6b9dbbde9aa72888c4caea"
PREMERGE_RECEIPT_DIGEST = "5b87156fd38488d45156fd4d8241e6d433a83f6b995c393c025c6d62df1be424"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
OWNER_ID = "api2-cfb-game-total-page2-step2-matchup-hero-phx"
LEASE_ID = "SCOPE-LEASE-3C34C342A60F9CAD5091D9A2"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"

ARTIFACT_MAP = {
    "cfb_game_total_page2_step2_matchup_hero_phx_v1.py": "838564a373c10c2c8ee3639db04d04036baad6a5",
    "devsystem/execution_plans/cfb-game-total-page2-step2-matchup-hero-phx.json": "eb8bb77ce7b5e048ff6fb67c246d61ecc6d2505e",
    "devsystem/runless_proof_plans/cfb-game-total-page2-step2-matchup-hero-phx.json": "c3e71b4c8bdd7085154e920b9976007306d65121",
    "tests/test_cfb_game_total_page2_step2_matchup_hero_phx_v1.py": "2e0b7e379d6fd00a8d62f99a9b57e1bb6adf1ea2",
}

DEPENDENCY_PATHS = (
    "cfb_game_total_clean_page_v14.py",
    "cfb_game_total_page1_visual_cleanup_step2_top_shell_v1.py",
    "streamlit_memory_lazy_router_v191.py",
)


def _decode_json(raw: dict, error: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(error)
    try:
        return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(error) from exc


def _assert_main_and_artifacts(client) -> dict[str, str]:
    observed_main = client.branch_sha("main")
    if observed_main != MAIN_SHA:
        raise RuntimeError(f"PAGE2_STEP2_MAIN_DRIFT:{observed_main}")
    tree = client.tree_blobs(MAIN_SHA)
    for path, expected_blob in ARTIFACT_MAP.items():
        observed_blob = tree.get(path)
        if observed_blob != expected_blob:
            raise RuntimeError(
                f"PAGE2_STEP2_ARTIFACT_DRIFT:{path}:{observed_blob}:{expected_blob}"
            )
    return tree


def _freeze_exact_step2(client) -> tuple[dict, dict]:
    backend = GithubRegistryBackend(client)
    before = backend.read_registry()
    before_snapshot = {
        "revision": int(before["revision"]),
        "state_hash": str(before["state_hash"]),
    }

    existing = (before.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if (
            existing.get("status") != "FROZEN"
            or existing.get("checkpoint_id") != FREEZE_TOKEN
            or existing.get("source_main_sha") != MAIN_SHA
            or existing.get("artifacts") != ARTIFACT_MAP
        ):
            raise RuntimeError("PAGE2_STEP2_FREEZE_TOKEN_CONFLICT")
        after = before
    else:
        flattened: dict[str, str] = {}
        for entry in (before.get("entries") or {}).values():
            flattened.update(entry.get("artifacts") or {})
        conflicts = [
            path
            for path, blob in ARTIFACT_MAP.items()
            if path in flattened and flattened[path] != blob
        ]
        if conflicts:
            raise RuntimeError("PAGE2_STEP2_FROZEN_BASELINE_CONFLICT:" + ",".join(sorted(conflicts)))

        updated = deepcopy(before)
        updated["revision"] = int(before["revision"]) + 1
        updated["source_main_sha"] = MAIN_SHA
        updated["entries"][FREEZE_TOKEN] = {
            "status": "FROZEN",
            "checkpoint_id": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "artifacts": dict(sorted(ARTIFACT_MAP.items())),
        }
        # Preserve every unrelated thaw exactly as observed.
        updated["active_thaws"] = deepcopy(before.get("active_thaws", []))
        updated["state_hash"] = _state_hash(updated)
        validate_registry(updated)
        text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if not backend._blob_sha:
            raise RuntimeError("PAGE2_STEP2_REGISTRY_BLOB_MISSING")
        client.update_content(
            backend.path,
            text,
            backend.branch,
            f"registry: freeze {FREEZE_TOKEN}",
            backend._blob_sha,
        )
        after = backend.read_registry()

    entry = (after.get("entries") or {}).get(FREEZE_TOKEN)
    if (
        not entry
        or entry.get("status") != "FROZEN"
        or entry.get("source_main_sha") != MAIN_SHA
        or entry.get("artifacts") != ARTIFACT_MAP
        or after.get("source_main_sha") != MAIN_SHA
    ):
        raise RuntimeError("PAGE2_STEP2_REGISTRY_READBACK_MISMATCH")

    after_snapshot = {
        "revision": int(after["revision"]),
        "state_hash": str(after["state_hash"]),
    }
    return before_snapshot, after_snapshot


def _publish_merged_main_gate(app, tree: dict[str, str], registry_before: dict, registry_after: dict) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    dependency_map = {path: tree[path] for path in DEPENDENCY_PATHS}
    proof_id = f"cfb-game-total-page2-step2-postmerge-{MAIN_SHA[:16]}"
    receipt = build_runless_receipt(
        proof_id=proof_id,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="2/8-postmerge-freeze",
        candidate_sha=MAIN_SHA,
        artifact_map=dict(sorted(ARTIFACT_MAP.items())),
        dependency_map=dependency_map,
        registry_before=registry_before,
        registry_after=registry_after,
        evidence_digests=[PREMERGE_RECEIPT_DIGEST, registry_after["state_hash"]],
        failure_class="NONE",
        deployment_identity=settings.deployment_identity,
        prior_digest=PREMERGE_RECEIPT_DIGEST,
        premerge_candidate_sha=PREMERGE_SHA,
        github_actions_fallback=0,
        freeze_token=FREEZE_TOKEN,
    )

    store = ReceiptStore(
        GithubReceiptBackend(
            client,
            MAIN_SHA,
            settings.receipt_ref,
            settings.receipt_path,
        ),
        settings.receipt_ref,
        settings.receipt_path,
    )
    receipt_path = f"{store.base_path}/{proof_id}.json"
    if store.backend.exists(receipt_path, store.ref):
        stored = store.get(proof_id)
        if stored.get("digest") != receipt.get("digest"):
            raise RuntimeError("PAGE2_STEP2_POSTMERGE_RECEIPT_CONFLICT")
        receipt = stored
    else:
        store.put(receipt)

    publish_gate(client, MAIN_SHA, "success", receipt, settings.gate_name)
    return receipt


def _release_step2_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    current = validate_lease_state(_decode_json(raw, "PAGE2_STEP2_LEASE_READ_FAILED"))
    holder = next(
        (
            item
            for item in current.get("holders", [])
            if item.get("owner_id") == OWNER_ID and item.get("lease_id") == LEASE_ID
        ),
        None,
    )
    if holder is None:
        return {
            "decision": "SCOPE_LEASE_ALREADY_RELEASED",
            "allowed": True,
            "remaining_holders": len(current.get("holders", [])),
            "state_hash": current["state_hash"],
            "revision": current["revision"],
        }

    released = release_scope(
        current,
        owner_id=OWNER_ID,
        lease_id=LEASE_ID,
        expected_revision=int(current["revision"]),
        expected_state_hash=str(current["state_hash"]),
    )
    result = released["result"]
    if result.get("decision") != "SCOPE_LEASE_RELEASED" or not result.get("allowed"):
        raise RuntimeError("PAGE2_STEP2_LEASE_RELEASE_FAILED:" + str(result.get("decision")))
    updated = released["state"]
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    client.update_content(
        LEASE_PATH,
        text,
        LEASE_BRANCH,
        f"lease: release {LEASE_ID}",
        raw["sha"],
    )

    readback_raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    readback = validate_lease_state(_decode_json(readback_raw, "PAGE2_STEP2_LEASE_READBACK_FAILED"))
    if any(item.get("lease_id") == LEASE_ID for item in readback.get("holders", [])):
        raise RuntimeError("PAGE2_STEP2_LEASE_READBACK_MISMATCH")
    return {
        **result,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "remaining_holders": len(readback.get("holders", [])),
    }


def execute(app) -> dict:
    client = app.state.github_client
    tree = _assert_main_and_artifacts(client)
    registry_before, registry_after = _freeze_exact_step2(client)
    receipt = _publish_merged_main_gate(app, tree, registry_before, registry_after)
    lease = _release_step2_lease(client)
    return {
        "status": "GREEN_FROZEN",
        "step": "2/8",
        "main_sha": MAIN_SHA,
        "premerge_candidate_sha": PREMERGE_SHA,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "merged_main_receipt_digest": receipt["digest"],
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": registry_after["revision"],
        "registry_hash": registry_after["state_hash"],
        "lease_released": lease.get("allowed") is True,
        "lease_decision": lease.get("decision"),
        "remaining_lease_holders": lease.get("remaining_holders"),
        "github_actions_enabled": False,
        "page1_files_modified": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step2_final = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3000],
            }
        app.state.cfb_game_total_page2_step2_final = result
        print(
            "CFB_GT_PAGE2_STEP2_FINAL="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )

    return app
