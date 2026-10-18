"""Collapsed maintainer diagnostics for the WNBA PRA playoff product."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def _records(frame):
    return frame.to_dict("records") if isinstance(frame, pd.DataFrame) and not frame.empty else []


def render_advanced_diagnostics(snapshot, context, consensus) -> None:
    with st.expander("⚙️ Advanced Diagnostics", expanded=False):
        st.json({
            "selected_date": context.selected_date,
            "effective_date": context.effective_date,
            "playoff_context": {
                "competition": context.competition_label,
                "series": context.series_label,
                "evidence_state": context.evidence_state,
                "sources": list(context.sources),
                "today_has_game": context.today_has_game,
            },
            "schedule": dict(snapshot.schedule_diag or {}),
            "availability": dict(snapshot.availability_diag or {}),
            "minutes_role": dict(snapshot.role_diag or {}),
            "market_meta": dict(snapshot.market_meta or {}),
            "matchup_meta": dict(snapshot.matchup_meta or {}),
            "monte_carlo_state": dict(snapshot.stored_mc_meta or {}),
            "market_consensus": _records(consensus),
            "raw_schedule_games": _records(snapshot.schedule),
        })


__all__ = ["render_advanced_diagnostics"]
