"""WNBA Step 6P full Phase 6 certification and master-freeze contract.

Step 6P certifies the *engineering state* of Phase 6 without activating
production.  The distinction is deliberate:

* Steps 6A/6B are retired legacy Render/SportsGameOdds paths.
* Steps 6C-6O form the active Kyre-owned market, reconciliation, guarded
  canary, activation-interlock, refresh, scheduler, observability, and
  activation/rollback architecture.
* A safe-deferred Step 6O state is a valid Phase 6 engineering completion
  state.  It does not mean the production scheduler is live.

This module is read-only and network-free.  It does not provision hosting,
mutate environment variables, contact DraftKings, write the Kyre feed, start a
scheduler, run Monte Carlo, or perform wager actions.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any

from sports_api.wnba_step6o_activation_rollback_package import (
    build_step6o_activation_rollback_package,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6P Phase 6 certification + master freeze"
MODEL_VERSION = "wnba_step_6p_phase6_certification_v1"
SCHEMA_VERSION = MODEL_VERSION

BASELINE_STEP6O_REVISION = "b149ef97020db616c32c5e43457ce5f955f9b2f0"
FROZEN_STEP6I_REVISION = "2195b1839f47745737c2d0e788c319743cda3ee0"
CORRECTED_STEP6M_REVISION = "1115ef42d522937a2bf17afaf3f73ff990daa054"
FROZEN_STEP6N_REVISION = "a5bdcbbd5312c0db0dd931d71844eed865542908"

CERTIFIED_REVISION_ENV = "WNBA_STEP6P_CERTIFIED_REVISION"


class WNBAStep6PCertificationError(RuntimeError):
    pass


class WNBAStep6PNotCertifiedError(WNBAStep6PCertificationError):
    pass


PHASE6_STEPS: tuple[dict[str, Any], ...] = (
    {
        "step": "6A",
        "state": "retired_legacy",
        "role": "legacy Render credential preflight",
        "workflow": ".github/workflows/wnba-step-6a-render-preflight.yml",
        "module": None,
        "successor": "6C",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6B",
        "state": "retired_legacy",
        "role": "legacy Render provisioning path",
        "workflow": ".github/workflows/wnba-step-6b-approved-provision.yml",
        "module": None,
        "successor": "6C",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6C",
        "state": "active_frozen_contract",
        "role": "Kyre-owned market feed architecture and durable storage contract",
        "workflow": ".github/workflows/wnba-step-6c.yml",
        "module": "sports_api/collectors/wnba_kyre_market_feed.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6D",
        "state": "active_frozen_contract",
        "role": "direct DraftKings GET adapter into Kyre-owned market schema",
        "workflow": ".github/workflows/wnba-step-6d.yml",
        "module": "sports_api/wnba_step6d_direct_integration.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6E",
        "state": "active_frozen_contract",
        "role": "read-only DraftKings endpoint discovery",
        "workflow": ".github/workflows/wnba-step-6e.yml",
        "module": "sports_api/wnba_draftkings_endpoint_discovery.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6F",
        "state": "active_frozen_contract",
        "role": "read-only WNBA player-prop market discovery",
        "workflow": ".github/workflows/wnba-step-6f.yml",
        "module": "sports_api/wnba_draftkings_prop_market_discovery.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6G",
        "state": "active_frozen_contract",
        "role": "shadow-only DraftKings ingestion validation",
        "workflow": ".github/workflows/wnba-step-6g.yml",
        "module": "sports_api/wnba_draftkings_shadow_ingestion.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6H",
        "state": "active_frozen_contract",
        "role": "official WNBA roster/slate reconciliation",
        "workflow": ".github/workflows/wnba-step-6h.yml",
        "module": "sports_api/wnba_official_reconciliation.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6I",
        "state": "active_frozen_contract",
        "role": "guarded reconciled DraftKings-to-Kyre sync authority",
        "workflow": ".github/workflows/wnba-step-6i.yml",
        "module": "sports_api/wnba_reconciled_direct_sync.py",
        "frozen_revision": FROZEN_STEP6I_REVISION,
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6J",
        "state": "implementation_frozen_live_canary_deferred",
        "role": "one-shot durable persistent-disk canary with automatic rollback",
        "workflow": ".github/workflows/wnba-step-6j.yml",
        "module": "sports_api/wnba_step6j_canary_activation.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6K",
        "state": "active_frozen_contract",
        "role": "post-canary fail-closed scheduler authorization interlock",
        "workflow": ".github/workflows/wnba-step-6k.yml",
        "module": "sports_api/wnba_step6k_activation_preflight.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6L",
        "state": "active_frozen_contract",
        "role": "guarded production Kyre-feed refresh authority",
        "workflow": ".github/workflows/wnba-step-6l.yml",
        "module": "sports_api/wnba_step6l_production_feed_refresh.py",
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6M",
        "state": "active_frozen_contract",
        "role": "Kyre-only scheduler orchestration preserving Step 5P/5Q guards",
        "workflow": ".github/workflows/wnba-step-6m.yml",
        "module": "sports_api/wnba_step6m_scheduler_orchestration.py",
        "frozen_revision": CORRECTED_STEP6M_REVISION,
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6N",
        "state": "active_frozen_contract",
        "role": "read-only production observability and incident classification",
        "workflow": ".github/workflows/wnba-step-6n.yml",
        "module": "sports_api/wnba_step6n_production_observability.py",
        "frozen_revision": FROZEN_STEP6N_REVISION,
        "paid_odds_vendor_allowed": False,
    },
    {
        "step": "6O",
        "state": "active_frozen_contract",
        "role": "deterministic activation and emergency rollback package",
        "workflow": ".github/workflows/wnba-step-6o.yml",
        "module": "sports_api/wnba_step6o_activation_rollback_package.py",
        "frozen_revision": BASELINE_STEP6O_REVISION,
        "paid_odds_vendor_allowed": False,
    },
)


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _step_ids() -> list[str]:
    return [str(row["step"]) for row in PHASE6_STEPS]


def _phase6_inventory_valid() -> bool:
    expected = [f"6{chr(code)}" for code in range(ord("A"), ord("P"))]
    actual = _step_ids()
    return actual == expected and len(set(actual)) == len(expected)


def build_step6p_phase6_certification(
    *,
    env: Mapping[str, str] | None = None,
    step6o_getter: Callable[..., dict[str, Any]] = build_step6o_activation_rollback_package,
) -> dict[str, Any]:
    """Build the network-free Phase 6 master certification record."""
    environment = _environment(env)
    step6o = step6o_getter(env=environment)
    step6o_semantics = step6o.get("semantics") or {}
    step6o_manifest = step6o.get("manifest") or {}

    retired = [row for row in PHASE6_STEPS if row["state"] == "retired_legacy"]
    active = [row for row in PHASE6_STEPS if row["state"] != "retired_legacy"]
    configured_revision = _clean(environment.get(CERTIFIED_REVISION_ENV))

    checks = {
        "complete_6a_through_6o_inventory": _phase6_inventory_valid(),
        "legacy_6a_6b_retired": [row["step"] for row in retired] == ["6A", "6B"],
        "legacy_successor_is_6c": all(row.get("successor") == "6C" for row in retired),
        "all_active_phase6_steps_disallow_paid_odds_vendor": all(
            row.get("paid_odds_vendor_allowed") is False for row in active
        ),
        "step6o_package_ready": step6o.get("package_ready") is True,
        "step6o_preserves_separate_live_activation_boundary": step6o_semantics.get(
            "live_activation_requires_separate_operator_boundary"
        )
        is True,
        "step6o_rollback_disables_runtime_first": step6o_semantics.get(
            "rollback_disables_runtime_before_refresh_or_image_recovery"
        )
        is True,
        "step6o_rollback_preserves_persistent_storage": step6o_semantics.get(
            "rollback_preserves_persistent_storage"
        )
        is True,
    }
    phase6_engineering_certified = all(checks.values())

    step6o_state = str(step6o.get("state") or "unknown")
    live_activation_ready = phase6_engineering_certified and step6o.get("live_activation_ready") is True
    live_activation_deferred = phase6_engineering_certified and not live_activation_ready
    safe_deferred = phase6_engineering_certified and step6o_state == "safe_deferred"

    if not phase6_engineering_certified:
        state = "phase6_certification_blocked"
    elif live_activation_ready:
        state = "phase6_complete_activation_ready"
    elif safe_deferred:
        state = "phase6_complete_safe_deferred"
    else:
        state = "phase6_complete_live_activation_blocked"

    inventory_manifest = [
        {
            "step": row["step"],
            "state": row["state"],
            "role": row["role"],
            "workflow": row["workflow"],
            "module": row.get("module"),
            "frozen_revision": row.get("frozen_revision"),
            "successor": row.get("successor"),
        }
        for row in PHASE6_STEPS
    ]
    manifest_payload = {
        "schema_version": SCHEMA_VERSION,
        "baseline_step6o_revision": BASELINE_STEP6O_REVISION,
        "frozen_anchors": {
            "step6i": FROZEN_STEP6I_REVISION,
            "corrected_step6m": CORRECTED_STEP6M_REVISION,
            "step6n": FROZEN_STEP6N_REVISION,
            "step6o": BASELINE_STEP6O_REVISION,
        },
        "step6o_manifest_sha256": step6o_manifest.get("manifest_sha256"),
        "phase6_inventory": inventory_manifest,
        "master_safety_policy": {
            "sportsgameodds_retired": True,
            "kyre_owned_market_path_only": True,
            "production_runtime_default_off": True,
            "step6j_canary_required_before_scheduler_authorization": True,
            "step6l_refresh_requires_step6k_authorization": True,
            "step6m_scheduler_requires_step6k_and_step6l": True,
            "step6n_observability_is_read_only": True,
            "step6o_activation_requires_separate_operator_boundary": True,
            "persistent_storage_preserved_on_rollback": True,
        },
    }
    master_manifest_sha256 = _hash(manifest_payload)

    blocking = [name for name, passed in checks.items() if not passed]

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6p_phase6_master_certification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": state,
        "phase6_engineering_certified": phase6_engineering_certified,
        "production_live": False,
        "live_activation_ready": live_activation_ready,
        "live_activation_deferred": live_activation_deferred,
        "safe_deferred": safe_deferred,
        "certified_revision_from_environment": configured_revision,
        "baseline_step6o_revision": BASELINE_STEP6O_REVISION,
        "checks": checks,
        "blocking_reasons": blocking,
        "step_6o": {
            "state": step6o_state,
            "package_ready": step6o.get("package_ready"),
            "live_activation_ready": step6o.get("live_activation_ready"),
            "manifest_sha256": step6o_manifest.get("manifest_sha256"),
            "activation_blocking_reasons": step6o.get("activation_blocking_reasons"),
        },
        "phase6_inventory": inventory_manifest,
        "master_freeze": {
            **manifest_payload,
            "master_manifest_sha256": master_manifest_sha256,
            "canonical_json_sha256": master_manifest_sha256,
        },
        "semantics": {
            "phase6_complete_does_not_mean_production_live": True,
            "safe_deferred_is_a_valid_engineering_completion_state": True,
            "step6a_step6b_must_remain_retired": True,
            "sports_game_odds_dependency_retired": True,
            "kyre_owned_market_path_is_authoritative": True,
            "production_runtime_mutated": False,
            "paid_host_created": False,
            "draftkings_called": False,
            "feed_write_performed": False,
            "scheduler_started": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "network_used": False,
            "live_activation_requires_new_explicit_boundary": True,
        },
    }


def require_step6p_phase6_certified(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = build_step6p_phase6_certification(env=env)
    if report.get("phase6_engineering_certified") is not True:
        raise WNBAStep6PNotCertifiedError(
            "WNBA Phase 6 certification is blocked: "
            + "; ".join(report.get("blocking_reasons") or ["unknown blocker"])
        )
    return report
