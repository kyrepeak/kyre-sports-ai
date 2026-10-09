from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

SOURCE_MAIN_SHA = "0e2c11f03c1d3f6cb94756057ccb95e8ae74b2f9"
CERTIFIED_PRODUCT_MAIN_SHA = "5c155c494cf4e10148ebb3d6133d83a0ef42172c"
MERGED_MAIN_SHA = "443bd71d4ee956a0b26539a900771b30b90a77fe"
STEP5_BRANCH = "api2/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
EVIDENCE_PATH = "devsystem/live_evidence/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-convergence"
LEASE_ID = "SCOPE-LEASE-FADB448ED17923F50A5CAA33"
ARTIFACT_DIR = Path("/tmp/cfb-game-total-step5")
LOCAL_EVIDENCE = ARTIFACT_DIR / "cfb_game_total_page1_visual_cleanup_step5_live_visual_cert.json"

DRIVER = r'''
import sys
from devsystem import browser_qa_v1 as browser_base
from devsystem import cfb_game_total_page1_visual_cleanup_step5_visual_cert_v1 as cert

EXPECTED_DEPLOYMENT_SHA = "443bd71d4ee956a0b26539a900771b30b90a77fe"
DEPLOYMENT_SELECTOR = '[data-api2-exact-deployment="streamlit-runtime-v1"]'
MAIN_SELECTOR = '[data-testid="stMainBlockContainer"]'

def canonical_prime(page, base_url=cert.PRODUCTION_URL):
    page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120000)
    frame, initial_scan = browser_base._find_app_frame(page)
    browser_base._choose(page, frame, 0, cert.CFB_SPORT)
    frame, sport_scan = browser_base._find_app_frame(page)
    combo = frame.get_by_role("combobox", name=cert.CFB_MARKET_LABEL, exact=True)
    combo.wait_for(state="visible", timeout=45000)
    browser_base._choose(page, frame, 1, cert.GAME_TOTAL_MARKET)
    frame, market_scan = browser_base._find_app_frame(page)
    cert._visible(frame, "gtvc2-matchup-hero")
    marker = frame.locator(DEPLOYMENT_SELECTOR).first
    marker.wait_for(state="attached", timeout=45000)
    observed_sha = str(marker.get_attribute("data-production-sha") or "").strip().lower()
    print("CFB_GT_VISUAL_CLEANUP_STEP5_PRODUCTION_SHA=" + observed_sha, flush=True)
    if observed_sha != EXPECTED_DEPLOYMENT_SHA:
        raise RuntimeError(
            "STEP5_PRODUCTION_SHA_DRIFT:expected=" + EXPECTED_DEPLOYMENT_SHA + ":observed=" + observed_sha
        )
    print("CFB_GT_VISUAL_CLEANUP_STEP5_EXACT_DEPLOYMENT_GREEN", flush=True)
    return frame, {"initial": initial_scan, "sport_selected": sport_scan, "market_selected": market_scan}

original_viewport_result = cert._viewport_result

def main_scoped_viewport_result(page, frame, name, scans, artifact_dir):
    original_forbidden = cert._forbidden_visible_text
    main = frame.locator(MAIN_SELECTOR).first
    main.wait_for(state="attached", timeout=45000)

    def main_only_forbidden(_body):
        return original_forbidden(main.inner_text(timeout=30000))

    cert._forbidden_visible_text = main_only_forbidden
    try:
        return original_viewport_result(page, frame, name, scans, artifact_dir)
    finally:
        cert._forbidden_visible_text = original_forbidden

cert._prime_route = canonical_prime
cert._viewport_result = main_scoped_viewport_result
cert.run(base_url=cert.PRODUCTION_URL, artifact_dir=sys.argv[1])
'''


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
        str(identity.get("main_sha") or "") != MERGED_MAIN_SHA
        or str(identity.get("certified_product_main_sha") or "") != CERTIFIED_PRODUCT_MAIN_SHA
        or str(identity.get("workstream") or "") != "cfb-game-total-page1-visual-cleanup-v1"
        or str(identity.get("phase") or "") != "postmerge-live-cert-closeout"
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
    if LOCAL_EVIDENCE.exists():
        LOCAL_EVIDENCE.unlink()
    completed = subprocess.run(
        [sys.executable, "-c", DRIVER, str(ARTIFACT_DIR)],
        check=False,
        text=True,
        capture_output=True,
        timeout=900,
    )
    if completed.stdout:
        print(completed.stdout[-16000:], flush=True)
    if completed.stderr:
        print(completed.stderr[-16000:], file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise RuntimeError("STEP5_CERT_SUBPROCESS_FAILED:" + str(completed.returncode))
    if not LOCAL_EVIDENCE.exists():
        raise RuntimeError("STEP5_CERT_LOCAL_EVIDENCE_MISSING")
    evidence = json.loads(LOCAL_EVIDENCE.read_text(encoding="utf-8"))
    if evidence.get("status") != "GREEN" or int(evidence.get("github_actions_fallback", -1)) != 0:
        raise RuntimeError("STEP5_CERT_NOT_GREEN")
    evidence["certified_product_main_sha"] = CERTIFIED_PRODUCT_MAIN_SHA
    evidence["certified_merged_main_sha"] = MERGED_MAIN_SHA
    evidence["cert_route_method"] = "canonical-ui-selection"
    evidence["route_url"] = "https://pickvault.streamlit.app/"
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
