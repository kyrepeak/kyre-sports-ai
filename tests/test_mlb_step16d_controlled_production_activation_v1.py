from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api import mlb_step16b_production_lifecycle_v1 as lifecycle
from sports_api import mlb_step16d_controlled_production_activation_v1 as step16d


def test_manifest_keeps_continuous_production_fail_closed() -> None:
    manifest = step16d.controlled_production_activation_manifest()
    assert manifest["default_enabled"] is False
    assert manifest["controlled_one_shot_activation_allowed"] is True
    assert manifest["exact_two_cycle_restart_proof_required"] is True
    assert manifest["fenced_lease_required"] is True
    assert manifest["checkpoint_cas_required"] is True
    assert manifest["finally_cleanup_required"] is True
    assert manifest["continuous_production_allowed"] is False
    assert manifest["production_runtime_allowed"] is False
    assert manifest["production_scheduler_allowed"] is False
    assert manifest["public_persistence_api_allowed"] is False
    assert manifest["wagering_allowed"] is False
    assert manifest["future_step16e_final_production_freeze_required"] is True


def test_step16d_is_default_off() -> None:
    assert step16d.step16d_enabled({}) is False
    with pytest.raises(step16d.MLBStep16DActivationDisabledError):
        step16d.validate_step16d_enablement({})


def test_release_revision_must_be_exact_and_immutable() -> None:
    source = {
        step16d.STEP16D_EXPECTED_REVISION_ENV: "a" * 40,
        step16d.RELEASE_BUILD_REVISION_ENV: "b" * 40,
    }
    with pytest.raises(step16d.MLBStep16DActivationIntegrityError):
        step16d._validated_revision(source)

    source[step16d.RELEASE_BUILD_REVISION_ENV] = "a" * 40
    assert step16d._validated_revision(source) == "a" * 40

    source["RENDER_GIT_COMMIT"] = "c" * 40
    with pytest.raises(step16d.MLBStep16DActivationIntegrityError):
        step16d._validated_revision(source)


def test_step16b_binding_identity_is_exact() -> None:
    binding = lifecycle._runtime_binding()
    validated = step16d._validate_runtime_binding(binding)
    assert set(validated) == {
        "scheduler_tick",
        "runtime_supervision",
        "recovery_decision",
        "load_restart_context",
        "restart_inputs",
        "persist_checkpoint",
        "renew_lease",
        "release_lease",
    }
    drifted = dict(binding)
    drifted["persist_checkpoint"] = lambda **_: None
    with pytest.raises(step16d.MLBStep16DActivationIntegrityError):
        step16d._validate_runtime_binding(drifted)


def test_synthetic_checkpoint_envelope_is_frozen_step14a_valid() -> None:
    envelope = step16d._build_checkpoint_envelope(
        slate_date="2026-01-15",
        cycle_number=1,
        prior_recovery_state=None,
    )
    assert envelope["slate_date"] == "2026-01-15"
    assert envelope["cycle_id"] is None
    assert envelope["scheduler_state"] == {
        "last_granted_slot_utc": None,
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }


