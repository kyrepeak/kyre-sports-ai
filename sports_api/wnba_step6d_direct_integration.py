"""Step 6D additive integration for the frozen Step 5O/5P WNBA pipeline.

The frozen Step 5O source remains unchanged.  This module is imported before
WNBA routers/schedulers and installs a narrow wrapper: whenever the existing
`kyre` provider is collected and direct sync is explicitly enabled, DraftKings
GET-only market data is first normalized and atomically written to the Step-6C
Kyre-owned feed.  Step 5O then reads that durable feed exactly as before.
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

from sports_api.collectors.wnba_draftkings_direct import (
    DRAFTKINGS_URLS_ENV,
    describe_draftkings_direct_onboarding,
    sync_draftkings_to_kyre_feed,
)
from sports_api.collectors.wnba_kyre_market_feed import collect_kyre_market_feed as _frozen_kyre_collector
import sports_api.wnba_prop_feed_failover as _frozen_failover

MODEL_SOURCE = "Kyre Sports API WNBA Step 6D direct-market integration"
MODEL_VERSION = "wnba_step_6d_direct_market_integration_v1"
DIRECT_SYNC_ENABLED_ENV = "WNBA_KYRE_DIRECT_SYNC_ENABLED"
DIRECT_SYNC_PROVIDER_ENV = "WNBA_KYRE_DIRECT_SYNC_PROVIDER"
SUPPORTED_DIRECT_PROVIDER = "draftkings"

_ORIGINAL_COLLECT_FAILOVER_LINE_BOARD = _frozen_failover.collect_failover_line_board
_ORIGINAL_BUILD_FAILOVER_DAILY_TOP_FIVE = _frozen_failover.build_failover_daily_top_five


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _truthy(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def direct_sync_enabled(env: Mapping[str, str] | None = None) -> bool:
    environment = _environment(env)
    if not _truthy(environment, DIRECT_SYNC_ENABLED_ENV, False):
        return False
    provider = str(environment.get(DIRECT_SYNC_PROVIDER_ENV, SUPPORTED_DIRECT_PROVIDER)).strip().casefold()
    return provider == SUPPORTED_DIRECT_PROVIDER


def get_step6d_direct_market_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    provider = str(environment.get(DIRECT_SYNC_PROVIDER_ENV, SUPPORTED_DIRECT_PROVIDER)).strip().casefold()
    enabled_flag = _truthy(environment, DIRECT_SYNC_ENABLED_ENV, False)
    onboarding = describe_draftkings_direct_onboarding(environment)
    active = enabled_flag and provider == SUPPORTED_DIRECT_PROVIDER and bool(onboarding.get("ready"))
    blockers: list[str] = []
    if not enabled_flag:
        blockers.append(f"{DIRECT_SYNC_ENABLED_ENV}=true is required")
    if provider != SUPPORTED_DIRECT_PROVIDER:
        blockers.append(f"{DIRECT_SYNC_PROVIDER_ENV} must be {SUPPORTED_DIRECT_PROVIDER}")
    if not onboarding.get("ready"):
        blockers.append(onboarding.get("configuration_error") or f"{DRAFTKINGS_URLS_ENV} is not ready")
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6d_direct_market_status",
        "model_version": MODEL_VERSION,
        "direct_sync_enabled": enabled_flag,
        "direct_sync_provider": provider,
        "direct_sync_active": active,
        "blockers": blockers,
        "draftkings": onboarding,
        "safety": {
            "frozen_step_5o_source_modified": False,
            "frozen_step_5p_source_modified": False,
            "sportsbook_http_method": "GET",
            "sportsbook_login_required": False,
            "sportsbook_account_cookie_required": False,
            "wager_action_supported": False,
            "paid_odds_vendor_required": False,
            "step_6c_persistent_feed_remains_source_of_truth": True,
        },
    }


def collect_kyre_market_feed_step6d(
    *,
    date: str | None = None,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Any = None,
) -> dict[str, Any]:
    environment = _environment(env)
    if direct_sync_enabled(environment):
        if date is None:
            # Let the frozen collector determine current-date semantics after
            # sync only when its caller supplied an explicit slate date.  The
            # scheduler normally supplies the verified slate date.
            from datetime import datetime, timezone
            target_date = datetime.now(timezone.utc).date().isoformat()
        else:
            target_date = str(date)
        sync_draftkings_to_kyre_feed(
            date=target_date,
            season=season,
            env=environment,
            requester=requester,
        )
    return _frozen_kyre_collector(date=date, season=season, env=environment, requester=requester)


def collect_failover_line_board_step6d(*args: Any, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("kyre_market_collector", collect_kyre_market_feed_step6d)
    return _ORIGINAL_COLLECT_FAILOVER_LINE_BOARD(*args, **kwargs)


def build_failover_daily_top_five_step6d(*args: Any, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("failover_builder", collect_failover_line_board_step6d)
    return _ORIGINAL_BUILD_FAILOVER_DAILY_TOP_FIVE(*args, **kwargs)


def install_step6d_integration() -> dict[str, Any]:
    """Install wrappers before scheduler/router imports bind frozen functions."""
    _frozen_failover.collect_failover_line_board = collect_failover_line_board_step6d
    _frozen_failover.build_failover_daily_top_five = build_failover_daily_top_five_step6d
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "frozen_source_files_modified": False,
    }


INSTALLATION = install_step6d_integration()
