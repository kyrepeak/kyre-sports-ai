"""CFB Game Total Page 1 — all-games Daily Slate API V1.

Read-only descriptive/contextual API for one America/Phoenix calendar day.
It discovers both FBS (ESPN group 80) and FCS (group 81), dedupes only by exact
ESPN event ID, preserves field provenance, and exposes raw verified sportsbook
observations without affecting any projection/model path.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

from sports_api.api.cfb_market_identity_v1 import reconcile_market_feed, resolve_verified_games
from sports_api.api.cfb_markets import _load_feed
from sports_api.api.cfb_odds_v1 import build_odds_payload

router = APIRouter(prefix="/api/v1/cfb", tags=["cfb"])

MODEL_VERSION = "CFB GAME TOTAL PAGE1 DAILY SLATE API V1"
SCHEMA_VERSION = "cfb_daily_slate_v1"
PHOENIX = ZoneInfo("America/Phoenix")
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/"
    "college-football/scoreboard"
)
HTTP_TIMEOUT_SECONDS = 12.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PAGE_WIDE_SOURCE_AUTHORITY = False
FABRICATION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _parse_aware(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def phoenix_day_utc_bounds(selected_day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(selected_day, time.min, tzinfo=PHOENIX)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def upstream_scoreboard_dates_for_phoenix_day(selected_day: date) -> tuple[str, ...]:
    start, end = phoenix_day_utc_bounds(selected_day)
    days: list[str] = []
    cursor = start.date()
    final = (end - timedelta(microseconds=1)).date()
    while cursor <= final:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return tuple(days)


def _competitor(comp: Mapping[str, Any], side: str) -> Mapping[str, Any] | None:
    for row in comp.get("competitors") or []:
        if isinstance(row, Mapping) and _clean(row.get("homeAway")).casefold() == side:
            return row
    return None


def _record(row: Mapping[str, Any]) -> str | None:
    for record in row.get("records") or []:
        if isinstance(record, Mapping) and _clean(record.get("summary")):
            return _clean(record.get("summary"))
    return None


def _rank(row: Mapping[str, Any]) -> int | None:
    curated = row.get("curatedRank") if isinstance(row.get("curatedRank"), Mapping) else {}
    raw = curated.get("current")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= 25 else None


def _team_payload(row: Mapping[str, Any]) -> dict[str, Any] | None:
    team = row.get("team") if isinstance(row.get("team"), Mapping) else {}
    team_id = _clean(team.get("id"))
    name = _clean(
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("location")
        or team.get("name")
    )
    if not name:
        return None
    logo = _clean(team.get("logo"))
    if not logo and team_id.isdigit():
        logo = f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
    return {
        "id": team_id or None,
        "name": name,
        "logo": logo or None,
        "record": _record(row),
        "rank": _rank(row),
        "score": _clean(row.get("score")) or None,
        "conference": _clean(team.get("conference")) or None,
    }


def _broadcast(comp: Mapping[str, Any]) -> str | None:
    names: list[str] = []
    for row in comp.get("broadcasts") or []:
        if not isinstance(row, Mapping):
            continue
        for name in row.get("names") or []:
            value = _clean(name)
            if value and value not in names:
                names.append(value)
    return ", ".join(names) or None


def _weather(comp: Mapping[str, Any]) -> dict[str, Any] | None:
    row = comp.get("weather") if isinstance(comp.get("weather"), Mapping) else {}
    if not row:
        return None
    temperature = _float(row.get("temperature"))
    wind_speed = _float(row.get("windSpeed"))
    precipitation = _float(row.get("precipitation"))
    gust = _float(row.get("windGust"))
    return {
        "summary": _clean(row.get("displayValue")) or None,
        "temperature_f": temperature,
        "precipitation_pct": precipitation,
        "wind_mph": wind_speed,
        "wind_gust_mph": gust,
        "wind_direction": _clean(row.get("windDirection")) or None,
        "source": "ESPN scoreboard weather metadata",
    }


def _status_payload(event: Mapping[str, Any], comp: Mapping[str, Any]) -> dict[str, Any]:
    status = comp.get("status") if isinstance(comp.get("status"), Mapping) else event.get("status")
    status = status if isinstance(status, Mapping) else {}
    status_type = status.get("type") if isinstance(status.get("type"), Mapping) else {}
    description = _clean(
        status_type.get("description")
        or status_type.get("detail")
        or status_type.get("shortDetail")
    ) or "Scheduled"
    state = _clean(status_type.get("state")).casefold()
    completed = bool(status_type.get("completed")) or state == "post" or description.casefold() == "final"
    live = state == "in" or any(token in description.casefold() for token in ("quarter", "halftime", "in progress"))
    if completed:
        normalized = "Final"
    elif "half" in description.casefold():
        normalized = "Halftime"
    elif live:
        normalized = "Live"
    else:
        normalized = "Scheduled"
    return {
        "state": normalized,
        "detail": description,
        "period": status.get("period") or event.get("status", {}).get("period"),
        "clock": _clean(status.get("displayClock") or event.get("status", {}).get("displayClock")) or None,
        "completed": completed,
    }


def scoreboard_market_observations(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    event_id = _clean(event.get("id"))
    competitions = event.get("competitions") or []
    if not event_id or not competitions or not isinstance(competitions[0], Mapping):
        return []
    comp = competitions[0]
    status = _status_payload(event, comp)
    phase = "live" if status["state"] in {"Live", "Halftime"} else "pregame"
    out: list[dict[str, Any]] = []
    for quote in comp.get("odds") or []:
        if not isinstance(quote, Mapping):
            continue
        provider = quote.get("provider") if isinstance(quote.get("provider"), Mapping) else {}
        sportsbook = _clean(provider.get("name") or provider.get("id"))
        if not sportsbook:
            continue
        provider_id = _clean(provider.get("id") or sportsbook).casefold().replace(" ", "_")
        common = {
            "game_id": event_id,
            "provider_id": provider_id,
            "sportsbook": sportsbook,
            "phase": phase,
            "observed_at_utc": None,
            "identity_verified": True,
            "provenance": "ESPN scoreboard market payload",
            "transport": "espn_scoreboard",
            "fabrication": False,
        }
        total = _float(quote.get("overUnder"))
        if total is not None:
            out.append({**common, "market_type": "game_total", "value": total})
        spread = _float(quote.get("spread"))
        if spread is not None:
            out.append(
                {
                    **common,
                    "market_type": "spread",
                    "home_value": spread,
                    "away_value": -spread,
                    "value": spread,
                }
            )
        away_odds = quote.get("awayTeamOdds") if isinstance(quote.get("awayTeamOdds"), Mapping) else {}
        home_odds = quote.get("homeTeamOdds") if isinstance(quote.get("homeTeamOdds"), Mapping) else {}
        away_ml = _float(away_odds.get("moneyLine"))
        home_ml = _float(home_odds.get("moneyLine"))
        if away_ml is not None or home_ml is not None:
            out.append(
                {
                    **common,
                    "market_type": "moneyline",
                    "away_value": away_ml,
                    "home_value": home_ml,
                    "value": home_ml if home_ml is not None else away_ml,
                }
            )
    return out


def normalize_scoreboard_event(
    event: Mapping[str, Any], *, subdivision: str
) -> dict[str, Any] | None:
    if not isinstance(event, Mapping):
        return None
    event_id = _clean(event.get("id"))
    competitions = event.get("competitions") or []
    if not event_id or not competitions or not isinstance(competitions[0], Mapping):
        return None
    comp = competitions[0]
    kickoff = _parse_aware(event.get("date") or comp.get("date"))
    if kickoff is None:
        return None
    away_row = _competitor(comp, "away")
    home_row = _competitor(comp, "home")
    if away_row is None or home_row is None:
        return None
    away = _team_payload(away_row)
    home = _team_payload(home_row)
    if away is None or home is None:
        return None

    venue_row = comp.get("venue") if isinstance(comp.get("venue"), Mapping) else {}
    address = venue_row.get("address") if isinstance(venue_row.get("address"), Mapping) else {}
    city_bits = [_clean(address.get("city")), _clean(address.get("state"))]
    city = ", ".join(bit for bit in city_bits if bit) or None
    status = _status_payload(event, comp)
    kickoff_phoenix = kickoff.astimezone(PHOENIX)
    tag = _clean(subdivision).upper()
    if tag not in {"FBS", "FCS"}:
        tag = "UNKNOWN"
    return {
        "event_id": event_id,
        "kickoff_utc": kickoff.isoformat(),
        "kickoff_phoenix": kickoff_phoenix.isoformat(),
        "phoenix_date": kickoff_phoenix.date().isoformat(),
        "away": away,
        "home": home,
        "subdivisions": [tag],
        "venue": _clean(venue_row.get("fullName")) or None,
        "city": city,
        "indoor": venue_row.get("indoor") if isinstance(venue_row.get("indoor"), bool) else None,
        "broadcast": _broadcast(comp),
        "weather": _weather(comp),
        "status": status,
        "market_observations": scoreboard_market_observations(event),
        "provenance": {
            "schedule": "ESPN college-football scoreboard exact-date subdivision feed",
            "identity": "official ESPN event_id",
            "logistics": "ESPN competition metadata",
        },
        "identity_verified": True,
        "fabrication": False,
        "page_wide_source_authority": False,
    }


def merge_scoreboard_games(
    rows: Iterable[Mapping[str, Any] | None], *, selected_day: date
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        event_id = _clean(raw.get("event_id"))
        if not event_id or _clean(raw.get("phoenix_date")) != selected_day.isoformat():
            continue
        if event_id not in by_id:
            by_id[event_id] = dict(raw)
            by_id[event_id]["subdivisions"] = list(raw.get("subdivisions") or [])
            by_id[event_id]["market_observations"] = [dict(v) for v in raw.get("market_observations") or []]
            continue
        existing = by_id[event_id]
        tags = set(existing.get("subdivisions") or [])
        tags.update(raw.get("subdivisions") or [])
        existing["subdivisions"] = sorted(tags, key=lambda item: (item != "FBS", item))
        existing["market_observations"].extend(dict(v) for v in raw.get("market_observations") or [])

    return sorted(
        by_id.values(),
        key=lambda game: (_clean(game.get("kickoff_phoenix")), _clean(game.get("event_id"))),
    )


def _fetch_scoreboard_payload(day: str, group_id: int) -> dict[str, Any]:
    response = httpx.get(
        ESPN_SCOREBOARD_URL,
        params={"dates": day.replace("-", ""), "limit": 500, "groups": group_id},
        timeout=HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": "KyreSportsAPI/CFB-Daily-Slate-V1", "Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ESPN scoreboard returned a non-object payload")
    return payload


def _exact_kyre_market_rows() -> list[dict[str, Any]]:
    try:
        feed = _load_feed()
        verified_games, _identity = resolve_verified_games(feed)
        payload = build_odds_payload(feed, verified_games)
    except Exception:
        return []
    return [dict(row) for row in payload.get("games") or [] if isinstance(row, Mapping)]


def _external_market_observation(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    if row.get("identity_verified") is not True:
        return []
    game_id = _clean(row.get("game_id"))
    sportsbook = _clean(row.get("sportsbook"))
    if not game_id or not sportsbook:
        return []
    market_type = _clean(row.get("market_type") or "game_total").casefold()
    provider_id = _clean(row.get("provider_id") or sportsbook).casefold().replace(" ", "_")
    phase = _clean(row.get("phase") or "pregame").casefold()
    common = {
        "game_id": game_id,
        "provider_id": provider_id,
        "sportsbook": sportsbook,
        "market_type": market_type,
        "phase": phase if phase in {"opening", "pregame", "live"} else "pregame",
        "observed_at_utc": _clean(row.get("line_updated_at_utc") or row.get("observed_at_utc")) or None,
        "identity_verified": True,
        "provenance": _clean(row.get("provenance")) or "Kyre Sports API verified market row",
        "transport": _clean(row.get("transport")) or "kyre_sports_api",
        "fabrication": False,
    }
    if market_type == "game_total":
        value = _float(row.get("total") if row.get("total") is not None else row.get("value"))
        return [{**common, "value": value}] if value is not None else []
    if market_type == "spread":
        value = _float(row.get("value"))
        home = _float(row.get("home_value"))
        away = _float(row.get("away_value"))
        if value is None and home is None and away is None:
            return []
        return [{**common, "value": value if value is not None else home, "home_value": home, "away_value": away}]
    if market_type == "moneyline":
        home = _float(row.get("home_value"))
        away = _float(row.get("away_value"))
        value = _float(row.get("value"))
        if home is None and away is None and value is None:
            return []
        return [{**common, "value": value if value is not None else home or away, "home_value": home, "away_value": away}]
    return []


def _dedupe_market_observations(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping) or raw.get("identity_verified") is not True:
            continue
        game_id = _clean(raw.get("game_id"))
        sportsbook = _clean(raw.get("sportsbook"))
        market_type = _clean(raw.get("market_type")).casefold()
        phase = _clean(raw.get("phase") or "pregame").casefold()
        if not game_id or not sportsbook or not market_type:
            continue
        key = (game_id, sportsbook.casefold(), market_type, phase)
        candidate = dict(raw)
        current = chosen.get(key)
        if current is None:
            chosen[key] = candidate
            continue
        current_ts = _parse_aware(current.get("observed_at_utc"))
        candidate_ts = _parse_aware(candidate.get("observed_at_utc"))
        if candidate_ts is not None and (current_ts is None or candidate_ts >= current_ts):
            chosen[key] = candidate
    return sorted(
        chosen.values(),
        key=lambda row: (
            _clean(row.get("game_id")),
            _clean(row.get("market_type")),
            _clean(row.get("sportsbook")).casefold(),
            _clean(row.get("phase")),
        ),
    )


def build_daily_slate_payload(
    selected_phoenix_date: date,
    *,
    now_utc: datetime | None = None,
    scoreboard_payloads: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
    market_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    del now_utc  # Reserved for later bounded live-state freshness metadata.
    normalized_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for day in upstream_scoreboard_dates_for_phoenix_day(selected_phoenix_date):
        for group_id, subdivision in ((80, "FBS"), (81, "FCS")):
            try:
                if scoreboard_payloads is None:
                    payload = _fetch_scoreboard_payload(day, group_id)
                else:
                    payload = dict(scoreboard_payloads.get((day, group_id)) or {})
                count = 0
                for event in payload.get("events") or []:
                    game = normalize_scoreboard_event(event, subdivision=subdivision)
                    if game is not None:
                        normalized_rows.append(game)
                        count += 1
                diagnostics.append({"date": day, "group_id": group_id, "subdivision": subdivision, "ok": True, "games": count})
            except Exception as exc:
                diagnostics.append({"date": day, "group_id": group_id, "subdivision": subdivision, "ok": False, "games": 0, "error": f"{type(exc).__name__}: {exc}"[:220]})

    games = merge_scoreboard_games(normalized_rows, selected_day=selected_phoenix_date)
    exact_market_rows = list(market_rows) if market_rows is not None else _exact_kyre_market_rows()
    external_observations: list[dict[str, Any]] = []
    for row in exact_market_rows:
        if isinstance(row, Mapping):
            external_observations.extend(_external_market_observation(row))
    external_by_game: dict[str, list[dict[str, Any]]] = {}
    for observation in external_observations:
        external_by_game.setdefault(_clean(observation.get("game_id")), []).append(observation)

    for game in games:
        combined = list(game.get("market_observations") or []) + external_by_game.get(game["event_id"], [])
        game["market_observations"] = _dedupe_market_observations(combined)

    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "requested_phoenix_date": selected_phoenix_date.isoformat(),
        "timezone": "America/Phoenix",
        "game_count": len(games),
        "games": games,
        "diagnostics": {"scoreboard_attempts": diagnostics},
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "page_wide_source_authority": PAGE_WIDE_SOURCE_AUTHORITY,
        "fabrication": FABRICATION,
    }


@router.get("/daily-slate")
def daily_slate(game_date: str = Query(..., min_length=10, max_length=10)) -> dict[str, Any]:
    try:
        selected_day = date.fromisoformat(game_date).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="game_date must be YYYY-MM-DD") from exc
    return build_daily_slate_payload(date.fromisoformat(selected_day))


__all__ = [
    "FABRICATION",
    "MODEL_VERSION",
    "PAGE_WIDE_SOURCE_AUTHORITY",
    "PHOENIX",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_daily_slate_payload",
    "daily_slate",
    "merge_scoreboard_games",
    "normalize_scoreboard_event",
    "phoenix_day_utc_bounds",
    "router",
    "scoreboard_market_observations",
    "upstream_scoreboard_dates_for_phoenix_day",
]
