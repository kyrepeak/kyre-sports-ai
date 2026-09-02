"""Compatibility entrypoint for the current MLB Matchup Explorer presentation."""
from __future__ import annotations

from mlb_matchup_hub_v28 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub

__all__ = ["FROZEN_MATCHUP_CHAIN", "VERSION", "render_matchup_hub"]
