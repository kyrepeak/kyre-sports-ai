"""Step 5.3 wrapper for the certified MLB Daily Game Picks V2.1.7 guard.

Keeps the full Step 5.2 exact-ID live FanDuel market layer intact, then upgrades
that read-only presentation hook to also derive raw implied probability, sportsbook
hold, and proportional no-vig fair probability. Production model math, Pick
Strength, selection/ranking, persistence, wagering, and WNBA behavior are unchanged.
"""
from __future__ import annotations

import mlb_daily_game_picks_v217_guard as previous
from mlb_daily_game_picks_market_probability_v1 import install_market_probability_layer

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.7 • STEP 5.3 NO-VIG MARKET PROBABILITY"


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # The inherited V2.1.7 guard calls its module-global install_live_market_context
    # immediately before rendering. Rebind only that presentation hook so Step 5.3
    # runs in the exact same safe location. The original lineup/risk guard and every
    # production calculation remain untouched.
    previous.install_live_market_context = install_market_probability_layer
    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )


__all__ = ["VERSION", "controller", "render_daily_game_picks"]
