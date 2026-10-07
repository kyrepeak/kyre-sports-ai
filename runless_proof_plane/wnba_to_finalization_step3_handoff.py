from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.atomic_wait_queue_lease_handoff_v1 import (
    atomic_release_and_handoff,
    reconcile_queue_from_lease,
    validate_queue_state,
)
from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_lease_state
from .registry import GithubRegistryBackend

LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
QUEUE_REF = "monster-lease-wait-queue"
QUEUE_PATH = "devsystem/atomic_wait_queue_state_v1.json"
OUTGOING_OWNER = "api2-wnba-pra-history-v1-step1"
OUTGOING_LEASE = "SCOPE-LEASE-58276A81543E070B30D3D29C"
TARGET_OWNER = "api2-finalization-authority-v1-step3"
TICKET_ID = "WAIT-TICKET-748127A71979A21A76B78EA6"
QUEUE_KEY = "runless-proof-plane-v1"
EXPECTED_LEASE_REVISION = 262
EXPECTED_LEASE_HASH = "d23803dccf6bc63a0354961dffe331e4edf484efc493ca4432e0c2ea74cc65cf"
EXPECTED_QUEUE_REVISION = 6
EXPECTED_QUEUE_HASH = "e58dedbfed57e26a0c351129153ccc37b3b808af7a15c1556e9864ad91ea0859"
FREEZE_TOKEN = "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1_FROZEN"


class WNBAFinalizationHandoffFailure(RuntimeError):
    pass