def _fake_controlled_activation(monkeypatch: pytest.MonkeyPatch, *, fail_cycle_two: bool = False):
    source = {
        step16d.STEP16D_EXPECTED_REVISION_ENV: "d" * 40,
        step16d.RELEASE_BUILD_REVISION_ENV: "d" * 40,
        step16d.STEP16D_CANARY_SLATE_DATE_ENV: "2026-01-15",
    }
    state = {
        "version": 0,
        "checkpoint_id": None,
        "checkpoint_rows": 0,
        "head_rows": 0,
        "lease_rows": 0,
        "released": [],
        "cleanup_called": False,
    }

    def load_restart_context(*, slate_date, owner_id, lease_ttl_seconds, env):
        del owner_id, lease_ttl_seconds, env
        version = state["version"]
        return {
            "slate_date": slate_date,
            "found": version > 0,
            "expected_head_version": version,
            "loaded_checkpoint_version": version if version > 0 else None,
            "checkpoint_id": state["checkpoint_id"],
            "recovery_state_for_restart": None,
            "lease": {
                "lease_key": "fake-lease",
                "owner_id": f"owner-{version}",
                "lease_token": "00000000-0000-0000-0000-000000000001",
                "fencing_generation": version + 1,
            },
        }

    def persist_checkpoint(*, restart_context, checkpoint_envelope, lease_ttl_seconds, env):
        del checkpoint_envelope, lease_ttl_seconds, env
        previous = restart_context["expected_head_version"]
        if fail_cycle_two and previous == 1:
            raise RuntimeError("injected cycle-two failure")
        saved = previous + 1
        state["version"] = saved
        state["checkpoint_id"] = f"checkpoint-{saved}"
        state["checkpoint_rows"] = saved
        state["head_rows"] = 1
        return {
            "previous_checkpoint_version": previous,
            "saved_checkpoint_version": saved,
            "saved_checkpoint_id": state["checkpoint_id"],
            "lease": deepcopy(restart_context["lease"]),
        }

    def release_lease(*, handle, env):
        del env
        state["released"].append(deepcopy(handle))
        state["lease_rows"] = 0
        return True

    fake_binding = {
        "scheduler_tick": lambda **_: None,
        "runtime_supervision": lambda **_: None,
        "recovery_decision": lambda **_: None,
        "load_restart_context": load_restart_context,
        "restart_inputs": lambda *_args, **_kwargs: None,
        "persist_checkpoint": persist_checkpoint,
        "renew_lease": lambda **kwargs: kwargs["handle"],
        "release_lease": release_lease,
    }

    def probe(*, env, checkpoint_key, lease_key):
        del env, checkpoint_key, lease_key
        return {
            "checkpoint_table_present": True,
            "checkpoint_head_table_present": True,
            "lease_table_present": True,
            "checkpoint_rows": state["checkpoint_rows"],
            "head_rows": state["head_rows"],
            "lease_rows": state["lease_rows"],
        }

    def cleanup(*, env, checkpoint_key, lease_key):
        del env, checkpoint_key, lease_key
        state["checkpoint_rows"] = 0
        state["head_rows"] = 0
        state["lease_rows"] = 0
        state["cleanup_called"] = True

    monkeypatch.setattr(step16d, "validate_step16d_enablement", lambda env=None: source)
    monkeypatch.setattr(lifecycle, "get_step16b_runtime_binding", lambda env=None: fake_binding)
    monkeypatch.setattr(step16d, "_validate_runtime_binding", lambda binding: dict(binding))
    monkeypatch.setattr(step16d, "_build_checkpoint_envelope", lambda **kwargs: {"cycle": kwargs["cycle_number"]})
    monkeypatch.setattr(step16d, "_direct_database_probe", probe)
    monkeypatch.setattr(step16d, "_cleanup_canary_rows", cleanup)
    return source, state


def test_controlled_activation_executes_exactly_two_cycles_and_cleans(monkeypatch: pytest.MonkeyPatch) -> None:
    source, state = _fake_controlled_activation(monkeypatch)
    result = step16d.run_step16d_controlled_production_activation(env=source)

    assert result["cycle_count"] == 2
    assert result["cycle_1_saved_version"] == 1
    assert result["cycle_2_recovered_version"] == 1
    assert result["cycle_2_saved_version"] == 2
    assert result["checkpoint_history_rows_before_cleanup"] == 2
    assert result["checkpoint_head_rows_before_cleanup"] == 1
    assert result["checkpoint_rows_after_cleanup"] == 0
    assert result["checkpoint_head_rows_after_cleanup"] == 0
    assert result["lease_rows_after_cleanup"] == 0
    assert result["continuous_production_started"] is False
    assert result["step16e_final_production_freeze_ready"] is True
    assert step16d.validate_step16d_result(result)["result_valid"] is True
    assert state["cleanup_called"] is True
    assert len(state["released"]) == 2


def test_failure_still_releases_and_cleans(monkeypatch: pytest.MonkeyPatch) -> None:
    source, state = _fake_controlled_activation(monkeypatch, fail_cycle_two=True)
    with pytest.raises(RuntimeError, match="injected cycle-two failure"):
        step16d.run_step16d_controlled_production_activation(env=source)
    assert state["cleanup_called"] is True
    assert state["checkpoint_rows"] == 0
    assert state["head_rows"] == 0
    assert state["lease_rows"] == 0
    assert len(state["released"]) >= 2
