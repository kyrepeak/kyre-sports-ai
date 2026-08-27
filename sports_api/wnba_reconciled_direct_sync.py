"""Step 6I guarded DraftKings -> Kyre market-feed synchronization.

Step 6H proved that the current DraftKings WNBA player-prop snapshot can be
reconciled against official WNBA team home, schedule, and roster pages. Step 6I
turns that proof into a hard write gate while remaining disabled by default.

The critical ordering is fetch once -> hash once -> reconcile that exact object
-> verify the object did not change -> atomically write that same object through
the frozen Step 6C writer. No second DraftKings fetch is allowed between
reconciliation and write.

Step 6I does not enable the production runtime, scheduler, or direct sync. It
adds a second explicit write switch and installs only in the application runtime
path used by Step 6D. There is no public mutation route.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

from sports_api.collectors.wnba_kyre_market_feed import write_kyre_market_feed as _STEP6C_WRITE
from sports_api.collectors.wnba_prop_feed_collector import WNBAPropFeedCollectorNotReadyError
from sports_api.wnba_official_reconciliation import _timeout
from sports_api.wnba_official_reconciliation_live import fetch_verified_draftkings_snapshot
from sports_api.wnba_official_team_page_reconciliation_live import (
    _fetch_page,
    reconcile_team_page_snapshot,
)
import sports_api.wnba_step6d_direct_integration as _step6d

MODEL_SOURCE = "Kyre Sports API WNBA Step 6I reconciled direct sync guard"
MODEL_VERSION = "wnba_step_6i_reconciled_direct_sync_guard_v1"
SCHEMA_VERSION = MODEL_VERSION

RECONCILED_SYNC_ENABLED_ENV = "WNBA_KYRE_RECONCILED_SYNC_ENABLED"
RECONCILED_SYNC_MAX_AGE_ENV = "WNBA_KYRE_RECONCILED_SYNC_MAX_AGE_SECONDS"
DEFAULT_MAX_AGE_SECONDS = 120.0
MAX_MAX_AGE_SECONDS = 600.0
MAX_FUTURE_SKEW_SECONDS = 30.0
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_ORIGINAL_STEP6D_SYNC = _step6d.sync_draftkings_to_kyre_feed


class WNBAReconciledSyncNotReadyError(WNBAPropFeedCollectorNotReadyError):
    """Raised before any write when Step 6I reconciliation is not green."""


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _truthy(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def reconciled_sync_enabled(env: Mapping[str, str] | None = None) -> bool:
    return _truthy(_environment(env), RECONCILED_SYNC_ENABLED_ENV, False)


def _max_age_seconds(env: Mapping[str, str]) -> float:
    raw = env.get(RECONCILED_SYNC_MAX_AGE_ENV)
    if raw is None or not str(raw).strip():
        return DEFAULT_MAX_AGE_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise WNBAReconciledSyncNotReadyError(f"{RECONCILED_SYNC_MAX_AGE_ENV} must be numeric.") from exc
    if not 1.0 <= value <= MAX_MAX_AGE_SECONDS:
        raise WNBAReconciledSyncNotReadyError(
            f"{RECONCILED_SYNC_MAX_AGE_ENV} must be between 1 and {int(MAX_MAX_AGE_SECONDS)} seconds."
        )
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_aware(value: Any, field: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WNBAReconciledSyncNotReadyError(f"Step 6I {field} must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAReconciledSyncNotReadyError(f"Step 6I {field} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _snapshot_identity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": snapshot.get("schema_version"),
        "date": snapshot.get("date"),
        "season": snapshot.get("season"),
        "captured_at_utc": snapshot.get("captured_at_utc"),
        "feed_source": snapshot.get("feed_source"),
        "feed_format": snapshot.get("feed_format"),
        "odds_format": snapshot.get("odds_format"),
        "offers": snapshot.get("offers") or [],
        "source_events": snapshot.get("source_events") or [],
    }


def snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _snapshot_identity(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _persistent_feed_identity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": snapshot.get("schema_version"),
        "date": snapshot.get("date"),
        "season": snapshot.get("season"),
        "captured_at_utc": snapshot.get("captured_at_utc"),
        "feed_source": snapshot.get("feed_source"),
        "feed_format": snapshot.get("feed_format"),
        "odds_format": snapshot.get("odds_format"),
        "offers": snapshot.get("offers") or [],
    }


def persistent_feed_sha256(snapshot: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _persistent_feed_identity(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _activation_requested(env: Mapping[str, str]) -> bool:
    return bool(_step6d.direct_sync_enabled(env) and reconciled_sync_enabled(env))


def get_reconciled_sync_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Network-free status. It never fetches DraftKings or official WNBA pages."""
    environment = _environment(env)
    direct_enabled = _step6d.direct_sync_enabled(environment)
    guard_enabled = reconciled_sync_enabled(environment)
    provider = str(environment.get(_step6d.DIRECT_SYNC_PROVIDER_ENV, _step6d.SUPPORTED_DIRECT_PROVIDER)).strip().casefold()
    blockers: list[str] = []
    if not direct_enabled:
        blockers.append(f"{_step6d.DIRECT_SYNC_ENABLED_ENV}=true with provider draftkings is required")
    if not guard_enabled:
        blockers.append(f"{RECONCILED_SYNC_ENABLED_ENV}=true is required")
    try:
        max_age = _max_age_seconds(environment)
    except WNBAReconciledSyncNotReadyError as exc:
        max_age = None
        blockers.append(str(exc))
    active = bool(direct_enabled and guard_enabled and max_age is not None)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6i_reconciled_direct_sync_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "direct_sync_enabled": direct_enabled,
        "direct_sync_provider": provider,
        "reconciled_sync_enabled": guard_enabled,
        "reconciled_sync_active": active,
        "snapshot_max_age_seconds": max_age,
        "max_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
        "blockers": blockers,
        "installation": dict(INSTALLATION) if "INSTALLATION" in globals() else {"installed": False},
        "safety": {
            "network_used_by_status": False,
            "feed_write_performed": False,
            "production_runtime_enablement_changed": False,
            "scheduler_enablement_changed": False,
            "direct_sync_enablement_changed": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "public_sync_route_exists": False,
            "step6c_writer_remains_atomic_storage_authority": True,
            "step6h_reconciliation_required_before_write": True,
        },
    }


