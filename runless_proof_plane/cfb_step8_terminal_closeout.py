from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
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

MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
STEP8_HEAD = "a1fbecbb5d5dd96d71ad21d4961bf8407c80be9e"
STEP8_THAW = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
V43 = "cfb_game_total_clean_page_v43.py"
V43_FROM = "ebb7bfa20489598a62891ec4e5e868fe350c8712"
V43_TO = "3a05f8f3f9d434a462da702d429e7db990c9b528"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-terminal-closeout"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"

STEP8_ARTIFACTS = (
    "cfb_game_total_clean_page_v43.py",
    "devsystem/cfb_game_total_mobile_production_step8_runless_v1.py",
    "devsystem/cfb_game_total_mobile_production_step8_v1.py",
    "devsystem/production_targets_v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-premerge-v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-v1.json",
    "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-v1.json",
    "tests/test_cfb_game_total_mobile_production_step8_v1.py",
    "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
)


class Step8TerminalCloseoutFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise Step8TerminalCloseoutFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _json_text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _run_public_proof() -> dict:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-terminal-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "main", REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            raise Step8TerminalCloseoutFailure("PUBLIC_CLONE_FAILED:" + (clone.stderr or clone.stdout)[-3000:])
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != MAIN_SHA:
            raise Step8TerminalCloseoutFailure(f"PUBLIC_MAIN_DRIFT:{head}")

        tests = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_cfb_game_total_mobile_production_step8_v1.py",
                "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=300,
        )
        if tests.returncode != 0:
            raise Step8TerminalCloseoutFailure("POSTMERGE_TEST_RED:" + ((tests.stdout or "") + "\n" + (tests.stderr or ""))[-8000:])

        install = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=360,
        )
        if install.returncode != 0:
            raise Step8TerminalCloseoutFailure("CHROMIUM_INSTALL_FAILED:" + ((install.stdout or "") + "\n" + (install.stderr or ""))[-5000:])

        code = r'''
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
from devsystem import cfb_game_total_mobile_production_step8_v1 as m

today = datetime.now(ZoneInfo(m.PHOENIX_TZ)).date()
days_until_saturday = (5 - today.weekday()) % 7
upcoming = today + timedelta(days=days_until_saturday)
m.HANDOFF_CERT_DAY = upcoming.isoformat()
identity = m.verify_render_identity()
artifacts = Path("artifacts/cfb-game-total-step8-terminal")
artifacts.mkdir(parents=True, exist_ok=True)
rows = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    try:
        for name, viewport in m.VIEWPORTS.items():
            page = browser.new_page(viewport=viewport)
            try:
                page1, selected_url, event_id = m._page1_result(page, name, artifacts, m.PRODUCTION_URL)
                page2 = m._page2_result(page, name, selected_url, event_id, artifacts)
                rows[name] = {
                    "event_id": event_id,
                    "page1_overflow": page1["horizontal_overflow"],
                    "page2_overflow": page2["horizontal_overflow"],
                    "page2_visible": page2["all_required_visible"],
                    "observed_event_ids": page2["observed_event_ids"],
                }
            finally:
                page.close()
    finally:
        browser.close()
if set(rows) != set(m.VIEWPORTS):
    raise RuntimeError("VIEWPORT_SET_DRIFT")
for name, row in rows.items():
    if row["page1_overflow"] is not False or row["page2_overflow"] is not False:
        raise RuntimeError("OVERFLOW:" + name)
    if row["page2_visible"] is not True:
        raise RuntimeError("PAGE2_NOT_VISIBLE:" + name)
    if set(row["observed_event_ids"]) != {row["event_id"]}:
        raise RuntimeError("EVENT_DRIFT:" + name)
print("CFB_STEP8_POSTMERGE_PUBLIC=" + json.dumps({
    "status": "PUBLIC_GREEN",
    "main_sha": "1b0169a8a6e644ae6971685fb50b9bd96d510106",
    "phoenix_today": today.isoformat(),
    "upcoming_slate_day": upcoming.isoformat(),
    "render_identity": identity,
    "viewports": rows,
    "github_actions_fallback": 0,
}, sort_keys=True))
'''
        proof = subprocess.run(
            [sys.executable, "-c", code],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=900,
        )
        output = (proof.stdout or "") + "\n" + (proof.stderr or "")
        if proof.returncode != 0:
            raise Step8TerminalCloseoutFailure("POSTMERGE_PUBLIC_RED:" + output[-12000:])
        marker = "CFB_STEP8_POSTMERGE_PUBLIC="
        rows = [line for line in (proof.stdout or "").splitlines() if line.startswith(marker)]
        if not rows:
            raise Step8TerminalCloseoutFailure("POSTMERGE_PUBLIC_RECEIPT_MISSING:" + output[-6000:])
        payload = json.loads(rows[-1][len(marker):])
        if payload.get("status") != "PUBLIC_GREEN" or payload.get("main_sha") != MAIN_SHA:
            raise Step8TerminalCloseoutFailure("POSTMERGE_PUBLIC_RECEIPT_REJECTED")
        return {"tests": (tests.stdout or "").strip()[-1200:], **payload}


