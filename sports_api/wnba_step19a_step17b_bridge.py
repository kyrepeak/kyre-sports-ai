"""Step 19A bridges the current DraftKings transport into frozen production seams.

Step 17B intentionally keeps the legacy Step-6D/6I process activation switches
OFF. Step 11D owns the actual scheduler sportsbook seam and resolves the Step-11A
DraftKings bridge dynamically. This module patches both seams without editing any
frozen Step-6/11/17 source file.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import os
from typing import Any
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

import sports_api.wnba_reconciled_direct_sync as _step6i
import sports_api.wnba_step6d_direct_integration as _step6d
import sports_api.wnba_step11_draftkings_provider as _step11a
import sports_api.wnba_step19a_draftkings_sportscontent as _step19a

MODEL_VERSION = "wnba_step19a_step17b_bridge_v2"
_ORIGINAL_STEP6D_COLLECTOR = _step6d.collect_kyre_market_feed_step6d
_ORIGINAL_STEP11A_FETCHER = _step11a.fetch_step11a_draftkings_provider_bridge
_FROZEN_STAT_ORDER = ("points", "rebounds", "assists", "pra")


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _local_reconciliation_env(env: Mapping[str, str]) -> dict[str, str]:
    local = {str(k): str(v) for k, v in dict(env).items()}
    local[_step6d.DIRECT_SYNC_ENABLED_ENV] = "true"
    local[_step6d.DIRECT_SYNC_PROVIDER_ENV] = _step6d.SUPPORTED_DIRECT_PROVIDER
    local[_step6i.RECONCILED_SYNC_ENABLED_ENV] = "true"
    return local


def _browser_get(url: str, *, headers: Mapping[str, str] | None, timeout: float) -> Any:
    return cffi_requests.get(
        url,
        headers=dict(headers or {}),
        impersonate="chrome120",
        timeout=float(timeout),
        allow_redirects=True,
    )


def _step11a_current_market_requester(*, env: Mapping[str, str], supplied_requester: Any = None):
    discovered: dict[str, str] = {}

    def requester(url: str, *, headers: Mapping[str, str] | None = None, timeout: float = 15.0, **_: Any):
        if url == _step11a.OFFICIAL_SCHEDULE_URL or (urlparse(url).hostname or "").casefold().endswith(".wnba.com"):
            if supplied_requester is not None:
                return supplied_requester(url, headers=dict(headers or {}), timeout=timeout)
            return _browser_get(url, headers=headers, timeout=timeout)
        if url not in _step11a.FROZEN_DRAFTKINGS_ENDPOINTS:
            raise _step11a.WNBAStep11DraftKingsProviderUpstreamError(
                "Step 19A Step11A bridge refuses an unexpected sportsbook URL."
            )
        if not discovered:
            site, targets = _step19a._discover_pregame_targets(env=env, requester=supplied_requester)
            by_stat = {str(row["stat"]): row for row in targets}
            for frozen_url, stat in zip(_step11a.FROZEN_DRAFTKINGS_ENDPOINTS, _FROZEN_STAT_ORDER):
                target = by_stat[stat]
                discovered[frozen_url] = _step19a._subcategory_url(
                    site, target["category_id"], target["subcategory_id"]
                )
        current_url = discovered[url]
        if supplied_requester is not None:
            return supplied_requester(current_url, headers=dict(headers or {}), timeout=timeout)
        return _browser_get(current_url, headers=headers, timeout=timeout)

    return requester


def fetch_step11a_draftkings_provider_bridge_step19a(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    requester: Any = None,
    roster_loader: Any = None,
    timeout_seconds: float = _step11a.DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    if not _step19a.step19a_sportscontent_enabled(environment):
        return _ORIGINAL_STEP11A_FETCHER(
            season=season, slate_date=slate_date, evaluated_at=evaluated_at,
            requester=requester, roster_loader=roster_loader,
            timeout_seconds=timeout_seconds, env=environment,
        )
    return _ORIGINAL_STEP11A_FETCHER(
        season=season,
        slate_date=slate_date,
        evaluated_at=evaluated_at,
        requester=_step11a_current_market_requester(env=environment, supplied_requester=requester),
        roster_loader=roster_loader,
        timeout_seconds=timeout_seconds,
        env=environment,
    )


def collect_kyre_market_feed_step19a(
    *,
    date: str | None = None,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Any = None,
) -> dict[str, Any]:
    environment = _environment(env)
    if not _step19a.step19a_sportscontent_enabled(environment):
        return _ORIGINAL_STEP6D_COLLECTOR(date=date, season=season, env=environment, requester=requester)
    target_date = str(date) if date is not None else datetime.now(timezone.utc).date().isoformat()
    local_env = _local_reconciliation_env(environment)
    _step6i.sync_reconciled_draftkings_to_kyre_feed(
        date=target_date, season=int(season), env=local_env, requester=requester
    )
    return _step6d._frozen_kyre_collector(
        date=date, season=season, env=environment, requester=requester
    )


def install_step19a_step17b_bridge() -> dict[str, Any]:
    _step6d.collect_kyre_market_feed_step6d = collect_kyre_market_feed_step19a
    _step11a.fetch_step11a_draftkings_provider_bridge = fetch_step11a_draftkings_provider_bridge_step19a
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "process_environment_mutated": False,
        "legacy_process_gates_required": False,
        "local_step6i_reconciliation_required": True,
        "step11a_current_transport_installed": True,
        "frozen_step17b_source_modified": False,
        "frozen_step11a_source_modified": False,
        "frozen_step11d_source_modified": False,
        "frozen_step6d_source_modified": False,
        "frozen_step6i_source_modified": False,
    }


INSTALLATION = install_step19a_step17b_bridge()

__all__ = [
    "INSTALLATION",
    "MODEL_VERSION",
    "collect_kyre_market_feed_step19a",
    "fetch_step11a_draftkings_provider_bridge_step19a",
    "install_step19a_step17b_bridge",
]
