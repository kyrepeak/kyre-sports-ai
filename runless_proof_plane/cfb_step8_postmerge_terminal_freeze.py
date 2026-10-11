from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    authorize_scope,
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_state,
)

from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "e6490b5e52a32c16b283cd676fb0c51c02e2b7df"
RECOVERY_HEAD = "b8a693bdce3f0e17a602e67fe89a60f63457b15a"
PRE_RECOVERY_MAIN = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
REDEPLOY_THAW = "THAW-CFB-GT-STEP8-STREAMLIT-REDEPLOY-R1"
REQUIREMENTS = "requirements.txt"
REQUIREMENTS_FROM = "1022d95a71b3c04aa5310b5057de74978e4cffa4"
REQUIREMENTS_TO = "7b2e379fc2f519c9bb8700a14b33b70d4eb0f581"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
RUNLESS_APP_ID = 5204253
RUNLESS_CHECK = "runless-final-gate"
PROOF_LEASE_ID = "SCOPE-LEASE-6E91B4C27A53D8F0B21C44E7"
PROOF_LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-deploy-refresh-proof-r2"
CLOSEOUT_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-postmerge-terminal-freeze"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"

FINAL_ARTIFACTS = (
    "cfb_game_total_clean_page_v43.py",
    "devsystem/cfb_game_total_mobile_production_step8_runless_v1.py",
    "devsystem/cfb_game_total_mobile_production_step8_v1.py",
    "devsystem/production_targets_v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-premerge-v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-v1.json",
    "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-v1.json",
    "tests/test_cfb_game_total_mobile_production_step8_v1.py",
    "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
    "requirements.txt",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-deploy-refresh-v1.json",
    "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-deploy-refresh-v1.json",
)


class Step8PostmergeFreezeFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise Step8PostmergeFreezeFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _json_text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _run(cmd, *, cwd: Path, timeout: int):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def _ensure_chromium(root: Path) -> None:
    probe = _run(
        [
            sys.executable,
            "-c",
            "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True,args=['--no-sandbox']); b.close(); p.stop(); print('READY')",
        ],
        cwd=root,
        timeout=45,
    )
    if probe.returncode == 0:
        return
    install = _run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=root, timeout=360)
    if install.returncode != 0:
        raise Step8PostmergeFreezeFailure("CHROMIUM_INSTALL_FAILED:" + ((install.stdout or "") + "\n" + (install.stderr or ""))[-8000:])