def _freeze(app, public_receipt: dict) -> dict:
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8TerminalCloseoutFailure("MAIN_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    if main_tree.get(V43) != V43_TO:
        raise Step8TerminalCloseoutFailure("V43_MAIN_BLOB_DRIFT")
    missing = [p for p in STEP8_ARTIFACTS if p not in main_tree]
    if missing:
        raise Step8TerminalCloseoutFailure("STEP8_ARTIFACT_MISSING:" + ",".join(missing))
    artifacts = {p: main_tree[p] for p in STEP8_ARTIFACTS}

    backend = GithubRegistryBackend(client)
    first = backend.read_registry()
    existing = first.get("entries", {}).get(FREEZE_TOKEN)
    step8_grants = [g for g in first.get("active_thaws", []) if g.get("thaw_id") == STEP8_THAW]
    if existing and not step8_grants:
        if existing.get("source_main_sha") != MAIN_SHA or existing.get("artifacts") != artifacts:
            raise Step8TerminalCloseoutFailure("EXISTING_FREEZE_TOKEN_DRIFT")
        return {
            "status": "GREEN_FROZEN",
            "already_frozen": True,
            "revision": first["revision"],
            "state_hash": first["state_hash"],
            "freeze_token": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "public_proof": public_receipt,
            "github_actions_fallback": 0,
        }

    if len(step8_grants) != 1:
        raise Step8TerminalCloseoutFailure("STEP8_THAW_NOT_UNIQUE")
    grant = step8_grants[0]
    if str(grant.get("target_head_sha") or "") != STEP8_HEAD:
        raise Step8TerminalCloseoutFailure("STEP8_THAW_TARGET_DRIFT")
    if grant.get("files") != {V43: {"from_blob": V43_FROM, "to_blob": V43_TO}}:
        raise Step8TerminalCloseoutFailure("STEP8_THAW_PAIR_DRIFT")

    lease_raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    lease_blob = lease_raw["sha"]
    lease_state = validate_scope_state(_decode(lease_raw))
    scope = build_scope(
        write_paths=[REGISTRY_PATH],
        dependency_tokens=["cfb:game-total:step8", "registry:cfb-game-total:step8"],
        shared_resources=["ref:monster-frozen-artifact-registry"],
        resource_identity={"main_sha": MAIN_SHA, "registry_state_hash": first["state_hash"]},
        exclusive=False,
    )
    claim = claim_scope(
        lease_state,
        owner_id=LEASE_OWNER,
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        scope=scope,
        expected_revision=lease_state["revision"],
        expected_state_hash=lease_state["state_hash"],
        ttl_seconds=900,
    )
    if claim["result"].get("allowed") is not True:
        raise Step8TerminalCloseoutFailure("LEASE_BLOCKED:" + json.dumps(claim["result"], sort_keys=True))
    lease_id = claim["result"]["lease_id"]
    client.update_content(
        LEASE_PATH,
        _json_text(claim["state"]),
        LEASE_BRANCH,
        "lease: claim CFB Step8 terminal closeout",
        lease_blob,
    )

    gate = authorize_scope(
        claim["state"],
        owner_id=LEASE_OWNER,
        lease_id=lease_id,
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        action_scope={
            "write_paths": [REGISTRY_PATH],
            "dependency_tokens": ["cfb:game-total:step8", "registry:cfb-game-total:step8"],
            "shared_resources": ["ref:monster-frozen-artifact-registry"],
            "resource_identity": {},
            "exclusive": False,
        },
    )
    if gate.get("allowed") is not True:
        raise Step8TerminalCloseoutFailure("LEASE_AUTHORIZATION_FAILED")

    current = backend.read_registry()
    if current["state_hash"] != first["state_hash"] or current["revision"] != first["revision"]:
        raise Step8TerminalCloseoutFailure("REGISTRY_CHANGED_AFTER_LEASE_CLAIM")
    unrelated_before = [deepcopy(g) for g in current.get("active_thaws", []) if g.get("thaw_id") != STEP8_THAW]
    planned = plan_baseline_forward_port(
        current,
        updates={V43: {"from_blob": V43_FROM, "to_blob": V43_TO}},
        source_main_sha=MAIN_SHA,
    )
    if set(planned.get("retired_empty_thaw_grants") or []) != {STEP8_THAW}:
        raise Step8TerminalCloseoutFailure("STEP8_THAW_RETIREMENT_DRIFT")
    next_registry = deepcopy(planned["registry"])
    if next_registry.get("active_thaws", []) != unrelated_before:
        raise Step8TerminalCloseoutFailure("UNRELATED_THAW_MUTATION")

    flattened = {}
    for token, entry in next_registry.get("entries", {}).items():
        for path, blob in entry.get("artifacts", {}).items():
            flattened.setdefault(path, set()).add(blob)
    conflicts = sorted(
        path for path, blob in artifacts.items()
        if path in flattened and flattened[path] != {blob}
    )
    if conflicts:
        raise Step8TerminalCloseoutFailure("FREEZE_BASELINE_CONFLICT:" + ",".join(conflicts))
    if FREEZE_TOKEN in next_registry.get("entries", {}):
        raise Step8TerminalCloseoutFailure("FREEZE_TOKEN_PREEXISTS_DURING_ACTIVE_THAW")
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
    entry = readback.get("entries", {}).get(FREEZE_TOKEN)
    if readback != next_registry or not entry:
        raise Step8TerminalCloseoutFailure("REGISTRY_READBACK_MISMATCH")
    if any(g.get("thaw_id") == STEP8_THAW for g in readback.get("active_thaws", [])):
        raise Step8TerminalCloseoutFailure("STEP8_THAW_STILL_ACTIVE")

    latest_lease_raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    latest_lease = validate_scope_state(_decode(latest_lease_raw))
    released = release_scope(
        latest_lease,
        owner_id=LEASE_OWNER,
        lease_id=lease_id,
        expected_revision=latest_lease["revision"],
        expected_state_hash=latest_lease["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise Step8TerminalCloseoutFailure("LEASE_RELEASE_FAILED:" + json.dumps(released["result"], sort_keys=True))
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Step8 terminal closeout",
        latest_lease_raw["sha"],
    )
    lease_check = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    if any(h.get("lease_id") == lease_id for h in lease_check.get("holders", [])):
        raise Step8TerminalCloseoutFailure("LEASE_READBACK_STILL_HELD")

    return {
        "status": "GREEN_FROZEN",
        "already_frozen": False,
        "previous_revision": current["revision"],
        "revision": readback["revision"],
        "state_hash": readback["state_hash"],
        "freeze_token": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "retired_thaw": STEP8_THAW,
        "remaining_thaw_ids": sorted(g.get("thaw_id") for g in readback.get("active_thaws", [])),
        "artifact_count": len(artifacts),
        "lease_released": True,
        "public_proof": public_receipt,
        "github_actions_fallback": 0,
    }


def execute(app) -> dict:
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8TerminalCloseoutFailure("MAIN_DRIFT")
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    existing = registry.get("entries", {}).get(FREEZE_TOKEN)
    if existing and not any(g.get("thaw_id") == STEP8_THAW for g in registry.get("active_thaws", [])):
        tree = client.tree_blobs(MAIN_SHA)
        expected = {p: tree[p] for p in STEP8_ARTIFACTS}
        if existing.get("source_main_sha") == MAIN_SHA and existing.get("artifacts") == expected:
            return {
                "status": "GREEN_FROZEN",
                "already_frozen": True,
                "revision": registry["revision"],
                "state_hash": registry["state_hash"],
                "freeze_token": FREEZE_TOKEN,
                "source_main_sha": MAIN_SHA,
                "github_actions_fallback": 0,
            }
    public_receipt = _run_public_proof()
    return _freeze(app, public_receipt)


def install_startup(app):
    app.state.cfb_step8_terminal_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_step8_terminal_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_step8_terminal_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:16000],
            }
        print("CFB_STEP8_TERMINAL_CLOSEOUT=" + json.dumps(app.state.cfb_step8_terminal_closeout, sort_keys=True, default=str), flush=True)

    return app
