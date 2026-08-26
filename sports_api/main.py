from fastapi import FastAPI

from sports_api.api.health import router as health_router
from sports_api.api.mlb import router as mlb_router
from sports_api.api.mlb_advanced_hitting import router as mlb_advanced_hitting_router
from sports_api.api.mlb_advanced_pitching import router as mlb_advanced_pitching_router
from sports_api.api.mlb_batter_pitcher import router as mlb_batter_pitcher_router
from sports_api.api.mlb_boxscore import router as mlb_boxscore_router
from sports_api.api.mlb_bullpen import router as mlb_bullpen_router
from sports_api.api.mlb_environment import router as mlb_environment_router
from sports_api.api.mlb_game_logs import router as mlb_game_logs_router
from sports_api.api.mlb_head_to_head import router as mlb_head_to_head_router
from sports_api.api.mlb_hitter_pitch_type import router as mlb_hitter_pitch_type_router
from sports_api.api.mlb_pitch_movement import router as mlb_pitch_movement_router
from sports_api.api.mlb_pitch_type_effectiveness import router as mlb_pitch_type_effectiveness_router
from sports_api.api.mlb_recent_form import router as mlb_recent_form_router
from sports_api.api.mlb_roster_status import router as mlb_roster_status_router
from sports_api.api.mlb_slate_verification import router as mlb_slate_verification_router
from sports_api.api.mlb_starting_pitchers import router as mlb_starting_pitchers_router
from sports_api.api.mlb_stats import router as mlb_stats_router
from sports_api.api.mlb_team_analytics import router as mlb_team_analytics_router

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
