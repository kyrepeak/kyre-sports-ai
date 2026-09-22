from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step16d_controlled_production_activation as s16d

EXPECTED_TOTAL_REGRESSION_TESTS = 660
NEW_STEP16D_TESTS = 20


def load_live_result(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return s16d.validate_live_activation_result(data)


def build_certification(*, live_result: dict[str, Any]) -> dict[str, Any]:
    manifest = s16d.build_contract_manifest(
        generated_at_utc=os.environ.get("GITHUB_RUN_STARTED_AT")
        or live_result.get("observed_at_utc")
    )
    return {
        "data_type": "wnba_step16d_controlled_production_activation_certification",
        "schema_version": "wnba_step_16d_controlled_production_activation_certification_v1",
        "certified": True,
        "branch": os.environ.get("GITHUB_REF_NAME", s16d.BRANCH),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "contract_id": s16d.CONTRACT_ID,
        "contract_content_sha256": manifest["contract_content_sha256"],
        "live_result_content_sha256": live_result["result_content_sha256"],
        "expected_total_regression_tests": EXPECTED_TOTAL_REGRESSION_TESTS,
        "new_step16d_tests": NEW_STEP16D_TESTS,
        "direct_psycopg_live_connection_certified": True,
        "production_docker_image_execution_certified": True,
        "two_cycle_durable_restart_certified": True,
        "canary_cleanup_zero_residue_certified": True,
        "continuous_production_runtime_started": False,
        "render_hosted_service_activation_certified": False,
        "lineage": manifest["lineage"],
        "activation": live_result["activation"],
        "cycles": live_result["cycles"],
        "cleanup": live_result["cleanup"],
        "safety": live_result["safety"],
        "phase_boundary": live_result["phase_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-result",
        default="step16d-out/step16d-controlled-production-activation-live-result.json",
    )
    parser.add_argument(
        "--output",
        default="step16d-controlled-production-activation-cert.json",
    )
    args = parser.parse_args()
    live = load_live_result(args.live_result)
    cert = build_certification(live_result=live)
    Path(args.output).write_text(
        json.dumps(cert, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "STEP16D_CERTIFIED",
        cert["certified_head_sha"],
        cert["live_result_content_sha256"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
