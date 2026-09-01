from __future__ import annotations

from copy import deepcopy
import json

import pytest

from sports_api import mlb_step15b_live_adapter_transaction_smoke_v1 as step15b


def _env(**extra: str) -> dict[str, str]:
    env = {step15b.STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV: "true"}
    env.update(extra)
    return env


def test_step15b_default_off():
    assert step15b.step15b_live_adapter_smoke_enabled({}) is False
    with pytest.raises(step15b.MLBStep15BLiveSmokeDisabledError):
        step15b.live_adapter_transaction_smoke_manifest(env={})


def test_step15b_refuses_production_switches():
    with pytest.raises(step15b.MLBStep15BLiveSmokeDisabledError):
        step15b.live_adapter_transaction_smoke_manifest(
            env=_env(MLB_PRODUCTION_RUNTIME_ENABLED="true")
        )


def test_live_evidence_hash_and_shape_are_frozen():
    evidence = step15b.load_live_smoke_evidence()
    validated = step15b.validate_live_smoke_evidence(evidence)
    assert validated == evidence
    assert evidence["evidence_content_sha256"] == step15b.LIVE_EVIDENCE_CONTENT_SHA256
    assert evidence["supabase_project"]["postgres_version"] == "17.6"
    assert evidence["supabase_project"]["primary"] is True


def test_live_evidence_proves_checkpoint_transaction_semantics():
    checkpoint = step15b.load_live_smoke_evidence()["checkpoint_smoke"]
    assert checkpoint["baseline_all_step14_tables_empty"] is True
    assert checkpoint["version_1_created"] is True
    assert checkpoint["load_round_trip_exact"] is True
    assert checkpoint["idempotent_repeat_history_rows"] == 1
    assert checkpoint["version_2_advanced"] is True
    assert checkpoint["history_rows_after_advance"] == 2
    assert checkpoint["stale_cas_rejected"] is True
    assert checkpoint["stale_transaction_rolled_back"] is True
    assert checkpoint["history_rows_after_stale_attempt"] == 2
    assert checkpoint["stale_history_row_survived"] is False


def test_live_evidence_proves_lease_fencing_semantics():
    lease = step15b.load_live_smoke_evidence()["lease_smoke"]
    assert lease["initial_acquire_generation"] == 1
    assert lease["duplicate_active_acquire_rows"] == 0
    assert lease["owner_a_renew_succeeded"] is True
    assert lease["wrong_owner_renew_rows"] == 0
    assert lease["test_only_expiry_forced"] is True
    assert lease["takeover_generation"] == 2
    assert lease["stale_owner_release_rows"] == 0
    assert lease["current_owner_release_succeeded"] is True


def test_live_evidence_proves_outer_rollback_cleanup():
    cleanup = step15b.load_live_smoke_evidence()["cleanup"]
    assert cleanup["cleanup_method"] == "outer_transaction_rollback"
    assert cleanup["live_step14_tables_returned_to_empty_state"] is True
    assert cleanup["checkpoint_history_rows_after_cleanup"] == 0
    assert cleanup["checkpoint_heads_rows_after_cleanup"] == 0
    assert cleanup["lease_rows_after_cleanup"] == 0
    assert cleanup["marker"] == "MLB_STEP15B_LIVE_TRANSACTION_SMOKE_EXECUTED"


def test_execution_boundary_keeps_runtime_and_production_off():
    boundary = step15b.load_live_smoke_evidence()["execution_boundary"]
    assert boundary["live_database_used"] is True
    assert boundary["frozen_adapter_sql_semantics_executed_live"] is True
    assert boundary["connected_supabase_sql_surface_used"] is True
    assert boundary["single_explicit_transaction_used"] is True
    assert boundary["transaction_rolled_back"] is True
    assert boundary["python_psycopg_adapter_connected_directly"] is False
    assert boundary["production_scheduler_started"] is False
    assert boundary["global_persistence_runtime_started"] is False
    assert boundary["background_worker_started"] is False
    assert boundary["public_persistence_api_exposed"] is False
    assert boundary["provider_calls"] == 0
    assert boundary["sportsbook_calls"] == 0
    assert boundary["production_activation"] == 0


def test_exact_frozen_step14_sql_fingerprints_match():
    assert step15b.validate_frozen_sql_fingerprints() == step15b.SQL_FINGERPRINTS


def test_manifest_certifies_step15b_and_requires_step15c():
    manifest = step15b.live_adapter_transaction_smoke_manifest(
        env=_env(), generated_at_utc="2026-09-01T20:45:00+00:00"
    )
    assert manifest["runtime_mode"] == "SHADOW_ONLY"
    assert manifest["final_certification_marker"] == (
        "MLB_STEP15B_LIVE_ADAPTER_TRANSACTION_SMOKE_GREEN"
    )
    assert manifest["execution_boundary"]["live_database_transaction_smoke_completed"] is True
    assert manifest["execution_boundary"]["all_smoke_writes_rolled_back"] is True
    assert manifest["execution_boundary"]["production_scheduler_started"] is False
    assert manifest["execution_boundary"]["global_persistence_runtime_started"] is False
    assert manifest["execution_boundary"]["runtime_cycle_executed"] is False
    assert manifest["execution_boundary"]["provider_calls"] == 0
    assert manifest["execution_boundary"]["sportsbook_calls"] == 0
    assert manifest["execution_boundary"]["production_activation"] == 0
    assert manifest["phase_boundary"]["step15b_complete"] is True
    assert manifest["phase_boundary"]["step15c_final_live_persistence_freeze_required"] is True


def test_manifest_hash_is_timestamp_independent():
    one = step15b.live_adapter_transaction_smoke_manifest(
        env=_env(), generated_at_utc="2026-09-01T20:45:00+00:00"
    )
    two = step15b.live_adapter_transaction_smoke_manifest(
        env=_env(), generated_at_utc="2026-09-01T20:46:00+00:00"
    )
    assert one["generated_at_utc"] != two["generated_at_utc"]
    assert one["smoke_manifest_sha256"] == two["smoke_manifest_sha256"]


def test_tampered_evidence_fails_closed(tmp_path):
    evidence = step15b.load_live_smoke_evidence()
    tampered = deepcopy(evidence)
    tampered["lease_smoke"]["takeover_generation"] = 3
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(step15b.MLBStep15BLiveSmokeIntegrityError):
        step15b.load_live_smoke_evidence(str(path))
