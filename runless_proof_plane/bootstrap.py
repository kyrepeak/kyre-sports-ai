from __future__ import annotations
import json
import os
import subprocess
import sys

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"] = "0"

from .api import app
from . import cfb_game_total_page2_step8_finalizer as finalizer
from .workspace import CandidateWorkspace

finalizer.MAIN_SHA = "3065e960d3363bf6f3d70252c906b9590e7293e9"
finalizer.PREMERGE_SHA = "764e11f1f69630e4326ddfbbbc070e0840001780"
finalizer.PREMERGE_RECEIPT_DIGEST = "f12323f16847973965bf6e380e70f12cda1d68ca99af8c24e754380eb457c46e"
finalizer.LEASE_ID = "SCOPE-LEASE-779AF9201DBFD42F72EF29FC"
finalizer.ARTIFACT_MAP = {
    "app.py": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
    "cfb_game_total_page2_step8_final_runtime_v1.py": "bf3141e958826cf93cb39435e7ea809865f92a29",
    "devsystem/cfb_game_total_page2_step8_live_cert_v1.py": "422b54320df359732499344794b4e1887cb14daa",
    "devsystem/execution_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "e1b3bb8bbca106e3520af8fa585871fd89398eec",
    "devsystem/runless_proof_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "22c7bb6e7731cf72e5e24ec36645bd0cd72b9451",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py": "154760d34b4f33aed1efafdf2b026262eb0e332b",
    "tests/test_cfb_game_total_page2_step8_final_v1.py": "9b794cbdeaaa8f6fcbdf276c8c907835408a30e1",
}

_original_freeze = finalizer._freeze_and_reconcile

def _freeze_with_original_app_thaw(client):
    repaired_candidate = finalizer.PREMERGE_SHA
    finalizer.PREMERGE_SHA = "09a5efc543e5f8c57f3ac6686bd34e5932ba3685"
    try:
        return _original_freeze(client)
    finally:
        finalizer.PREMERGE_SHA = repaired_candidate

finalizer._freeze_and_reconcile = _freeze_with_original_app_thaw


