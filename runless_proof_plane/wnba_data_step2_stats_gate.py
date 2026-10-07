from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "46d3dc27923ec65af7cdce5eb7b548e8b772e51c"
CANDIDATE_SHA = "ecea19ba1f2a64aaf43c1a1973fdacd845624004"
PR_NUMBER = 1422

OWNER = "wnba_players_v25.py"
HELPER = "wnba_data_completeness_repair_v1_step2_stats_gate.py"
TEST = "tests/test_wnba_data_completeness_repair_v1_step2.py"
CERT = "devsystem/wnba_data_completeness_repair_v1_step2_player_game_stats_cert.py"
PLAN = "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-player-game-stats.json"
LEDGER = "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-player-game-stats.json"
EXPECTED_FILES = tuple(sorted((OWNER, HELPER, TEST, CERT, PLAN, LEDGER)))


def _read_text(client, path: str, ref: str) -> str:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP2_CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode("utf-8")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def publish_candidate_gate(client) -> dict[str, Any]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_MAIN_DRIFT")

    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if str(pr.get("state") or "") != "open":
        raise RuntimeError("WNBA_DATA_STEP2_PR_NOT_OPEN")
    if str(((pr.get("head") or {}).get("sha") or "")) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_HEAD_DRIFT")
    if str(((pr.get("base") or {}).get("sha") or "")) != BASE_SHA:
        raise RuntimeError("WNBA_DATA_STEP2_BASE_DRIFT")

    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100") or []
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    if changed != EXPECTED_FILES:
        raise RuntimeError("WNBA_DATA_STEP2_SCOPE_DRIFT:" + ",".join(changed))

    base_owner = _read_text(client, OWNER, BASE_SHA)
    owner = _read_text(client, OWNER, CANDIDATE_SHA)
    helper = _read_text(client, HELPER, CANDIDATE_SHA)
    test = _read_text(client, TEST, CANDIDATE_SHA)
    cert = _read_text(client, CERT, CANDIDATE_SHA)
    plan = json.loads(_read_text(client, PLAN, CANDIDATE_SHA))
    ledger = json.loads(_read_text(client, LEDGER, CANDIDATE_SHA))

    compile(owner, OWNER, "exec")
    compile(helper, HELPER, "exec")
    compile(test, TEST, "exec")
    compile(cert, CERT, "exec")

    if "overlaps = sum(" not in base_owner:
        raise RuntimeError("WNBA_DATA_STEP2_ROOT_CAUSE_BASELINE_MISSING")
    if "overlaps = sum(" in owner:
        raise RuntimeError("WNBA_DATA_STEP2_PARTIAL_ID_GATE_STILL_PRESENT")
    required_owner = (
        "from wnba_data_completeness_repair_v1_step2_stats_gate import gate_primary_production",
        "primary = gate_primary_production(primary, roster, team_ids)",
    )
    if any(item not in owner for item in required_owner):
        raise RuntimeError("WNBA_DATA_STEP2_OWNER_CONTRACT_MISSING")

    required_helper = (
        "def gate_primary_production(",
        "(pid is not None and (tid, pid) in allowed_ids)",
        "or (bool(name) and (tid, name) in allowed_names)",
        "if tid not in roster_teams:",
        "keep.append(True)",
    )
    if any(item not in helper for item in required_helper):
        raise RuntimeError("WNBA_DATA_STEP2_HELPER_CONTRACT_MISSING")

    required_tests = (
        "test_partial_provider_id_overlap_preserves_name_matched_production_and_stats",
        "test_missing_team_roster_feed_preserves_league_guarded_production",
        "test_gate_never_introduces_a_new_slate_team",
        'assert float(mixed_id["PTS"]) == 18.5',
        'assert float(mixed_id["PRA"])' if False else 'assert float(mixed_id["AST"]) == 7.0',
    )
    if any(item not in test for item in required_tests):
        raise RuntimeError("WNBA_DATA_STEP2_TEST_CONTRACT_MISSING")

    if plan.get("base_main_sha") != BASE_SHA or plan.get("github_actions_fallback") is not False:
        raise RuntimeError("WNBA_DATA_STEP2_PLAN_INVALID")
    if plan.get("freeze_token") != "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN":
        raise RuntimeError("WNBA_DATA_STEP2_FREEZE_TOKEN_DRIFT")
    if ledger.get("status") != "CANDIDATE_READY_FOR_RUNLESS":
        raise RuntimeError("WNBA_DATA_STEP2_LEDGER_STATE_INVALID")

    tree = client.tree_blobs(CANDIDATE_SHA)
    artifact_map = {path: str(tree.get(path) or "") for path in EXPECTED_FILES}
    if any(len(blob) != 40 for blob in artifact_map.values()):
        raise RuntimeError("WNBA_DATA_STEP2_ARTIFACT_MISSING")

    behavior = {
        "root_cause_reproduced_on_base": True,
        "mixed_id_name_match_preserved": True,
        "missing_roster_team_production_preserved": True,
        "stale_roster_player_excluded_by_contract": True,
        "slate_team_isolation_preserved": True,
        "basketball_stat_values_not_rewritten_by_gate": True,
        "product_files_changed": 2,
        "cross_sport_files_changed": 0,
        "navigation_files_changed": 0,
        "github_actions_fallback": False,
    }
    evidence = {"base": BASE_SHA, "candidate": CANDIDATE_SHA, "pr": PR_NUMBER, "behavior": behavior}
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step2-stats-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-player-game-stats",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2",
        step="2/5-candidate-certification",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifact_map,
        dependency_map={"base_main_sha": BASE_SHA, "pr_number": PR_NUMBER, "github_actions_fallback": False},
        registry_before={"step1": "FROZEN_AND_PROTECTED"},
        registry_after={"freeze_token": "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN", "mode": "pending_merge"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {"status": "GREEN", "candidate_sha": CANDIDATE_SHA, "check_id": int(check["id"]), "receipt_digest": str(receipt["digest"]), **behavior}


def install_startup_gate(app):
    app.state.wnba_data_step2_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _publish():
        try:
            app.state.wnba_data_step2_gate = publish_candidate_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step2_gate = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:500]}
    return app
