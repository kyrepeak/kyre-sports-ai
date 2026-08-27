"""Contract-based Render service discovery for the Step 6J canary retry.

The first Step 6J attempt stopped before any Render mutation because the
existing service display name differs from the historical default. This wrapper
does not weaken the gate: it finds candidates using the frozen Step 6C disk,
Kyre-owned market-feed, staging, and ingest-token contract. Exactly one service
must match before the original Step 6J operator is allowed to continue.
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
from sports_api.tools import wnba_step6j_render_canary as base
from sports_api.wnba_render_attachment_readiness import DEFAULT_DISK_MOUNT_PATH
from sports_api.wnba_render_provisioning import (
    RENDER_API_KEY_ENV,
    RENDER_OWNER_ID_ENV,
    RenderAPIClient,
    _items,
    _service_image_ref,
    _service_url,
)
from sports_api.wnba_render_provisioning_step6c import INGEST_TOKEN_ENV

MODEL_SOURCE = "Kyre Sports API WNBA Step 6J frozen-contract Render discovery"
MODEL_VERSION = "wnba_step_6j_contract_render_discovery_v1"


class Step6JRenderContractDiscoveryError(RuntimeError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _all_services(client: RenderAPIClient, owner_id: str) -> list[dict[str, Any]]:
    """Read every service in the resolved workspace; GET only."""
    document = client.request(
        "GET",
        "/v1/services",
        params={"ownerId": owner_id, "limit": 100},
    )
    return _items(document, ("service",))


def _matches_frozen_step6c_environment(environment: Mapping[str, str]) -> bool:
    return bool(
        environment.get(MARKET_PROVIDER_MODE_ENV) == "kyre"
        and environment.get(KYRE_MARKET_FEED_PATH_ENV) == DEFAULT_KYRE_MARKET_FEED_PATH
        and environment.get("WNBA_PROP_FEED_FAILOVER_ORDER") == "kyre"
        and environment.get("WNBA_PERSISTENT_VOLUME_ROOT") == DEFAULT_DISK_MOUNT_PATH
        and environment.get("WNBA_STAGING_HOST_PROVIDER") == "render"
        and environment.get("WNBA_HOST_ENVIRONMENT") == "staging"
        and _clean(environment.get(INGEST_TOKEN_ENV))
    )


def discover_frozen_step6c_services(client: RenderAPIClient, owner_id: str) -> list[dict[str, Any]]:
    """Return only services that satisfy the immutable Step 6C durable-feed contract."""
    candidates: list[dict[str, Any]] = []
    for service in _all_services(client, owner_id):
        service_id = _clean(service.get("id"))
        if not service_id or not _service_url(service) or not _service_image_ref(service):
            continue
        disks = client.list_disks(service_id)
        if base._matching_disk(disks) is None:
            continue
        environment = base._env_map(client.list_env_vars(service_id))
        if not _matches_frozen_step6c_environment(environment):
            continue
        candidates.append(service)
    return candidates


def run_render_canary_with_contract_discovery(
    *,
    revision: str,
    release_id: str,
    image_ref: str,
    activation_id: str,
    date: str,
    season: int,
    api_key: str,
    owner_id: str | None,
) -> dict[str, Any]:
    """Run the original canary after replacing name lookup with strict contract lookup."""
    original_list_services = RenderAPIClient.list_services

    def _contract_list_services(client: RenderAPIClient, resolved_owner_id: str, requested_name: str) -> list[dict[str, Any]]:
        candidates = discover_frozen_step6c_services(client, resolved_owner_id)
        if len(candidates) != 1:
            raise Step6JRenderContractDiscoveryError(
                f"Expected exactly one existing Render service matching the frozen Step 6C contract; found {len(candidates)}."
            )
        return candidates

    RenderAPIClient.list_services = _contract_list_services
    try:
        result = base.run_render_canary(
            revision=revision,
            release_id=release_id,
            image_ref=image_ref,
            activation_id=activation_id,
            date=date,
            season=season,
            api_key=api_key,
            owner_id=owner_id,
        )
    finally:
        RenderAPIClient.list_services = original_list_services

    result["service_discovery"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "strategy": "frozen_step6c_contract",
        "historical_display_name_required": False,
        "exactly_one_contract_match_required": True,
        "discovery_network_method": "render_get_only",
        "paid_resource_created": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WNBA Step 6J using frozen-contract Render service discovery.")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--activation-id", required=True)
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = _clean(os.environ.get(RENDER_API_KEY_ENV))
    owner_id = _clean(os.environ.get(RENDER_OWNER_ID_ENV))
    if not api_key:
        raise SystemExit(f"{RENDER_API_KEY_ENV} is required.")

    result = run_render_canary_with_contract_discovery(
        revision=args.revision,
        release_id=args.release_id,
        image_ref=args.image_ref,
        activation_id=args.activation_id,
        date=args.date,
        season=args.season,
        api_key=api_key,
        owner_id=owner_id,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
