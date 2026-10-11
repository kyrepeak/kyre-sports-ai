from __future__ import annotations

import base64
import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_state,
)

from .registry import REGISTRY_PATH

MERGED_SHA = "c102a55985dbe2c3ab2ece3d24a7c82206989173"
CANDIDATE_SHA = "d265eb22cc2919a603c75534373393d8a6c5c9f5"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
ROUTER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
ROUTER_FROM = "811b0cec681aa1b1b0fddc4c3d4170dd3770dd50"
ROUTER_TO = "2a73aba9b5a746a4e5ab8ab7040210df3e705666"
THAW_ID = "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R1"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
PRE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-page1-event-guard-r1"
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-terminal-freeze-event-guard-r1"
PRODUCTION_URL = "https://pickvault.streamlit.app"
PROOF_DAY = "2026-10-17"
EVENT_KEY = "ks_cfb_game_total_event_id"
SYNC_KEY = "ks_cfb_game_total_selector_sync"
PAGE1_TESTID = "gt163-game-strip"
PAGE2_TESTID = "gtp2s8-final"
FORBIDDEN = ("data limited", "mock data")
FINAL_ARTIFACTS = (
    "app.py",
    "cfb_game_total_clean_page_v43.py",
    "cfb_game_total_page2_step8_final_runtime_v1.py",
    "devsystem/cfb_game_total_mobile_production_step8_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-step8-page1-event-guard-r1.json",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py",
    "tests/test_cfb_game_total_step8_page1_event_guard_r1.py",
)


class TerminalFreezeFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise TerminalFreezeFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _event(url: str) -> str:
    values = parse_qs(urlparse(str(url or "")).query).get(EVENT_KEY) or []
    return str(values[-1] if values else "").strip()


def _route() -> str:
    return PRODUCTION_URL.rstrip("/") + "/?" + urlencode(
        {
            "ks_sport": "College Football",
            "ks_cfb_market": "Game Total",
            "ks_cfb_game_total_date": PROOF_DAY,
        }
    )


def _frame_with_testid(page, testid: str, timeout_seconds: float):
    deadline = time.monotonic() + timeout_seconds
    last = []
    while time.monotonic() < deadline:
        last = []
        for frame in page.frames:
            try:
                count = frame.locator(f'[data-testid="{testid}"]').count()
                body = frame.locator("body").inner_text(timeout=2500)
            except Exception:
                count = 0
                body = ""
            last.append({"url": str(getattr(frame, "url", "") or ""), "count": count, "body": body[:300]})
            if "get this app back up" in body.casefold():
                try:
                    wake = frame.get_by_text("Yes, get this app back up!", exact=False)
                    if wake.count() > 0:
                        wake.first.click()
                        page.wait_for_timeout(2500)
                        continue
                except Exception:
                    pass
            if count > 0:
                return frame
        page.wait_for_timeout(700)
    raise TerminalFreezeFailure(f"TESTID_NOT_FOUND:{testid}:{json.dumps(last, ensure_ascii=True)}")


