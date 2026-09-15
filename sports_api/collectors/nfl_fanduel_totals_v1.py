"""Read-only FanDuel NFL Game Totals collector V1.

Combines the certified NFL ESPN <-> FanDuel exact-event reconciliation with the
already-proven FanDuel canonical pregame ``Total Points`` semantics. Sportsbook
information is context only and never modifies football-only projection logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping

from sports_api.collectors.nfl_fanduel_passing_yards import (
    NFLPassingYardsCollectorError,
    fetch_fanduel_event_page,
    fetch_fanduel_nfl_landing,
    parse_official_event,
    reconcile_fanduel_event,
)
from sports_api.collectors.nfl_passing_yards_render_espn_v2 import (
    fetch_espn_event_summary_hosted,
)

SCHEMA_VERSION = "nfl_game_totals_market_v1"
SPORTSBOOK = "FanDuel"
TOTAL_MARKET_NAME = "Total Points"
MAX_NFL_TOTAL = 200.0


class NFLGameTotalsCollectorError(RuntimeError):
    """The NFL Game Totals market could not be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        out: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                out.append(row)
        return out
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _market_name(market: Mapping[str, Any]) -> str:
    return _text(
        market.get("marketName")
        or market.get("name")
        or market.get("displayName")
    )


def _market_id(market: Mapping[str, Any]) -> str:
    return _text(market.get("marketId") or market.get("id") or market.get("_attachment_key"))


def _market_is_open_pregame(market: Mapping[str, Any]) -> bool:
    status = _text(market.get("marketStatus") or market.get("status")).upper()
    return status == "OPEN" and market.get("inPlay") is not True


def _runner_role(runner: Mapping[str, Any]) -> str:
    result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
    return _text((result or {}).get("type")).upper()


def _active_runners(market: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        runner
        for runner in _rows(market.get("runners"))
        if _text(runner.get("runnerStatus")).upper() in {"", "ACTIVE"}
    ]


def _role_runner(market: Mapping[str, Any], role: str) -> dict[str, Any]:
    matches = [row for row in _active_runners(market) if _runner_role(row) == role]
    if len(matches) != 1:
        raise NFLGameTotalsCollectorError(
            f"Total Points expected exactly one active {role} runner, found {len(matches)}"
        )
    return matches[0]


def _total(runner: Mapping[str, Any]) -> float:
    try:
        value = float(runner.get("handicap"))
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsCollectorError("Total Points runner has no valid handicap") from exc
    if not math.isfinite(value) or value <= 0 or value > MAX_NFL_TOTAL:
        raise NFLGameTotalsCollectorError(
            "Total Points runner handicap is outside the supported NFL range"
        )
    return value


def _american_odds(runner: Mapping[str, Any]) -> int:
    win = runner.get("winRunnerOdds") if isinstance(runner.get("winRunnerOdds"), Mapping) else {}
    display = (
        (win or {}).get("americanDisplayOdds")
        if isinstance((win or {}).get("americanDisplayOdds"), Mapping)
        else {}
    )
    value = (display or {}).get("americanOddsInt")
    if value is None:
        value = (display or {}).get("americanOdds")
    try:
        price = int(value)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsCollectorError("Total Points runner has no valid American odds") from exc
    if price == 0 or abs(price) < 100:
        raise NFLGameTotalsCollectorError(
            "Total Points American odds are outside the supported contract"
        )
    return price


def _totals_market(
    event_page: Mapping[str, Any],
    provider_event_id: str,
) -> dict[str, Any]:
    attachments = event_page.get("attachments") if isinstance(event_page, Mapping) else {}
    if not isinstance(attachments, Mapping):
        raise NFLGameTotalsCollectorError("FanDuel NFL event page has no attachments object")

    candidates: list[dict[str, Any]] = []
    for market in _rows(attachments.get("markets")):
        if _market_name(market) != TOTAL_MARKET_NAME or not _market_is_open_pregame(market):
            continue
        market_event_id = _text(
            market.get("eventId") or market.get("eventID") or market.get("event_id")
        )
        if market_event_id and market_event_id != provider_event_id:
            continue
        candidates.append(market)

    if len(candidates) != 1:
        raise NFLGameTotalsCollectorError(
            f"expected exactly one open pregame FanDuel Total Points market, found {len(candidates)}"
        )
    return candidates[0]


