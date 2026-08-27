"""Step 6H live runtime binding for the current official WNBA schedule CDN."""
from __future__ import annotations

from typing import Any

import sports_api.wnba_official_reconciliation_live as _live
from sports_api.wnba_current_schedule_cdn import get_daily_schedule_dataset

MODEL_SOURCE = "Kyre Sports API WNBA Step 6H current official schedule binding"
MODEL_VERSION = "wnba_step_6h_current_official_schedule_binding_v1"


def run_live_official_reconciliation(*, date: str, season: int, env=None) -> dict[str, Any]:
    # Step 6H v2 deliberately resolves its schedule collector through a module
    # global. Bind that dependency to the corrected current-season WNBA CDN
    # transport for this evidence-only live probe.
    previous = _live.get_daily_schedule_dataset
    _live.get_daily_schedule_dataset = get_daily_schedule_dataset
    try:
        report = _live.run_live_official_reconciliation(date=date, season=season, env=env)
    finally:
        _live.get_daily_schedule_dataset = previous
    report["schedule_transport_source"] = MODEL_SOURCE
    report["schedule_transport_model_version"] = MODEL_VERSION
    return report
