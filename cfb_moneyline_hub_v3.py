"""College Football Moneyline Hub V3 — mixed-division schedule/data hotfix.

Additive correctness wrapper over permanently frozen Step-5 Moneyline Hub V2.

Only data providers are swapped while this wrapper renders:
- schedule: cfb_schedule_v2
- team data: cfb_team_data_v2

The frozen Moneyline Model V1, UI math, probability math, and Step-5 output
contract remain byte-identical.
"""
from __future__ import annotations

import streamlit as st

import cfb_moneyline_hub_v2 as prior
import cfb_schedule_v2 as schedule_v2
import cfb_team_data_v2 as team_data_v2

MODEL_VERSION = "CFB MONEYLINE HUB V3 • MIXED-DIVISION HOTFIX"
FROZEN_CFB_MONEYLINE_HUB = "cfb_moneyline_hub_v2"
MARKET = "Moneyline"


def render_moneyline_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🛠️ CFB mixed-division hotfix ACTIVE • FBS-vs-FCS schedule + team-data "
        "supplement • frozen Step 5 Moneyline Model V1 unchanged"
    )

    original_schedule = prior.schedule
    original_team_data = prior.team_data
    prior.schedule = schedule_v2
    prior.team_data = team_data_v2
    try:
        return prior.render_moneyline_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        prior.schedule = original_schedule
        prior.team_data = original_team_data


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        return prior.render_cfb_hub(
            market,
            section_header,
            status_info,
            team_logo,
            h,
        )
    return render_moneyline_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


__all__ = [
    "FROZEN_CFB_MONEYLINE_HUB",
    "MARKET",
    "MODEL_VERSION",
    "render_cfb_hub",
    "render_moneyline_hub",
]
