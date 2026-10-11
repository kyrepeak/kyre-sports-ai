from __future__ import annotations
import os
from datetime import datetime, timezone

from devsystem.scope_aware_execution_lease_v1 import renew_scope

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_PREMERGE_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC_ON_START"] = "0"

from .api import app
from . import cfb_step8_terminal_freeze_event_guard_r3 as terminal


def _verified_premerge_authority(client):
    receipt = terminal._decode(
        client.content(terminal.PREMERGE_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    if (
        receipt.get("proof_id") != terminal.PREMERGE_PROOF_ID
        or receipt.get("candidate_sha") != terminal.CANDIDATE_SHA
        or receipt.get("digest") != terminal.PREMERGE_RECEIPT_DIGEST
        or receipt.get("failure_class") != "NONE"
    ):
        raise terminal.TerminalFreezeFailure("PREMERGE_AUTHORITY_DRIFT")
    return {
        "proof_id": terminal.PREMERGE_PROOF_ID,
        "receipt_digest": terminal.PREMERGE_RECEIPT_DIGEST,
    }


def _jump_route_cert_script():
    return f'''
import json
from urllib.parse import urlencode
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{terminal.PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{terminal.HANDOFF_CERT_DAY}"


def _jump_route_for_day(base_url, selected_day):
    query = urlencode({{
        "ks_jump_sport": "CFB",
        "ks_jump_market": "Game Total",
        "ks_cfb_game_total_date": str(selected_day),
    }})
    return base_url.rstrip("/") + "/?" + query


cert._route_for_day = _jump_route_for_day
_original_page1 = cert._page1_result


def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(page, name, artifact_dir, base_url)
    frame, _ = cert._find_cfb_frame(
        page,
        required_markers=cert.PAGE1_FRAME_MARKERS,
        required_testids=(cert.PHOENIX_DAY_TESTID, cert.PAGE1_TESTID),
        timeout_seconds=30.0,
    )
    wrapper_event = cert._event_from_url(page.url)
    frame_event = cert._event_from_url(str(getattr(frame, "url", "") or ""))
    if wrapper_event or frame_event:
        raise cert.Step8MobileProductionFailure(
            f"PAGE1_AUTO_EVENT_VISIBLE:{{name}}:{{wrapper_event}}:{{frame_event}}"
        )
    row["auto_event_visible"] = False
    return row, selected_url, event_id


cert._page1_result = _guarded_page1
payload = cert.run_public(
    base_url="{terminal.PRODUCTION_URL}",
    artifact_dir="artifacts/cfb-game-total-step8-terminal-r4",
)
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")
print("CFB_STEP8_R4_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True), flush=True)
'''


_original_claim = terminal._claim


def _resume_or_claim(client, registry_hash):
    raw = client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH)
    state = terminal.validate_scope_state(terminal._decode(raw))
    owned = [
        h for h in state.get("holders", [])
        if h.get("owner_id") == terminal.FINAL_OWNER
    ]
    if owned:
        if len(owned) != 1:
            raise terminal.TerminalFreezeFailure("R4_RESUME_LEASE_NOT_UNIQUE")
        holder = owned[0]
        scope = holder.get("scope") or {}
        identity = scope.get("resource_identity") or {}
        expected_writes = {
            terminal.REGISTRY_PATH,
            terminal.LEDGER_PATH,
            terminal.TERMINAL_RECEIPT_PATH,
        }
        if (
            identity.get("main_sha") != terminal.PRODUCT_MAIN_SHA
            or identity.get("registry_state_hash") != registry_hash
            or not expected_writes.issubset(set(scope.get("write_paths") or []))
            or f"candidate:{terminal.CANDIDATE_SHA}" not in set(scope.get("dependency_tokens") or [])
            or "cfb:game-total:step8" not in set(scope.get("dependency_tokens") or [])
        ):
            raise terminal.TerminalFreezeFailure("R4_RESUME_LEASE_IDENTITY_DRIFT")

        now = datetime.now(timezone.utc)
        heartbeat = datetime.fromisoformat(
            str(holder.get("heartbeat_at_utc") or "").replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        age_seconds = (now - heartbeat).total_seconds()
        if age_seconds < 180:
            raise terminal.TerminalFreezeFailure(
                f"R4_RESUME_ALREADY_ACTIVE:heartbeat_age_seconds={age_seconds:.1f}"
            )

        lease_id = str(holder.get("lease_id") or "")
        renewed = renew_scope(
            state,
            owner_id=terminal.FINAL_OWNER,
            lease_id=lease_id,
            now_utc=now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            expected_revision=state["revision"],
            expected_state_hash=state["state_hash"],
            ttl_seconds=2400,
        )
        if renewed["result"].get("allowed") is not True:
            raise terminal.TerminalFreezeFailure(
                "R4_RESUME_RENEW_FAILED:" + str(renewed["result"])
            )
        client.update_content(
            terminal.LEASE_PATH,
            terminal._text(renewed["state"]),
            terminal.LEASE_BRANCH,
            "lease: dead-man resume CFB Step8 terminal R4",
            raw["sha"],
        )
        return lease_id
    return _original_claim(client, registry_hash)


terminal._ensure_authority = _verified_premerge_authority
terminal._cert_script = _jump_route_cert_script
terminal._claim = _resume_or_claim
terminal.install_startup(app)
