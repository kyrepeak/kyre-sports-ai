"""Read-only FanDuel NCAAF game-total collector for CFB odds Step 2.

The collector uses FanDuel's anonymous sportsbook web JSON surface. It performs
one GET against the verified ncaaf content page and extracts only the canonical
pregame Total Points market.

No account, cookies, wager action, personal token, paid odds vendor, model
projection, fuzzy identity, or synthetic game ID is used here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from typing import Any, Mapping

import httpx

FANDUEL_BASE_URL = "https://api.sportsbook.fanduel.com"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
NCAAF_PAGE_ID = "ncaaf"
TOTAL_MARKET_NAME = "Total Points"
MAX_RESPONSE_BYTES = 20_000_000
DEFAULT_TIMEOUT_SECONDS = 20.0

FANDUEL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-CFB/1.0; read-only)",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": FANDUEL_REGION,
}


class CFBFanDuelCollectorError(RuntimeError):
    """FanDuel CFB total surface could not be safely normalized."""


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                result.append(row)
        return result
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _event_id(event: Mapping[str, Any]) -> str:
    return _text(
        event.get("eventId")
        or event.get("id")
        or event.get("_attachment_key")
    )


def _event_name(event: Mapping[str, Any]) -> str:
    return _text(
        event.get("name")
        or event.get("eventName")
        or event.get("displayName")
    )


def _parse_aware(value: Any, field: str) -> datetime:
    text = _text(value)
    if not text:
        raise CFBFanDuelCollectorError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CFBFanDuelCollectorError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CFBFanDuelCollectorError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_matchup(event_name: str) -> tuple[str, str]:
    parts = _text(event_name).split(" @ ")
    if len(parts) != 2:
        raise CFBFanDuelCollectorError(f"not a two-team CFB matchup: {event_name!r}")
    away, home = (part.strip() for part in parts)
    if not away or not home:
        raise CFBFanDuelCollectorError(f"missing CFB team in matchup: {event_name!r}")
    return away, home


def _get_json(
    url: str,
    *,
    params: Mapping[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        with httpx.Client(
            headers=FANDUEL_HEADERS,
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            with client.stream("GET", url, params=dict(params)) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise CFBFanDuelCollectorError(
                            f"FanDuel response exceeded {MAX_RESPONSE_BYTES} bytes"
                        )
                    chunks.append(chunk)
        raw = b"".join(chunks)
    except CFBFanDuelCollectorError:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise CFBFanDuelCollectorError(
            f"FanDuel CFB GET failed: {type(exc).__name__}"
        ) from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CFBFanDuelCollectorError(
            "FanDuel CFB response was not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CFBFanDuelCollectorError("FanDuel CFB response was not a JSON object")
    return payload


def fetch_fanduel_ncaaf_page(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/content-managed-page",
        params={
            "_ak": FANDUEL_PUBLIC_WEB_KEY,
            "page": "CUSTOM",
            "customPageId": NCAAF_PAGE_ID,
            "timezone": "America/New_York",
        },
        timeout=timeout,
    )


def _runner_role(runner: Mapping[str, Any]) -> str:
    result = runner.get("result") if isinstance(runner.get("result"), dict) else {}
    return _text(result.get("type")).upper()


def _runner_line(runner: Mapping[str, Any]) -> float:
    try:
        line = float(runner.get("handicap"))
    except (TypeError, ValueError) as exc:
        raise CFBFanDuelCollectorError("Total Points runner has invalid handicap") from exc
    if not math.isfinite(line) or line <= 0 or line > 200:
        raise CFBFanDuelCollectorError(
            "Total Points runner handicap is outside the supported CFB range"
        )
    return line


def _total_line(market: Mapping[str, Any]) -> float:
    status = _text(market.get("marketStatus") or market.get("status")).upper()
    if status != "OPEN" or market.get("inPlay") is True:
        raise CFBFanDuelCollectorError("Total Points market is not open pregame")

    active = [
        runner
        for runner in _rows(market.get("runners"))
        if _text(runner.get("runnerStatus")).upper() in {"", "ACTIVE"}
    ]
    overs = [runner for runner in active if _runner_role(runner) == "OVER"]
    unders = [runner for runner in active if _runner_role(runner) == "UNDER"]
    if len(overs) != 1 or len(unders) != 1:
        raise CFBFanDuelCollectorError(
            "Total Points market must contain exactly one active OVER and UNDER"
        )
    over_line = _runner_line(overs[0])
    under_line = _runner_line(unders[0])
    if over_line != under_line:
        raise CFBFanDuelCollectorError(
            f"Total Points line mismatch: {over_line} vs {under_line}"
        )
    return over_line


def normalize_fanduel_ncaaf_page(
    payload: Mapping[str, Any],
    *,
    observed_at_utc: datetime,
) -> dict[str, Any]:
    if observed_at_utc.tzinfo is None or observed_at_utc.utcoffset() is None:
        raise ValueError("observed_at_utc must be timezone-aware")
    now = observed_at_utc.astimezone(timezone.utc)

    attachments = payload.get("attachments")
    if not isinstance(attachments, dict):
        raise CFBFanDuelCollectorError("FanDuel NCAAF page has no attachments object")

    events = _rows(attachments.get("events"))
    markets = _rows(attachments.get("markets"))
    event_map = {_event_id(event): event for event in events if _event_id(event)}

    total_markets: dict[str, list[dict[str, Any]]] = {}
    for market in markets:
        if _text(
            market.get("marketName")
            or market.get("name")
            or market.get("displayName")
        ) != TOTAL_MARKET_NAME:
            continue
        event_id = _text(
            market.get("eventId")
            or market.get("eventID")
            or market.get("event_id")
        )
        if event_id:
            total_markets.setdefault(event_id, []).append(market)

    games: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    matchup_event_count = 0

    for event_id, event in sorted(
        event_map.items(),
        key=lambda pair: (_text(pair[1].get("openDate")), pair[0]),
    ):
        name = _event_name(event)
        if " @ " not in name:
            continue
        matchup_event_count += 1
        try:
            away_team, home_team = parse_matchup(name)
            start = _parse_aware(event.get("openDate"), "FanDuel event openDate")
            if start <= now:
                continue

            candidates = total_markets.get(event_id, [])
            open_candidates = [
                market
                for market in candidates
                if _text(market.get("marketStatus") or market.get("status")).upper()
                == "OPEN"
                and market.get("inPlay") is not True
            ]
            if len(open_candidates) != 1:
                raise CFBFanDuelCollectorError(
                    f"expected one open pregame Total Points market, found {len(open_candidates)}"
                )
            total = _total_line(open_candidates[0])
            games.append(
                {
                    "game_id": event_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "start_time_utc": _utc_iso(start),
                    "total": total,
                    "sportsbook": "FanDuel",
                    "updated_at_utc": _utc_iso(now),
                    "line_status": "active",
                }
            )
        except Exception as exc:
            rejected.append(
                {
                    "provider_game_id": event_id,
                    "provider_event_name": name or None,
                    "reason": f"{type(exc).__name__}: {exc}"[:320],
                }
            )

    if not games:
        raise CFBFanDuelCollectorError(
            "FanDuel NCAAF page produced no future open Total Points games"
        )

    game_ids = [row["game_id"] for row in games]
    if len(set(game_ids)) != len(game_ids):
        raise CFBFanDuelCollectorError("FanDuel NCAAF page produced duplicate event IDs")

    return {
        "schema_version": "cfb_market_feed_v1",
        "captured_at_utc": _utc_iso(now),
        "source": "FanDuel anonymous public NCAAF content-managed-page",
        "games": games,
        "provider_diagnostics": {
            "provider": "FanDuel",
            "transport": "anonymous_public_get_only",
            "http_methods": ["GET"],
            "custom_page_id": NCAAF_PAGE_ID,
            "landing_event_count": len(events),
            "matchup_event_count": matchup_event_count,
            "landing_market_count": len(markets),
            "total_points_market_count": sum(len(v) for v in total_markets.values()),
            "accepted_game_count": len(games),
            "rejected_game_count": len(rejected),
            "rejected_games": rejected,
            "network_requests": 1,
            "paid_odds_vendor_required": False,
            "sportsbook_credentials_required": False,
            "wager_actions": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def collect_fanduel_cfb_total_feed(
    *,
    now_utc: datetime | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    page_fetcher=None,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    fetch = page_fetcher or (lambda: fetch_fanduel_ncaaf_page(timeout=timeout))
    payload = fetch()
    if not isinstance(payload, Mapping):
        raise CFBFanDuelCollectorError("FanDuel page fetcher returned a non-object")
    return normalize_fanduel_ncaaf_page(payload, observed_at_utc=now)


__all__ = [
    "CFBFanDuelCollectorError",
    "FANDUEL_BASE_URL",
    "FANDUEL_REGION",
    "NCAAF_PAGE_ID",
    "TOTAL_MARKET_NAME",
    "collect_fanduel_cfb_total_feed",
    "fetch_fanduel_ncaaf_page",
    "normalize_fanduel_ncaaf_page",
    "parse_matchup",
]
