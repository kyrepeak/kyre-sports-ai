from fastapi import FastAPI

from sports_api.api.health import router as health_router
from sports_api.api.mlb import router as mlb_router
from sports_api.api.mlb_stats import router as mlb_stats_router

app = FastAPI(
    title="Kyre Sports API",
    description="Sports data and analytics API for the Kyre Sports AI Streamlit app.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(mlb_router)
app.include_router(mlb_stats_router)


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
