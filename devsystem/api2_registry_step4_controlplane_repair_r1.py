from __future__ import annotations

import base64
import json
from typing import Any

BRIDGE_REVISION = 296
BRIDGE_HASH = "ab1cf49c69e6bcdff218c55556f1655eff74fca4b0af367601a36b27338bb32d"
BRIDGE_ENTRY_COUNT = 1
BRIDGE_THAW_COUNT = 0
TARGET_REVISION = 297
TARGET_HASH = "cd805a3acb3d6c1ab083a753bf943ac7f596950f8995675bc969597af3a09905"
TARGET_ENTRY_COUNT = 146
TARGET_THAW_COUNT = 5
SOURCE_MAIN_SHA = "6b3a37891fc2938736e8f371d29c3337682a4a22"
STEP4_CANDIDATE_SHA = "dd1ecbbe24299b453aab8dea290061b8613d5e8b"
STEP4_THAW_ID = "THAW-NBA-SPREAD-STEP4-MOST-BET-FEATURE-R1"
STEP3_FREEZE_TOKEN = "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
TARGET_PAYLOAD_URL = "https://jqajcdckalsfizbvngiu.supabase.co/functions/v1/api2-registry-payload-builder-temp"
_EXPECTED_STEP4_FILES = {
    "nba_spread_page_v1.py": {
        "from_blob": "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0",
        "to_blob": "0ad62af70010051c3ac8f4477d63263a228eb76b",
    }
}


class API2RegistryRepairFailure(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise API2RegistryRepairFailure(code)


def validate_target_payload(payload: dict[str, Any], *, require_full_registry: bool = True) -> None:
    if int(payload.get("revision", -1)) != TARGET_REVISION:
        _fail("TARGET_REVISION")
    if str(payload.get("state_hash") or "") != TARGET_HASH:
        _fail("TARGET_HASH")
    if str(payload.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        _fail("TARGET_MAIN_IDENTITY")
    step3 = (payload.get("entries") or {}).get(STEP3_FREEZE_TOKEN) or {}
    if step3.get("status") != "FROZEN":
        _fail("STEP3_FREEZE_MISSING")
    matches = [item for item in payload.get("active_thaws", []) if item.get("thaw_id") == STEP4_THAW_ID]
    if len(matches) != 1:
        _fail("STEP4_THAW_COUNT")
    exact = matches[0]
    if (
        exact.get("status") != "ACTIVE"
        or exact.get("target_head_sha") != STEP4_CANDIDATE_SHA
        or exact.get("files") != _EXPECTED_STEP4_FILES
    ):
        _fail("STEP4_THAW_IDENTITY")
    if require_full_registry:
        if len(payload.get("entries") or {}) != TARGET_ENTRY_COUNT:
            _fail("TARGET_ENTRY_COUNT")
        if len(payload.get("active_thaws") or []) != TARGET_THAW_COUNT:
            _fail("TARGET_THAW_COUNT")


def _decode_json_content(raw: dict[str, Any] | None, label: str) -> tuple[dict[str, Any], str]:
    if not raw or raw.get("encoding") != "base64" or not raw.get("sha"):
        _fail(label + "_READ_FAILED")
    try:
        text = base64.b64decode(raw["content"]).decode("utf-8")
        return json.loads(text), text
    except Exception as exc:
        raise API2RegistryRepairFailure(label + "_DECODE_FAILED") from exc


def _validate_bridge(payload: dict[str, Any]) -> None:
    if int(payload.get("revision", -1)) != BRIDGE_REVISION:
        _fail("BRIDGE_REVISION")
    if str(payload.get("state_hash") or "") != BRIDGE_HASH:
        _fail("BRIDGE_HASH")
    if str(payload.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        _fail("BRIDGE_MAIN_IDENTITY")
    if len(payload.get("entries") or {}) != BRIDGE_ENTRY_COUNT:
        _fail("BRIDGE_ENTRY_COUNT")
    if len(payload.get("active_thaws") or []) != BRIDGE_THAW_COUNT:
        _fail("BRIDGE_THAW_COUNT")


def execute() -> dict[str, Any]:
    import httpx
    from devsystem.frozen_artifact_registry_v1 import validate_registry
    from runless_proof_plane.config import Settings
    from runless_proof_plane.github_app import GithubAppAuth
    from runless_proof_plane.github_client import GithubClient

    settings = Settings.from_env()
    auth = GithubAppAuth(settings)
    client = GithubClient(auth, settings.repository)
    if client.branch_sha("main") != SOURCE_MAIN_SHA:
        _fail("MAIN_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    bridge, _ = _decode_json_content(raw, "BRIDGE_REGISTRY")
    _validate_bridge(bridge)
    validate_registry(bridge)

    response = httpx.get(TARGET_PAYLOAD_URL, headers={"cache-control": "no-cache"}, timeout=30.0)
    if response.status_code != 200:
        _fail("TARGET_PAYLOAD_FETCH_" + str(response.status_code))
    target_text = response.text
    try:
        target = json.loads(target_text)
    except Exception as exc:
        raise API2RegistryRepairFailure("TARGET_PAYLOAD_DECODE") from exc
    validate_target_payload(target, require_full_registry=True)
    validate_registry(target)

    update = client.update_content(
        REGISTRY_PATH,
        target_text,
        REGISTRY_BRANCH,
        "registry: restore full Step3 state and bind NBA Spread Step4 thaw",
        str(raw["sha"]),
    )
    readback_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    readback, readback_text = _decode_json_content(readback_raw, "TARGET_REGISTRY_READBACK")
    validate_target_payload(readback, require_full_registry=True)
    validate_registry(readback)
    if readback_text != target_text:
        _fail("TARGET_BYTES_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "registry_revision": TARGET_REVISION,
        "registry_state_hash": TARGET_HASH,
        "entry_count": TARGET_ENTRY_COUNT,
        "thaw_count": TARGET_THAW_COUNT,
        "step4_thaw_id": STEP4_THAW_ID,
        "step4_candidate_sha": STEP4_CANDIDATE_SHA,
        "commit_sha": str((update.get("commit") or {}).get("sha") or ""),
        "blob_sha": str((readback_raw or {}).get("sha") or ""),
        "github_actions_fallback": 0,
    }


def main() -> int:
    result = execute()
    print("API2_REGISTRY_STEP4_REPAIR=" + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
