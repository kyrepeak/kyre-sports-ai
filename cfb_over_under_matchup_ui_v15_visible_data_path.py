"""CFB O/U UI V15 — visible-data-path hotfix.

Additive hotfix above permanently frozen V14.

Root cause
----------
V14 reconciled the selected matchup, but its hero forwarded only the reconciled
game object into the frozen V13 hero while still forwarding the stale away/home
profiles it received from the caller. That allowed the visible Step-1/Step-2
cards to keep showing 0-0 / NR / blank Coaches even though the reconciliation
engine had already recovered the correct evidence.

V15 resolves one matchup once for presentation and forwards the reconciled
game, away profile, and home profile together into the complete frozen hero
stack. It also routes the base date loader through Schedule V4 so the visible
schedule diagnostics, venue, broadcast, event ID, event records, and event rank
use the same alias-safe ESPN match.

No model formula, projection weight, selection threshold, sportsbook input,
market probability, EV, or Monte Carlo behavior is added.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import cfb_over_under_deep_data_reconciliation_v1 as deep_data
import cfb_over_under_hub_v1 as base_hub
import cfb_over_under_matchup_ui_v1 as step1_ui
import cfb_over_under_matchup_ui_v14_deep_data as frozen_v14
import cfb_schedule_v4 as schedule_v4

MODEL_VERSION = "CFB O/U UI V15 • VISIBLE DATA PATH HOTFIX"
FROZEN_PARENT_UI = "cfb_over_under_matchup_ui_v14_deep_data"
MARKET = "Over/Under"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _reconciled_triplet(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        evidence, _ = deep_data.reconcile_matchup(
            game,
            _clean(game.get("game_date")),
        )
    except Exception:
        return dict(game), dict(away), dict(home)

    game2 = dict(evidence.get("game") or game)
    away2 = dict(evidence.get("away") or away)
    home2 = dict(evidence.get("home") or home)
    return game2, away2, home2


def _hero_v15(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    game2, away2, home2 = _reconciled_triplet(game, away, home)
    return (
        frozen_v14._FROZEN_V13_HERO(game2, away2, home2)
        + frozen_v14._current_data_panel(game2, away2, home2)
    )


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
):
    st.caption("🟢 CFB O/U • VISIBLE DATA PATH HOTFIX V1 ACTIVE")

    original_hero = frozen_v14._hero_v14
    original_base_schedule = base_hub.schedule
    original_step1_schedule = step1_ui.schedule

    frozen_v14._hero_v14 = _hero_v15
    base_hub.schedule = schedule_v4
    step1_ui.schedule = schedule_v4
    try:
        return frozen_v14.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v14._hero_v14 = original_hero
        base_hub.schedule = original_base_schedule
        step1_ui.schedule = original_step1_schedule


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
):
    if market != MARKET:
        raise ValueError(
            f"Visible-data-path O/U UI received unsupported market: {market}"
        )
    return render_over_under_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


__all__ = [
    "FROZEN_PARENT_UI",
    "MARKET",
    "MODEL_VERSION",
    "_hero_v15",
    "_reconciled_triplet",
    "render_cfb_hub",
    "render_over_under_hub",
]