def _decode(raw: dict, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise WNBAFinalizationHandoffFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
    except Exception as exc:
        raise WNBAFinalizationHandoffFailure(label + "_DECODE_FAILED") from exc


def _read(client, path: str, ref: str, label: str) -> tuple[dict, dict]:
    raw = client.content(path, ref=ref)
    return _decode(raw, label), raw


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _frozen_and_thawed(registry: dict) -> tuple[list[str], list[str]]:
    frozen = sorted({
        path
        for entry in (registry.get("entries") or {}).values()
        for path in (entry.get("artifacts") or {})
    })
    thawed = sorted({
        path
        for thaw in (registry.get("active_thaws") or [])
        if str(thaw.get("status") or "ACTIVE").upper() == "ACTIVE"
        for path in (thaw.get("files") or {})
    })
    return frozen, thawed


def _target_holder(lease: dict) -> dict | None:
    for holder in lease.get("holders") or []:
        identity = ((holder.get("scope") or {}).get("resource_identity") or {})
        if holder.get("owner_id") == TARGET_OWNER and identity.get("queue:ticket") == TICKET_ID:
            return holder
    return None


def _receipt(queue: dict) -> dict | None:
    return next(
        (r for r in (queue.get("handoff_receipts") or []) if r.get("ticket_id") == TICKET_ID),
        None,
    )


def _persist_queue_reconcile(client, lease: dict, queue: dict, queue_raw: dict, now_utc: str) -> tuple[dict, dict]:
    reconciled = reconcile_queue_from_lease(
        queue,
        lease,
        expected_queue_revision=int(queue["revision"]),
        expected_queue_state_hash=str(queue["state_hash"]),
        now_utc=now_utc,
    )
    if reconciled["result"].get("allowed") is not True:
        raise WNBAFinalizationHandoffFailure("QUEUE_RECONCILE_BLOCKED:" + str(reconciled["result"].get("decision")))
    state = reconciled["state"]
    if state != queue:
        client.update_content(
            QUEUE_PATH,
            json.dumps(state, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            QUEUE_REF,
            "queue: reconcile Finalization Step 3 atomic lease handoff",
            queue_raw["sha"],
        )
    return state, reconciled["result"]


def execute(client):
    now_utc = _now()
    lease, lease_raw = _read(client, LEASE_PATH, LEASE_REF, "LEASE")
    queue, queue_raw = _read(client, QUEUE_PATH, QUEUE_REF, "QUEUE")
    lease = validate_lease_state(lease)
    queue = validate_queue_state(queue)

    registry = validate_registry(GithubRegistryBackend(client).read_registry())
    if FREEZE_TOKEN not in (registry.get("entries") or {}):
        raise WNBAFinalizationHandoffFailure("WNBA_FREEZE_TOKEN_MISSING")
    frozen_paths, thawed_paths = _frozen_and_thawed(registry)

    existing_holder = _target_holder(lease)
    existing_receipt = _receipt(queue)
    if existing_holder and existing_receipt:
        return {
            "status": "GREEN",
            "decision": "ATOMIC_LEASE_HANDOFF_ALREADY_COMMITTED",
            "ticket_id": TICKET_ID,
            "previous_lease_id": OUTGOING_LEASE,
            "new_owner_id": TARGET_OWNER,
            "new_lease_id": existing_holder["lease_id"],
            "lease_revision": int(lease["revision"]),
            "lease_state_hash": str(lease["state_hash"]),
            "queue_revision": int(queue["revision"]),
            "queue_state_hash": str(queue["state_hash"]),
            "handoff_receipt": existing_receipt,
            "next_legal_action": "RESUME_RESERVED_WORKSTREAM",
        }

    if existing_holder:
        queue, reconcile_result = _persist_queue_reconcile(client, lease, queue, queue_raw, now_utc)
        existing_receipt = _receipt(queue)
        if not existing_receipt:
            raise WNBAFinalizationHandoffFailure("HANDOFF_RECONCILE_RECEIPT_MISSING")
        return {
            "status": "GREEN",
            "decision": "ATOMIC_LEASE_HANDOFF_RECONCILED",
            "ticket_id": TICKET_ID,
            "previous_lease_id": OUTGOING_LEASE,
            "new_owner_id": TARGET_OWNER,
            "new_lease_id": existing_holder["lease_id"],
            "lease_revision": int(lease["revision"]),
            "lease_state_hash": str(lease["state_hash"]),
            "queue_revision": int(queue["revision"]),
            "queue_state_hash": str(queue["state_hash"]),
            "handoff_receipt": existing_receipt,
            "reconcile_decision": reconcile_result.get("decision"),
            "next_legal_action": "RESUME_RESERVED_WORKSTREAM",
        }

    outcome = atomic_release_and_handoff(
        lease,
        queue,
        releasing_owner_id=OUTGOING_OWNER,
        releasing_lease_id=OUTGOING_LEASE,
        queue_key=QUEUE_KEY,
        now_utc=now_utc,
        expected_lease_revision=EXPECTED_LEASE_REVISION,
        expected_lease_state_hash=EXPECTED_LEASE_HASH,
        expected_queue_revision=EXPECTED_QUEUE_REVISION,
        expected_queue_state_hash=EXPECTED_QUEUE_HASH,
        lease_ttl_seconds=3600,
        frozen_paths=frozen_paths,
        thawed_paths=thawed_paths,
    )
    result = outcome["result"]
    if result.get("decision") != "ATOMIC_LEASE_HANDOFF_COMMITTED" or result.get("allowed") is not True:
        raise WNBAFinalizationHandoffFailure("ATOMIC_HANDOFF_BLOCKED:" + json.dumps(result, sort_keys=True))
    if result.get("ticket_id") != TICKET_ID or result.get("new_owner_id") != TARGET_OWNER:
        raise WNBAFinalizationHandoffFailure("ATOMIC_HANDOFF_TARGET_DRIFT")

    new_lease = validate_lease_state(outcome["lease_state"])
    new_queue = validate_queue_state(outcome["queue_state"])

    client.update_content(
        LEASE_PATH,
        json.dumps(new_lease, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: atomic handoff WNBA to API2 Finalization Step 3",
        lease_raw["sha"],
    )
    try:
        client.update_content(
            QUEUE_PATH,
            json.dumps(new_queue, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            QUEUE_REF,
            "queue: commit WNBA to Finalization Step 3 handoff receipt",
            queue_raw["sha"],
        )
    except Exception:
        live_lease, _ = _read(client, LEASE_PATH, LEASE_REF, "LEASE_RECOVERY")
        live_queue, live_queue_raw = _read(client, QUEUE_PATH, QUEUE_REF, "QUEUE_RECOVERY")
        live_lease = validate_lease_state(live_lease)
        live_queue = validate_queue_state(live_queue)
        new_queue, _ = _persist_queue_reconcile(client, live_lease, live_queue, live_queue_raw, now_utc)

    lease_readback, _ = _read(client, LEASE_PATH, LEASE_REF, "LEASE_READBACK")
    queue_readback, _ = _read(client, QUEUE_PATH, QUEUE_REF, "QUEUE_READBACK")
    lease_readback = validate_lease_state(lease_readback)
    queue_readback = validate_queue_state(queue_readback)
    holder = _target_holder(lease_readback)
    receipt = _receipt(queue_readback)
    if not holder or not receipt:
        raise WNBAFinalizationHandoffFailure("ATOMIC_HANDOFF_READBACK_MISMATCH")
    if any(h.get("lease_id") == OUTGOING_LEASE for h in lease_readback.get("holders") or []):
        raise WNBAFinalizationHandoffFailure("OUTGOING_WNBA_LEASE_STILL_PRESENT")
    if any(t.get("ticket_id") == TICKET_ID for t in queue_readback.get("tickets") or []):
        raise WNBAFinalizationHandoffFailure("WAIT_TICKET_STILL_PENDING")

    return {
        "status": "GREEN",
        "decision": "ATOMIC_LEASE_HANDOFF_COMMITTED",
        "ticket_id": TICKET_ID,
        "previous_owner_id": OUTGOING_OWNER,
        "previous_lease_id": OUTGOING_LEASE,
        "new_owner_id": TARGET_OWNER,
        "new_lease_id": holder["lease_id"],
        "lease_revision": int(lease_readback["revision"]),
        "lease_state_hash": str(lease_readback["state_hash"]),
        "queue_revision": int(queue_readback["revision"]),
        "queue_state_hash": str(queue_readback["state_hash"]),
        "handoff_receipt": receipt,
        "next_legal_action": "RESUME_RESERVED_WORKSTREAM",
        "frozen_path_count": len(frozen_paths),
        "thawed_path_count": len(thawed_paths),
    }


def install_startup(app):
    app.state.wnba_to_finalization_step3_handoff = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_to_finalization_step3_handoff = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_to_finalization_step3_handoff = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "WNBA_TO_FINALIZATION_STEP3_HANDOFF="
            + json.dumps(app.state.wnba_to_finalization_step3_handoff, sort_keys=True),
            flush=True,
        )

    return app
