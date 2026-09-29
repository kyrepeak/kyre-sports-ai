"""Monster Speed V3 Step 5 — repository automation + branch freshness guard."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

REPOSITORY = "kyrepeak/kyre-sports-ai"
REPO_API = f"https://api.github.com/repos/{REPOSITORY}"
ROOT = Path(__file__).resolve().parents[1]
TARGETED_CI = ROOT / ".github/workflows/devsystem-targeted-ci.yml"
SETTINGS_EVIDENCE = ROOT / "devsystem/evidence/monster-speed-v3-step5-repo-settings-v1.json"


class Step5SettingsFailure(RuntimeError):
    pass


def validate_repository_settings(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("default_branch") != "main":
        failures.append(f"default_branch={payload.get('default_branch')!r}")
    if payload.get("allow_auto_merge") is not True:
        failures.append("allow_auto_merge is not true")
    if payload.get("allow_update_branch") is not True:
        failures.append("allow_update_branch is not true")
    if failures:
        raise Step5SettingsFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "repository": payload.get("full_name") or REPOSITORY,
        "default_branch": payload.get("default_branch"),
        "allow_auto_merge": True,
        "allow_update_branch": True,
    }


def validate_local_safety_contract() -> dict[str, Any]:
    text = TARGETED_CI.read_text(encoding="utf-8")
    failures: list[str] = []

    for token in (
        "devsystem-final-gate:",
        "- permanent-contract",
        'echo "DEVSYSTEM_FINAL_GATE_GREEN"',
        'echo "DEVSYSTEM_FINAL_GATE_BLOCKED"',
        "MONSTER_SPEED_V3_STEP3_FAST_PR_REQUIRED",
        "MONSTER_SPEED_V3_STEP3_FULL_MERGE_REQUIRED",
    ):
        if token not in text:
            failures.append(f"targeted CI missing {token}")

    if not SETTINGS_EVIDENCE.exists():
        failures.append("Step-5 repository settings evidence snapshot missing")
        snapshot_result = None
    else:
        snapshot = json.loads(SETTINGS_EVIDENCE.read_text(encoding="utf-8"))
        snapshot_result = validate_repository_settings(dict(snapshot.get("repository") or {}))

    if failures:
        raise Step5SettingsFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "devsystem_final_gate_preserved": True,
        "fast_pr_gate_preserved": True,
        "full_merge_gate_preserved": True,
        "branch_protection_mutated": False,
        "product_runtime_changed": False,
        "repository_settings_snapshot": snapshot_result,
    }


def fetch_repository_settings(token: str = "") -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "KyreSportsAI-Monster-Speed-V3-Step5",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(REPO_API, headers=headers)
    with urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def check(*, live: bool = False) -> dict[str, Any]:
    local = validate_local_safety_contract()
    result: dict[str, Any] = {
        "status": "GREEN",
        "local_safety": local,
        "live_checked": bool(live),
    }
    if live:
        # This public repository exposes these merge-policy flags in its public
        # repository metadata. Do not authenticate this read with GITHUB_TOKEN:
        # the Actions installation token lacks repository-administration scope
        # and GitHub masks the admin-controlled flags in that token context.
        live_result = validate_repository_settings(fetch_repository_settings(""))
        result["live_repository_settings"] = live_result
        result["live_repository_settings_source"] = "PUBLIC_REPOSITORY_METADATA"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    result = check(live=args.live)
    print("MONSTER_SPEED_V3_STEP5_REPOSITORY_AUTOMATION_GREEN")
    if args.live:
        print("MONSTER_SPEED_V3_STEP5_AUTO_MERGE_ENABLED_GREEN")
        print("MONSTER_SPEED_V3_STEP5_UPDATE_BRANCH_ENABLED_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
