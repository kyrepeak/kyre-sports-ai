"""Read-only FanDuel WNBA PRA collector.

This module reads FanDuel's anonymous public sportsbook JSON surface and emits
only canonical pregame Points + Rebounds + Assists offers for the existing WNBA
Step-5M feed adapter. It never logs in, places wagers, invents a line, or owns
player/game identity; exact identity remains downstream in the Kyre Sports API.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import re
from typing import Any, Callable, Mapping

import httpx

FANDUEL_PROVIDER_ID = "fanduel"
FANDUEL_BASE_URL = "https://api.sportsbook.fanduel.com"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
WNBA_PAGE_ID = "wnba"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_RESPONSE_BYTES = 20_000_000

FANDUEL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-WNBA/1.0; read-only)",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": FANDUEL_REGION,
}

_PRA_MARKET_RE = re.compile(
    r"^(?P<player>.+?)\s*(?:-|–|—|:)\s*(?:player\s+)?(?:points\s*[+&,/]\s*rebounds\s*[+&,/]\s*assists|points\s+rebounds\s+assists|pra)\s*$",
    re.IGNORECASE,
)


class WNBAFanDuelCollectorError(RuntimeError):
    """FanDuel WNBA PRA payload could not be safely normalized."""


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                result.append(row)
        return result
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _event_id(row: Mapping[str, Any]) -> str:
    return _text(row.get("eventId") or row.get("id") or row.get("_attachment_key"))


def _market_id(row: Mapping[str, Any]) -> str:
    return _text(row.get("marketId") or row.get("id") or row.get("_attachment_key"))


def _parse_aware(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _matchup(name: Any) -> tuple[str, str] | None:
    parts = _text(name).split(" @ ")
    if len(parts) != 2:
        return None
    away, home = (part.strip() for part in parts)
    return (away, home) if away and home else None


def _pra_player(market: Mapping[str, Any]) -> str | None:
    explicit = _text(market.get("playerName") or market.get("participantName"))
    name = _text(market.get("marketName") or market.get("name") or market.get("displayName"))
    match = _PRA_MARKET_RE.match(name)
    if match:
        return _text(match.group("player")) or None
    stat = re.sub(r"[^a-z]+", " ", _text(market.get("stat") or market.get("marketType")).casefold()).strip()
    if explicit and stat in {"pra", "points rebounds assists", "player points rebounds assists"}:
        return explicit
    return None


def _runner_side(runner: Mapping[str, Any]) -> str | None:
    result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
    value = _text(result.get("type") or runner.get("side") or runner.get("runnerName") or runner.get("name")).casefold()
    if value.startswith("over") or value == "o":
        return "over"
    if value.startswith("under") or value == "u":
        return "under"
    return None


def _runner_line(runner: Mapping[str, Any]) -> float | None:
    for key in ("handicap", "line", "point"):
        value = runner.get(key)
        if value in (None, "") or isinstance(value, bool):
            continue
        try:
            line = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(line) and 0.0 <= line <= 200.0:
            return line
    return None


def _runner_odds(runner: Mapping[str, Any]) -> int | None:
    nested = runner.get("winRunnerOdds") if isinstance(runner.get("winRunnerOdds"), Mapping) else {}
    display = nested.get("americanDisplayOdds") if isinstance(nested.get("americanDisplayOdds"), Mapping) else {}
    values = (
        display.get("americanOdds"),
        nested.get("americanOdds"),
        runner.get("americanOdds"),
        runner.get("price"),
    )
    for value in values:
        if value in (None, "") or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number.is_integer() and abs(number) >= 100:
            return int(number)
    return None


def _default_request(path: str, params: Mapping[str, Any], *, timeout: float) -> dict[str, Any]:
    url = FANDUEL_BASE_URL + path
    try:
        with httpx.Client(headers=FANDUEL_HEADERS, timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", url, params=dict(params)) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise WNBAFanDuelCollectorError(
                            f"FanDuel WNBA response exceeded {MAX_RESPONSE_BYTES} bytes"
                        )
                    chunks.append(chunk)
        raw = b"".join(chunks)
    except WNBAFanDuelCollectorError:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise WNBAFanDuelCollectorError(
            f"FanDuel WNBA GET failed: {type(exc).__name__}"
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WNBAFanDuelCollectorError("FanDuel WNBA response was not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise WNBAFanDuelCollectorError("FanDuel WNBA response was not a JSON object")
    return payload


def collect_fanduel_wnba_feed(
    *,
    date: str | None = None,
    season: int = 2026,
    env: Mapping[str, str] | None = None,
    requester: Callable[[str, Mapping[str, Any]], dict[str, Any]] | None = None,
    now_utc: datetime | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Collect current FanDuel WNBA PRA offers in canonical Step-5M format."""
    del env  # FanDuel public read path requires no secret configuration.
    target_date = _text(date) or datetime.now(timezone.utc).date().isoformat()
    if not isinstance(season, int) or isinstance(season, bool) or season <= 0:
        raise ValueError("season must be a positive integer")
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)

    if requester is None:
        request = lambda path, params: _default_request(path, params, timeout=timeout)
    else:
        request = requester

    landing = request(
        "/sbapi/content-managed-page",
        {
            "_ak": FANDUEL_PUBLIC_WEB_KEY,
            "page": "CUSTOM",
            "customPageId": WNBA_PAGE_ID,
            "timezone": "America/New_York",
        },
    )
    attachments = landing.get("attachments") if isinstance(landing, Mapping) else None
    if not isinstance(attachments, Mapping):
        raise WNBAFanDuelCollectorError("FanDuel WNBA landing page has no attachments object")

    events = _rows(attachments.get("events"))
    offers: list[dict[str, Any]] = []
    for event in events:
        event_id = _event_id(event)
        matchup = _matchup(event.get("name") or event.get("eventName") or event.get("displayName"))
        if not event_id or matchup is None:
            continue
        start = _parse_aware(event.get("openDate") or event.get("startTime"))
        if start is not None and start <= now:
            continue
        if _text(event.get("eventStatus") or event.get("status")).upper() in {"CLOSED", "FINISHED", "SETTLED"}:
            continue
        away_team, home_team = matchup
        page = request(
            "/sbapi/event-page",
            {"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id},
        )
        page_attachments = page.get("attachments") if isinstance(page, Mapping) else None
        if not isinstance(page_attachments, Mapping):
            continue
        markets = _rows(page_attachments.get("markets"))
        for market in markets:
            if _text(market.get("eventId") or market.get("eventID") or market.get("event_id")) not in {"", event_id}:
                continue
            player = _pra_player(market)
            if not player:
                continue
            status = _text(market.get("marketStatus") or market.get("status")).upper()
            if status and status != "OPEN":
                continue
            if market.get("inPlay") is True:
                continue
            market_id = _market_id(market)
            captured = _parse_aware(
                market.get("lastUpdate")
                or market.get("lastUpdated")
                or market.get("updatedAt")
            ) or now
            for runner in _rows(market.get("runners")):
                runner_status = _text(runner.get("runnerStatus") or runner.get("status")).upper()
                if runner_status not in {"", "ACTIVE", "OPEN"}:
                    continue
                side = _runner_side(runner)
                line = _runner_line(runner)
                odds = _runner_odds(runner)
                if side is None or line is None or odds is None:
                    continue
                source_offer_id = _text(
                    runner.get("runnerId")
                    or runner.get("id")
                    or runner.get("selectionId")
                    or runner.get("_attachment_key")
                )
                player_id = runner.get("playerId") or market.get("playerId")
                offers.append(
                    {
                        "sportsbook": "FanDuel",
                        "player_id": player_id,
                        "player_name": player,
                        "stat": "pra",
                        "side": side,
                        "line": line,
                        "american_odds": odds,
                        "market_captured_at_utc": _utc_iso(captured),
                        "source_event_id": event_id,
                        "source_market_id": market_id,
                        "source_offer_id": source_offer_id,
                        "home_team": home_team,
                        "away_team": away_team,
                    }
                )

    offers.sort(
        key=lambda row: (
            row["source_event_id"],
            row["player_name"].casefold(),
            row["line"],
            row["side"],
            row["source_offer_id"],
        )
    )
    return {
        "provider_id": FANDUEL_PROVIDER_ID,
        "feed_source": "FanDuel anonymous public WNBA sportsbook JSON",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "date": target_date,
        "season": season,
        "collected_at_utc": _utc_iso(now),
        "raw_feed": {"offers": offers},
    }


__all__ = [
    "FANDUEL_PROVIDER_ID",
    "WNBAFanDuelCollectorError",
    "collect_fanduel_wnba_feed",
]
