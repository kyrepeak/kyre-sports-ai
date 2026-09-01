from __future__ import annotations

from copy import deepcopy
import json

import pytest

from sports_api import mlb_step15_final_live_persistence_release_freeze_v1 as step15c
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS


def _env() -> dict[str, str]:
    return {
        "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED": "true",
        "MLB_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED": "true",
    }


def test_step15c_default_off() -> None:
    assert step15c.step15c_final_live_persistence_freeze_enabled({}) is False


def test_step15c_requires_parent_smoke_gate() -> None:
    with pytest.raises(step15c.MLBStep15CReleaseFreezeDisabledError):
        step15c.final_live_persistence_release_manifest(
            env={"MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED": "true"}
        )


def test_step15c_refuses_production_switches() -> None:
    env = _env()
    env["MLB_PRODUCTION_RUNTIME_ENABLED"] = "true"
    with pytest.raises(step15c.MLBStep15CReleaseFreezeDisabledError):
        step15c.final_live_persistence_release_manifest(env=env)


def test_final_live_evidence_loads_and_validates() -> None:
    evidence = step15c.load_final_live_evidence()
    validated = step15c.validate_final_live_evidence(evidence)
    assert validated == evidence
    assert evidence["evidence_content_sha256"] == (
        step15c.FINAL_LIVE_EVIDENCE_CONTENT_SHA256
    )


def test_evidence_hash_ignores_observation_timestamp(tmp_path) -> None:
    evidence = step15c.load_final_live_evidence()
    evidence["observed_at_utc"] = "2099-01-01T00:00:00Z"
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    assert step15c.load_final_live_evidence(str(path))["observed_at_utc"] == (
        "2099-01-01T00:00:00Z"
    )


def test_evidence_rejects_project_drift() -> None:
    evidence = deepcopy(step15c.load_final_live_evidence())
    evidence["supabase_project"]["ref"] = "wrong"
    with pytest.raises(step15c.MLBStep15CReleaseFreezeIntegrityError):
        step15c.validate_final_live_evidence(evidence)


def test_evidence_rejects_nonempty_runtime_tables() -> None:
    evidence = deepcopy(step15c.load_final_live_evidence())
    evidence["live_final_state"]["row_counts"]["mlb_runtime_checkpoints"] = 1
    with pytest.raises(step15c.MLBStep15CReleaseFreezeIntegrityError):
        step15c.validate_final_live_evidence(evidence)


def test_evidence_rejects_client_schema_access() -> None:
    evidence = deepcopy(step15c.load_final_live_evidence())
    evidence["access_boundary"]["anon_schema_usage"] = True
    with pytest.raises(step15c.MLBStep15CReleaseFreezeIntegrityError):
        step15c.validate_final_live_evidence(evidence)


def test_evidence_rejects_activation_drift() -> None:
    evidence = deepcopy(step15c.load_final_live_evidence())
    evidence["activation_boundary"]["production_runtime"] = True
    with pytest.raises(step15c.MLBStep15CReleaseFreezeIntegrityError):
        step15c.validate_final_live_evidence(evidence)


def test_release_manifest_freezes_step15_and_keeps_activation_off() -> None:
    manifest = step15c.final_live_persistence_release_manifest(
        env=_env(), generated_at_utc="2026-09-01T21:00:00+00:00"
    )
    assert manifest["final_certification_marker"] == (
        "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_GREEN"
    )
    assert manifest["runtime_mode"] == "SHADOW_ONLY"
    assert manifest["phase_boundary"]["step15_complete_and_frozen"] is True
    assert manifest["live_database_contract"]["all_required_tables_present"] is True
    assert manifest["live_database_contract"]["all_runtime_tables_empty_at_freeze"] is True
    assert manifest["activation_contract"]["production_runtime_enabled"] is False
    assert manifest["activation_contract"]["production_scheduler_started"] is False
    assert manifest["activation_contract"]["provider_calls"] == 0
    assert manifest["activation_contract"]["sportsbook_calls"] == 0


def test_release_manifest_hash_is_timestamp_independent() -> None:
    first = step15c.final_live_persistence_release_manifest(
        env=_env(), generated_at_utc="2026-09-01T21:00:00+00:00"
    )
    second = step15c.final_live_persistence_release_manifest(
        env=_env(), generated_at_utc="2026-09-01T22:00:00+00:00"
    )
    assert first["release_manifest_sha256"] == second["release_manifest_sha256"]


def test_step15c_preserves_all_protected_invariants() -> None:
    manifest = step15c.final_live_persistence_release_manifest(env=_env())
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False
