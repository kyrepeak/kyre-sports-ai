from fastapi import FastAPI

from sports_api.api.health import router as health_router

app = FastAPI(
    title="Kyre Sports API",
    description="Sports data and analytics API for the Kyre Sports AI Streamlit app.",
    version="0.1.0",
)

app.include_router(health_router)


@app.get("/", tags=["system"])
def root():
    return {
        "name": "Kyre Sports API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }
