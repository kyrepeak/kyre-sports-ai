"""Credentialless ESPN public-scoreboard fallback for NBA spread market context.

This module is market context only. It exact-matches the frozen NBA schedule,
reads the sportsbook identity carried by ESPN's public scoreboard payload, and
publishes only paired spreads/prices that can be verified for that exact game.
It never participates in model, projection, probability, ranking, or decision
math.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import math
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}
PHOENIX = ZoneInfo("America/Phoenix")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return "".join(ch for ch in _clean(value).casefold() if ch.isalnum())


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _american_price(value: object) -> int | None:
    parsed = _number(value)
    if parsed is None or abs(parsed) < 100 or abs(parsed) > 100000:
        return None
    rounded = int(round(parsed))
    return rounded if math.isclose(parsed, rounded, abs_tol=1e-9) else None


def _as_utc(value: object) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _event_date_phoenix(event: Mapping[str, Any]) -> str | None:
    parsed = _as_utc(event.get("date"))
    return parsed.astimezone(PHOENIX).date().isoformat() if parsed is not None else None


def _team_tokens(team: Mapping[str, Any] | None) -> set[str]:
    raw = dict(team or {})
    values = {
        raw.get("displayName"),
        raw.get("shortDisplayName"),
        raw.get("name"),
        raw.get("abbreviation"),
    }
    location = _clean(raw.get("location"))
    name = _clean(raw.get("name"))
    if location and name:
        values.add(f"{location} {name}")
    return {_norm(value) for value in values if _norm(value)}


def _schedule_tokens(game: Mapping[str, object], side: str) -> set[str]:
    name = game.get(f"{side}_name")
    code = game.get(f"{side}_tricode")
    return {_norm(value) for value in (name, code) if _norm(value)}


def _competition_teams(competition: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    away = None
    home = None
    for competitor in competition.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _clean(competitor.get("homeAway")).casefold()
        if side == "away":
            away = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else None
        elif side == "home":
            home = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else None
    return away, home


def _resolve_schedule_game(
    event: Mapping[str, Any],
    competition: Mapping[str, Any],
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[str, object] | None:
    event_date = _event_date_phoenix(event)
    if not event_date:
        return None
    away_team, home_team = _competition_teams(competition)
    away_tokens = _team_tokens(away_team)
    home_tokens = _team_tokens(home_team)
    if not away_tokens or not home_tokens:
        return None

    matches: list[dict[str, object]] = []
    for raw in schedule_games:
        if _clean(raw.get("status")).upper() not in ELIGIBLE_STATES:
            continue
        if _clean(raw.get("game_date_phoenix")) != event_date:
            continue
        if not (away_tokens & _schedule_tokens(raw, "away")):
            continue
        if not (home_tokens & _schedule_tokens(raw, "home")):
            continue
        if not _clean(raw.get("game_key")):
            continue
        matches.append(dict(raw))
    return matches[0] if len(matches) == 1 else None


def _line_pair(point_spread: Mapping[str, Any], phase: str) -> tuple[float, float, int | None, int | None] | None:
    away_phase = ((point_spread.get("away") or {}).get(phase) or {})
    home_phase = ((point_spread.get("home") or {}).get(phase) or {})
    if not isinstance(away_phase, Mapping) or not isinstance(home_phase, Mapping):
        return None
    away = _number(away_phase.get("line"))
    home = _number(home_phase.get("line"))
    if away is None or home is None or not math.isclose(away + home, 0.0, abs_tol=1e-9):
        return None
    return away, home, _american_price(away_phase.get("odds")), _american_price(home_phase.get("odds"))


def normalize_espn_spread_observations_v1(
    payloads: Sequence[Mapping[str, Any]],
    schedule_games: Sequence[Mapping[str, object]],
    *,
    retrieved_at_utc: str,
) -> list[dict[str, object]]:
    retrieved = _as_utc(retrieved_at_utc)
    if retrieved is None:
        raise ValueError("retrieved_at_utc must be an ISO-8601 timestamp")
    retrieved_text = _iso_utc(retrieved)
    rows: list[dict[str, object]] = []

    for payload in payloads:
        for event in payload.get("events") or []:
            if not isinstance(event, Mapping):
                continue
            competitions = event.get("competitions") or []
            if not competitions or not isinstance(competitions[0], Mapping):
                continue
            competition = competitions[0]
            game = _resolve_schedule_game(event, competition, schedule_games)
            if game is None:
                continue
            for odds in competition.get("odds") or []:
                if not isinstance(odds, Mapping):
                    continue
                provider = odds.get("provider") or {}
                sportsbook = _clean(provider.get("displayName") or provider.get("name")) if isinstance(provider, Mapping) else ""
                if not sportsbook:
                    continue
                point_spread = odds.get("pointSpread") or {}
                if not isinstance(point_spread, Mapping):
                    continue
                current = _line_pair(point_spread, "close")
                if current is None:
                    spread = _number(odds.get("spread"))
                    if spread is None:
                        continue
                    current = (-spread, spread, None, None)
                away_spread, home_spread, away_price, home_price = current
                opened = _line_pair(point_spread, "open")
                row = {
                    "game_key": _clean(game.get("game_key")),
                    "game_date_phoenix": _clean(game.get("game_date_phoenix")),
                    "away_tricode": _clean(game.get("away_tricode")).upper(),
                    "home_tricode": _clean(game.get("home_tricode")).upper(),
                    "sportsbook": sportsbook,
                    "away_spread": away_spread,
                    "home_spread": home_spread,
                    "away_price": away_price,
                    "home_price": home_price,
                    "observed_at_utc": retrieved_text,
                    "retrieved_at_utc": retrieved_text,
                    "source_transport": "ESPN Public Scoreboard",
                    "source_event_id": _clean(event.get("id")) or None,
                    "sportsbook_projection_influence": 0.0,
                }
                if opened is not None:
                    row.update(
                        {
                            "open_away_spread": opened[0],
                            "open_home_spread": opened[1],
                            "open_away_price": opened[2],
                            "open_home_price": opened[3],
                        }
                    )
                rows.append(row)

    deduped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (_clean(row.get("game_key")), _clean(row.get("sportsbook")).casefold())
        previous = deduped.get(key)
        if previous is not None:
            pair = (float(previous["away_spread"]), float(previous["home_spread"]))
            current = (float(row["away_spread"]), float(row["home_spread"]))
            if pair != current:
                deduped.pop(key, None)
                continue
        deduped[key] = row
    return list(deduped.values())


def load_verified_espn_spread_observations_v1(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    request_get: Callable[..., Any] = requests.get,
    now_utc: datetime | None = None,
    timeout: float = 12.0,
) -> dict[str, object]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    dates = sorted(
        {
            _clean(game.get("game_date_phoenix"))
            for game in schedule_games
            if _clean(game.get("status")).upper() in ELIGIBLE_STATES and _clean(game.get("game_date_phoenix"))
        }
    )
    base: dict[str, object] = {
        "source": "ESPN Public Scoreboard",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": 0.0,
    }
    if not dates:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "ESPN_NO_ELIGIBLE_SCHEDULE_DATES"}

    payloads: list[Mapping[str, Any]] = []
    for date in dates:
        try:
            response = request_get(
                ESPN_SCOREBOARD_URL,
                params={"dates": date.replace("-", "")},
                headers={"User-Agent": "KyreSportsAI/1.0"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return {**base, "verification": "UNAVAILABLE", "diagnostic_state": f"ESPN_MARKET_PROVIDER_ERROR:{type(exc).__name__}"}
        if isinstance(payload, Mapping):
            payloads.append(payload)

    retrieved = _iso_utc(now)
    observations = normalize_espn_spread_observations_v1(
        payloads,
        schedule_games,
        retrieved_at_utc=retrieved,
    )
    if not observations:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "ESPN_NO_VERIFIED_SPREAD_ROWS"}
    return {
        **base,
        "verification": "VERIFIED",
        "diagnostic_state": "ESPN_DRAFTKINGS_FALLBACK_OK",
        "observations": observations,
        "retrieved_at_utc": retrieved,
    }


__all__ = [
    "ESPN_SCOREBOARD_URL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_FROZEN_STEPS",
    "normalize_espn_spread_observations_v1",
    "load_verified_espn_spread_observations_v1",
]
