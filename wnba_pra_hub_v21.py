"""WNBA PRA V2.1 UI bridge using the official-CDN schedule transport hotfix."""

import wnba_pra_hub_v2 as hub
from wnba_data_v21 import (
    current_season,
    data_health,
    empirical_profile,
    game_for_team,
    logo_url,
    official_roster,
    player_form_table,
    player_game_log,
    schedule_for_date,
    slate_player_pool,
    team_player_pool,
)

# Patch the V2 hub's module globals. Its rendering/model functions resolve these
# names at call time, so the UI remains unchanged while transport uses V2.1.
hub.current_season = current_season
hub.data_health = data_health
hub.empirical_profile = empirical_profile
hub.game_for_team = game_for_team
hub.logo_url = logo_url
hub.official_roster = official_roster
hub.player_form_table = player_form_table
hub.player_game_log = player_game_log
hub.schedule_for_date = schedule_for_date
hub.slate_player_pool = slate_player_pool
hub.team_player_pool = team_player_pool
hub.MODEL_VERSION = "PRA V2.1"


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
