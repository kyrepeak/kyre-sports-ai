from fastapi import FastAPI

from sports_api.api.health import router as health_router
from sports_api.api.mlb import router as mlb_router
from sports_api.api.mlb_boxscore import router as mlb_boxscore_router
from sports_api.api.mlb_game_logs import router as mlb_game_logs_router
from sports_api.api.mlb_head_to_head import router as mlb_head_to_head_router
from sports_api.api.mlb_recent_form import router as mlb_recent_form_router
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
