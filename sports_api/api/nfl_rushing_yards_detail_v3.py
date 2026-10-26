"""NFL Rushing Yards Page 2 detail V3 successor.

Wraps the frozen V2 detail service and enriches fields that V2 intentionally
left semantic/pending. The public route and schema stay unchanged; Kyre Sports
API remains the only application-facing gateway.
"""
from __future__ import annotations

from typing import Any, Mapping

from sports_api.api import nfl_rushing_yards_detail_v2 as base
from sports_api.nfl_rushing_yards_page2_enrichment_v1 import (
    TEAM_NAMES,
    build_injury_personnel_context,
    collect_market_context,
    collect_official_nfl_injury_report,
    collect_weather,
    repair_history_dates,
)

VERSION = "NFL_RUSHING_YARDS_DETAIL_V3_DATA_COMPLETENESS"
_BASE_BUILD = base.build_detail_bundle


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _game_sides(detail: Mapping[str, Any]) -> tuple[str, str]:
    team = _text(detail.get("team_abbr")).upper()
    opponent = _text(detail.get("opponent_abbr")).upper()
    home_away = _text(detail.get("home_away")).upper()
    if home_away == "AWAY":
        return team, opponent
    return opponent, team


def _schedule_map() -> dict[str, str]:
    try:
        frame = base.slate._load_games_csv()
    except Exception:
        return {}
    if frame is None or getattr(frame, "empty", True):
        return {}
    out: dict[str, str] = {}
    for _, row in frame.iterrows():
        game_id = _text(row.get("game_id"))
        gameday = _text(row.get("gameday"))[:10]
        if game_id and gameday:
            out[game_id] = gameday
    return out


def _clean_final_read(detail: dict[str, Any], *, personnel_verified: bool, weather_verified: bool, movement_verified: bool) -> None:
    final = dict(detail.get("final_read") or {})
    risks = [str(item) for item in (final.get("risk_factors") or [])]
    unresolved = [str(item) for item in (final.get("unresolved") or [])]
    if personnel_verified:
        risks = [item for item in risks if "Personnel verification" not in item]
    if weather_verified:
        unresolved = [item for item in unresolved if "Weather verification" not in item]
    if movement_verified:
        unresolved = [item for item in unresolved if "line-movement history" not in item]
    final["risk_factors"] = risks
    final["unresolved"] = unresolved
    detail["final_read"] = final


def enrich_detail_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(payload or {})
    if out.get("ready") is not True or not isinstance(out.get("detail"), Mapping):
        return out
    detail = dict(out["detail"])
    away, home = _game_sides(detail)
    away_name = TEAM_NAMES.get(away, away)
    home_name = TEAM_NAMES.get(home, home)
    kickoff = _text(detail.get("game_time") or (detail.get("environment") or {}).get("kickoff_et"))
    player_name = _text(detail.get("player_name"))
    team = _text(detail.get("team_abbr")).upper()
    opponent = _text(detail.get("opponent_abbr")).upper()

    market = dict(detail.get("market_intelligence") or detail.get("market") or {})
    current_prop = {
        "sportsbook": market.get("sportsbook"),
        "current_line": market.get("current_line") if market.get("current_line") is not None else market.get("line"),
    }
    market_context = collect_market_context(
        away_name=away_name,
        home_name=home_name,
        kickoff_iso=kickoff,
        player_name=player_name,
        current_prop=current_prop,
    )
    market.update(dict(market_context.get("prop_history") or {}))
    detail["market_intelligence"] = market

    script = dict(detail.get("game_script") or {})
    game_market = dict(market_context.get("game_market") or {})
    if game_market:
        sportsbook = _text(game_market.get("sportsbook"))
        team_spread = game_market.get("away_spread") if team == away else game_market.get("home_spread")
        if team_spread is not None:
            script["spread"] = team_spread
            script["spread_status"] = f"{team} {float(team_spread):+.1f} · {sportsbook}"
            script["spread_verification"] = "VERIFIED"
        if game_market.get("total") is not None:
            script["total"] = game_market.get("total")
            script["total_status"] = f"{float(game_market['total']):.1f} · {sportsbook}"
            script["total_verification"] = "VERIFIED"
        script["game_market_timestamp"] = game_market.get("timestamp")

    weather = collect_weather(home_abbr=home, kickoff_iso=kickoff) if kickoff and home else {"verification":"UNAVAILABLE","display":"Weather data unavailable"}
    script["weather"] = weather
    script["weather_status"] = _text(weather.get("display"))
    script["weather_verification"] = weather.get("verification")
    detail["game_script"] = script

    try:
        report = collect_official_nfl_injury_report()
    except Exception:
        report = {}
    injury = build_injury_personnel_context(report, player_name=player_name, team=team, opponent=opponent)
    detail["availability"] = dict(injury.get("availability") or {})
    ol = dict(injury.get("offensive_line") or {})
    front = dict(injury.get("defensive_front") or {})
    personnel_verified = ol.get("verification") == "VERIFIED" and front.get("verification") == "VERIFIED"
    detail["personnel"] = {
        "status": "VERIFIED" if personnel_verified else "DATA_UNAVAILABLE",
        "display": f"OL: {_text(ol.get('display'))} · Opp front: {_text(front.get('display'))}" if personnel_verified else "Official personnel report unavailable",
        "offensive_line": ol,
        "defensive_front": front,
        "source": "NFL.com Official Injury Report",
    }

    schedule = _schedule_map()
    history = dict(detail.get("matchup_history") or {})
    history["games_detail"] = repair_history_dates(
        [dict(row) for row in (history.get("games_detail") or []) if isinstance(row, Mapping)],
        schedule,
    )
    detail["matchup_history"] = history
    comparable = dict(detail.get("comparable_matchups") or {})
    comparable["games_detail"] = repair_history_dates(
        [dict(row) for row in (comparable.get("games_detail") or []) if isinstance(row, Mapping)],
        schedule,
    )
    detail["comparable_matchups"] = comparable

    lineage = dict(detail.get("source_lineage") or {})
    lineage.update({
        "page2_injury_personnel": "NFL.com Official Injury Report",
        "page2_weather": "National Weather Service + canonical NFL stadium registry",
        "page2_game_market": "The Odds API featured NFL spreads/totals via Kyre Sports API",
        "page2_prop_history": "The Odds API historical player_rush_yds snapshots when subscription coverage permits",
        "page2_history_dates": "nflverse canonical schedule mapping",
    })
    detail["source_lineage"] = lineage
    _clean_final_read(
        detail,
        personnel_verified=personnel_verified,
        weather_verified=weather.get("verification") == "VERIFIED",
        movement_verified=market.get("movement") is not None,
    )
    detail["data_completeness_version"] = VERSION
    out["detail"] = detail
    return out


def build_detail_bundle(*, player_id: str, game_id: str, target_date: str | None = None) -> dict[str, Any]:
    return enrich_detail_payload(_BASE_BUILD(player_id=player_id, game_id=game_id, target_date=target_date))


# The V2 FastAPI route calls its module-global builder at request time. Replace
# that one symbol and reuse the exact same router/schema/public URL.
base.build_detail_bundle = build_detail_bundle
router = base.router
SCHEMA_VERSION = base.SCHEMA_VERSION
SERVICE = base.SERVICE
GATEWAY = base.GATEWAY

__all__ = ["GATEWAY", "SCHEMA_VERSION", "SERVICE", "VERSION", "build_detail_bundle", "enrich_detail_payload", "router"]
