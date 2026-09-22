"""Certification artifact builder for WNBA Step 12B live runtime assembly."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

from sports_api import wnba_step12b_live_runtime_assembly as step12b

ARTIFACT = Path("step12b-live-runtime-cert.json")
TEST_HELPERS = Path("tests/test_wnba_step12b_live_runtime_assembly.py")


def _load_helpers():
    spec = importlib.util.spec_from_file_location("step12b_cert_helpers", TEST_HELPERS)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Step 12B certification helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    helpers = _load_helpers()
    evaluated = datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
    dk_bridge = helpers.bridge(
        helpers.dk.PROVIDER,
        [helpers.record(evaluated=evaluated)],
        evaluated,
    )
    fd_bridge = helpers.bridge(
        helpers.fd.PROVIDER,
        [helpers.record(evaluated=evaluated)],
        evaluated,
    )
    dk_calls: list[dict] = []
    fd_calls: list[dict] = []
    projection_calls: list[dict] = []

    def projection_loader(**kwargs):
        projection_calls.append(kwargs)
        return helpers.distribution(kwargs["player_id"])

    request = step12b.build_step12b_request(
        season=2026,
        slate_date="2026-08-28",
        evaluated_at=evaluated,
    )
    result = step12b.run_step12b_live_runtime_job(
        request,
        env=helpers.env(),
        draftkings_fetcher=helpers.fetcher_for(dk_bridge, dk_calls),
        fanduel_fetcher=helpers.fetcher_for(fd_bridge, fd_calls),
        projection_loader=projection_loader,
    )

    assert step12b.STEP12A_FROZEN_SHA == "4523abb8b230e8e29d9f9d298232dfb8948fc883"
    assert step12b.DEFAULT_ENABLED is False
    assert step12b.PRODUCTION_ACTIVATION_ALLOWED is False
    assert step12b.BACKGROUND_SCHEDULER_ALLOWED is False
    assert step12b.PERSISTENCE_ALLOWED is False
    assert step12b.SUPABASE_WRITE_ALLOWED is False
    assert step12b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED is False
    assert step12b.WAGERING_ALLOWED is False
    assert step12b.CERTIFIED_SIMULATIONS == 5_000_000
    assert result["status"] == "healthy"
    assert result["health"] == "healthy"
    assert result["market_overlap"]["exact_line_multibook_group_count"] == 1
    assert result["projection_assembly"]["built_target_count"] == 1
    assert result["runtime_summary"]["step8_distribution_count"] == 1
    assert result["runtime_summary"]["qualified_prop_count"] == 1
    assert len(dk_calls) == 1
    assert len(fd_calls) == 1
    assert len(projection_calls) == 1
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
        "paid_odds_vendor_used",
        "basketball_model_modified",
        "step8_distribution_modified_after_generation",
    ):
        assert result["guardrails"][key] is False, key

    artifact = {
        "data_type": "wnba_step12b_live_runtime_assembly_certification",
        "schema_version": step12b.SCHEMA_VERSION,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "step12a_frozen_sha": step12b.STEP12A_FROZEN_SHA,
        "step11e_frozen_sha": step12b.STEP11E_FROZEN_SHA,
        "step8_frozen_sha": step12b.STEP8_FROZEN_SHA,
        "certified_simulations_per_target": step12b.CERTIFIED_SIMULATIONS,
        "request_content_sha256": result["request_content_sha256"],
        "runtime_content_sha256": result["runtime_content_sha256"],
        "status": result["status"],
        "health": result["health"],
        "provider_discovery": {
            "draftkings_calls": len(dk_calls),
            "fanduel_calls": len(fd_calls),
            "discovery_reused_without_second_fetch": result["provider_discovery"][
                "sportsbook_network_fetches_reused_in_step11_tick"
            ],
        },
        "market_overlap": result["market_overlap"],
        "projection_assembly": result["projection_assembly"],
        "runtime_summary": result["runtime_summary"],
        "lineage": result["lineage"],
        "guardrails": result["guardrails"],
        "certified": True,
    }
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print("STEP12B_LIVE_RUNTIME_ASSEMBLY_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
