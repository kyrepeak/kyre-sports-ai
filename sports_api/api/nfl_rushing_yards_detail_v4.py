"""NFL Rushing Yards Page 2 detail V4 live-readback repair.

Keeps the certified V3 enrichment/presentation contract intact while replacing
only the two provider functions that failed in production after PR #1824.
"""
from __future__ import annotations

from sports_api.api import nfl_rushing_yards_detail_v3 as v3
from sports_api.nfl_rushing_yards_page2_live_repair_r1 import (
    TEAM_NAMES,
    build_injury_personnel_context,
    collect_market_context,
    collect_official_nfl_injury_report,
    collect_weather,
    repair_history_dates,
)

VERSION = "NFL_RUSHING_YARDS_DETAIL_V4_LIVE_REPAIR_R1"

# V3 resolves these names at request time. Replace only the failed provider
# seams; all V3 normalization, weather/date repair, decision logic, and public
# schema remain unchanged.
v3.TEAM_NAMES = TEAM_NAMES
v3.build_injury_personnel_context = build_injury_personnel_context
v3.collect_market_context = collect_market_context
v3.collect_official_nfl_injury_report = collect_official_nfl_injury_report
v3.collect_weather = collect_weather
v3.repair_history_dates = repair_history_dates

build_detail_bundle = v3.build_detail_bundle
enrich_detail_payload = v3.enrich_detail_payload
router = v3.router
SCHEMA_VERSION = v3.SCHEMA_VERSION
SERVICE = v3.SERVICE
GATEWAY = v3.GATEWAY

# The reused V2 route resolves its module-global builder at request time.
v3.base.build_detail_bundle = build_detail_bundle

__all__ = ["GATEWAY", "SCHEMA_VERSION", "SERVICE", "VERSION", "build_detail_bundle", "enrich_detail_payload", "router"]