def _public_proof() -> dict:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-postmerge-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "main", REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            raise Step8PostmergeFreezeFailure("CLONE_FAILED:" + (clone.stderr or clone.stdout)[-5000:])
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != MAIN_SHA:
            raise Step8PostmergeFreezeFailure(f"MAIN_DRIFT:{head}")

        tests = _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_cfb_game_total_mobile_production_step8_v1.py",
                "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
            ],
            cwd=root,
            timeout=300,
        )
        if tests.returncode != 0:
            raise Step8PostmergeFreezeFailure("POSTMERGE_TEST_RED:" + ((tests.stdout or "") + "\n" + (tests.stderr or ""))[-12000:])

        _ensure_chromium(root)
        code = r'''
import json,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from playwright.sync_api import sync_playwright
from devsystem import cfb_game_total_mobile_production_step8_v1 as m

today = datetime.now(ZoneInfo(m.PHOENIX_TZ)).date()
first = today + timedelta(days=((5 - today.weekday()) % 7 or 7))
upcoming = None
for week in range(4):
    day = first + timedelta(days=7*week)
    try:
        r = requests.get(m.RENDER_URL.rstrip('/') + '/api/v1/cfb/selector/verified-games', params={'game_date': day.isoformat()}, timeout=20)
        payload = r.json() if r.ok else {}
    except Exception:
        payload = {}
    games = payload.get('games') if isinstance(payload, dict) else None
    if isinstance(games, list) and games:
        upcoming = day
        break
if upcoming is None:
    upcoming = first
m.HANDOFF_CERT_DAY = upcoming.isoformat()
artifacts = Path('artifacts/cfb-game-total-step8-postmerge')
artifacts.mkdir(parents=True, exist_ok=True)
identity = m.verify_render_identity()
rows = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--no-sandbox'])
    try:
        ready = False
        readiness = []
        probe = browser.new_page(viewport={'width':390,'height':844})
        try:
            for attempt in range(1,9):
                probe.goto(m.page1_route(m.PRODUCTION_URL), wait_until='domcontentloaded', timeout=120000)
                time.sleep(2)
                url_events = {m._event_from_url(probe.url)}
                for f in probe.frames:
                    url_events.add(m._event_from_url(str(getattr(f,'url','') or '')))
                url_events.discard('')
                try:
                    frame, scans = m._find_cfb_frame(
                        probe,
                        required_markers=m.PAGE1_FRAME_MARKERS,
                        required_testids=(m.PHOENIX_DAY_TESTID,m.PAGE1_TESTID),
                        timeout_seconds=12.0,
                    )
                    fresh = not url_events
                except Exception as exc:
                    scans = []
                    fresh = False
                    err = type(exc).__name__
                readiness.append({'attempt':attempt,'stale_event_ids':sorted(url_events),'fresh':fresh})
                if fresh:
                    ready = True
                    break
                time.sleep(10)
        finally:
            probe.close()
        if not ready:
            raise RuntimeError('PICKVAULT_DID_NOT_CONVERGE:' + json.dumps(readiness,sort_keys=True))

        for name, viewport in m.VIEWPORTS.items():
            page = browser.new_page(viewport=viewport)
            try:
                page1, selected_url, event_id = m._page1_result(page,name,artifacts,m.PRODUCTION_URL)
                preselect_events = {m._event_from_url(page.url)}
                for f in page.frames:
                    preselect_events.add(m._event_from_url(str(getattr(f,'url','') or '')))
                preselect_events.discard('')
                if preselect_events:
                    raise RuntimeError('PAGE1_AUTO_EVENT_PRESENT:' + name + ':' + json.dumps(sorted(preselect_events)))
                page2 = m._page2_result(page,name,selected_url,event_id,artifacts)
                if page1.get('horizontal_overflow') is not False or page2.get('horizontal_overflow') is not False:
                    raise RuntimeError('OVERFLOW:' + name)
                if page2.get('all_required_visible') is not True:
                    raise RuntimeError('PAGE2_NOT_VISIBLE:' + name)
                if set(page2.get('observed_event_ids') or []) != {event_id}:
                    raise RuntimeError('EVENT_DRIFT:' + name)
                rows[name] = {
                    'event_id':event_id,
                    'page1_overflow':page1.get('horizontal_overflow'),
                    'page2_overflow':page2.get('horizontal_overflow'),
                    'page2_visible':page2.get('all_required_visible'),
                }
            finally:
                page.close()
    finally:
        browser.close()
print('CFB_STEP8_POSTMERGE_PUBLIC=' + json.dumps({
    'status':'PUBLIC_GREEN',
    'main_sha':'e6490b5e52a32c16b283cd676fb0c51c02e2b7df',
    'phoenix_today':today.isoformat(),
    'upcoming_slate_day':upcoming.isoformat(),
    'render_identity':identity,
    'viewports':rows,
    'github_actions_fallback':0,
},sort_keys=True))
'''
        proof = _run([sys.executable, "-c", code], cwd=root, timeout=420)
        output = (proof.stdout or "") + "\n" + (proof.stderr or "")
        if proof.returncode != 0:
            raise Step8PostmergeFreezeFailure("POSTMERGE_PUBLIC_RED:" + output[-16000:])
        marker = "CFB_STEP8_POSTMERGE_PUBLIC="
        receipts = [line for line in (proof.stdout or "").splitlines() if line.startswith(marker)]
        if not receipts:
            raise Step8PostmergeFreezeFailure("POSTMERGE_PUBLIC_RECEIPT_MISSING:" + output[-8000:])
        receipt = json.loads(receipts[-1][len(marker):])
        if receipt.get("status") != "PUBLIC_GREEN" or receipt.get("main_sha") != MAIN_SHA:
            raise Step8PostmergeFreezeFailure("POSTMERGE_PUBLIC_RECEIPT_REJECTED")
        receipt["static_tests"] = (tests.stdout or "").strip()[-1500:]
        return receipt


