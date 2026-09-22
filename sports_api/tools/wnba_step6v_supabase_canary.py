"""Step 6V GitHub -> Supabase live Step 6J canary operator.

This operator is intentionally narrow. It never provisions Supabase, installs
schema, starts the WNBA scheduler, enables production runtime, runs Monte Carlo,
or places wagers. It expects an already-created Supabase project with the Step
6R schema installed.

The process-wide/base environment must begin with every temporary Step 6J write
switch OFF and production runtime OFF. The operator copies that environment,
enables the Step 6J/6I switches only in a private mapping passed to the Step 6S
canary function, then verifies the completed durable state with a separate
all-OFF mapping through Step 6T. No temporary switch is written back to
os.environ or any remote service.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV as PRODUCTION_RUNTIME_ENV
from sports_api.wnba_reconciled_direct_sync import RECONCILED_SYNC_ENABLED_ENV
from sports_api.wnba_step6d_direct_integration import (
    DIRECT_SYNC_ENABLED_ENV,
    DIRECT_SYNC_PROVIDER_ENV,
    SUPPORTED_DIRECT_PROVIDER,
)
from sports_api.wnba_step6j_canary_activation import ACTIVATION_ID_ENV, CANARY_ENABLED_ENV
from sports_api.wnba_step6q_durable_storage import STORAGE_BACKEND_ENV, SUPABASE_BACKEND
from sports_api.wnba_step6r_supabase_storage import (
    SUPABASE_SECRET_KEY_ENV,
    SUPABASE_URL_ENV,
    get_step6r_supabase_storage_status,
)
from sports_api.wnba_step6s_canary_storage import run_storage_aware_step6j_canary
from sports_api.wnba_step6t_canary_evidence import verify_step6t_canary_evidence

MODEL_SOURCE = "Kyre Sports API WNBA Step 6V GitHub Supabase canary operator"
MODEL_VERSION = "wnba_step_6v_github_supabase_canary_operator_v1"
SCHEMA_VERSION = MODEL_VERSION

_ACTIVATION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{6,160}$")
_DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class WNBAStep6VCanaryError(RuntimeError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_environment(env: Mapping[str, str] | None) -> dict[str, str]:
    return dict(os.environ if env is None else env)


def _require_base_fail_closed(environment: Mapping[str, str]) -> None:
    if _truthy(environment.get(PRODUCTION_RUNTIME_ENV)):
        raise WNBAStep6VCanaryError("Step 6V refuses to run while WNBA production runtime is enabled.")
    already_enabled = [
        name
        for name in (CANARY_ENABLED_ENV, DIRECT_SYNC_ENABLED_ENV, RECONCILED_SYNC_ENABLED_ENV)
        if _truthy(environment.get(name))
    ]
    if already_enabled:
        raise WNBAStep6VCanaryError(
            "Step 6V requires all temporary Step 6J/6I write switches to begin OFF."
        )
    backend = (_clean(environment.get(STORAGE_BACKEND_ENV)) or "filesystem").casefold()
    if backend != SUPABASE_BACKEND:
        raise WNBAStep6VCanaryError(f"{STORAGE_BACKEND_ENV} must be {SUPABASE_BACKEND!r} for Step 6V.")
    readiness = get_step6r_supabase_storage_status(environment)
    if readiness.get("configuration_ready") is not True:
        raise WNBAStep6VCanaryError(
            str(readiness.get("configuration_error") or "Step 6R Supabase configuration is not ready.")
        )


def _validated_inputs(*, date: str, season: int, activation_id: str) -> tuple[str, int, str]:
    canary_date = _clean(date)
    if not canary_date or not _DATE_RE.fullmatch(canary_date):
        raise WNBAStep6VCanaryError("Step 6V canary date must use YYYY-MM-DD.")
    try:
        canary_season = int(season)
    except (TypeError, ValueError) as exc:
        raise WNBAStep6VCanaryError("Step 6V season must be an integer.") from exc
    if canary_season < 2024 or canary_season > 2100:
        raise WNBAStep6VCanaryError("Step 6V season is outside the supported safety range.")
    canary_id = _clean(activation_id)
    if not canary_id or not _ACTIVATION_ID_RE.fullmatch(canary_id):
        raise WNBAStep6VCanaryError("Step 6V requires a safe one-shot activation id.")
    return canary_date, canary_season, canary_id


def _active_canary_environment(base: Mapping[str, str], activation_id: str) -> dict[str, str]:
    environment = dict(base)
    environment[STORAGE_BACKEND_ENV] = SUPABASE_BACKEND
    environment[PRODUCTION_RUNTIME_ENV] = "false"
    environment[DIRECT_SYNC_ENABLED_ENV] = "true"
    environment[DIRECT_SYNC_PROVIDER_ENV] = SUPPORTED_DIRECT_PROVIDER
    environment[RECONCILED_SYNC_ENABLED_ENV] = "true"
    environment[CANARY_ENABLED_ENV] = "true"
    environment[ACTIVATION_ID_ENV] = activation_id
    return environment


def _verification_environment(base: Mapping[str, str]) -> dict[str, str]:
    environment = dict(base)
    environment[STORAGE_BACKEND_ENV] = SUPABASE_BACKEND
    environment[PRODUCTION_RUNTIME_ENV] = "false"
    environment[DIRECT_SYNC_ENABLED_ENV] = "false"
    environment[RECONCILED_SYNC_ENABLED_ENV] = "false"
    environment[CANARY_ENABLED_ENV] = "false"
    return environment


def _assert_evidence_matches(canary: Mapping[str, Any], evidence: Mapping[str, Any], activation_id: str) -> None:
    identity = evidence.get("canary_identity") if isinstance(evidence.get("canary_identity"), Mapping) else {}
    if canary.get("status") != "completed" or evidence.get("evidence_verified") is not True:
        raise WNBAStep6VCanaryError("Step 6V did not receive completed canary + verified durable evidence.")
    if canary.get("storage_backend") != SUPABASE_BACKEND or identity.get("storage_backend") != SUPABASE_BACKEND:
        raise WNBAStep6VCanaryError("Step 6V result is not bound to Supabase durable storage.")
    if canary.get("activation_id") != activation_id or identity.get("activation_id") != activation_id:
        raise WNBAStep6VCanaryError("Step 6V activation identity drifted between canary and evidence verification.")
    post_sha = (_clean(canary.get("post_write_sha256")) or "").casefold()
    evidence_post_sha = (_clean(identity.get("post_write_sha256")) or "").casefold()
    if not _HEX_SHA256_RE.fullmatch(post_sha) or post_sha != evidence_post_sha:
        raise WNBAStep6VCanaryError("Step 6V durable post-write SHA-256 did not survive evidence verification.")
    canonical_sha = (_clean(canary.get("verified_persistent_feed_sha256")) or "").casefold()
    evidence_canonical_sha = (_clean(identity.get("verified_persistent_feed_sha256")) or "").casefold()
    if not _HEX_SHA256_RE.fullmatch(canonical_sha) or canonical_sha != evidence_canonical_sha:
        raise WNBAStep6VCanaryError("Step 6V canonical feed identity drifted after durable verification.")
    if evidence.get("scheduler_authorized") is not False:
        raise WNBAStep6VCanaryError("Step 6V refuses evidence that authorizes the scheduler.")


def run_step6v_supabase_canary(
    *,
    date: str,
    season: int,
    activation_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run one Step 6S Supabase canary and independently verify it with Step 6T."""
    canary_date, canary_season, canary_id = _validated_inputs(
        date=date,
        season=season,
        activation_id=activation_id,
    )
    base = _base_environment(env)
    _require_base_fail_closed(base)

    active = _active_canary_environment(base, canary_id)
    canary = run_storage_aware_step6j_canary(
        date=canary_date,
        season=canary_season,
        activation_id=canary_id,
        env=active,
    )

    verification = _verification_environment(base)
    evidence = verify_step6t_canary_evidence(verification)
    _assert_evidence_matches(canary, evidence, canary_id)

    identity = evidence.get("canary_identity") or {}
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6v_live_supabase_canary_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "step6j_complete_candidate": True,
        "status": "completed",
        "activation_id": canary_id,
        "date": canary_date,
        "season": canary_season,
        "storage_backend": SUPABASE_BACKEND,
        "canary": {
            "already_completed": canary.get("already_completed"),
            "offer_side_count": canary.get("offer_side_count"),
            "pre_write_sha256": canary.get("pre_write_sha256"),
            "post_write_sha256": canary.get("post_write_sha256"),
            "verified_persistent_feed_sha256": canary.get("verified_persistent_feed_sha256"),
            "snapshot_sha256": canary.get("snapshot_sha256"),
            "reconciliation_fingerprint_sha256": canary.get("reconciliation_fingerprint_sha256"),
            "attestation_sha256": canary.get("attestation_sha256"),
            "rollback_available": canary.get("rollback_available"),
        },
        "evidence": {
            "evidence_verified": True,
            "evidence_sha256": evidence.get("evidence_sha256"),
            "rollback_verified": identity.get("rollback_verified"),
            "rollback_mode": identity.get("rollback_mode"),
            "backup_content_sha256": identity.get("backup_content_sha256"),
            "marker_content_sha256": identity.get("marker_content_sha256"),
            "feed_size_bytes": identity.get("feed_size_bytes"),
        },
        "final_switch_state": {
            PRODUCTION_RUNTIME_ENV: False,
            DIRECT_SYNC_ENABLED_ENV: False,
            RECONCILED_SYNC_ENABLED_ENV: False,
            CANARY_ENABLED_ENV: False,
        },
        "safety": {
            "base_environment_mutated": False,
            "temporary_write_switches_persisted": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "scheduler_authorized": False,
            "supabase_schema_provisioned": False,
            "render_provisioned": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_value_returned": False,
        },
    }


def _write_json(path: str, document: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(document), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the one-shot Step 6V Supabase-backed Step 6J canary.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--activation-id", required=True)
    parser.add_argument("--output", required=False)
    args = parser.parse_args(argv)
    result = run_step6v_supabase_canary(
        date=args.date,
        season=args.season,
        activation_id=args.activation_id,
    )
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
