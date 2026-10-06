from __future__ import annotations

import base64
import hashlib
import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "896bd5f78ef6b6f7d7084413cc1e35ac6489fdc2"
CANDIDATE_SHA = "6c9ce57a99fb49225935b3b17fdd582dc136204b"
PR_NUMBER = 1417
OWNER_FILE = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
TEST_FILE = "tests/test_wnba_pushstate_repair_v1_step2.py"
CERT_FILE = "devsystem/wnba_pushstate_repair_v1_step2_idempotent_query_cert.py"
PLAN_FILE = "devsystem/runless_proof_plans/wnba-pushstate-repair-v1-step2-idempotent-query.json"
LEDGER_FILE = "devsystem/task_ledgers/wnba-pushstate-repair-v1-step2-idempotent-query.json"
STEP2_ARTIFACTS = (OWNER_FILE, TEST_FILE, CERT_FILE, PLAN_FILE, LEDGER_FILE)


class _CountingQueryParams(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.write_count = 0

    def __setitem__(self, key, value):
        self.write_count += 1
        return super().__setitem__(key, value)


def _read_text(client, path: str, ref: str) -> str:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode()


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _verify_identity(client) -> dict[str, str]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}")
    if str(pr.get("state")) != "open":
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_PR_NOT_OPEN")
    if str(((pr.get("head") or {}).get("sha") or "")) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_HEAD_DRIFT")
    base = pr.get("base") or {}
    if str(base.get("ref") or "") != "main" or str(base.get("sha") or "") != BASE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_BASE_DRIFT")
    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100")
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    if changed != tuple(sorted(STEP2_ARTIFACTS)):
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_SCOPE_DRIFT:" + ",".join(changed))
    blobs = client.tree_blobs(CANDIDATE_SHA)
    artifact_map = {path: str(blobs.get(path) or "") for path in STEP2_ARTIFACTS}
    if any(len(value) != 40 for value in artifact_map.values()):
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_ARTIFACT_IDENTITY_MISSING")
    return artifact_map


def _execute_candidate_behavior(source: str) -> dict[str, int]:
    fake_st = ModuleType("streamlit")
    fake_st.session_state = {}
    fake_st.query_params = _CountingQueryParams({"ks_jump_sport": "WNBA", "ks_jump_market": "PRA"})
    fake_st.cache_data = lambda *args, **kwargs: (lambda fn: fn)
    fake_st.markdown = lambda *args, **kwargs: None

    nav = ModuleType("wnba_pra_navigation_v2_step1")
    nav.PAGE_SLATE = "slate"
    nav.PAGE_GAME = "game"
    nav.PAGE_PLAYER = "player"
    nav.current_state = lambda: SimpleNamespace(page=nav.PAGE_GAME)
    nav._write_query = lambda state: None

    replacements = {
        "streamlit": fake_st,
        "wnba_pra_navigation_v2_step1": nav,
    }
    for name in (
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity",
        "wnba_pra_game_center_v2_step3",
        "wnba_pra_player_intelligence_v2_step4",
        "wnba_pra_performance_v2_step5",
        "wnba_pra_repair_v1_step3_data",
        "wnba_pra_slate_v2_step2",
    ):
        replacements[name] = ModuleType(name)

    prior = {name: sys.modules.get(name) for name in replacements}
    try:
        for name, module in replacements.items():
            sys.modules[name] = module
        candidate = ModuleType("wnba_pushstate_step2_candidate")
        candidate.__file__ = OWNER_FILE
        exec(compile(source, OWNER_FILE, "exec"), candidate.__dict__)

        game = SimpleNamespace(page=nav.PAGE_GAME)
        for _ in range(150):
            candidate._pin_deep_wnba_shell_route(game)
        redundant = int(fake_st.query_params.write_count)

        fake_st.query_params = _CountingQueryParams()
        player = SimpleNamespace(page=nav.PAGE_PLAYER)
        candidate._pin_deep_wnba_shell_route(player)
        first = int(fake_st.query_params.write_count)
        candidate._pin_deep_wnba_shell_route(player)
        second = int(fake_st.query_params.write_count)

        if redundant != 0 or first != 2 or second != 2:
            raise RuntimeError(
                f"WNBA_PUSHSTATE_STEP2_BEHAVIOR_FAILED:redundant={redundant},first={first},second={second}"
            )
        if dict(fake_st.query_params) != {"ks_jump_sport": "WNBA", "ks_jump_market": "PRA"}:
            raise RuntimeError("WNBA_PUSHSTATE_STEP2_ROUTE_HANDOFF_FAILED")
        return {"redundant_150": redundant, "first_missing": first, "second_rerun_total": second}
    finally:
        for name, old in prior.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def publish_candidate_gate(client) -> dict[str, Any]:
    artifact_map = _verify_identity(client)
    owner_source = _read_text(client, OWNER_FILE, CANDIDATE_SHA)
    test_source = _read_text(client, TEST_FILE, CANDIDATE_SHA)
    cert_source = _read_text(client, CERT_FILE, CANDIDATE_SHA)
    plan = json.loads(_read_text(client, PLAN_FILE, CANDIDATE_SHA))
    ledger = json.loads(_read_text(client, LEDGER_FILE, CANDIDATE_SHA))
    compile(test_source, TEST_FILE, "exec")
    compile(cert_source, CERT_FILE, "exec")
    behavior = _execute_candidate_behavior(owner_source)

    if plan.get("freeze_token") != "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN":
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_PLAN_DRIFT")
    if ledger.get("green_plus_frozen_claimed") is not False:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_PREMATURE_GREEN_CLAIM")

    evidence = {
        "behavior": behavior,
        "pr": PR_NUMBER,
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "scope_count": len(STEP2_ARTIFACTS),
        "github_actions_fallback": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step2-{CANDIDATE_SHA[:16]}",
        task_id="wnba-pushstate-repair-v1-step2-idempotent-query",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step2",
        step="2/4-candidate-certification",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifact_map,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "pr_number": PR_NUMBER,
            "proof_authority": "Runless Proof Plane",
            "proof_mode": "in-process-candidate-runtime-behavior",
        },
        registry_before={"step1": "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN", "mode": "read-only"},
        registry_after={"step1": "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN", "mode": "read-only"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": check.get("id"),
        "receipt_digest": receipt["digest"],
        **behavior,
    }


def install_startup_gate(app):
    app.state.wnba_pushstate_step2_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _publish_wnba_pushstate_step2_gate():
        try:
            app.state.wnba_pushstate_step2_gate = publish_candidate_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step2_gate = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
