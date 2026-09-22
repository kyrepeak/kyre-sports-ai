"""WNBA Daily Picks V36 — Step 18C reliability presentation over V35."""
from __future__ import annotations

from typing import Any, Mapping
import streamlit as st

import wnba_daily_picks_hub_v35 as v35
from wnba_streamlit_consumer_v2 import load_latest_daily_picks

MODEL_VERSION = "WNBA DAILY PICKS V36 • STEP 18C RELIABILITY"

# V35 resolves these helpers dynamically, so V36 can preserve its certified card
# presentation while swapping only the hardened read/state layer.
v35.load_latest_daily_picks = load_latest_daily_picks
_ORIGINAL_RENDER_STATUS = v35._render_status

_REASON_TEXT = {
    "not_executed": "The latest scheduler cycle completed without a current qualified Daily Picks board.",
    "provider_transient_not_ready": "A required sportsbook feed is temporarily unavailable. No old picks are being reused.",
    "transient_failure": "The production controller is temporarily degraded. Daily Picks will stay empty until a healthy fresh cycle.",
    "circuit_open": "The production safety circuit is open. Daily Picks are hidden until the scheduler recovers.",
    "board_unavailable": "No current qualified Daily Picks board is available.",
}


def _render_status_reliable(view: Mapping[str, Any]) -> None:
    if str(view.get("state") or "") == "unavailable":
        reason = str(view.get("reason") or "board_unavailable")
        st.info(_REASON_TEXT.get(reason, f"No current qualified WNBA Daily Picks board is available. Production reason: {reason}."))
        snapshot = view.get("snapshot") if isinstance(view.get("snapshot"), Mapping) else {}
        runtime = view.get("runtime") if isinstance(view.get("runtime"), Mapping) else {}
        details = []
        try:
            if snapshot.get("age_seconds") is not None:
                details.append(f"snapshot age {float(snapshot['age_seconds']):.0f}s")
        except (TypeError, ValueError):
            pass
        if runtime.get("next_refresh_due_at_utc"):
            details.append(f"next refresh {runtime['next_refresh_due_at_utc']}")
        if details:
            st.caption(" • ".join(details))
        return
    _ORIGINAL_RENDER_STATUS(view)


v35._render_status = _render_status_reliable


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return v35.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
