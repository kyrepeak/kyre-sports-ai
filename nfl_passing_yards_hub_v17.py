"""NFL Passing Yards V17 — early-season verified baseline bridge.

Presentation/data-routing wrapper over certified V16. It preserves Steps 1–10
math and the cleanup UI while allowing verified 2025 regular-season evidence to
bridge the opening 2026 slate when no current-season completed-game sample exists.
Current-season data always wins automatically as soon as it is usable.

Production hotfix: ESPN Core season statistics are now requested from the
explicit all-splits ``statistics/0`` resource first. This fixes the blank Step 2+
chain seen on the Sep. 13 opening-week slate without changing model math.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import nfl_passing_yards_defense_v1 as defense_v1
import nfl_passing_yards_defense_v2 as defense_v2
import nfl_passing_yards_environment_v2 as environment_v2
import nfl_passing_yards_espn_stat_split_v1 as stat_split
import nfl_passing_yards_hub_v16 as prior
import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_pressure_v2 as pressure_v2

MODEL_VERSION = "NFL PASSING YARDS V17 • EARLY SEASON VERIFIED BRIDGE • ESPN SPLIT-ZERO HOTFIX"

_EARLY_CSS = r"""
<style>
.kpy17-prov{margin:5px 0 7px;border:1px solid #6c5b28;background:#241f0d;border-radius:9px;padding:6px 8px;color:#e8c96f;font-size:.44rem;line-height:1.45;font-weight:850}
.kpy17-prov b{color:#fff}
</style>
"""


def _with_provenance(html: str, row: dict, label: str) -> str:
    if not row or not row.get("early_season_fallback"):
        return html
    prov = str(row.get("baseline_provenance") or "EARLY-SEASON VERIFIED BASELINE")
    note = (
        f'<div class="kpy17-prov"><b>{escape(label)}:</b> {escape(prov)} • '
        'current-season data will replace this automatically once a verified sample exists.</div>'
    )
    return html + note


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_EARLY_CSS, unsafe_allow_html=True)

    original_profile_builder = step7_ui.profile.build_qb_profile
    original_profile_season_loader = step7_ui.profile._season_stats_payload
    original_team_stats_loader = defense_v1._team_stats_payload
    original_defense_builder = step7_ui.defense.build_pass_defense_profile
    original_pressure_builder = step7_ui.pressure.build_pressure_matchup
    original_environment_builder = step7_ui.environment.build_game_environment
    original_profile_card = step7_ui.step2_ui._profile_card
    original_defense_card = step7_ui.step3_ui._defense_card

    profiles: list[dict] = []
    defenses: list[dict] = []

    def capture_profile(*args, **kwargs):
        row = dict(original_profile_builder(*args, **kwargs) or {})
        profiles.append(row)
        return row

    def bridged_defense(*args, **kwargs):
        row = dict(defense_v2.build_pass_defense_profile(*args, **kwargs) or {})
        defenses.append(row)
        return row

    def profile_card(team_ctx: dict, qb_profile: dict) -> str:
        return _with_provenance(original_profile_card(team_ctx, qb_profile), qb_profile, "Step 2 source")

    def defense_card(qb_ctx: dict, opponent_ctx: dict, defense_profile: dict) -> str:
        return _with_provenance(original_defense_card(qb_ctx, opponent_ctx, defense_profile), defense_profile, "Step 3 source")

    # Exact verified IDs still drive every request. The only transport change is
    # selecting ESPN's explicit all-splits statistics/0 resource first.
    step7_ui.profile._season_stats_payload = stat_split.athlete_stats_payload
    defense_v1._team_stats_payload = stat_split.team_stats_payload
    step7_ui.profile.build_qb_profile = capture_profile
    step7_ui.defense.build_pass_defense_profile = bridged_defense
    step7_ui.pressure.build_pressure_matchup = pressure_v2.build_pressure_matchup
    step7_ui.environment.build_game_environment = environment_v2.build_game_environment
    step7_ui.step2_ui._profile_card = profile_card
    step7_ui.step3_ui._defense_card = defense_card
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.profile._season_stats_payload = original_profile_season_loader
        defense_v1._team_stats_payload = original_team_stats_loader
        step7_ui.profile.build_qb_profile = original_profile_builder
        step7_ui.defense.build_pass_defense_profile = original_defense_builder
        step7_ui.pressure.build_pressure_matchup = original_pressure_builder
        step7_ui.environment.build_game_environment = original_environment_builder
        step7_ui.step2_ui._profile_card = original_profile_card
        step7_ui.step3_ui._defense_card = original_defense_card


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
