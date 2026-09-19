"""Additive Render entrypoint for feed-independent CFB verified identities.

The certified shared-host application remains the base app. This wrapper adds
one read-only CFB identity route used by the Streamlit Game Total selector.
No existing route, lifespan, model, projection, or sportsbook behavior is
replaced or modified.
"""
from sports_api.main import app
from sports_api.api.cfb_verified_games_v1 import verified_games

VERIFIED_GAMES_PATH = "/api/v1/cfb/markets/verified-games"

app.add_api_route(
    VERIFIED_GAMES_PATH,
    verified_games,
    methods=["GET"],
    tags=["cfb"],
)

__all__ = ["VERIFIED_GAMES_PATH", "app"]
