from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone

from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, validate_state
from .models import ProofRequest
from .prove import execute_proof_request

ENV_TRIGGER = "RPP_UNIVERSAL_SPORTS_STEP5_PROVE_ON_START"
ENV_CANDIDATE = "RPP_UNIVERSAL_SPORTS_STEP5_CANDIDATE_SHA"
TASK_ID = "universal-sports-source-finalization-v1-step5"
WORKSTREAM = "universal-sports-source-finalization-v1"
BRANCH = "api2-universal-sports-source-finalization-v1-step5-health-identity"
SOURCE_MAIN_SHA = "64b1d5835bf8354801bbc354d0ef180813ed0cf2"
AUTHORIZATION_ID = "AUTH-UNIVERSAL-SPORTS-STEP5-63C5C149"
OWNER_ID = "chatgpt:api2:universal-sports-source-finalization-v1-step5"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
ALLOWED_PATHS = {
    "devsystem/contracts/universal-sports-identity-health-v1.json",
    "devsystem/execution_plans/universal-sports-source-finalization-v1-step5.json",
    "devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step5.json",
    "devsystem/task_ledgers/universal-sports-source-finalization-v1-step5.json",
    "devsystem/universal_sports_identity_health_v1.py",
    "docs/superpowers/plans/2026-10-13-universal-sports-source-finalization-v1-step5.md",
    "tests/test_devsystem_universal_sports_identity_health_step5_v1.py",
}

class UniversalSportsStep5AuthorityFailure(RuntimeError):
    pass

def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise UniversalSportsStep5AuthorityFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise UniversalSportsStep5AuthorityFailure(label + "_DECODE_FAILED") from exc

def _candidate() -> str:
    value = os.environ.get(ENV_CANDIDATE, "").strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_CANDIDATE_ENV_INVALID")
    return value

def _changed_paths(client, candidate_sha: str) -> tuple[str, ...]:
    if client.branch_sha("main") != SOURCE_MAIN_SHA:
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != candidate_sha:
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_BRANCH_HEAD_DRIFT")
    main_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    candidate_tree = client.tree_blobs(candidate_sha)
    changed = tuple(sorted(path for path in set(main_tree) | set(candidate_tree) if main_tree.get(path) != candidate_tree.get(path)))
    unexpected = sorted(set(changed) - ALLOWED_PATHS)
    if unexpected:
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_SCOPE_ESCAPE:" + ",".join(unexpected))
    if set(changed) != ALLOWED_PATHS:
        missing = sorted(ALLOWED_PATHS - set(changed))
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_EXPECTED_PATH_MISSING:" + ",".join(missing))
    return changed

def _prepare_lease(client, candidate_sha: str, changed: tuple[str, ...]):
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_state(_decode_json(raw, "UNIVERSAL_SPORTS_STEP5_SCOPE_LEASE"))
    scope = build_scope(
        write_paths=changed,
        dependency_tokens=("workstream:universal-sports-source-finalization-v1",),
        shared_resources=(),
        resource_identity={"candidate_sha": candidate_sha, "source_main_sha": SOURCE_MAIN_SHA},
    )
    claimed = claim_scope(
        state,
        owner_id=OWNER_ID,
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        scope=scope,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
        ttl_seconds=1800,
        frozen_paths=(),
        thawed_paths=(),
    )
    if claimed["result"].get("allowed") is not True:
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_SCOPE_LEASE_BLOCKED:" + str(claimed["result"].get("decision")))
    client.update_content(
        LEASE_PATH,
        json.dumps(claimed["state"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: bind Universal Sports Step5 exact scope",
        str(raw.get("sha") or ""),
    )
    readback = validate_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_REF), "UNIVERSAL_SPORTS_STEP5_SCOPE_LEASE_READBACK"))
    lease_id = str(claimed["result"]["lease_id"])
    if len([item for item in readback.get("holders", []) if item.get("lease_id") == lease_id]) != 1:
        raise UniversalSportsStep5AuthorityFailure("UNIVERSAL_SPORTS_STEP5_SCOPE_LEASE_READBACK_MISMATCH")
    return lease_id

def execute(app):
    candidate_sha = _candidate()
    changed = _changed_paths(app.state.github_client, candidate_sha)
    lease_id = _prepare_lease(app.state.github_client, candidate_sha, changed)
    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=candidate_sha,
        lease_id=lease_id,
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=SOURCE_MAIN_SHA,
    )
    result = execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=app.state.github_client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )
    return {**dict(result), "changed_paths": list(changed), "lease_id": lease_id, "github_actions_fallback": 0}

def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV_TRIGGER, "").strip() != "1":
            return
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:2000]}
        app.state.universal_sports_step5_authority_prove = result
        print("UNIVERSAL_SPORTS_STEP5_AUTHORITY_PROVE=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    return app
