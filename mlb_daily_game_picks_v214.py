"""MLB Daily Game Picks V2.1.4 — sportsbook cooldown quarantine.

Orchestration hotfix only. Preserves V2.1.3 persistent completed-card snapshots,
V2.1.2.x live-risk and market-gap logic, all seven production model formulas,
simulation depths, sportsbook verification gates, normalization, Step 5/6 scoring,
team logos, and identity firewalls.

Fixes the 0/7 freeze when Run Line triggers an HTTP 429 at stage 1:
- Run Line/Total cooldown is isolated to those two sportsbook-backed stages;
- the controller continues immediately through Moneyline, Pitcher K, H+R+RBI,
  Home Run, and 1+ Hit;
- once those five finish, the existing visible armed cooldown waits only for
  Run Line + Total;
- when the provider resets, the existing resume controller rebuilds only the two
  unfinished sportsbook stages and skips the five completed stages.
"""
from __future__ import annotations

import streamlit as st

import mlb_daily_game_picks_v213 as previous
import mlb_daily_game_picks_v2125 as retry
import mlb_daily_game_picks_v2124 as resume_ui

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.4 • 429 QUARANTINE"

# V2.1.2.5 kept a reference to the original proven V2.0.8 stage builder before
# adding its stop-on-429 handoff. Use that original builder so a sportsbook 429
# cannot set controller.active=False in the middle of the seven-stage pass.
_NATIVE_STAGE_BUILDER = retry._BASE_BUILD_STAGE


def _cooldown_pack(games_df, stage, current=None):
    """Return/save an incomplete pack without making another provider request."""
    key = controller._pack_key(games_df, stage)
    pack = dict(current) if isinstance(current, dict) else {}
    pack["complete"] = False
    pack.setdefault("rows", [])
    pack.setdefault("remaining_count", 0)
    errors = list(pack.get("errors") or [])
    note = "Sportsbook provider cooldown is active; request skipped so other production connectors can continue."
    if not errors or errors[-1] != note:
        errors.append(note)
    pack["errors"] = errors
    if key:
        st.session_state[key] = pack
    return pack


def _build_stage_v214(games_df, stage):
    """Quarantine sportsbook cooldown while allowing the rest of the card to build."""
    if stage in {"runline", "total"}:
        current = controller._pack(games_df, stage)
        if resume_ui._cooldown_until(games_df):
            return _cooldown_pack(games_df, stage, current)

    built = _NATIVE_STAGE_BUILDER(games_df, stage)

    if stage in {"runline", "total"} and not controller._complete(built):
        cooldown = resume_ui._cooldown_until(games_df)
        if cooldown:
            day = controller._day(games_df)
            # Do NOT stop the active full-card controller here. Let V2.0.8 mark
            # this stage blocked for this pass and advance to the next connector.
            st.session_state[resume_ui._notice_key(day)] = (
                "Sportsbook cooldown isolated to Run Line + Total. The other five production connectors will continue automatically."
            )
    return built


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # V2.1.2.5 defensively reassigns this hook each render, so install V2.1.4
    # immediately before entering the inherited renderer.
    controller._build_stage = _build_stage_v214
    st.caption(
        "🧱 V2.1.4 429 quarantine: Run Line/Total rate limits no longer freeze the full card; the other five connectors continue while sportsbook retry waits."
    )
    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