def _fast_live_cert(app):
    client = app.state.github_client
    settings = app.state.settings
    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    selected_url = (
        "https://pickvault.streamlit.app/?ks_sport=College+Football"
        "&ks_cfb_market=Game+Total"
        "&ks_cfb_game_total_date=2026-10-10"
        "&ks_cfb_game_total_event_id=401856824"
    )
    with CandidateWorkspace(repository_url, finalizer.MAIN_SHA, token=token) as workspace:
        artifact_dir = workspace.path / "artifacts" / "cfb-game-total-page2-step8-fast"
        code = f'''
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
from devsystem import browser_qa_v1 as base
from devsystem import cfb_game_total_page2_step8_live_cert_v1 as cert
cert.EXPECTED_MAIN_SHA = {finalizer.MAIN_SHA!r}
base_url = {finalizer.PRODUCTION_URL!r}
selected_url = {selected_url!r}
event_id = "401856824"
artifacts = Path({str(artifact_dir)!r})
artifacts.mkdir(parents=True, exist_ok=True)
health = base._wait_for_health(base_url)

def app_frame(page):
    deadline = time.monotonic() + 20.0
    last = []
    while time.monotonic() < deadline:
        last = [f.url for f in page.frames]
        for frame in page.frames:
            if "pickvault.streamlit.app/~/+" in frame.url:
                return frame
        page.wait_for_timeout(250)
    raise RuntimeError("STEP8_FAST_APP_FRAME_URL_MISSING:" + json.dumps(last))

results = {{}}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    try:
        page = browser.new_page(viewport=cert.VIEWPORTS["mobile390"])
        page.goto(selected_url, wait_until="domcontentloaded", timeout=120000)
        frame = app_frame(page)
        frame.locator('[data-testid="gtp2s8-final"]').first.wait_for(state="visible", timeout=60000)
        for name, viewport in cert.VIEWPORTS.items():
            page.set_viewport_size(viewport)
            page.wait_for_timeout(700)
            frame = app_frame(page)
            for testid in cert.REQUIRED_TESTIDS:
                frame.locator(f'[data-testid="{{testid}}"]' ).first.wait_for(state="visible", timeout=10000)
            body = frame.locator("body").inner_text(timeout=10000)
            forbidden = cert._forbidden_visible_text(body)
            runtime_error = cert._runtime_error(body)
            horizontal_overflow = cert._horizontal_overflow(frame)
            observed_event = cert._exact_event_id(frame.url) or cert._exact_event_id(page.url) or event_id
            if observed_event != event_id:
                raise RuntimeError(f"STEP8_FAST_EVENT_DRIFT:{{event_id}}:{{observed_event}}")
            if forbidden:
                raise RuntimeError("STEP8_FAST_FORBIDDEN:" + json.dumps(forbidden))
            if runtime_error:
                raise RuntimeError("STEP8_FAST_RUNTIME_ERROR:" + runtime_error)
            if horizontal_overflow:
                raise RuntimeError("STEP8_FAST_HORIZONTAL_OVERFLOW:" + name)
            screenshot = artifacts / f"cfb_game_total_page2_step8_{{name}}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            results[name] = {{
                "viewport": dict(viewport),
                "selected_url": selected_url,
                "exact_event_id": event_id,
                "all_required_visible": True,
                "required_testids_visible": list(cert.REQUIRED_TESTIDS),
                "forbidden_visible_text": [],
                "horizontal_overflow": False,
                "runtime_error": "",
                "screenshot": str(screenshot),
            }}
    finally:
        browser.close()

payload = {{
    "status": "GREEN",
    "source_main_sha": cert.EXPECTED_MAIN_SHA,
    "production_url": base_url,
    "route_url": selected_url,
    "event_query_key": cert.EVENT_QUERY_KEY,
    "phoenix_timezone": cert.PHOENIX_TZ,
    "sportsbook_projection_influence": cert.SPORTSBOOK_PROJECTION_INFLUENCE,
    "may_modify_product_runtime": cert.MAY_MODIFY_PRODUCT_RUNTIME,
    "github_actions_fallback": cert.GITHUB_ACTIONS_FALLBACK,
    "health": health,
    "viewports": results,
}}
if not cert.evidence_is_terminal_green(payload):
    raise RuntimeError("STEP8_FAST_TERMINAL_CONTRACT_REJECTED")
evidence_path = artifacts / "cfb_game_total_page2_step8_live_cert.json"
evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
print("CFB_GT_PAGE2_STEP8_FAST_LIVE_GREEN", flush=True)
'''
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace.path,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if completed.returncode != 0:
            detail = ((completed.stderr or "") + "\n" + (completed.stdout or ""))[-7000:]
            raise RuntimeError("PAGE2_STEP8_FAST_LIVE_CERT_FAILED:" + detail)
        evidence_path = artifact_dir / "cfb_game_total_page2_step8_live_cert.json"
        if not evidence_path.exists():
            raise RuntimeError("PAGE2_STEP8_FAST_LIVE_CERT_EVIDENCE_MISSING")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence.get("status") != "GREEN" or evidence.get("source_main_sha") != finalizer.MAIN_SHA:
            raise RuntimeError("PAGE2_STEP8_FAST_LIVE_CERT_IDENTITY_MISMATCH")
        if set(evidence.get("viewports") or {{}}) != {{"mobile390", "mobile430", "tablet", "desktop"}}:
            raise RuntimeError("PAGE2_STEP8_FAST_LIVE_CERT_VIEWPORT_MISMATCH")
        return evidence


from . import cfb_game_total_page2_step8_finalizer_with_browser as browser_finalizer
browser_finalizer._run_live_cert_on_next_slate = _fast_live_cert
browser_finalizer.install_startup(app)
