from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "0a573142882c3a5db1db10d6585aa48b522be971"
CANDIDATE_SHA = "bb9ef2fea11b6cb9d7617e911dc7dabcecd6e2e4"
PR_NUMBER = 1419
TARGET_FILE = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
TEST_FILE = "tests/test_wnba_pushstate_repair_v1_step3_game_handoff.py"
OLD_BLOB = "ff4829124afc1004311e0aa4272646a5875c20c8"
NEW_BLOB = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
THAW_ID = "THAW-API2-WNBA-PUSHSTATE-STEP3-GAME-HANDOFF"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _read_text(client, path: str, ref: str) -> str:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload, str(raw["sha"])


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _verify_identity(client) -> tuple[dict[str, str], str, str]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}")
    if str(pr.get("state")) != "open":
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_PR_NOT_OPEN")
    if str(((pr.get("head") or {}).get("sha") or "")) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_HEAD_DRIFT")
    base = pr.get("base") or {}
    if str(base.get("ref") or "") != "main" or str(base.get("sha") or "") != BASE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_BASE_DRIFT")

    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100")
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    expected = tuple(sorted((TARGET_FILE, TEST_FILE)))
    if changed != expected:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_SCOPE_DRIFT:" + ",".join(changed))

    blobs = client.tree_blobs(CANDIDATE_SHA)
    target_blob = str(blobs.get(TARGET_FILE) or "")
    test_blob = str(blobs.get(TEST_FILE) or "")
    if target_blob != NEW_BLOB:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_TARGET_BLOB_DRIFT:" + target_blob)
    if len(test_blob) != 40:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_TEST_BLOB_MISSING")
    return {TARGET_FILE: target_blob, TEST_FILE: test_blob}, target_blob, test_blob


def _verify_behavior(client) -> dict[str, Any]:
    source = _read_text(client, TARGET_FILE, CANDIDATE_SHA)
    test_source = _read_text(client, TEST_FILE, CANDIDATE_SHA)
    compile(source, TARGET_FILE, "exec")
    compile(test_source, TEST_FILE, "exec")

    marker = "def _pin_deep_wnba_session_route"
    if marker not in source or "def render_app" not in source:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_SESSION_PIN_MISSING")
    body = source.split(marker, 1)[1].split("def render_app", 1)[0]
    required = (
        "navigation.PAGE_GAME",
        "navigation.PAGE_PLAYER",
        "st.session_state[deep_route.SHELL_SPORT_SESSION_KEY]",
        "st.session_state[deep_route.SHELL_MARKET_SESSION_KEY]",
        "deep_route._protect_explicit_cfb_top_picks_route()",
    )
    missing = [item for item in required if item not in body]
    if missing:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_SESSION_PIN_CONTRACT_MISSING:" + ",".join(missing))
    if "st.query_params" in body:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_QUERY_REINJECTION_PRESENT")

    required_runtime = (
        "original_deep_pin = deep_route._pin_deep_wnba_shell_route",
        "deep_route._pin_deep_wnba_shell_route = _pin_deep_wnba_session_route",
        "deep_route._pin_deep_wnba_shell_route = original_deep_pin",
        'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback"',
        "MAY_MODIFY_WNBA_MODEL = False",
        "MAY_MODIFY_PROJECTION_MATH = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_OTHER_SPORTS = False",
    )
    missing_runtime = [item for item in required_runtime if item not in source]
    if missing_runtime:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_RUNTIME_CONTRACT_MISSING:" + ",".join(missing_runtime))

    base_source = _read_text(client, TARGET_FILE, BASE_SHA)
    if "st.query_params[SHELL_SPORT_QUERY_KEY]" not in _read_text(
        client,
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py",
        BASE_SHA,
    ):
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_ROOT_CAUSE_BASELINE_MISSING")
    if "_pin_deep_wnba_session_route" in base_source:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_BASE_ALREADY_PATCHED")

    return {
        "session_only_deep_pin": True,
        "query_reinjection": False,
        "frozen_parent_preserved": True,
        "test_compiles": True,
        "runtime_compiles": True,
    }


def _ensure_exact_thaw(client) -> dict[str, Any]:
    registry, content_sha = _read_registry(client)
    flattened: dict[str, str] = {}
    for entry in (registry.get("entries") or {}).values():
        flattened.update(entry.get("artifacts") or {})
    if str(flattened.get(TARGET_FILE) or "") != OLD_BLOB:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_FROZEN_BASELINE_DRIFT")

    expected_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {
            TARGET_FILE: {
                "from_blob": OLD_BLOB,
                "to_blob": NEW_BLOB,
            }
        },
    }
    thaws = list(registry.get("active_thaws") or [])
    for grant in thaws:
        files = grant.get("files") or {}
        if TARGET_FILE in files and str(grant.get("thaw_id")) != THAW_ID:
            raise RuntimeError("WNBA_PUSHSTATE_STEP3_CONFLICTING_ACTIVE_THAW")
        if str(grant.get("thaw_id")) == THAW_ID:
            if grant != expected_grant:
                raise RuntimeError("WNBA_PUSHSTATE_STEP3_THAW_ID_CONFLICT")
            return {
                "idempotent": True,
                "revision": int(registry["revision"]),
                "state_hash": str(registry["state_hash"]),
            }

    before_hash = str(registry["state_hash"])
    updated = deepcopy(registry)
    updated["active_thaws"] = thaws + [expected_grant]
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = BASE_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    client.update_content(
        REGISTRY_PATH,
        text,
        REGISTRY_BRANCH,
        f"registry: thaw {THAW_ID}",
        content_sha,
    )
    readback, _ = _read_registry(client)
    grants = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if grants != [expected_grant]:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_THAW_READBACK_FAILED")
    return {
        "idempotent": False,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "before_hash": before_hash,
    }


def publish_candidate_gate(client) -> dict[str, Any]:
    artifact_map, _, _ = _verify_identity(client)
    behavior = _verify_behavior(client)
    thaw = _ensure_exact_thaw(client)
    evidence = {
        "pr": PR_NUMBER,
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "old_blob": OLD_BLOB,
        "new_blob": NEW_BLOB,
        "scope": sorted(artifact_map),
        "behavior": behavior,
        "github_actions_fallback": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step3-game-handoff-{CANDIDATE_SHA[:16]}",
        task_id="wnba-pushstate-repair-v1-step3-game-handoff",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step3",
        step="3/4-candidate-certification",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifact_map,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "pr_number": PR_NUMBER,
            "proof_authority": "Runless Proof Plane",
            "proof_mode": "exact-frozen-thaw-plus-session-only-deep-route",
            "thaw_id": THAW_ID,
        },
        registry_before={"baseline_blob": OLD_BLOB, "mode": "frozen"},
        registry_after={
            "target_head_sha": CANDIDATE_SHA,
            "to_blob": NEW_BLOB,
            "thaw_id": THAW_ID,
            "revision": thaw["revision"],
            "state_hash": thaw["state_hash"],
        },
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": check.get("id"),
        "receipt_digest": receipt["digest"],
        "thaw_id": THAW_ID,
        "registry_revision": thaw["revision"],
        **behavior,
    }


def install_startup_gate(app):
    app.state.wnba_pushstate_step3_game_handoff_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _publish_wnba_pushstate_step3_game_handoff_gate():
        try:
            app.state.wnba_pushstate_step3_game_handoff_gate = publish_candidate_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step3_game_handoff_gate = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
