"""Read-only FanDuel MLB in-play game-market collector.

Step 9D is deliberately separate from the frozen pregame collector. It reuses
its already-certified public GET transport, official MLB schedule reconciliation,
and market normalizers, but accepts only OPEN markets explicitly marked
``inPlay == True``. The output is keyed by official MLB gamePk so downstream
consumers never need team-name or fuzzy matching.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from sports_api.collectors.mlb_fanduel_direct import (
    CORE_MARKET_NAMES,
    EASTERN,
    FANDUEL_REGION,
    MLBMarketCollectorError,
    _event_id,
    _event_name,
    _game_status,
    _iso_utc,
    _market_id,
    _market_name,
    _normalize_moneyline,
    _normalize_run_line,
    _normalize_total,
    _official_team,
    _rows,
    fetch_fanduel_event_page,
    fetch_fanduel_mlb_landing,
    fetch_mlb_schedule,
    parse_fanduel_matchup,
    reconcile_official_game,
)

DATA_TYPE = "mlb_inplay_game_odds_snapshot_v1"
SCHEMA_VERSION = 1
MAX_STARTED_AGE = timedelta(hours=18)


def _market_is_open_inplay(market: Mapping[str, Any]) -> bool:
    status = str(market.get("marketStatus") or market.get("status") or "").strip().upper()
    return status == "OPEN" and market.get("inPlay") is True


def _find_inplay_core_market(
    markets: list[dict[str, Any]],
    exact_name: str,
) -> dict[str, Any] | None:
    candidates = [
        market
        for market in markets
        if _market_name(market) == exact_name and _market_is_open_inplay(market)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda market: (
            int(market.get("sortPriority") or 10_000),
            _market_id(market),
        )
    )
    return candidates[0]


def normalize_inplay_core_markets(markets: list[dict[str, Any]]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    moneyline = _find_inplay_core_market(markets, CORE_MARKET_NAMES["moneyline"])
    run_line = _find_inplay_core_market(markets, CORE_MARKET_NAMES["run_line"])
    total = _find_inplay_core_market(markets, CORE_MARKET_NAMES["total"])
    if moneyline is not None:
        normalized["moneyline"] = _normalize_moneyline(moneyline)
    if run_line is not None:
        normalized["run_line"] = _normalize_run_line(run_line)
    if total is not None:
        normalized["total"] = _normalize_total(total)
    return normalized


def _normalize_inplay_game(
    *,
    event: Mapping[str, Any],
    event_page: Mapping[str, Any],
    schedule_payload: Mapping[str, Any],
) -> dict[str, Any]:
    event_name = _event_name(event)
    away_name, home_name = parse_fanduel_matchup(event_name)
    event_start = str(event.get("openDate") or "").strip()
    if not event_start:
        raise MLBMarketCollectorError(f"FanDuel event {_event_id(event)} has no openDate")

    official_game, match_method = reconcile_official_game(
        schedule_payload,
        away_team=away_name,
        home_team=home_name,
        sportsbook_start_utc=event_start,
    )
    away_id, official_away = _official_team(official_game, "away")
    home_id, official_home = _official_team(official_game, "home")

    attachments = event_page.get("attachments") or {}
    if not isinstance(attachments, dict):
        raise MLBMarketCollectorError(f"FanDuel event {_event_id(event)} has no attachments")
    markets = _rows(attachments.get("markets"))
    core = normalize_inplay_core_markets(markets)
    if not core:
        raise MLBMarketCollectorError(
            f"FanDuel event {_event_id(event)} has no OPEN in-play core markets"
        )

    try:
        official_game_id = int(official_game.get("gamePk"))
    except (TypeError, ValueError) as exc:
        raise MLBMarketCollectorError("official MLB schedule game is missing gamePk") from exc
    if official_game_id <= 0:
        raise MLBMarketCollectorError("official MLB schedule gamePk must be positive")

    return {
        "official_game_id": official_game_id,
        "sportsbook_event_id": _event_id(event),
        "sportsbook_event_name": event_name,
        "official_schedule_match": match_method,
        "scheduled_start_utc": str(official_game.get("gameDate") or event_start),
        "sportsbook_start_utc": event_start,
        "game_status": _game_status(official_game),
        "away_team": {"id": away_id, "name": official_away},
        "home_team": {"id": home_id, "name": official_home},
        "sportsbook": "FanDuel",
        "sportsbook_region": FANDUEL_REGION,
        "market_phase": "IN_PLAY",
        "in_play": True,
        "markets": core,
        "market_availability": {
            "moneyline": "moneyline" in core,
            "run_line": "run_line" in core,
            "total": "total" in core,
        },
        "fully_priced": all(key in core for key in ("moneyline", "run_line", "total")),
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
    }


def collect_inplay_mlb_game_odds(
    *,
    now_utc: datetime | None = None,
    official_game_id: int | None = None,
    max_events: int = 30,
    landing_fetcher: Callable[[], Mapping[str, Any]] | None = None,
    event_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
    schedule_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect FanDuel OPEN in-play MLB Moneyline, Run Line and Total markets."""

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if isinstance(official_game_id, bool):
        raise ValueError("official_game_id must be a positive integer or None")
    if official_game_id is not None:
        official_game_id = int(official_game_id)
        if official_game_id <= 0:
            raise ValueError("official_game_id must be positive")
    if max_events <= 0:
        raise ValueError("max_events must be positive")

    get_landing = landing_fetcher or fetch_fanduel_mlb_landing
    get_event = event_fetcher or (lambda event_id: fetch_fanduel_event_page(event_id))
    get_schedule = schedule_fetcher or fetch_mlb_schedule

    landing = dict(get_landing())
    attachments = landing.get("attachments") or {}
    if not isinstance(attachments, dict):
        raise MLBMarketCollectorError("FanDuel MLB landing page has no attachments object")
    landing_events = _rows(attachments.get("events"))

    candidates: list[dict[str, Any]] = []
    for event in landing_events:
        if " @ " not in _event_name(event):
            continue
        start_text = str(event.get("openDate") or "").strip()
        if not start_text:
            continue
        try:
            start_utc = _iso_utc(start_text)
        except MLBMarketCollectorError:
            continue
        age = now - start_utc
        if age < timedelta(0) or age > MAX_STARTED_AGE:
            continue
        candidates.append(event)
    candidates.sort(key=lambda event: str(event.get("openDate") or ""), reverse=True)
    candidates = candidates[:max_events]

    schedule_cache: dict[str, Mapping[str, Any]] = {}
    normalized_games: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for event in candidates:
        event_id = _event_id(event)
        try:
            start_utc = _iso_utc(str(event.get("openDate") or ""))
            slate_date = start_utc.astimezone(EASTERN).date().isoformat()
            if slate_date not in schedule_cache:
                schedule_cache[slate_date] = dict(get_schedule(slate_date))
            game = _normalize_inplay_game(
                event=event,
                event_page=dict(get_event(event_id)),
                schedule_payload=schedule_cache[slate_date],
            )
            if official_game_id is not None and game["official_game_id"] != official_game_id:
                continue
            normalized_games.append(game)
        except Exception as exc:
            rejected.append(
                {
                    "sportsbook_event_id": event_id or None,
                    "sportsbook_event_name": _event_name(event) or None,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    normalized_games.sort(key=lambda game: int(game["official_game_id"]))
    fully_priced_count = sum(1 for game in normalized_games if game.get("fully_priced") is True)
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "collected_at_utc": now.isoformat(),
        "provider": "FanDuel",
        "transport": "anonymous_public_get_only",
        "http_methods": ["GET"],
        "sportsbook_region": FANDUEL_REGION,
        "market_phase": "IN_PLAY",
        "requested_official_game_id": official_game_id,
        "landing_event_count": len(landing_events),
        "candidate_started_event_count": len(candidates),
        "matched_inplay_game_count": len(normalized_games),
        "fully_priced_game_count": fully_priced_count,
        "official_schedule_dates": sorted(schedule_cache),
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "games": normalized_games,
        "rejected_events": rejected,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "collect_inplay_mlb_game_odds",
    "normalize_inplay_core_markets",
]