def _browser_readback() -> dict:
    route = _route()
    observations = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            for attempt in range(1, 19):
                try:
                    page.goto(route, wait_until="domcontentloaded", timeout=60000)
                    frame = _frame_with_testid(page, PAGE1_TESTID, 35)
                    page.wait_for_timeout(1800)
                    outer_event = _event(page.url)
                    frame_event = _event(frame.url)
                    body = frame.locator("body").inner_text(timeout=5000)
                    forbidden = [term for term in FORBIDDEN if term in body.casefold()]
                    cards = frame.locator(f'[data-testid="{PAGE1_TESTID}"] a[data-event-id]')
                    card_count = cards.count()
                    observations.append(
                        {
                            "attempt": attempt,
                            "outer_event": outer_event,
                            "frame_event": frame_event,
                            "card_count": card_count,
                            "forbidden": forbidden,
                            "frame_url": frame.url,
                        }
                    )
                    if outer_event or frame_event or card_count < 1:
                        page.wait_for_timeout(7000)
                        continue
                    if forbidden:
                        raise TerminalFreezeFailure("PAGE1_FORBIDDEN_VISIBLE:" + ",".join(forbidden))

                    first = cards.first
                    selected_event = str(first.get_attribute("data-event-id") or "").strip()
                    if not selected_event:
                        raise TerminalFreezeFailure("PAGE1_CARD_EVENT_ID_MISSING")
                    first.click()
                    page2 = _frame_with_testid(page, PAGE2_TESTID, 70)
                    page.wait_for_timeout(1200)
                    body2 = page2.locator("body").inner_text(timeout=5000)
                    forbidden2 = [term for term in FORBIDDEN if term in body2.casefold()]
                    if forbidden2:
                        raise TerminalFreezeFailure("PAGE2_FORBIDDEN_VISIBLE:" + ",".join(forbidden2))
                    page2_event = _event(page2.url) or _event(page.url)
                    if page2_event and page2_event != selected_event:
                        raise TerminalFreezeFailure(f"PAGE2_EVENT_MISMATCH:{selected_event}:{page2_event}")
                    if page2.locator('[data-testid="gtp2s8-back-to-slate"]').count() < 1:
                        raise TerminalFreezeFailure("PAGE2_BACK_TO_SLATE_MISSING")
                    return {
                        "status": "GREEN",
                        "production_url": route,
                        "viewport": "390x844",
                        "page1_clean_event_query": True,
                        "page1_card_count": card_count,
                        "selected_event_id": selected_event,
                        "page2_live": True,
                        "page2_event_id": page2_event or selected_event,
                        "forbidden_visible": [],
                        "attempt": attempt,
                    }
                except TerminalFreezeFailure:
                    raise
                except Exception as exc:
                    observations.append({"attempt": attempt, "error": type(exc).__name__, "detail": str(exc)[:1000]})
                    page.wait_for_timeout(7000)
            raise TerminalFreezeFailure("PRODUCTION_DID_NOT_CONVERGE:" + json.dumps(observations[-8:], ensure_ascii=True))
        finally:
            browser.close()


def _claim_final_lease(client, registry_hash: str):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    working = state
    for holder in list(working.get("holders", [])):
        if holder.get("owner_id") == PRE_OWNER:
            released = release_scope(
                working,
                owner_id=PRE_OWNER,
                lease_id=str(holder.get("lease_id") or ""),
                expected_revision=working["revision"],
                expected_state_hash=working["state_hash"],
            )
            if released["result"].get("allowed") is not True:
                raise TerminalFreezeFailure("PRE_LEASE_RELEASE_FAILED")
            working = released["state"]
            break
    scope = build_scope(
        write_paths=[REGISTRY_PATH],
        dependency_tokens=["cfb:game-total:step8", "router:cfb-game-total"],
        shared_resources=["ref:monster-frozen-artifact-registry", "route:cfb-game-total"],
        resource_identity={"main_sha": MERGED_SHA, "registry_state_hash": registry_hash},
        exclusive=False,
    )
    claimed = claim_scope(
        working,
        owner_id=FINAL_OWNER,
        now_utc=_now(),
        scope=scope,
        expected_revision=working["revision"],
        expected_state_hash=working["state_hash"],
        ttl_seconds=1200,
    )
    if claimed["result"].get("allowed") is not True:
        raise TerminalFreezeFailure("FINAL_LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(
        LEASE_PATH,
        _text(claimed["state"]),
        LEASE_BRANCH,
        "lease: handoff CFB Step8 to terminal freeze",
        raw["sha"],
    )
    return str(claimed["result"]["lease_id"]), claimed["state"]


