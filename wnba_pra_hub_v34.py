"""WNBA PRA V3.4 — today-slate rollover + injury-source integrity.

V3.4 keeps the V3.3 injury/minutes/role fingerprint protections and adds:
- automatic Eastern-date rollover to today's slate once per calendar day/session;
- a conservative same-day RotoWire daily-lineups OUT/status supplement;
- no use of RotoWire expected lineups as confirmed starters.

Projection formulas, matchup weights, SportsGameOdds grading and 5M/10M Monte
Carlo rules remain unchanged.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_rotowire_status_v34 as rotowire
import wnba_pra_hub_v33 as v33

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "PRA V3.4 • TODAY SLATE + MULTI-SOURCE AVAILABILITY"
MLB_FROZEN_BASELINE = v33.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = v33.MLB_FROZEN_BRANCH


def _roll_to_today_once():
    """Reset a stale prior-day widget state without blocking manual date research."""
    today = datetime.now(ET).date()
    today_key = today.isoformat()
    marker_key = "wnba_pra_v34_rollover_day"

    if st.session_state.get(marker_key) != today_key:
        st.session_state["wnba_pra_v2_date"] = today
        st.session_state[marker_key] = today_key
        st.session_state["wnba_pra_v34_auto_rolled"] = True


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _roll_to_today_once()
    rotowire.install()

    st.caption(
        "📅 PRA V3.4 • TODAY-SLATE ROLLOVER ACTIVE • ESPN/current roster + RotoWire same-day status supplement • "
        "V3.3 injury/minutes/role fingerprint protection retained"
    )

    result = v33.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    if st.session_state.pop("wnba_pra_v34_auto_rolled", False):
        today = datetime.now(ET).strftime("%Y-%m-%d")
        st.toast(f"📅 PRA slate auto-rolled to today (ET): {today}")

    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
