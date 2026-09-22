"""MLB Moneyline V16.4 compatibility boundary -> V16.5 clean presentation.

The Streamlit router still imports this historical filename. Forward that exact
boundary to V16.5, which preserves the frozen V16.3/V16.2/V16.1/V16 model chain
and Step 7C exact-ID FanDuel context while restoring clean mobile card styling.
"""
from __future__ import annotations

MODEL_VERSION = "V16.4 COMPATIBILITY BOUNDARY -> V16.5 CLEAN PRESENTATION"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    # Lazy import keeps the memory-safe router behavior: the Moneyline graph is
    # loaded only after the user selects the MLB Moneyline route.
    from mlb_moneyline_hub_v165 import render_moneyline_hub as render_v165
    return render_v165(games_df, section_header, status_info, team_logo, h)


__all__ = ["DEFAULT_API_BASE_URL", "MODEL_VERSION", "render_moneyline_hub"]