def _freeze_registry(client) -> dict:
    raw = client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry")
    registry = _decode(raw)
    validated = validate_registry(registry)
    if validated["artifacts"].get(ROUTER) != ROUTER_FROM:
        raise TerminalFreezeFailure("ROUTER_FROZEN_BASELINE_DRIFT")
    main_tree = client.tree_blobs(MERGED_SHA)
    if main_tree.get(ROUTER) != ROUTER_TO:
        raise TerminalFreezeFailure("MERGED_ROUTER_BLOB_DRIFT")
    thaws = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if len(thaws) != 1:
        raise TerminalFreezeFailure("EVENT_GUARD_THAW_NOT_UNIQUE")
    exact = thaws[0]
    if exact.get("target_head_sha") != CANDIDATE_SHA:
        raise TerminalFreezeFailure("EVENT_GUARD_THAW_TARGET_DRIFT")

    planned = plan_baseline_forward_port(
        registry,
        updates={ROUTER: {"from_blob": ROUTER_FROM, "to_blob": ROUTER_TO}},
        source_main_sha=MERGED_SHA,
    )
    if THAW_ID not in set(planned.get("retired_empty_thaw_grants") or []):
        raise TerminalFreezeFailure("EVENT_GUARD_THAW_NOT_RETIRED")
    updated = deepcopy(planned["registry"])
    artifacts = {}
    for path in FINAL_ARTIFACTS:
        blob = main_tree.get(path)
        if not blob:
            raise TerminalFreezeFailure("FINAL_ARTIFACT_MISSING:" + path)
        artifacts[path] = blob
    existing = updated.get("entries", {}).get(FREEZE_TOKEN)
    entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_SHA,
        "artifacts": dict(sorted(artifacts.items())),
    }
    if existing and existing != entry:
        raise TerminalFreezeFailure("FREEZE_TOKEN_CONFLICT")
    updated["entries"][FREEZE_TOKEN] = entry
    updated["source_main_sha"] = MERGED_SHA
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _text(updated),
        "monster-frozen-artifact-registry",
        "registry: freeze CFB Game Total native rebuild Step8",
        raw["sha"],
    )
    readback = _decode(client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry"))
    validate_registry(readback)
    frozen = readback.get("entries", {}).get(FREEZE_TOKEN)
    if frozen != entry or any(g.get("thaw_id") == THAW_ID for g in readback.get("active_thaws", [])):
        raise TerminalFreezeFailure("TERMINAL_FREEZE_READBACK_MISMATCH")
    return {
        "status": "FROZEN",
        "freeze_token": FREEZE_TOKEN,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "source_main_sha": str(readback["source_main_sha"]),
        "artifact_count": len(artifacts),
        "event_guard_thaw_retired": True,
    }


def _release_final_lease(client, lease_id: str, claimed_state) -> None:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    holder = next((h for h in state.get("holders", []) if h.get("lease_id") == lease_id and h.get("owner_id") == FINAL_OWNER), None)
    if not holder:
        return
    released = release_scope(
        state,
        owner_id=FINAL_OWNER,
        lease_id=lease_id,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is True:
        client.update_content(LEASE_PATH, _text(released["state"]), LEASE_BRANCH, "lease: release CFB Step8 terminal freeze", raw["sha"])


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MERGED_SHA:
        raise TerminalFreezeFailure("MAIN_DRIFT")
    merged = client.commit(MERGED_SHA)
    parents = {str(p.get("sha") or "") for p in merged.get("parents", [])}
    if CANDIDATE_SHA not in parents:
        raise TerminalFreezeFailure("MERGED_CANDIDATE_PARENT_MISSING")
    registry = _decode(client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry"))
    validate_registry(registry)
    lease_id, claimed_state = _claim_final_lease(client, str(registry["state_hash"]))
    try:
        production = _browser_readback()
        frozen = _freeze_registry(client)
        client.publish_check(
            MERGED_SHA,
            "cfb-step8-terminal-freeze",
            "success",
            {"title": "CFB Step 8 GREEN + FROZEN", "summary": FREEZE_TOKEN},
        )
        return {
            "status": "GREEN+FROZEN",
            "workstream": WORKSTREAM,
            "merged_sha": MERGED_SHA,
            "lease_id": lease_id,
            "production": production,
            "freeze": frozen,
            "github_actions_fallback": 0,
        }
    finally:
        _release_final_lease(client, lease_id, claimed_state)


def install_startup(app):
    app.state.cfb_step8_terminal_freeze_event_guard = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
        app.state.cfb_step8_terminal_freeze_event_guard = result
        print("CFB_STEP8_TERMINAL_FREEZE_EVENT_GUARD=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    return app
