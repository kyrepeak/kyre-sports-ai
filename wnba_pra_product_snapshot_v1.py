"""Read-only snapshot boundary for the WNBA PRA playoff product.

This module only copies outputs from the preserved production engine. It never
recalculates projections, qualification, probabilities, Monte Carlo, ranking,
or final-card selection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

import wnba_pra_market_v29 as market
import wnba_pra_matchup_v30 as matchup
import wnba_pra_final_v32 as final
import wnba_schedule_v25 as schedule
import wnba_pra_hub_v27 as v27
import wnba_role_v282 as role


def _frame(value: Any) -> pd.DataFrame:
    return value.copy(deep=True) if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _mapping(value: Any) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class PRAProductSnapshot:
    day: str
    schedule: pd.DataFrame
    schedule_diag: Mapping[str, Any]
    projections: pd.DataFrame
    market_rows: pd.DataFrame
    market_meta: Mapping[str, Any]
    matchup_rows: pd.DataFrame
    matchup_meta: Mapping[str, Any]
    stored_mc_rows: pd.DataFrame
    stored_mc_meta: Mapping[str, Any]
    final_card: pd.DataFrame
    availability_diag: Mapping[str, Any]
    role_diag: Mapping[str, Any]


def build_product_snapshot(day: str) -> PRAProductSnapshot:
    projections_raw, schedule_raw = market._projection_frame(day)
    market_raw, market_meta_raw = market.grade_pra_markets(day)
    matchup_raw, matchup_meta_raw = matchup.grade_matchup_pra(day)
    stored_raw, stored_meta_raw = final._stored_rows(day)
    stored_rows = _frame(stored_raw)
    final_raw = final.select_master_card(stored_rows.copy(deep=True), limit=final.MAX_CARD)

    return PRAProductSnapshot(
        day=str(day),
        schedule=_frame(schedule_raw),
        schedule_diag=_mapping(schedule.schedule_diagnostics(day)),
        projections=_frame(projections_raw),
        market_rows=_frame(market_raw),
        market_meta=_mapping(market_meta_raw),
        matchup_rows=_frame(matchup_raw),
        matchup_meta=_mapping(matchup_meta_raw),
        stored_mc_rows=stored_rows,
        stored_mc_meta=_mapping(stored_meta_raw),
        final_card=_frame(final_raw),
        availability_diag=_mapping(v27.availability.availability_diagnostics(day)),
        role_diag=_mapping(role.role_diagnostics(day)),
    )


__all__ = ["PRAProductSnapshot", "build_product_snapshot"]
