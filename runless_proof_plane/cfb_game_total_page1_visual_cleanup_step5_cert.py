from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

SOURCE_MAIN_SHA = "0e2c11f03c1d3f6cb94756057ccb95e8ae74b2f9"
MERGED_MAIN_SHA = "5c155c494cf4e10148ebb3d6133d83a0ef42172c"
STEP5_BRANCH = "api2/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
EVIDENCE_PATH = "devsystem/live_evidence/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-convergence"
LEASE_ID = "SCOPE-LEASE-B255E6B5C7A6A1D05F969372"
ARTIFACT_DIR = Path("/tmp/cfb-game-total-step5")
LOCAL_EVIDENCE = ARTIFACT_DIR / "cfb_game_total_page1_visual_cleanup_step5_live_visual_cert.json"


def _decode(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _holder(client):
    state = validate_scope_lease_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_CERT_LEASE"))
    now = datetime.now(timezone.utc)
    matches = [
        item for item in state.get("holders", [])
        if item.get("owner_id") == LEASE_OWNER
        and item.get("lease_id") == LEASE_ID
        and now < _utc(item["expires_at_utc"])
    ]
    if len(matches) != 1:
        return None
    holder = matches[0]
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    if (
        str(identity.get("main_sha") or "") != SOURCE_MAIN_SHA
        or str(identity.get("workstream") or "") != "cfb-game-total-page1-visual-cleanup-v1"
    ):
        raise RuntimeError("STEP5_CERT_LEASE_IDENTITY_DRIFT")
    return holder


def _existing_evidence(client):
    raw = client.content(EVIDENCE_PATH, ref=STEP5_BRANCH, allow_404=True)
    if raw is None:
        return None
    return _decode(raw, "STEP5_CERT_EXISTING_EVIDENCE")


def should_run(client):
    try:
        return _holder(client) is not None and client.branch_sha("main") == MERGED_MAIN_SHA and _existing_evidence(client) is None
    except Exception:
        return False


def _persist_evidence(client, evidence):
    text = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    raw = client.content(EVIDENCE_PATH, ref=STEP5_BRANCH, allow_404=True)
    if raw is None:
        client.put_content(EVIDENCE_PATH, text, STEP5_BRANCH, "CFB Game Total Step5: persist live visual evidence")
        return
    existing = _decode(raw, "STEP5_CERT_EXISTING_EVIDENCE")
    if existing != evidence:
        raise RuntimeError("STEP5_CERT_EVIDENCE_CONFLICT")


def execute(app):
    client = app.state.github_client
    if _holder(client) is None:
        raise RuntimeError("STEP5_CERT_LEASE_NOT_LIVE")
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("STEP5_CERT_MAIN_DRIFT")
    existing = _existing_evidence(client)
    if existing is not None:
        return {"status": "GREEN", "decision": "STEP5_CERT_ALREADY_TERMINAL", "evidence": existing, "github_actions_fallback": 0}

    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, timeout=300)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "devsystem.cfb_game_total_page1_visual_cleanup_step5_visual_cert_v1",
            "--base-url",
            "https://pickvault.streamlit.app",
            "--artifact-dir",
            str(ARTIFACT_DIR),
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=600,
    )
    if completed.stdout:
        print(completed.stdout[-12000:], flush=True)
    if completed.stderr:
        print(completed.stderr[-12000:], file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise RuntimeError("STEP5_CERT_SUBPROCESS_FAILED:" + str(completed.returncode))
    if not LOCAL_EVIDENCE.exists():
        raise RuntimeError("STEP5_CERT_LOCAL_EVIDENCE_MISSING")
    evidence = json.loads(LOCAL_EVIDENCE.read_text(encoding="utf-8"))
    if evidence.get("status") != "GREEN" or int(evidence.get("github_actions_fallback", -1)) != 0:
        raise RuntimeError("STEP5_CERT_NOT_GREEN")
    evidence["certified_merged_main_sha"] = MERGED_MAIN_SHA
    _persist_evidence(client, evidence)
    return {
        "status": "GREEN",
        "decision": "STEP5_LIVE_VISUAL_CERT_GREEN",
        "evidence": evidence,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step5_cert = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step5_cert = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step5_cert = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP5_CERT="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step5_cert, sort_keys=True),
            flush=True,
        )

    return app
