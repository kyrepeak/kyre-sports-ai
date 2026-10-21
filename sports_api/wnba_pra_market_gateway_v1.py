"""Kyre Sports API WNBA PRA market gateway.

The gateway owns provider routing for the WNBA PRA product. FanDuel is the
primary read-only market source. DraftKings Step 19A is used only when the
primary source is unavailable or has no usable two-sided PRA market. Quotes are
never averaged, repriced, or synthesized.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import os
import re
from typing import Any

from sports_api.collectors.wnba_fanduel_direct import collect_fanduel_wnba_feed
from sports_api.wnba_step19a_draftkings_sportscontent import build_step19a_draftkings_snapshot

MODEL_VERSION = "WNBA PRA MARKET GATEWAY V1 • KYRE API ONLY"
SCHEMA_VERSION = "wnba_pra_market_gateway_v1"
PRIMARY_PROVIDER = "fanduel"
SECONDARY_PROVIDER = "draftkings"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate(date: str, season: int) -> tuple[str, int]:
    text = str(date or "").strip()
    if not _DATE_RE.fullmatch(text):
        raise ValueError("date must use YYYY-MM-DD")
    try:
        datetime.strptime(text, "%Y-%m-%d")
        season_int = int(season)
    except (TypeError, ValueError) as exc:
        raise ValueError("date/season is invalid") from exc
    if season_int <= 0:
        raise ValueError("season must be positive")
    return text, season_int


def _offers(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    obj = payload if isinstance(payload, Mapping) else {}
    direct = obj.get("offers")
    if isinstance(direct, list):
        return [dict(row) for row in direct if isinstance(row, Mapping)]
    raw = obj.get("raw_feed")
    values = raw.get("offers") if isinstance(raw, Mapping) else None
    return [dict(row) for row in values if isinstance(row, Mapping)] if isinstance(values, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _event_teams(payload: Mapping[str, Any] | None) -> dict[str, tuple[str, str]]:
    obj = payload if isinstance(payload, Mapping) else {}
    events = obj.get("source_events")
    out: dict[str, tuple[str, str]] = {}
    if not isinstance(events, list):
        return out
    for row in events:
        if not isinstance(row, Mapping):
            continue
        event_id = _text(row.get("source_event_id"))
        name = _text(row.get("event_name"))
        if not event_id or " @ " not in name:
            continue
        away, home = (part.strip() for part in name.split(" @ ", 1))
        if away and home:
            out[event_id] = (away, home)
    return out


def _enrich_identity(raw_offers: list[dict[str, Any]], payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    event_teams = _event_teams(payload)
    out: list[dict[str, Any]] = []
    for source in raw_offers:
        row = dict(source)
        if not _text(row.get("away_team")) or not _text(row.get("home_team")):
            pair = event_teams.get(_text(row.get("source_event_id")))
            if pair:
                row.setdefault("away_team", pair[0])
                row.setdefault("home_team", pair[1])
                if not _text(row.get("away_team")):
                    row["away_team"] = pair[0]
                if not _text(row.get("home_team")):
                    row["home_team"] = pair[1]
        out.append(row)
    return out


def _pra_offer(row: Mapping[str, Any]) -> bool:
    stat = _text(row.get("stat")).casefold().replace(" ", "")
    return stat in {"pra", "points+rebounds+assists", "pointsreboundsassists"}


def _line(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_two_sided_pra(raw_offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return exact provider quotes only for player/line groups with both sides."""
    eligible = [row for row in raw_offers if _pra_offer(row)]
    groups: dict[tuple[str, str, float], set[str]] = {}
    for row in eligible:
        player = _text(row.get("player_name"))
        event_id = _text(row.get("source_event_id"))
        line = _line(row.get("line"))
        side = _text(row.get("side")).casefold()
        if not player or line is None or side not in {"over", "under"}:
            continue
        groups.setdefault((event_id, player.casefold(), line), set()).add(side)
    usable = {key for key, sides in groups.items() if {"over", "under"}.issubset(sides)}
    out: list[dict[str, Any]] = []
    for row in eligible:
        line = _line(row.get("line"))
        key = (_text(row.get("source_event_id")), _text(row.get("player_name")).casefold(), line)
        if line is not None and key in usable:
            out.append(dict(row))
    return out


def _provider_health(provider_id: str, state: str, count: int, *, error: str | None = None) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "state": state,
        "pra_offer_count": int(count),
        "error": error,
    }


def _default_draftkings(*, date: str, season: int) -> dict[str, Any]:
    env = dict(os.environ)
    env["WNBA_STEP19A_DRAFTKINGS_SPORTSCONTENT_ENABLED"] = "true"
    env.setdefault("WNBA_STEP19A_DRAFTKINGS_SITE", "dkusaz")
    return build_step19a_draftkings_snapshot(date=date, season=season, env=env)


def build_pra_market_board(
    *,
    date: str,
    season: int = 2026,
    fanduel_collector: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_collector: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    day, season_int = _validate(date, season)
    primary = fanduel_collector or collect_fanduel_wnba_feed
    secondary = draftkings_collector or _default_draftkings
    health: list[dict[str, Any]] = []

    try:
        primary_payload = primary(date=day, season=season_int)
        primary_offers = _valid_two_sided_pra(_enrich_identity(_offers(primary_payload), primary_payload))
        if primary_offers:
            health.append(_provider_health(PRIMARY_PROVIDER, "READY", len(primary_offers)))
            return _result(day, season_int, PRIMARY_PROVIDER, primary_offers, health, primary_payload)
        health.append(_provider_health(PRIMARY_PROVIDER, "EMPTY", 0))
    except Exception as exc:
        health.append(_provider_health(PRIMARY_PROVIDER, "DEGRADED", 0, error=type(exc).__name__))

    try:
        secondary_payload = secondary(date=day, season=season_int)
        secondary_offers = _valid_two_sided_pra(_enrich_identity(_offers(secondary_payload), secondary_payload))
        if secondary_offers:
            health.append(_provider_health(SECONDARY_PROVIDER, "READY", len(secondary_offers)))
            return _result(day, season_int, SECONDARY_PROVIDER, secondary_offers, health, secondary_payload)
        health.append(_provider_health(SECONDARY_PROVIDER, "EMPTY", 0))
    except Exception as exc:
        health.append(_provider_health(SECONDARY_PROVIDER, "DEGRADED", 0, error=type(exc).__name__))

    return _result(day, season_int, None, [], health, None)


def _result(
    day: str,
    season: int,
    provider_id: str | None,
    offers: list[dict[str, Any]],
    health: list[dict[str, Any]],
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source_events = list((payload or {}).get("source_events") or []) if isinstance(payload, Mapping) else []
    books = sorted({_text(row.get("sportsbook")) for row in offers if _text(row.get("sportsbook"))})
    players = sorted({_text(row.get("player_name")) for row in offers if _text(row.get("player_name"))})
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "source": "Kyre Sports API",
        "date": day,
        "season": season,
        "state": "READY" if offers else "NO_CURRENT_PRA_MARKET",
        "primary_provider": PRIMARY_PROVIDER,
        "selected_provider": provider_id,
        "provider_health": health,
        "offers": offers,
        "source_events": source_events,
        "sportsbooks": books,
        "pra_offer_count": len(offers),
        "player_count": len(players),
        "line_averaging": False,
        "application_gateway": "kyre_sports_api",
    }


__all__ = ["MODEL_VERSION", "SCHEMA_VERSION", "build_pra_market_board"]