def _validate_reconciliation(
    snapshot: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    requested_date: str,
    requested_season: int,
    before_sha256: str,
    after_sha256: str,
    now: datetime,
    max_age_seconds: float,
) -> tuple[list[str], float | None]:
    blockers: list[str] = []
    if before_sha256 != after_sha256:
        blockers.append("snapshot_mutated_during_reconciliation")
    if str(snapshot.get("date")) != str(requested_date):
        blockers.append("snapshot_date_mismatch")
    try:
        snapshot_season = int(snapshot.get("season"))
    except (TypeError, ValueError):
        snapshot_season = -1
    if snapshot_season != int(requested_season):
        blockers.append("snapshot_season_mismatch")
    if str(report.get("date")) != str(requested_date):
        blockers.append("reconciliation_date_mismatch")
    try:
        report_season = int(report.get("season"))
    except (TypeError, ValueError):
        report_season = -1
    if report_season != int(requested_season):
        blockers.append("reconciliation_season_mismatch")

    age_seconds: float | None = None
    try:
        captured = _parse_aware(snapshot.get("captured_at_utc"), "captured_at_utc")
        age_seconds = (now.astimezone(timezone.utc) - captured).total_seconds()
        if age_seconds > max_age_seconds:
            blockers.append("snapshot_stale")
        if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
            blockers.append("snapshot_capture_time_in_future")
    except WNBAReconciledSyncNotReadyError:
        blockers.append("snapshot_capture_time_invalid")

    offers = [row for row in snapshot.get("offers") or [] if isinstance(row, Mapping)]
    events = [row for row in snapshot.get("source_events") or [] if isinstance(row, Mapping)]
    market_ids = {str(row.get("source_market_id")) for row in offers if row.get("source_market_id")}
    event_ids = {str(row.get("source_event_id")) for row in events if row.get("source_event_id")}
    if not offers:
        blockers.append("snapshot_has_no_offers")
    if not events:
        blockers.append("snapshot_has_no_events")
    if not market_ids:
        blockers.append("snapshot_has_no_markets")

    if not report.get("ready_for_auto_sync"):
        blockers.append("step6h_not_ready")
    if report.get("blockers"):
        blockers.append("step6h_has_blockers")
    if report.get("mismatch_details"):
        blockers.append("step6h_has_mismatches")
    if not report.get("step6g_shadow_ready"):
        blockers.append("step6g_shadow_not_ready")
    if int(report.get("offer_side_count") or -1) != len(offers):
        blockers.append("offer_count_reconciliation_mismatch")
    if int(report.get("market_count") or -1) != len(market_ids):
        blockers.append("market_count_reconciliation_mismatch")
    if int(report.get("verified_market_count") or -1) != len(market_ids):
        blockers.append("not_all_markets_verified")
    if int(report.get("draftkings_event_count") or -1) != len(event_ids):
        blockers.append("event_count_reconciliation_mismatch")
    if int(report.get("verified_event_count") or -1) != len(event_ids):
        blockers.append("not_all_events_verified")

    player_count = int(report.get("verified_player_count") or 0)
    roster_count = int(report.get("verified_roster_membership_count") or 0)
    if player_count <= 0 or roster_count <= 0 or player_count != roster_count:
        blockers.append("not_all_players_verified")
    if any(not bool(row.get("verified")) for row in report.get("event_verifications") or []):
        blockers.append("event_verification_contains_failure")
    if any(not bool(row.get("verified")) for row in report.get("player_verifications") or []):
        blockers.append("player_verification_contains_failure")

    fingerprint = str(report.get("reconciliation_fingerprint_sha256") or "").casefold()
    if not _SHA256_RE.fullmatch(fingerprint):
        blockers.append("reconciliation_fingerprint_invalid")
    return sorted(set(blockers)), age_seconds


