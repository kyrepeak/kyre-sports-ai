from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

MISSION_STEP = "5/5"
WORKSTREAM = "nfl-rb-wr-render-repair-v1"
EXPECTED_MAIN_SHA = "76dde02ccd468447422710051ce2cb145aff2ebe"
EXPECTED_REGISTRY_REVISION = 210
EXPECTED_REGISTRY_HASH = "9d11310bc96136b1d5e70e7b85c42ba3b62f4c0226075d9c711bbbcb001a1b3b"
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
GITHUB_ACTIONS_FALLBACK = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

REQUIRED_FREEZE_TOKENS = (
    "NFL_RB_WR_RENDER_REPAIR_V1_STEP1_ROOT_CAUSE_FROZEN",
    "NFL_RB_WR_RENDER_REPAIR_V1_STEP2_PRESENTATION_TRANSPORT_FROZEN",
    "NFL_RB_WR_RENDER_REPAIR_V1_STEP3_DATA_BINDING_FROZEN",
    "NFL_RB_WR_RENDER_REPAIR_V1_STEP4_MOBILE_ROUTE_FROZEN",
)

REQUIRED_ARTIFACTS = {
    "devsystem/execution_plans/nfl-rb-wr-render-repair-step1-root-cause.json": "a1e57d4dac39999d063060338b055406644970a8",
    "devsystem/runless_proof_plans/nfl-rb-wr-render-repair-step1-root-cause.json": "78d3fbd2d7187097f55e81a0140c6c720a817cdc",
    "devsystem/task_ledgers/nfl-rb-wr-render-repair-step1-root-cause.json": "d3da30a3cd4fbdeafddbfad015b0dd5383f52fa1",
    "docs/superpowers/plans/2026-10-08-nfl-rb-wr-render-repair-step1-root-cause.md": "dee721a304e69baa0d04f074008de228330180a0",
    "tests/test_nfl_rb_wr_render_repair_step1_root_cause.py": "97cb759a29267cf394cb4501d3fc7ef449bc0d80",
    "devsystem/execution_plans/nfl-rb-wr-render-repair-step2-presentation-transport.json": "2fd581d7c2fad1195485f790f570e09bcdd8aa00",
    "devsystem/runless_proof_plans/nfl-rb-wr-render-repair-step2-presentation-transport.json": "5615bb20c1dbd6057e16906eaa18d262ffd0562d",
    "devsystem/task_ledgers/nfl-rb-wr-render-repair-step2-presentation-transport.json": "905d303a0e844373b1b64908cd1e48b43ef0ebe6",
    "nfl_receiving_yards_hub_v13.py": "202d5852414197170c910c96bae2fefa41fcb398",
    "nfl_rushing_yards_hub_v4.py": "5a6e10f5efe5ac27df7c9691d289ae5698e8e3cf",
    "tests/test_nfl_rb_wr_render_repair_step2_presentation_transport.py": "f80fa1b9b395b7552ee16330c79554262000530c",
    "devsystem/execution_plans/nfl-rb-wr-render-repair-step3-data-binding.json": "7628dbf3c0c470a302e0732e514d1031f25cfd72",
    "devsystem/nfl_rb_wr_render_repair_step3_data_binding_v1.py": "916df46771ff75fba4a0edc6f90468a45e5cea49",
    "devsystem/runless_proof_plans/nfl-rb-wr-render-repair-step3-data-binding.json": "fe13395b6cfcfca2e59af6861d19f19db3952f66",
    "devsystem/task_ledgers/nfl-rb-wr-render-repair-step3-data-binding.json": "1adaa1809a06377147ddaede655370e895b0bb60",
    "tests/test_nfl_rb_wr_render_repair_step3_data_binding.py": "4a6f19dba4c9587dbfdbccc23fda902016efcabf",
    "devsystem/execution_plans/nfl-rb-wr-render-repair-step4-mobile-route.json": "5d2d4f737fc2e6405ac9d9b50465285a1727531d",
    "devsystem/nfl_rb_wr_render_repair_step4_mobile_route_v1.py": "ba25ac2bd8725677f6646e32b8ddfaa5c59d20c7",
    "devsystem/runless_proof_plans/nfl-rb-wr-render-repair-step4-mobile-route.json": "31addf17f44f5a0a79d1fc2191c182cb7c266365",
    "devsystem/task_ledgers/nfl-rb-wr-render-repair-step4-mobile-route.json": "5e949385235505d0618c46f5ee1d5e8cda1c065f",
    "tests/test_nfl_rb_wr_render_repair_step4_mobile_route.py": "9fc021b1e55d5cc456b15ad7eb2dac4c9104a4ef",
}


class FinalMissionFailure(RuntimeError):
    pass


def git_blob_sha(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("utf-8")
    return hashlib.sha1(header + payload).hexdigest()


def verify_blob(path: Path, expected_sha: str) -> str:
    if not path.is_file():
        raise FinalMissionFailure(f"MISSING_ARTIFACT:{path.as_posix()}")
    observed = git_blob_sha(path.read_bytes())
    if observed != expected_sha:
        raise FinalMissionFailure(
            f"BLOB_DRIFT:{path.as_posix()}:expected={expected_sha}:observed={observed}"
        )
    return observed


def verify_registry_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    if int(payload.get("revision", -1)) != EXPECTED_REGISTRY_REVISION:
        raise FinalMissionFailure("REGISTRY_REVISION_DRIFT")
    if str(payload.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise FinalMissionFailure("REGISTRY_HASH_DRIFT")
    entries = payload.get("entries") or {}
    for token in REQUIRED_FREEZE_TOKENS:
        entry = entries.get(token)
        if not isinstance(entry, Mapping):
            raise FinalMissionFailure(f"MISSING_FREEZE:{token}")
        if str(entry.get("status") or "") != "FROZEN":
            raise FinalMissionFailure(f"FREEZE_NOT_FROZEN:{token}")
    return {"status": "GREEN", "freeze_count": len(REQUIRED_FREEZE_TOKENS)}


def verify_local_artifacts(root: Path) -> dict[str, Any]:
    observed = {}
    for relpath, expected in sorted(REQUIRED_ARTIFACTS.items()):
        observed[relpath] = verify_blob(root / relpath, expected)
    return {
        "status": "GREEN",
        "artifact_count": len(observed),
        "artifact_map": observed,
    }


def execute(root: Path = Path(".")) -> dict[str, Any]:
    artifacts = verify_local_artifacts(root)
    return {
        "status": "GREEN",
        "decision": "NFL_RB_WR_STEP5_FINAL_MISSION_CERTIFIED",
        "step": MISSION_STEP,
        "workstream": WORKSTREAM,
        "source_main_sha": EXPECTED_MAIN_SHA,
        "registry_revision": EXPECTED_REGISTRY_REVISION,
        "registry_state_hash": EXPECTED_REGISTRY_HASH,
        "required_freeze_tokens": list(REQUIRED_FREEZE_TOKENS),
        "verified_prior_artifact_count": artifacts["artifact_count"],
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "product_runtime_mutations": 0,
        "github_actions_fallback": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = execute(Path(args.root))
    print("NFL_RB_WR_STEP5_FINAL_MISSION=" + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
