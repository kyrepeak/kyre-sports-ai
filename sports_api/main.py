from fastapi import FastAPI

from sports_api.api.health import router as health_router
from sports_api.api.mlb import router as mlb_router
from sports_api.api.mlb_advanced_hitting import router as mlb_advanced_hitting_router
from sports_api.api.mlb_advanced_pitching import router as mlb_advanced_pitching_router
from sports_api.api.mlb_arsenal_matchup import router as mlb_arsenal_matchup_router
from sports_api.api.mlb_batted_ball_context import router as mlb_batted_ball_context_router
from sports_api.api.mlb_batter_pitcher import router as mlb_batter_pitcher_router
from sports_api.api.mlb_boxscore import router as mlb_boxscore_router
from sports_api.api.mlb_bullpen import router as mlb_bullpen_router
from sports_api.api.mlb_environment import router as mlb_environment_router
from sports_api.api.mlb_game_logs import router as mlb_game_logs_router
from sports_api.api.mlb_head_to_head import router as mlb_head_to_head_router
from sports_api.api.mlb_hit_defense_context import router as mlb_hit_defense_context_router
from sports_api.api.mlb_hit_environment_context import router as mlb_hit_environment_context_router
from sports_api.api.mlb_hit_opportunity_features import router as mlb_hit_opportunity_features_router
from sports_api.api.mlb_hitter_pitch_type import router as mlb_hitter_pitch_type_router
from sports_api.api.mlb_lineup_matchups import router as mlb_lineup_matchups_router
from sports_api.api.mlb_park_factor_context import router as mlb_park_factor_context_router
from sports_api.api.mlb_pitch_movement import router as mlb_pitch_movement_router
from sports_api.api.mlb_pitch_type_effectiveness import router as mlb_pitch_type_effectiveness_router
from sports_api.api.mlb_plate_appearances import router as mlb_plate_appearances_router
from sports_api.api.mlb_recent_form import router as mlb_recent_form_router
from sports_api.api.mlb_roster_status import router as mlb_roster_status_router
from sports_api.api.mlb_slate_verification import router as mlb_slate_verification_router
from sports_api.api.mlb_starting_pitchers import router as mlb_starting_pitchers_router
from sports_api.api.mlb_stats import router as mlb_stats_router
from sports_api.api.mlb_team_analytics import router as mlb_team_analytics_router
from sports_api.api.wnba import router as wnba_router
from sports_api.api.wnba_advanced import router as wnba_advanced_router
from sports_api.api.wnba_availability import router as wnba_availability_router
from sports_api.api.wnba_clutch_context import router as wnba_clutch_context_router
from sports_api.api.wnba_defensive_activity import router as wnba_defensive_activity_router
from sports_api.api.wnba_event_lineup_context import router as wnba_event_lineup_context_router
from sports_api.api.wnba_lineup_context import router as wnba_lineup_context_router
from sports_api.api.wnba_live_game import router as wnba_live_game_router
from sports_api.api.wnba_matchup_context import router as wnba_matchup_context_router
from sports_api.api.wnba_officiating_context import router as wnba_officiating_context_router
from sports_api.api.wnba_rotation_context import router as wnba_rotation_context_router
from sports_api.api.wnba_schedule_context import router as wnba_schedule_context_router
from sports_api.api.wnba_shot_context import router as wnba_shot_context_router
from sports_api.api.wnba_standings import router as wnba_standings_router
from sports_api.api.wnba_team_history import router as wnba_team_history_router
from sports_api.api.wnba_tracking import router as wnba_tracking_router

app = FastAPI(
    title="Kyre Sports API",
    description="Sports data and analytics API for the Kyre Sports AI Streamlit app.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(mlb_router)
app.include_router(mlb_stats_router)
app.include_router(mlb_game_logs_router)
app.include_router(mlb_recent_form_router)
app.include_router(mlb_boxscore_router)
app.include_router(mlb_team_analytics_router)
app.include_router(mlb_head_to_head_router)
app.include_router(mlb_starting_pitchers_router)
app.include_router(mlb_slate_verification_router)
app.include_router(mlb_bullpen_router)
app.include_router(mlb_environment_router)
app.include_router(mlb_batter_pitcher_router)
app.include_router(mlb_roster_status_router)
app.include_router(mlb_advanced_hitting_router)
app.include_router(mlb_advanced_pitching_router)
app.include_router(mlb_pitch_type_effectiveness_router)
app.include_router(mlb_pitch_movement_router)
app.include_router(mlb_hitter_pitch_type_router)
app.include_router(mlb_arsenal_matchup_router)
app.include_router(mlb_lineup_matchups_router)
app.include_router(mlb_plate_appearances_router)
app.include_router(mlb_hit_opportunity_features_router)
app.include_router(mlb_hit_environment_context_router)
app.include_router(mlb_hit_defense_context_router)
app.include_router(mlb_batted_ball_context_router)
app.include_router(mlb_park_factor_context_router)
app.include_router(wnba_router)
app.include_router(wnba_advanced_router)
app.include_router(wnba_availability_router)
app.include_router(wnba_clutch_context_router)
app.include_router(wnba_defensive_activity_router)
app.include_router(wnba_event_lineup_context_router)
app.include_router(wnba_lineup_context_router)
app.include_router(wnba_live_game_router)
app.include_router(wnba_matchup_context_router)
app.include_router(wnba_officiating_context_router)
app.include_router(wnba_rotation_context_router)
app.include_router(wnba_schedule_context_router)
app.include_router(wnba_shot_context_router)
app.include_router(wnba_standings_router)
app.include_router(wnba_team_history_router)
app.include_router(wnba_tracking_router)


@app.get("/", tags=["system"])
def root():
    return {
        "name": "Kyre Sports API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "first_data_endpoint": "/api/v1/mlb/games/today",
    }
