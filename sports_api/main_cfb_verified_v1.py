"""Additive Render entrypoint for feed-independent CFB verified identities.

The certified shared-host application remains the base app. This wrapper mounts
one read-only CFB identity router used by the Streamlit Game Total selector.
No existing route, lifespan, model, projection, or sportsbook behavior is
replaced or modified.
"""
from sports_api.main import app
from sports_api.api.cfb_verified_games_v1 import router as cfb_verified_games_router

app.include_router(cfb_verified_games_router)

__all__ = ["app"]
