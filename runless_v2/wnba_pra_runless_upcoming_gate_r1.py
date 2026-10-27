"""MONSTER WNBA PRA active Runless upcoming-games-only gate R1.

The production Page 1 snapshot reads `runless_v2.wnba_pra_market_v1` directly.
This successor makes the official WNBA schedule authoritative before any
sportsbook offer can enter that board. Live/final/past-tip games fail closed.
Dependency-injected provider collectors remain available for isolated routing
unit tests; production/default calls always enforce the official schedule gate.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import re
from typing import Any

from . import wnba_pra_market_v1 as previous
from .wnba_schedule_v1 import build_daily_schedule

MODEL_VERSION = "MONSTER_WNBA_PRA_RUNLESS_UPCOMING_GATE_R1"
_ORIGINAL_BUILD = previous.build_pra_market_board

_TEAM_ALIASES = {
    "atlanta dream": "atl", "atl dream": "atl", "dream": "atl", "atl": "atl",
    "chicago sky": "chi", "sky": "chi", "chi": "chi",
    "connecticut sun": "con", "sun": "con", "con": "con",
    "dallas wings": "dal", "wings": "dal", "dal": "dal",
    "golden state valkyries": "gsv", "gs valkyries": "gsv", "valkyries": "gsv", "gsv": "gsv",
    "indiana fever": "ind", "fever": "ind", "ind": "ind",
    "las vegas aces": "lva", "aces": "lva", "lva": "lva",
    "los angeles sparks": "las", "la sparks": "las", "sparks": "las", "las": "las",
    "minnesota lynx": "min", "lynx": "min", "min": "min",
    "new york liberty": "nyl", "ny liberty": "nyl", "liberty": "nyl", "nyl": "nyl",
    "phoenix mercury": "phx", "mercury": "phx", "phx": "phx",
    "seattle storm": "sea", "storm": "sea", "sea": "sea",
    "washington mystics": "was", "mystics": "was", "was": "was",
    "portland fire": "por", "fire": "por", "por": "por",
    "toronto tempo": "tor", "tempo": "tor", "tor": "tor",
}


def _team_key(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    return _TEAM_ALIASES.get(text, text)


def _team_name(value: Any) -> str:
    row = value if isinstance(value, Mapping) else {}
    for key in ("full_name", "display_name", "name", "team_tricode"):
        text = str(row.get(key) or "").strip()
        if text:
            return text
    city = str(row.get("team_city") or "").strip()
    name = str(row.get("team_name") or "").strip()
    return " ".join(part for part in (city, name) if part)


def _utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _eligible_pairs(schedule: Mapping[str, Any], *, now_utc: datetime | None = None) -> set[frozenset[str]]:
    current = _now(now_utc)
    pairs: set[frozenset[str]] = set()
    games = schedule.get("games")
    if not isinstance(games, list):
        return pairs
    for game in games:
        if not isinstance(game, Mapping):
            continue
        status = game.get("status") if isinstance(game.get("status"), Mapping) else {}
        if str(status.get("category") or "").strip().casefold() != "scheduled":
            continue
        start = _utc(game.get("game_datetime_utc") or game.get("game_datetime_eastern"))
        if start is None or start <= current:
            continue
        away = _team_key(_team_name(game.get("away")))
        home = _team_key(_team_name(game.get("home")))
        if away and home and away != home:
            pairs.add(frozenset((away, home)))
    return pairs


def _filter_offers(rows: list[dict[str, Any]], pairs: set[frozenset[str]]) -> list[dict[str, Any]]:
    if not pairs:
        return []
    kept: list[dict[str, Any]] = []
    for row in rows:
        away = _team_key(row.get("away_team"))
        home = _team_key(row.get("home_team"))
        if away and home and frozenset((away, home)) in pairs:
            kept.append(dict(row))
    return kept


def _empty_board(*, date: str, season: int, state: str, schedule_games: int, error: str | None = None) -> dict[str, Any]:
    return {
        "service": "Kyre Sports API — Vercel",
        "state": state,
        "date": date,
        "season": int(season),
        "selected_provider": None,
        "sportsbooks": [],
        "pra_offer_count": 0,
        "player_count": 0,
        "players": [],
        "offers": [],
        "provider_health": [],
        "consensus_averaging": False,
        "projection_weight": 0.0,
        "pregame_gate": {
            "authority": "WNBA Official Schedule",
            "rule": "FUTURE_SCHEDULED_ONLY",
            "schedule_games": int(schedule_games),
            "eligible_games": 0,
            "offers_removed": 0,
            "error": error,
        },
    }


def build_pra_market_board(
    *,
    date: str,
    season: int = 2026,
    fanduel_collector: Callable[..., list[dict[str, Any]]] | None = None,
    draftkings_collector: Callable[..., list[dict[str, Any]]] | None = None,
    schedule_builder: Callable[..., dict[str, Any]] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Schedule-gated successor for the active Runless PRA board."""
    injected_provider_test = fanduel_collector is not None or draftkings_collector is not None
    enforce_schedule = schedule_builder is not None or not injected_provider_test

    if not enforce_schedule:
        return _ORIGINAL_BUILD(
            date=date,
            season=season,
            fanduel_collector=fanduel_collector,
            draftkings_collector=draftkings_collector,
        )

    schedule_fn = schedule_builder or build_daily_schedule
    try:
        schedule = schedule_fn(date=date, season=season)
    except Exception as exc:
        return _empty_board(
            date=date,
            season=season,
            state="SCHEDULE_UNAVAILABLE",
            schedule_games=0,
            error=type(exc).__name__,
        )

    games = schedule.get("games") if isinstance(schedule, Mapping) else None
    schedule_games = len(games) if isinstance(games, list) else 0
    pairs = _eligible_pairs(schedule, now_utc=now_utc)
    if not pairs:
        return _empty_board(
            date=date,
            season=season,
            state="NO_UPCOMING_WNBA_GAMES",
            schedule_games=schedule_games,
        )

    board = _ORIGINAL_BUILD(
        date=date,
        season=season,
        fanduel_collector=fanduel_collector,
        draftkings_collector=draftkings_collector,
    )
    raw_offers = [dict(row) for row in (board.get("offers") or []) if isinstance(row, Mapping)]
    offers = _filter_offers(raw_offers, pairs)
    board = dict(board)
    board["offers"] = offers
    board["pra_offer_count"] = len(offers)
    board["players"] = sorted({str(row.get("player_name") or "").strip() for row in offers if str(row.get("player_name") or "").strip()})
    board["player_count"] = len(board["players"])
    board["sportsbooks"] = sorted({str(row.get("sportsbook") or "").strip() for row in offers if str(row.get("sportsbook") or "").strip()})
    if not offers:
        board["state"] = "NO_CURRENT_PRA_MARKET"
        board["selected_provider"] = None
    board["pregame_gate"] = {
        "authority": "WNBA Official Schedule",
        "rule": "FUTURE_SCHEDULED_ONLY",
        "schedule_games": schedule_games,
        "eligible_games": len(pairs),
        "offers_removed": len(raw_offers) - len(offers),
        "error": None,
    }
    return board


def install() -> dict[str, Any]:
    previous.build_pra_market_board = build_pra_market_board
    try:
        from . import wnba_pra_page_snapshot_v1 as page_snapshot
        page_snapshot.build_pra_market_board = build_pra_market_board
    except Exception:
        pass
    return {
        "model_version": MODEL_VERSION,
        "authority": "MONSTER_ONLY",
        "active_path": "runless_v2.wnba_pra_page_snapshot_v1",
        "schedule_authority": "WNBA Official Schedule",
        "live_final_past_tip_allowed": False,
    }


install()

__all__ = [
    "MODEL_VERSION",
    "_eligible_pairs",
    "_filter_offers",
    "build_pra_market_board",
    "install",
]
