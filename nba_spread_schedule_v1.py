"""NBA Spread Step 3 — verified rolling schedule + Phoenix game identity.

This module owns schedule identity only. It deliberately does not expose or use
sportsbook lines, public betting, injuries, projections, probabilities, edges,
or rankings.

Two independent schedule sources are required before a slate is trusted:
NBA Official CDN and ESPN NBA. Missing or conflicting provider data fails
closed instead of guessing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

MODEL_VERSION = "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False

PHOENIX_TZ = ZoneInfo("America/Phoenix")
UTC = timezone.utc
ROLLING_DAYS = 7

NBA_OFFICIAL_SCHEDULE_URLS = (
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
)
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

NBA_TEAM_TRICODES = frozenset(
    {
        "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
        "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
        "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
    }
)

DEFAULT_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0; +schedule-verification)",
}


def rolling_phoenix_dates(*, now_utc: datetime | None = None, days: int = ROLLING_DAYS) -> tuple[str, ...]:
    """Return a rolling Phoenix-calendar date window beginning *today* locally."""
    if days < 1 or days > 14:
        raise ValueError("days must be between 1 and 14")
    current = now_utc or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    local_date = current.astimezone(PHOENIX_TZ).date()
    return tuple((local_date + timedelta(days=offset)).isoformat() for offset in range(days))


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _tricode(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    return code if code in NBA_TEAM_TRICODES else None


def _clean_name(value: Any, fallback: str) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _team_name(team: dict[str, Any], code: str) -> str:
    display = team.get("displayName") or team.get("teamName")
    city = str(team.get("teamCity") or "").strip()
    name = str(display or "").strip()
    if city and name and not name.lower().startswith(city.lower()):
        name = f"{city} {name}"
    return _clean_name(name, code)


def normalize_game_status(status_text: Any, espn_state: Any = None, status_code: Any = None) -> str:
    """Map provider-specific states to the Step-3 canonical game states."""
    text = str(status_text or "").strip().lower()
    state = str(espn_state or "").strip().lower()
    try:
        code = int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        code = None

    if "cancel" in text:
        return "CANCELLED"
    if any(token in text for token in ("delay", "postpon")):
        return "DELAYED"
    if code == 3 or state == "post" or "final" in text:
        return "FINAL"
    if code == 2 or state == "in" or any(token in text for token in ("in progress", "halftime", "quarter")):
        return "LIVE"
    return "UPCOMING"


def _game_record(
    *,
    source: str,
    source_game_id: Any,
    away_code: str,
    away_name: str,
    home_code: str,
    home_name: str,
    tip_utc: datetime,
    status: str,
    venue: str = "",
) -> dict[str, Any]:
    local = tip_utc.astimezone(PHOENIX_TZ)
    phoenix_date = local.date().isoformat()
    return {
        "source": source,
        "source_game_id": str(source_game_id or "").strip(),
        "game_key": f"{away_code}@{home_code}:{phoenix_date}",
        "away_tricode": away_code,
        "away_name": away_name,
        "home_tricode": home_code,
        "home_name": home_name,
        "tip_utc": tip_utc.isoformat().replace("+00:00", "Z"),
        "tip_iso_phoenix": local.isoformat(),
        "tip_phoenix": local.strftime("%-I:%M %p %Z"),
        "game_date_phoenix": phoenix_date,
        "status": status,
        "venue": _clean_name(venue, "Venue unavailable") if venue else "",
    }


def parse_nba_official(payload: dict[str, Any], window_dates: Iterable[str]) -> list[dict[str, Any]]:
    allowed_dates = set(window_dates)
    output: list[dict[str, Any]] = []
    league = payload.get("leagueSchedule") if isinstance(payload, dict) else None
    date_blocks = league.get("gameDates") if isinstance(league, dict) else None
    if not isinstance(date_blocks, list):
        return output

    for block in date_blocks:
        if not isinstance(block, dict):
            continue
        for game in block.get("games") or []:
            if not isinstance(game, dict):
                continue
            away = game.get("awayTeam") or {}
            home = game.get("homeTeam") or {}
            if not isinstance(away, dict) or not isinstance(home, dict):
                continue
            away_code = _tricode(away.get("teamTricode"))
            home_code = _tricode(home.get("teamTricode"))
            tip = _parse_utc(game.get("gameDateTimeUTC"))
            if not away_code or not home_code or tip is None:
                continue
            row = _game_record(
                source="NBA Official",
                source_game_id=game.get("gameId"),
                away_code=away_code,
                away_name=_team_name(away, away_code),
                home_code=home_code,
                home_name=_team_name(home, home_code),
                tip_utc=tip,
                status=normalize_game_status(game.get("gameStatusText"), None, game.get("gameStatus")),
                venue=str(game.get("arenaName") or ""),
            )
            if row["game_date_phoenix"] in allowed_dates:
                output.append(row)
    return sorted(output, key=lambda item: (item["tip_utc"], item["game_key"]))


def parse_espn(payload: dict[str, Any], window_dates: Iterable[str]) -> list[dict[str, Any]]:
    allowed_dates = set(window_dates)
    output: list[dict[str, Any]] = []
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return output

    for event in events:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
        competitors = competition.get("competitors") or []
        by_side = {
            str(item.get("homeAway") or "").lower(): item
            for item in competitors
            if isinstance(item, dict)
        }
        away_wrapper = by_side.get("away") or {}
        home_wrapper = by_side.get("home") or {}
        away = away_wrapper.get("team") or {}
        home = home_wrapper.get("team") or {}
        if not isinstance(away, dict) or not isinstance(home, dict):
            continue
        away_code = _tricode(away.get("abbreviation"))
        home_code = _tricode(home.get("abbreviation"))
        tip = _parse_utc(competition.get("date") or event.get("date"))
        if not away_code or not home_code or tip is None:
            continue

        status_type = ((event.get("status") or {}).get("type") or {}) if isinstance(event.get("status") or {}, dict) else {}
        state = status_type.get("state") if isinstance(status_type, dict) else None
        detail = ""
        if isinstance(status_type, dict):
            detail = status_type.get("description") or status_type.get("shortDetail") or status_type.get("detail") or ""
        venue = competition.get("venue") or {}
        venue_name = venue.get("fullName") if isinstance(venue, dict) else ""
        row = _game_record(
            source="ESPN NBA",
            source_game_id=event.get("id"),
            away_code=away_code,
            away_name=_team_name(away, away_code),
            home_code=home_code,
            home_name=_team_name(home, home_code),
            tip_utc=tip,
            status=normalize_game_status(detail, state, None),
            venue=str(venue_name or ""),
        )
        if row["game_date_phoenix"] in allowed_dates:
            output.append(row)
    return sorted(output, key=lambda item: (item["tip_utc"], item["game_key"]))


def reconcile_verified_schedule(
    official_games: list[dict[str, Any]],
    espn_games: list[dict[str, Any]],
    window_dates: Iterable[str],
) -> dict[str, Any]:
    """Require exact matchup identity across both sources; conflicts fail closed."""
    dates = tuple(window_dates)
    official = {str(item.get("game_key")): item for item in official_games}
    espn = {str(item.get("game_key")): item for item in espn_games}

    if set(official) != set(espn):
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "PROVIDER_CONFLICT",
            "games": [],
            "source_agreement": 0,
            "window_dates": dates,
        }

    reconciled: list[dict[str, Any]] = []
    for key in sorted(official):
        left = official[key]
        right = espn[key]
        left_tip = _parse_utc(left.get("tip_utc"))
        right_tip = _parse_utc(right.get("tip_utc"))
        if left_tip is None or right_tip is None or abs((left_tip - right_tip).total_seconds()) > 15 * 60:
            return {
                "verification": "UNAVAILABLE",
                "diagnostic_state": "PROVIDER_CONFLICT",
                "games": [],
                "source_agreement": 0,
                "window_dates": dates,
            }

        left_status = str(left.get("status") or "UPCOMING")
        right_status = str(right.get("status") or "UPCOMING")
        # Live/final transitions can land a few seconds apart. Choose the more
        # advanced state only when matchup identity and tip time already agree.
        order = {"UPCOMING": 0, "DELAYED": 1, "LIVE": 2, "FINAL": 3, "CANCELLED": 4}
        status = max((left_status, right_status), key=lambda value: order.get(value, 0))
        merged = dict(left)
        merged["status"] = status
        merged["confirming_sources"] = ["NBA Official", "ESPN NBA"]
        merged["source_game_ids"] = {
            "NBA Official": left.get("source_game_id"),
            "ESPN NBA": right.get("source_game_id"),
        }
        reconciled.append(merged)

    reconciled.sort(key=lambda item: (item["tip_utc"], item["game_key"]))
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "SOURCE_CONSENSUS",
        "games": reconciled,
        "source_agreement": 2,
        "window_dates": dates,
    }


def _request_json(session: requests.Session, url: str, *, params: dict[str, Any] | None = None, timeout: float = 8.0) -> dict[str, Any]:
    response = session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("schedule provider returned non-object JSON")
    return payload


def _fetch_official(session: requests.Session, *, timeout: float) -> dict[str, Any]:
    last_error: Exception | None = None
    for url in NBA_OFFICIAL_SCHEDULE_URLS:
        try:
            payload = _request_json(session, url, timeout=timeout)
            if isinstance((payload.get("leagueSchedule") or {}).get("gameDates"), list):
                return payload
        except Exception as exc:  # fail over only within the same official source family
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("NBA official schedule unavailable")


def _fetch_espn(session: requests.Session, window_dates: tuple[str, ...], *, timeout: float) -> dict[str, Any]:
    start = window_dates[0].replace("-", "")
    end = window_dates[-1].replace("-", "")
    return _request_json(
        session,
        ESPN_SCOREBOARD_URL,
        params={"dates": f"{start}-{end}", "limit": 1000},
        timeout=timeout,
    )


def load_verified_nba_schedule(
    *,
    now_utc: datetime | None = None,
    days: int = ROLLING_DAYS,
    session: requests.Session | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch and reconcile the rolling NBA schedule with strict fail-closed semantics."""
    window = rolling_phoenix_dates(now_utc=now_utc, days=days)
    http = session or requests.Session()
    generated = (now_utc or datetime.now(UTC))
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=UTC)
    generated_phoenix = generated.astimezone(PHOENIX_TZ).isoformat()

    try:
        official_payload = _fetch_official(http, timeout=timeout)
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "NBA_OFFICIAL_UNAVAILABLE",
            "games": [],
            "source_agreement": 0,
            "window_dates": window,
            "generated_at_phoenix": generated_phoenix,
            "provider_errors": {"NBA Official": type(exc).__name__},
        }

    try:
        espn_payload = _fetch_espn(http, window, timeout=timeout)
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "ESPN_NBA_UNAVAILABLE",
            "games": [],
            "source_agreement": 0,
            "window_dates": window,
            "generated_at_phoenix": generated_phoenix,
            "provider_errors": {"ESPN NBA": type(exc).__name__},
        }

    official_games = parse_nba_official(official_payload, window)
    espn_games = parse_espn(espn_payload, window)
    result = reconcile_verified_schedule(official_games, espn_games, window)
    result["generated_at_phoenix"] = generated_phoenix
    result["provider_errors"] = {}
    return result


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "PHOENIX_TZ",
    "NBA_TEAM_TRICODES",
    "rolling_phoenix_dates",
    "normalize_game_status",
    "parse_nba_official",
    "parse_espn",
    "reconcile_verified_schedule",
    "load_verified_nba_schedule",
]
