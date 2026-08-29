"""Step 19A bridge for the frozen Step 17B always-on runtime.

Step 17B intentionally keeps the legacy Step-6D/6I process-level activation
switches OFF. This bridge does not weaken that invariant. When the additive
Step-19A transport gate is enabled, it creates a private per-call environment
copy with the old Step-6D/6I gates enabled only for the duration of the already
frozen Step-6I reconciliation/write function. The process environment remains
unchanged, and official WNBA reconciliation remains mandatory before a feed
write.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import os
from typing import Any

import sports_api.wnba_reconciled_direct_sync as _step6i
import sports_api.wnba_step6d_direct_integration as _step6d
import sports_api.wnba_step19a_draftkings_sportscontent as _step19a

MODEL_VERSION = "wnba_step19a_step17b_bridge_v1"
_ORIGINAL_STEP6D_COLLECTOR = _step6d.collect_kyre_market_feed_step6d


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _local_reconciliation_env(env: Mapping[str, str]) -> dict[str, str]:
    local = {str(k): str(v) for k, v in dict(env).items()}
    local[_step6d.DIRECT_SYNC_ENABLED_ENV] = "true"
    local[_step6d.DIRECT_SYNC_PROVIDER_ENV] = _step6d.DRAFTKINGS_PROVIDER_ID
    local[_step6i.RECONCILED_SYNC_ENABLED_ENV] = "true"
    return local


def collect_kyre_market_feed_step19a(
    *,
    date: str | None = None,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Any = None,
) -> dict[str, Any]:
    environment = _environment(env)
    if not _step19a.step19a_sportscontent_enabled(environment):
        return _ORIGINAL_STEP6D_COLLECTOR(
            date=date,
            season=season,
            env=environment,
            requester=requester,
        )

    target_date = str(date) if date is not None else datetime.now(timezone.utc).date().isoformat()
    local_env = _local_reconciliation_env(environment)
    _step6i.sync_reconciled_draftkings_to_kyre_feed(
        date=target_date,
        season=int(season),
        env=local_env,
        requester=requester,
    )
    # Read the durable Step-6C feed using the real frozen process environment.
    # No legacy process-level switch is changed or persisted.
    return _step6d._frozen_kyre_collector(
        date=date,
        season=season,
        env=environment,
        requester=requester,
    )


def install_step19a_step17b_bridge() -> dict[str, Any]:
    _step6d.collect_kyre_market_feed_step6d = collect_kyre_market_feed_step19a
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "process_environment_mutated": False,
        "legacy_process_gates_required": False,
        "local_step6i_reconciliation_required": True,
        "frozen_step17b_source_modified": False,
        "frozen_step6d_source_modified": False,
        "frozen_step6i_source_modified": False,
    }


INSTALLATION = install_step19a_step17b_bridge()

__all__ = [
    "INSTALLATION",
    "MODEL_VERSION",
    "collect_kyre_market_feed_step19a",
    "install_step19a_step17b_bridge",
]