def _verify_merge_and_runless(client) -> dict:
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8PostmergeFreezeFailure("MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(row.get("sha") or "") for row in commit.get("parents", [])}
    if parents != {PRE_RECOVERY_MAIN, RECOVERY_HEAD}:
        raise Step8PostmergeFreezeFailure("MERGE_LINEAGE_DRIFT")
    checks = client.request("GET", f"/commits/{RECOVERY_HEAD}/check-runs") or {}
    matches = []
    for row in checks.get("check_runs", []):
        app = row.get("app") or {}
        if row.get("name") == RUNLESS_CHECK and int(app.get("id") or 0) == RUNLESS_APP_ID and row.get("status") == "completed" and row.get("conclusion") == "success":
            matches.append(row)
    if not matches:
        raise Step8PostmergeFreezeFailure("RUNLESS_MERGE_AUTHORITY_MISSING")
    newest = sorted(matches, key=lambda row: str(row.get("completed_at") or ""))[-1]
    return {
        "check_id": newest.get("id"),
        "receipt_summary": str((newest.get("output") or {}).get("summary") or ""),
        "completed_at": newest.get("completed_at"),
    }


def _lease_for_closeout(client, registry_hash: str) -> tuple[str, dict]:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    working = state
    proof_holder = next((h for h in working.get("holders", []) if h.get("lease_id") == PROOF_LEASE_ID and h.get("owner_id") == PROOF_LEASE_OWNER), None)
    if proof_holder is not None:
        released = release_scope(
            working,
            owner_id=PROOF_LEASE_OWNER,
            lease_id=PROOF_LEASE_ID,
            expected_revision=working["revision"],
            expected_state_hash=working["state_hash"],
        )
        if released["result"].get("allowed") is not True:
            raise Step8PostmergeFreezeFailure("PROOF_LEASE_RELEASE_FAILED")
        working = released["state"]

    scope = build_scope(
        write_paths=[REGISTRY_PATH],
        dependency_tokens=["cfb:game-total:step8", "registry:step8-final-freeze"],
        shared_resources=["ref:monster-frozen-artifact-registry"],
        resource_identity={"main_sha": MAIN_SHA, "registry_state_hash": registry_hash},
        exclusive=False,
    )
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    claimed = claim_scope(
        working,
        owner_id=CLOSEOUT_OWNER,
        now_utc=now,
        scope=scope,
        expected_revision=working["revision"],
        expected_state_hash=working["state_hash"],
        ttl_seconds=900,
    )
    if claimed["result"].get("allowed") is not True:
        raise Step8PostmergeFreezeFailure("CLOSEOUT_LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(
        LEASE_PATH,
        _json_text(claimed["state"]),
        LEASE_BRANCH,
        "lease: handoff CFB Step8 proof to terminal freeze",
        raw["sha"],
    )
    return str(claimed["result"]["lease_id"]), claimed["state"]


def _freeze(app, public_receipt: dict, runless_receipt: dict) -> dict:
    client = app.state.github_client
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    main_tree = client.tree_blobs(MAIN_SHA)
    if main_tree.get(REQUIREMENTS) != REQUIREMENTS_TO:
        raise Step8PostmergeFreezeFailure("REQUIREMENTS_MAIN_BLOB_DRIFT")
    missing = [path for path in FINAL_ARTIFACTS if path not in main_tree]
    if missing:
        raise Step8PostmergeFreezeFailure("FINAL_ARTIFACT_MISSING:" + ",".join(missing))
    artifacts = {path: main_tree[path] for path in FINAL_ARTIFACTS}

    existing = registry.get("entries", {}).get(FREEZE_TOKEN)
    exact_thaws = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == REDEPLOY_THAW]
    if existing and not exact_thaws:
        if existing.get("source_main_sha") != MAIN_SHA or existing.get("artifacts") != artifacts:
            raise Step8PostmergeFreezeFailure("EXISTING_FREEZE_TOKEN_DRIFT")
        return {
            "status": "GREEN_FROZEN",
            "already_frozen": True,
            "revision": registry["revision"],
            "state_hash": registry["state_hash"],
            "freeze_token": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "public_proof": public_receipt,
            "runless": runless_receipt,
            "github_actions_fallback": 0,
        }

    lease_id, lease_state = _lease_for_closeout(client, str(registry["state_hash"]))
    gate = authorize_scope(
        lease_state,
        owner_id=CLOSEOUT_OWNER,
        lease_id=lease_id,
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        action_scope={
            "write_paths": [REGISTRY_PATH],
            "dependency_tokens": ["cfb:game-total:step8", "registry:step8-final-freeze"],
            "shared_resources": ["ref:monster-frozen-artifact-registry"],
            "resource_identity": {},
            "exclusive": False,
        },
    )
    if gate.get("allowed") is not True:
        raise Step8PostmergeFreezeFailure("CLOSEOUT_SCOPE_NOT_AUTHORIZED")

    current = backend.read_registry()
    if current["revision"] != registry["revision"] or current["state_hash"] != registry["state_hash"]:
        raise Step8PostmergeFreezeFailure("REGISTRY_CHANGED_AFTER_LEASE")
    unrelated_before = [deepcopy(g) for g in current.get("active_thaws", []) if g.get("thaw_id") != REDEPLOY_THAW]
    baseline = validate_registry(current)["artifacts"].get(REQUIREMENTS)

    if baseline == REQUIREMENTS_FROM:
        if len(exact_thaws) != 1:
            raise Step8PostmergeFreezeFailure("REDEPLOY_THAW_NOT_UNIQUE")
        grant = exact_thaws[0]
        if str(grant.get("target_head_sha") or "") != RECOVERY_HEAD or grant.get("files") != {REQUIREMENTS: {"from_blob": REQUIREMENTS_FROM, "to_blob": REQUIREMENTS_TO}}:
            raise Step8PostmergeFreezeFailure("REDEPLOY_THAW_IDENTITY_DRIFT")
        planned = plan_baseline_forward_port(
            current,
            updates={REQUIREMENTS: {"from_blob": REQUIREMENTS_FROM, "to_blob": REQUIREMENTS_TO}},
            source_main_sha=MAIN_SHA,
        )
        if set(planned.get("retired_empty_thaw_grants") or []) != {REDEPLOY_THAW}:
            raise Step8PostmergeFreezeFailure("REDEPLOY_THAW_RETIREMENT_DRIFT")
        next_registry = deepcopy(planned["registry"])
    elif baseline == REQUIREMENTS_TO and not exact_thaws:
        next_registry = deepcopy(current)
        next_registry["revision"] = int(current["revision"]) + 1
        next_registry["source_main_sha"] = MAIN_SHA
    else:
        raise Step8PostmergeFreezeFailure("REQUIREMENTS_REGISTRY_STATE_DRIFT")

    if next_registry.get("active_thaws", []) != unrelated_before:
        raise Step8PostmergeFreezeFailure("UNRELATED_THAW_MUTATION")

    flattened = {}
    for token, entry in next_registry.get("entries", {}).items():
        for path, blob in (entry.get("artifacts") or {}).items():
            flattened.setdefault(path, set()).add(str(blob))
    conflicts = sorted(path for path, blob in artifacts.items() if path in flattened and flattened[path] != {blob})
    if conflicts:
        raise Step8PostmergeFreezeFailure("FINAL_FREEZE_BASELINE_CONFLICT:" + ",".join(conflicts))

    next_registry["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(artifacts.items())),
    }
    next_registry["source_main_sha"] = MAIN_SHA
    next_registry["state_hash"] = _hash(_payload_without_hash(next_registry))
    validate_registry(next_registry)
    client.update_content(
        REGISTRY_PATH,
        _json_text(next_registry),
        backend.branch,
        "registry: freeze CFB Game Total native rebuild Step 8",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if readback != next_registry:
        raise Step8PostmergeFreezeFailure("REGISTRY_READBACK_MISMATCH")
    if any(g.get("thaw_id") == REDEPLOY_THAW for g in readback.get("active_thaws", [])):
        raise Step8PostmergeFreezeFailure("REDEPLOY_THAW_STILL_ACTIVE")
    entry = readback.get("entries", {}).get(FREEZE_TOKEN)
    if not entry or entry.get("source_main_sha") != MAIN_SHA or entry.get("artifacts") != artifacts:
        raise Step8PostmergeFreezeFailure("FREEZE_ENTRY_READBACK_MISMATCH")

    lease_raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    lease_current = validate_scope_state(_decode(lease_raw))
    released = release_scope(
        lease_current,
        owner_id=CLOSEOUT_OWNER,
        lease_id=lease_id,
        expected_revision=lease_current["revision"],
        expected_state_hash=lease_current["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise Step8PostmergeFreezeFailure("CLOSEOUT_LEASE_RELEASE_FAILED")
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Step8 terminal freeze",
        lease_raw["sha"],
    )
    lease_readback = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    if any(h.get("lease_id") == lease_id for h in lease_readback.get("holders", [])):
        raise Step8PostmergeFreezeFailure("CLOSEOUT_LEASE_STILL_HELD")

    return {
        "status": "GREEN_FROZEN",
        "already_frozen": False,
        "revision": readback["revision"],
        "state_hash": readback["state_hash"],
        "freeze_token": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "retired_thaw": REDEPLOY_THAW,
        "remaining_thaw_ids": sorted(str(g.get("thaw_id") or "") for g in readback.get("active_thaws", [])),
        "artifact_count": len(artifacts),
        "lease_released": True,
        "public_proof": public_receipt,
        "runless": runless_receipt,
        "github_actions_fallback": 0,
    }


def execute(app) -> dict:
    runless_receipt = _verify_merge_and_runless(app.state.github_client)
    public_receipt = _public_proof()
    return _freeze(app, public_receipt, runless_receipt)


def install_startup(app):
    app.state.cfb_step8_postmerge_terminal_freeze = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_step8_postmerge_terminal_freeze = execute(app)
            except Exception as exc:
                app.state.cfb_step8_postmerge_terminal_freeze = {
                    "status": "FAIL",
                    "error": type(exc).__name__,
                    "detail": str(exc)[:20000],
                }
            print("CFB_STEP8_POSTMERGE_TERMINAL_FREEZE=" + json.dumps(app.state.cfb_step8_postmerge_terminal_freeze, sort_keys=True, default=str), flush=True)
        threading.Thread(target=worker, daemon=True, name="cfb-step8-postmerge-terminal-freeze").start()

    return app
