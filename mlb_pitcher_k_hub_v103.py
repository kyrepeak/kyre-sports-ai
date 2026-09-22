"""MLB Pitcher Strikeouts O/U V1.0.3 schedule compatibility bridge.

Fixes the isolated Pitcher K page's V3.2 schedule diagnostic call without
changing any other MLB/WNBA route, schedule behavior, projection math, or odds
logic. The V1.0 engine expected games_for_date_with_diagnostics(); MLB Schedule
V3.2 exposes the same contract as load_with_diagnostics().
"""

import mlb_schedule_v32 as schedule

# Compatibility alias for the isolated Pitcher K engine only.
if not hasattr(schedule, "games_for_date_with_diagnostics"):
    schedule.games_for_date_with_diagnostics = schedule.load_with_diagnostics

import mlb_pitcher_k_hub_v102 as base

MODEL_VERSION = "Pitcher K V1.0.3"


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    return base.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
