from __future__ import annotations

import base64
import json
from typing import Any

PRESTATE_REVISION = 297
PRESTATE_HASH = "cd805a3acb3d6c1ab083a753bf943ac7f596950f8995675bc969597af3a09905"
TARGET_REVISION = 298
TARGET_HASH = "8fe7ae89228fcfc04e816212cffa3dfce8a4ca6a25357c8be17a0d04eda19a62"
SOURCE_MAIN_SHA = "6b3a37891fc2938736e8f371d29c3337682a4a22"
OLD_CANDIDATE_SHA = "dd1ecbbe24299b453aab8dea290061b8613d5e8b"
NEW_CANDIDATE_SHA = "1a1445d3cfaa7e3074c73b91bc3d94ab814daac5"
THAW_ID = "THAW-NBA-SPREAD-STEP4-MOST-BET-FEATURE-R1"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
TARGET_PAYLOAD_URL = "https://jqajcdckalsfizbvngiu.supabase.co/functions/v1/api2-registry-step4-rebind-payload-temp"
EXPECTED_FILES = {
    "nba_spread_page_v1.py": {
        "from_blob": "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0",
        "to_blob": "0ad62af70010051c3ac8f4477d63263a228eb76b",
    }
}


class Step4ThawRebindFailure(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise Step4ThawRebindFailure(code)


def _decode(raw: dict[str, Any] | None, label: str) -> tuple[dict[str, Any], str]:
    if not raw or raw.get("encoding") != "base64" or not raw.get("sha"):
        _fail(label + "_READ")
    try:
        text = base64.b64decode(raw["content"]).decode("utf-8")
        return json.loads(text), text
    except Exception as exc:
        raise Step4ThawRebindFailure(label + "_DECODE") from exc


def _exact_thaw(payload: dict[str, Any]) -> dict[str, Any]:
    matches = [x for x in payload.get("active_thaws", []) if x.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        _fail("THAW_COUNT")
    return matches[0]


def validate_prestate(payload: dict[str, Any]) -> None:
    if int(payload.get("revision", -1)) != PRESTATE_REVISION:
        _fail("PRESTATE_REVISION")
    if payload.get("state_hash") != PRESTATE_HASH:
        _fail("PRESTATE_HASH")
    if payload.get("source_main_sha") != SOURCE_MAIN_SHA:
        _fail("PRESTATE_MAIN")
    if len(payload.get("entries") or {}) != 146 or len(payload.get("active_thaws") or []) != 5:
        _fail("PRESTATE_SHAPE")
    thaw = _exact_thaw(payload)
    if thaw.get("status") != "ACTIVE" or thaw.get("target_head_sha") != OLD_CANDIDATE_SHA or thaw.get("files") != EXPECTED_FILES:
        _fail("PRESTATE_THAW_IDENTITY")


def validate_target(payload: dict[str, Any], *, require_full: bool = True) -> None:
    if int(payload.get("revision", -1)) != TARGET_REVISION:
        _fail("TARGET_REVISION")
    if payload.get("state_hash") != TARGET_HASH:
        _fail("TARGET_HASH")
    if payload.get("source_main_sha") != SOURCE_MAIN_SHA:
        _fail("TARGET_MAIN")
    if require_full and (len(payload.get("entries") or {}) != 146 or len(payload.get("active_thaws") or []) != 5):
        _fail("TARGET_SHAPE")
    thaw = _exact_thaw(payload)
    if thaw.get("status") != "ACTIVE" or thaw.get("target_head_sha") != NEW_CANDIDATE_SHA or thaw.get("files") != EXPECTED_FILES:
        _fail("TARGET_THAW_IDENTITY")


def execute() -> dict[str, Any]:
    import httpx
    from devsystem.frozen_artifact_registry_v1 import validate_registry
    from runless_proof_plane.config import Settings
    from runless_proof_plane.github_app import GithubAppAuth
    from runless_proof_plane.github_client import GithubClient

    settings = Settings.from_env()
    client = GithubClient(GithubAppAuth(settings), settings.repository)
    if client.branch_sha("main") != SOURCE_MAIN_SHA:
        _fail("MAIN_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    prestate, _ = _decode(raw, "PRESTATE")
    validate_prestate(prestate)
    validate_registry(prestate)

    response = httpx.get(TARGET_PAYLOAD_URL, headers={"cache-control": "no-cache"}, timeout=30.0)
    if response.status_code != 200:
        _fail("TARGET_FETCH_" + str(response.status_code))
    target_text = response.text
    try:
        target = json.loads(target_text)
    except Exception as exc:
        raise Step4ThawRebindFailure("TARGET_DECODE") from exc
    validate_target(target, require_full=True)
    validate_registry(target)

    update = client.update_content(
        REGISTRY_PATH,
        target_text,
        REGISTRY_BRANCH,
        "registry: rebind NBA Spread Step4 thaw to isolated proof head",
        str(raw["sha"]),
    )
    readback_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    readback, readback_text = _decode(readback_raw, "READBACK")
    validate_target(readback, require_full=True)
    validate_registry(readback)
    if readback_text != target_text:
        _fail("READBACK_BYTES_MISMATCH")

    return {
        "status": "GREEN",
        "registry_revision": TARGET_REVISION,
        "registry_state_hash": TARGET_HASH,
        "step4_candidate_sha": NEW_CANDIDATE_SHA,
        "step4_thaw_id": THAW_ID,
        "commit_sha": str((update.get("commit") or {}).get("sha") or ""),
        "blob_sha": str((readback_raw or {}).get("sha") or ""),
        "github_actions_fallback": 0,
    }


def main() -> int:
    print("NBA_SPREAD_STEP4_THAW_REBIND=" + json.dumps(execute(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