def _build_reconciled_sync_bundle(
    *,
    date: str,
    season: int,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    environment = _environment(env)
    max_age = _max_age_seconds(environment)
    timeout_seconds = _timeout(environment)
    snapshot = fetch_verified_draftkings_snapshot(date=str(date), season=int(season), env=environment)
    if not isinstance(snapshot, dict):
        raise WNBAReconciledSyncNotReadyError("Step 6I DraftKings snapshot must be an object.")
    before_sha = snapshot_sha256(snapshot)

    def page_fetcher(team_name: str, path: str) -> Mapping[str, Any]:
        return _fetch_page(team_name, path, timeout_seconds=timeout_seconds, requester=None)

    report = reconcile_team_page_snapshot(snapshot, season=int(season), page_fetcher=page_fetcher)
    after_sha = snapshot_sha256(snapshot)
    current = (now or _utc_now()).astimezone(timezone.utc)
    blockers, age_seconds = _validate_reconciliation(
        snapshot,
        report,
        requested_date=str(date),
        requested_season=int(season),
        before_sha256=before_sha,
        after_sha256=after_sha,
        now=current,
        max_age_seconds=max_age,
    )
    ready = not blockers
    write_requested = _activation_requested(environment)
    attestation_identity = {
        "date": str(date),
        "season": int(season),
        "snapshot_sha256": before_sha,
        "persistent_feed_sha256": persistent_feed_sha256(snapshot),
        "reconciliation_fingerprint_sha256": report.get("reconciliation_fingerprint_sha256"),
        "offer_side_count": len(snapshot.get("offers") or []),
        "market_count": report.get("market_count"),
        "event_count": report.get("draftkings_event_count"),
        "verified_player_count": report.get("verified_player_count"),
        "blockers": blockers,
        "reconciliation_ready": ready,
    }
    attestation_sha = hashlib.sha256(
        json.dumps(attestation_identity, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    attestation = {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6i_reconciled_sync_attestation",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": current.isoformat(),
        "date": str(date),
        "season": int(season),
        "snapshot_captured_at_utc": snapshot.get("captured_at_utc"),
        "snapshot_age_seconds": None if age_seconds is None else round(age_seconds, 6),
        "snapshot_max_age_seconds": max_age,
        "snapshot_sha256": before_sha,
        "snapshot_post_reconciliation_sha256": after_sha,
        "persistent_feed_sha256": persistent_feed_sha256(snapshot),
        "reconciliation_fingerprint_sha256": report.get("reconciliation_fingerprint_sha256"),
        "attestation_sha256": attestation_sha,
        "offer_side_count": len(snapshot.get("offers") or []),
        "market_count": report.get("market_count"),
        "draftkings_event_count": report.get("draftkings_event_count"),
        "verified_event_count": report.get("verified_event_count"),
        "verified_market_count": report.get("verified_market_count"),
        "verified_player_count": report.get("verified_player_count"),
        "verified_roster_membership_count": report.get("verified_roster_membership_count"),
        "step6g_shadow_ready": bool(report.get("step6g_shadow_ready")),
        "step6h_ready": bool(report.get("ready_for_auto_sync")),
        "reconciliation_ready": ready,
        "write_requested": write_requested,
        "write_authorized": bool(ready and write_requested),
        "would_sync_if_enabled": ready,
        "blockers": blockers,
        "step6h_blockers": list(report.get("blockers") or []),
        "mismatch_count": len(report.get("mismatch_details") or []),
        "event_evidence_ids": sorted(
            str(row.get("official_game_evidence_id"))
            for row in report.get("event_verifications") or []
            if row.get("official_game_evidence_id")
        ),
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "feed_write_performed": False,
            "production_runtime_enablement_changed": False,
            "scheduler_enablement_changed": False,
            "direct_sync_enablement_changed": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "draftkings_refetch_between_reconciliation_and_write": False,
        },
    }
    return attestation, snapshot


def build_reconciled_sync_attestation(
    *,
    date: str,
    season: int,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build live GET-only Step 6I evidence without ever writing the feed."""
    attestation, _ = _build_reconciled_sync_bundle(date=date, season=season, env=env)
    return attestation


def sync_reconciled_draftkings_to_kyre_feed(
    *,
    date: str,
    season: int,
    urls: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    requester: Any = None,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """The only Step 6I runtime write path; disabled unless both switches are on."""
    del requester
    environment = _environment(env)
    if not reconciled_sync_enabled(environment):
        return {
            "provider_id": "draftkings_direct",
            "synced": False,
            "reason": "reconciled_sync_guard_disabled",
            "feed_write_performed": False,
            "reconciled_sync_enabled": False,
        }
    if not _step6d.direct_sync_enabled(environment):
        raise WNBAReconciledSyncNotReadyError(
            f"Step 6I requires {_step6d.DIRECT_SYNC_ENABLED_ENV}=true and provider=draftkings."
        )
    if urls is not None:
        raise WNBAReconciledSyncNotReadyError(
            "Step 6I does not allow per-call DraftKings URL overrides; it uses the frozen verified transport."
        )

    attestation, snapshot = _build_reconciled_sync_bundle(date=str(date), season=int(season), env=environment)
    if not attestation.get("reconciliation_ready") or not attestation.get("write_authorized"):
        raise WNBAReconciledSyncNotReadyError(
            "Step 6I reconciliation is not write-authorized: " + ", ".join(attestation.get("blockers") or ["unknown blocker"])
        )

    expected_sha = str(attestation["snapshot_sha256"])
    write_document = deepcopy(snapshot)
    immediate_sha = snapshot_sha256(write_document)
    if immediate_sha != expected_sha:
        raise WNBAReconciledSyncNotReadyError("Step 6I snapshot changed before durable write.")

    storage = _STEP6C_WRITE(write_document, path=path, env=environment)
    result = dict(attestation)
    result.update(
        {
            "provider_id": "draftkings_direct",
            "synced": True,
            "feed_write_performed": True,
            "storage": storage,
        }
    )
    result["safety"] = dict(attestation["safety"])
    result["safety"]["feed_write_performed"] = True
    return result


def install_step6i_integration() -> dict[str, Any]:
    """Interpose the Step 6I guard on the application runtime Step 6D write hook."""
    _step6d.sync_draftkings_to_kyre_feed = sync_reconciled_draftkings_to_kyre_feed
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "patched_runtime_hook": "sports_api.wnba_step6d_direct_integration.sync_draftkings_to_kyre_feed",
        "frozen_step6c_source_modified": False,
        "frozen_step6d_source_modified": False,
        "direct_collector_source_modified": False,
        "public_sync_route_added": False,
    }


INSTALLATION = install_step6i_integration()
