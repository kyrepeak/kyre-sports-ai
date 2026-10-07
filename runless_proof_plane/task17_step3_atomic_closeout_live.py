from __future__ import annotations

import json

from devsystem.frozen_artifact_registry_v1 import validate_registry

from . import task17_step3_atomic_closeout as base
from .registry import GithubRegistryBackend


def _bind_live_registry_identity(client) -> tuple[int, str]:
    lease = base._read_json(client, base.LEASE_PATH, base.LEASE_REF, "STEP3_LEASE")
    holders = [item for item in (lease.get("holders") or []) if item.get("lease_id") == base.LEASE_ID]
    if len(holders) != 1:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_ID_DRIFT")
    holder = holders[0]
    if str(holder.get("owner_id") or "") != base.LEASE_OWNER:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_OWNER_DRIFT")
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    if str(identity.get("main_sha") or "") != base.MAIN_SHA:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_MAIN_DRIFT")
    lease_registry_hash = str(identity.get("registry_state_hash") or "")
    if not lease_registry_hash:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_REGISTRY_MISSING")

    registry = GithubRegistryBackend(client).read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != base.MAIN_SHA:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_REGISTRY_MAIN_DRIFT")
    registry_hash = str(registry.get("state_hash") or "")
    if registry_hash != lease_registry_hash:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LIVE_LEASE_REGISTRY_DRIFT")

    revision = int(registry.get("revision") or -1)
    if revision < 0:
        raise base.Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_REGISTRY_REVISION_INVALID")
    return revision, registry_hash


def execute(client):
    revision, registry_hash = _bind_live_registry_identity(client)
    base.EXPECTED_REGISTRY_REVISION = revision
    base.EXPECTED_REGISTRY_HASH = registry_hash
    return base.execute(client)


def install_startup(app):
    app.state.task17_step3_atomic_closeout_live = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step3_atomic_closeout_live = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step3_atomic_closeout_live = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "RUNLESS_TASK17_STEP3_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.task17_step3_atomic_closeout_live, sort_keys=True),
            flush=True,
        )

    return app
