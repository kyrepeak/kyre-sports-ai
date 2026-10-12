from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any

CURRENT_REVISION = 297
CURRENT_HASH = "cd805a3acb3d6c1ab083a753bf943ac7f596950f8995675bc969597af3a09905"
TARGET_REVISION = 298
SOURCE_MAIN_SHA = "6b3a37891fc2938736e8f371d29c3337682a4a22"
OLD_HEAD = "dd1ecbbe24299b453aab8dea290061b8613d5e8b"
NEW_HEAD = "1a1445d3cfaa7e3074c73b91bc3d94ab814daac5"
STEP4_THAW_ID = "THAW-NBA-SPREAD-STEP4-MOST-BET-FEATURE-R1"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
_EXPECTED_FILES = {
    "nba_spread_page_v1.py": {
        "from_blob": "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0",
        "to_blob": "0ad62af70010051c3ac8f4477d63263a228eb76b",
    }
}


class API2RegistryThawRebindFailure(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise API2RegistryThawRebindFailure(code)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(payload: dict[str, Any]) -> str:
    current = deepcopy(payload)
    current.pop("state_hash", None)
    return hashlib.sha256(_canonical(current).encode("utf-8")).hexdigest()


def rebind_payload(payload: dict[str, Any], *, require_current_hash: bool = True) -> dict[str, Any]:
    if int(payload.get("revision", -1)) != CURRENT_REVISION:
        _fail("CURRENT_REVISION")
    if str(payload.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        _fail("CURRENT_MAIN_IDENTITY")
    if require_current_hash and str(payload.get("state_hash") or "") != CURRENT_HASH:
        _fail("CURRENT_HASH")
    if str(payload.get("state_hash") or "") != _state_hash(payload):
        _fail("CURRENT_HASH_INVALID")

    matches = [item for item in payload.get("active_thaws", []) if item.get("thaw_id") == STEP4_THAW_ID]
    if len(matches) != 1:
        _fail("STEP4_THAW_COUNT")
    exact = matches[0]
    if (
        exact.get("status") != "ACTIVE"
        or exact.get("target_head_sha") != OLD_HEAD
        or exact.get("files") != _EXPECTED_FILES
    ):
        _fail("STEP4_THAW_IDENTITY")

    target = deepcopy(payload)
    rebound = False
    for item in target["active_thaws"]:
        if item.get("thaw_id") == STEP4_THAW_ID:
            item["target_head_sha"] = NEW_HEAD
            rebound = True
    if not rebound:
        _fail("STEP4_THAW_NOT_REBOUND")

    target["revision"] = TARGET_REVISION
    target.pop("state_hash", None)
    target["state_hash"] = _state_hash(target)
    return target


def _decode(raw: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not raw or raw.get("encoding") != "base64" or not raw.get("sha"):
        _fail("REGISTRY_READ_FAILED")
    try:
        text = base64.b64decode(raw["content"]).decode("utf-8")
        return json.loads(text), text
    except Exception as exc:
        raise API2RegistryThawRebindFailure("REGISTRY_DECODE_FAILED") from exc


def execute() -> dict[str, Any]:
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
    current, _ = _decode(raw)
    validate_registry(current)
    target = rebind_payload(current, require_current_hash=True)
    validate_registry(target)
    target_text = _canonical(target)

    update = client.update_content(
        REGISTRY_PATH,
        target_text,
        REGISTRY_BRANCH,
        "registry: rebind NBA Spread Step4 thaw to isolated proof head",
        str(raw["sha"]),
    )
    readback_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    readback, readback_text = _decode(readback_raw)
    validate_registry(readback)
    if readback != target:
        _fail("READBACK_SEMANTIC_MISMATCH")
    if readback_text != target_text:
        _fail("READBACK_BYTES_MISMATCH")

    return {
        "status": "GREEN",
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "step4_thaw_id": STEP4_THAW_ID,
        "step4_candidate_sha": NEW_HEAD,
        "commit_sha": str((update.get("commit") or {}).get("sha") or ""),
        "blob_sha": str((readback_raw or {}).get("sha") or ""),
        "github_actions_fallback": 0,
    }


def main() -> int:
    print("API2_STEP4_THAW_REBIND=" + json.dumps(execute(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
