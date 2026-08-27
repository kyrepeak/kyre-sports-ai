"""Step 6H live runtime binding for official WNBA team-page reconciliation."""
from __future__ import annotations

from typing import Any

from sports_api.wnba_official_team_page_reconciliation_live import (
    MODEL_SOURCE as TEAM_PAGE_SOURCE,
    MODEL_VERSION as TEAM_PAGE_MODEL_VERSION,
    run_live_official_reconciliation as _run_team_page_reconciliation,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6H official team-page runtime binding"
MODEL_VERSION = "wnba_step_6h_official_team_page_runtime_binding_v1"


def run_live_official_reconciliation(*, date: str, season: int, env=None) -> dict[str, Any]:
    report = _run_team_page_reconciliation(date=date, season=season, env=env)
    report["schedule_transport_source"] = MODEL_SOURCE
    report["schedule_transport_model_version"] = MODEL_VERSION
    report["official_team_page_source"] = TEAM_PAGE_SOURCE
    report["official_team_page_model_version"] = TEAM_PAGE_MODEL_VERSION
    return report
