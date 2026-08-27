"""Read-only Render inventory probe for Step 6J service identification.

This probe exists because the historical Render display name and the full
frozen Step 6C environment signature did not identify the live service. It
uses Render GET requests only and emits a strictly sanitized inventory: service
identity, image reference, persistent-disk metadata, selected non-secret WNBA
environment values, and presence booleans for secrets. Secret values are never
returned or logged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sports_api.collectors.wnba_kyre_market_feed import (
    DEFAULT_KYRE_MARKET_FEED_PATH,
    KYRE_MARKET_FEED_PATH_ENV,
    MARKET_PROVIDER_MODE_ENV,
)
from sports_api.wnba_render_attachment_readiness import (
    DEFAULT_DISK_MOUNT_PATH,
    DEFAULT_DISK_NAME,
    DEFAULT_DISK_SIZE_GB,
)
from sports_api.wnba_render_provisioning import (
    RENDER_API_KEY_ENV,
    RENDER_OWNER_ID_ENV,
    RenderAPIClient,
    _items,
    _service_image_ref,
    _service_runtime,
    _service_type,
    _service_url,
    resolve_owner_id,
)
from sports_api.wnba_render_provisioning_step6c import ARCHIVE_HMAC_ENV, INGEST_TOKEN_ENV

MODEL_SOURCE = "Kyre Sports API WNBA Step 6J read-only Render inventory"
MODEL_VERSION = "wnba_step_6j_render_inventory_v1"

SAFE_ENV_KEYS = (
    "PORT",
    "WNBA_DEPLOYMENT_MODE",
    "WNBA_DEPLOYMENT_REPLICA_COUNT",
    "WNBA_PERSISTENT_VOLUME_ROOT",
    "WNBA_CURRENT_BOARD_STORE_PATH",
    "WNBA_PROP_FEED_STORE_PATH",
    "WNBA_BACKTEST_STORE_PATH",
    "WNBA_BOARD_SCHEDULER_LOCK_PATH",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_RELEASE_ID",
    "WNBA_RELEASE_CHANNEL",
    "WNBA_DEPLOYMENT_REVISION",
    "WNBA_DEPLOYMENT_IMAGE_REF",
    "WNBA_STAGING_HOST_PROVIDER",
    "WNBA_HOST_ENVIRONMENT",
    "WNBA_STAGING_EXPECTED_SERVICE_NAME",
    "WNBA_RELEASE_IMAGE_REPOSITORY",
    "WNBA_RENDER_PROVISIONED",
    "WNBA_RENDER_SERVICE_ID",
    "WNBA_RENDER_SERVICE_URL",
    "WNBA_RENDER_DISK_NAME",
    "WNBA_RENDER_DISK_MOUNT_PATH",
    "WNBA_RENDER_DISK_SIZE_GB",
    "WNBA_RENDER_INSTANCE_COUNT",
    MARKET_PROVIDER_MODE_ENV,
    KYRE_MARKET_FEED_PATH_ENV,
    "WNBA_PROP_FEED_FAILOVER_ORDER",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _env_map(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        key = _clean(row.get("key") or row.get("name"))
        if key:
            result[key] = _clean(row.get("value")) or ""
    return result


def _all_services(client: RenderAPIClient, owner_id: str) -> list[dict[str, Any]]:
    document = client.request(
        "GET",
        "/v1/services",
        params={"ownerId": owner_id, "limit": 100},
    )
    return _items(document, ("service",))


def _sanitize_disk(disk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean(disk.get("id")),
        "name": _clean(disk.get("name")),
        "mount_path": _clean(disk.get("mountPath") or disk.get("mount_path")),
        "size_gb": disk.get("sizeGB") if disk.get("sizeGB") is not None else disk.get("size_gb"),
    }


def _disk_contract_match(disks: list[Mapping[str, Any]]) -> bool:
    matches = 0
    for disk in disks:
        try:
            size = int(disk.get("sizeGB") or disk.get("size_gb") or 0)
        except (TypeError, ValueError):
            size = 0
        if (
            _clean(disk.get("name")) == DEFAULT_DISK_NAME
            and _clean(disk.get("mountPath") or disk.get("mount_path")) == DEFAULT_DISK_MOUNT_PATH
            and size >= DEFAULT_DISK_SIZE_GB
        ):
            matches += 1
    return matches == 1


def build_inventory(*, api_key: str, owner_id: str | None = None) -> dict[str, Any]:
    with RenderAPIClient(api_key=api_key, timeout_seconds=25) as client:
        resolved_owner = resolve_owner_id(client, owner_id)
        services = _all_services(client, resolved_owner)
        rows: list[dict[str, Any]] = []
        for service in services:
            service_id = _clean(service.get("id"))
            if not service_id:
                continue
            disks_raw = client.list_disks(service_id)
            environment = _env_map(client.list_env_vars(service_id))
            safe_env = {key: environment.get(key) for key in SAFE_ENV_KEYS if key in environment}
            signals = {
                "exact_step6c_disk_contract": _disk_contract_match(disks_raw),
                "persistent_volume_root_matches": environment.get("WNBA_PERSISTENT_VOLUME_ROOT") == DEFAULT_DISK_MOUNT_PATH,
                "provider_mode_is_kyre": environment.get(MARKET_PROVIDER_MODE_ENV) == "kyre",
                "kyre_feed_path_matches": environment.get(KYRE_MARKET_FEED_PATH_ENV) == DEFAULT_KYRE_MARKET_FEED_PATH,
                "failover_order_is_kyre": environment.get("WNBA_PROP_FEED_FAILOVER_ORDER") == "kyre",
                "host_provider_is_render": environment.get("WNBA_STAGING_HOST_PROVIDER") == "render",
                "host_environment_is_staging": environment.get("WNBA_HOST_ENVIRONMENT") == "staging",
                "ingest_token_present": bool(_clean(environment.get(INGEST_TOKEN_ENV))),
                "archive_hmac_present": bool(_clean(environment.get(ARCHIVE_HMAC_ENV))),
                "production_runtime_enabled": str(environment.get("WNBA_PRODUCTION_RUNTIME_ENABLED") or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"},
            }
            score_keys = (
                "exact_step6c_disk_contract",
                "persistent_volume_root_matches",
                "provider_mode_is_kyre",
                "kyre_feed_path_matches",
                "failover_order_is_kyre",
                "host_provider_is_render",
                "host_environment_is_staging",
                "ingest_token_present",
            )
            rows.append(
                {
                    "service_id": service_id,
                    "service_name": _clean(service.get("name")),
                    "service_type": _service_type(service),
                    "service_runtime": _service_runtime(service),
                    "service_url": _service_url(service),
                    "image_ref": _service_image_ref(service),
                    "disks": [_sanitize_disk(disk) for disk in disks_raw],
                    "safe_environment": safe_env,
                    "contract_signals": signals,
                    "step6c_signal_score": sum(1 for key in score_keys if signals[key]),
                    "step6c_signal_max": len(score_keys),
                }
            )

    rows.sort(key=lambda row: (-int(row["step6c_signal_score"]), str(row.get("service_name") or "")))
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6j_render_inventory",
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "service_count": len(rows),
        "services": rows,
        "safety": {
            "render_requests": "GET only",
            "render_mutation_performed": False,
            "feed_write_performed": False,
            "secret_values_returned": False,
            "scheduler_started": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitized read-only Render inventory for WNBA Step 6J.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    api_key = _clean(os.environ.get(RENDER_API_KEY_ENV))
    owner_id = _clean(os.environ.get(RENDER_OWNER_ID_ENV))
    if not api_key:
        raise SystemExit(f"{RENDER_API_KEY_ENV} is required.")
    report = build_inventory(api_key=api_key, owner_id=owner_id)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
