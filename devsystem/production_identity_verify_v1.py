"""Fail closed unless live Render matches the certified production identity."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = ROOT / "devsystem" / "production_targets_v1.json"
OBSERVABILITY_VERSION = "KYRE_OBSERVABILITY_V1"


class ProductionIdentityFailure(RuntimeError):
    pass


def _targets(path: Path = TARGETS_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    render = payload.get("render_api") or {}
    required = ("url", "service_id", "source_branch", "certified_commit")
    missing = [key for key in required if not str(render.get(key) or "").strip()]
    if missing:
        raise ProductionIdentityFailure(
            "Render production identity target is incomplete: " + ", ".join(missing)
        )
    return payload


def verify() -> dict[str, Any]:
    targets = _targets()
    expected = targets["render_api"]
    url = str(expected["url"]).rstrip("/") + "/health/details"

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "KyreSportsAI-ProductionIdentityVerify/1.0",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    runtime = payload.get("runtime") or {}

    observed = {
        "service_id": str(runtime.get("service_id") or ""),
        "source_branch": str(runtime.get("deploy_branch") or ""),
        "certified_commit": str(runtime.get("deploy_commit") or ""),
        "branch_aligned": runtime.get("branch_aligned"),
        "observability_version": payload.get("observability_version"),
    }

    if observed["service_id"] != expected["service_id"]:
        raise ProductionIdentityFailure(
            f"Render service ID drift: expected={expected['service_id']!r} "
            f"actual={observed['service_id']!r}"
        )
    if observed["source_branch"] != expected["source_branch"]:
        raise ProductionIdentityFailure(
            f"Render branch drift: expected={expected['source_branch']!r} "
            f"actual={observed['source_branch']!r}"
        )
    if observed["certified_commit"] != expected["certified_commit"]:
        raise ProductionIdentityFailure(
            f"Render certified commit drift: expected={expected['certified_commit']!r} "
            f"actual={observed['certified_commit']!r}"
        )
    if observed["branch_aligned"] is not True:
        raise ProductionIdentityFailure("Render reports branch alignment false")
    if observed["observability_version"] != OBSERVABILITY_VERSION:
        raise ProductionIdentityFailure(
            "Render observability version drift: "
            f"expected={OBSERVABILITY_VERSION!r} "
            f"actual={observed['observability_version']!r}"
        )

    result = {
        "status": "GREEN",
        "render_url": expected["url"],
        **observed,
    }
    print("DEVSYSTEM_PRODUCTION_IDENTITY_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    verify()
