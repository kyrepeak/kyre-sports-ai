"""Certification artifact builder for WNBA Step 12A shadow-runner deployment readiness."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

ARTIFACT = Path("step12a-shadow-runner-cert.json")


def _env() -> dict[str, str]:
    return {
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED": "true",
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED": "true",
        "WNBA_STEP11B_NETWORK_REFRESH_ENABLED": "true",
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
        "WNBA_STEP10_FASTAPI_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
        "WNBA_STEP9_FASTAPI_ENABLED": "true",
        "WNBA_STEP9_THRESHOLD_PRICING_ENABLED": "true",
        "WNBA_STEP9B_MARKET_COMPARISON_ENABLED": "true",
        "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED": "true",
        "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def _step8() -> dict:
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T06:30:00+00:00",
        "game_id": "1022600291",
        "player_id": 1642301,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {"converged": True},
        "distributions": {
            "points": {"probability_mass": [{"value": 20, "probability": 0.36}, {"value": 21, "probability": 0.64}]},
            "rebounds": {"probability_mass": [{"value": 10, "probability": 0.4}, {"value": 11, "probability": 0.6}]},
            "assists": {"probability_mass": [{"value": 4, "probability": 0.4}, {"value": 5, "probability": 0.6}]},
            "points_rebounds_assists": {"probability_mass": [{"value": 39, "probability": 0.4}, {"value": 40, "probability": 0.6}]},
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def main() -> None:
    assert step12a.STEP11E_FROZEN_SHA == "f96d580e398aaa199c424e3b70b7a8f1386a8452"
    assert release.DEFAULT_ENABLED is False
    assert release.PRODUCTION_ACTIVATION_ALLOWED is False
    assert release.BACKGROUND_SCHEDULER_ALLOWED is False
    assert release.PERSISTENCE_ALLOWED is False
    assert release.SUPABASE_WRITE_ALLOWED is False
    assert release.PUBLIC_FASTAPI_ACTIVATION_ALLOWED is False
    assert release.WAGERING_ALLOWED is False

    req = step12a.build_step12a_request(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=[_step8()],
        evaluated_at="2026-08-28T06:50:00+00:00",
    )
    shadow = {
        "shadow_board_content_sha256": "a" * 64,
        "lineage": {
            "step10_pipeline_content_sha256": "b" * 64,
            "step9_ranking_content_sha256": "c" * 64,
        },
    }
    with patch.object(
        step11e.step11d,
        "run_step11d_multibook_shadow_board",
        return_value=shadow,
    ):
        response = step12a.run_step12a_shadow_job(req, env=_env())

    assert response["status"] == "healthy"
    assert response["guardrails"]["external_execution_surface"] is True
    for key in (
        "scheduler_started",
        "background_worker_started",
        "sleep_performed",
        "state_persisted",
        "public_fastapi_route_added",
        "supabase_mutated",
        "persistence_mutated",
        "production_runtime_enabled",
        "production_activation_allowed",
        "wager_action_performed",
        "authentication_used",
        "cookies_used",
        "basketball_projection_changed",
        "step8_distribution_changed",
    ):
        assert response["guardrails"][key] is False, key

    artifact = {
        "data_type": "wnba_step12a_shadow_runner_certification",
        "schema_version": step12a.SCHEMA_VERSION,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "step11e_frozen_sha": step12a.STEP11E_FROZEN_SHA,
        "request_content_sha256": response["request_content_sha256"],
        "runner_content_sha256": response["runner_content_sha256"],
        "status": response["status"],
        "health": response["health"],
        "lineage": response["lineage"],
        "guardrails": response["guardrails"],
        "certified": True,
    }
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print("STEP12A_SHADOW_RUNNER_DEPLOYMENT_READINESS_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