def normalize_game_totals_market(
    market: Mapping[str, Any],
    *,
    official_event: Mapping[str, Any],
    provider_event: Mapping[str, Any],
    captured_at_utc: datetime,
) -> dict[str, Any]:
    if captured_at_utc.tzinfo is None or captured_at_utc.utcoffset() is None:
        raise ValueError("captured_at_utc must be timezone-aware")
    if _market_name(market) != TOTAL_MARKET_NAME:
        raise NFLGameTotalsCollectorError("market is not canonical FanDuel Total Points")
    if not _market_is_open_pregame(market):
        raise NFLGameTotalsCollectorError("Total Points market is not open pregame")

    event_id = _text(official_event.get("event_id"))
    if not event_id.isdigit():
        raise NFLGameTotalsCollectorError("official ESPN NFL event ID is invalid")

    over = _role_runner(market, "OVER")
    under = _role_runner(market, "UNDER")
    over_total = _total(over)
    under_total = _total(under)
    if not math.isclose(over_total, under_total, abs_tol=1e-9):
        raise NFLGameTotalsCollectorError(
            f"Total Points line mismatch: over={over_total} under={under_total}"
        )

    captured = captured_at_utc.astimezone(timezone.utc).isoformat()
    away_team = dict(official_event.get("away") or {})
    home_team = dict(official_event.get("home") or {})
    provider_event_id = _text(provider_event.get("provider_event_id"))
    if not provider_event_id:
        raise NFLGameTotalsCollectorError("reconciled FanDuel event ID is missing")

    return {
        "schema_version": SCHEMA_VERSION,
        "service": "Kyre Sports API",
        "sport": "nfl",
        "market": "game_total",
        "official_event_id": event_id,
        "captured_at_utc": captured,
        "ready": True,
        "market_available": True,
        "identity": {
            "official_authority": "ESPN",
            "official_event_id": event_id,
            "provider_event_id": provider_event_id,
            "away_team_id": _text(away_team.get("team_id")),
            "home_team_id": _text(home_team.get("team_id")),
            "away_abbr": _text(away_team.get("abbr")),
            "home_abbr": _text(home_team.get("abbr")),
            "kickoff_delta_seconds": int(provider_event.get("kickoff_delta_seconds") or 0),
            "team_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
        },
        "books": [
            {
                "official_event_id": event_id,
                "sportsbook": SPORTSBOOK,
                "provider": "FanDuel via Kyre Sports API",
                "provider_event_id": provider_event_id,
                "market_id": _market_id(market),
                "total": over_total,
                "over_price": _american_odds(over),
                "under_price": _american_odds(under),
                "updated_at_utc": captured,
                "line_status": "active",
            }
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "model_probability_input": False,
            "multi_book_capable": True,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def collect_fanduel_nfl_game_total(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    espn_fetcher=None,
    landing_fetcher=None,
    event_page_fetcher=None,
) -> dict[str, Any]:
    """Collect one exact-ID FanDuel NFL pregame Game Total snapshot."""
    event_id = _text(official_event_id)
    if not event_id.isdigit():
        raise NFLGameTotalsCollectorError("official ESPN event_id must be numeric")
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")

    try:
        if espn_fetcher is None:
            summary, _summary_source = fetch_espn_event_summary_hosted(event_id)
        else:
            summary = espn_fetcher(event_id)
        official = parse_official_event(summary)
        if _text(official.get("event_id")) != event_id:
            raise NFLGameTotalsCollectorError("hosted ESPN summary event identity mismatch")

        landing = (landing_fetcher or fetch_fanduel_nfl_landing)()
        provider_event = reconcile_fanduel_event(landing, official)
        provider_event_id = _text(provider_event.get("provider_event_id"))
        if not provider_event_id:
            raise NFLGameTotalsCollectorError("reconciled FanDuel event ID is missing")

        event_page = (event_page_fetcher or fetch_fanduel_event_page)(provider_event_id)
        market = _totals_market(event_page, provider_event_id)
        return normalize_game_totals_market(
            market,
            official_event=official,
            provider_event=provider_event,
            captured_at_utc=now,
        )
    except NFLGameTotalsCollectorError:
        raise
    except NFLPassingYardsCollectorError as exc:
        raise NFLGameTotalsCollectorError(str(exc)) from exc
    except Exception as exc:
        raise NFLGameTotalsCollectorError(
            f"NFL Game Totals collection failed: {type(exc).__name__}"
        ) from exc


__all__ = [
    "MAX_NFL_TOTAL",
    "NFLGameTotalsCollectorError",
    "SCHEMA_VERSION",
    "SPORTSBOOK",
    "TOTAL_MARKET_NAME",
    "collect_fanduel_nfl_game_total",
    "normalize_game_totals_market",
]
