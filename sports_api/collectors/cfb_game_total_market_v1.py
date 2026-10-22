"""Approved CFB Game Total sportsbook collection for Kyre Sports API.

FanDuel is the primary direct sportsbook. The Odds API is an optional secondary
used only when the API owner asks for missing-game coverage. Quotes are kept
book-specific; no consensus line, averaging, fabrication, or projection input is
created here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sports_api.collectors import cfb_fanduel_direct as fanduel
from sports_api.collectors import cfb_fanduel_moneyline_v1 as identity

MODEL_VERSION = "CFB GAME TOTAL MARKET V1 • KYRE SPORTS API"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds"
_ALLOWED_BOOK_KEYS = {
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "williamhill_us": "Caesars",
    "caesars": "Caesars",
    "bet365": "bet365",
    "fanatics": "Fanatics",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _american(value: Any) -> int | None:
    if isinstance(value, Mapping):
        return identity._american(value)
    number = _finite(value)
    if number is None or number == 0 or abs(number) < 100 or abs(number) > 100_000:
        return None
    return int(round(number))


def _active_market(market: Mapping[str, Any]) -> bool:
    status = _clean(market.get("marketStatus") or market.get("status")).upper()
    return status == "OPEN" and market.get("inPlay") is not True and market.get("isLive") is not True


def _market_name(market: Mapping[str, Any]) -> str:
    return _clean(market.get("marketName") or market.get("name") or market.get("displayName"))


def _event_id(market: Mapping[str, Any]) -> str:
    return _clean(market.get("eventId") or market.get("eventID") or market.get("event_id"))


def _market_id(market: Mapping[str, Any]) -> str:
    return _clean(market.get("marketId") or market.get("id") or market.get("_attachment_key"))


def _runner_role(runner: Mapping[str, Any]) -> str:
    role = _clean(runner.get("side")).upper()
    if role in {"AWAY", "HOME"}:
        return role
    result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
    role = _clean(result.get("type")).upper()
    return role


def _active_runners(market: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for runner in fanduel._rows(market.get("runners") or market.get("selections")):
        status = _clean(runner.get("runnerStatus") or runner.get("status")).upper()
        if status in {"", "ACTIVE"}:
            out.append(dict(runner))
    return out


def _two_sides(market: Mapping[str, Any]) -> dict[str, dict[str, Any]] | None:
    sides: dict[str, dict[str, Any]] = {}
    for runner in _active_runners(market):
        role = _runner_role(runner)
        if role not in {"AWAY", "HOME"} or role in sides:
            continue
        sides[role] = runner
    return sides if set(sides) == {"AWAY", "HOME"} else None


def _total(market: Mapping[str, Any]) -> tuple[float, int | None, int | None] | None:
    overs: list[dict[str, Any]] = []
    unders: list[dict[str, Any]] = []
    for runner in _active_runners(market):
        role = _runner_role(runner)
        if role == "OVER":
            overs.append(runner)
        elif role == "UNDER":
            unders.append(runner)
    if len(overs) != 1 or len(unders) != 1:
        return None
    over_line = _finite(overs[0].get("handicap"))
    under_line = _finite(unders[0].get("handicap"))
    if over_line is None or under_line is None or over_line <= 0 or abs(over_line - under_line) > 1e-6:
        return None
    return over_line, _american(overs[0]), _american(unders[0])


def _spread(market: Mapping[str, Any]) -> tuple[float, int | None, float, int | None] | None:
    sides = _two_sides(market)
    if sides is None:
        return None
    away_line = _finite(sides["AWAY"].get("handicap"))
    home_line = _finite(sides["HOME"].get("handicap"))
    if away_line is None or home_line is None or abs(away_line + home_line) > 1e-6:
        return None
    return away_line, _american(sides["AWAY"]), home_line, _american(sides["HOME"])


def _moneyline(market: Mapping[str, Any]) -> tuple[int, int] | None:
    sides = _two_sides(market)
    if sides is None:
        return None
    away = _american(sides["AWAY"])
    home = _american(sides["HOME"])
    if away is None or home is None:
        return None
    return away, home


def normalize_fanduel_game_markets(
    payload: Mapping[str, Any], *, observed_at_utc: datetime
) -> list[dict[str, Any]]:
    """Return one FanDuel quote object per future matchup, preserving exact prices."""
    if observed_at_utc.tzinfo is None or observed_at_utc.utcoffset() is None:
        raise ValueError("observed_at_utc must be timezone-aware")
    attachments = payload.get("attachments")
    if not isinstance(attachments, Mapping):
        return []
    events = fanduel._rows(attachments.get("events"))
    markets = fanduel._rows(attachments.get("markets"))
    event_map = {fanduel._event_id(row): row for row in events if fanduel._event_id(row)}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for market in markets:
        if not _active_market(market):
            continue
        event_id = _event_id(market)
        if event_id:
            grouped.setdefault(event_id, []).append(dict(market))

    observed = observed_at_utc.astimezone(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for provider_event_id, event in event_map.items():
        name = fanduel._event_name(event)
        if " @ " not in name:
            continue
        try:
            away_team, home_team = fanduel.parse_matchup(name)
        except Exception:
            continue
        candidates = grouped.get(provider_event_id, [])
        total_market = next((m for m in candidates if _market_name(m) == "Total Points"), None)
        if total_market is None:
            continue
        total = _total(total_market)
        if total is None:
            continue
        total_line, over_price, under_price = total
        spread_market = next((m for m in candidates if _market_name(m) in {"Spread", "Point Spread"}), None)
        moneyline_market = next((m for m in candidates if _market_name(m) == "Moneyline"), None)
        spread = _spread(spread_market) if spread_market is not None else None
        moneyline = _moneyline(moneyline_market) if moneyline_market is not None else None
        start = _clean(event.get("openDate")) or None
        row: dict[str, Any] = {
            "sportsbook": "FanDuel",
            "market": "game_total",
            "provider_event_id": provider_event_id,
            "provider_market_id": _market_id(total_market),
            "away_team": away_team,
            "home_team": home_team,
            "start_time_utc": start,
            "total_line": total_line,
            "over_price": over_price,
            "under_price": under_price,
            "away_spread": None,
            "away_spread_price": None,
            "home_spread": None,
            "home_spread_price": None,
            "away_moneyline": None,
            "home_moneyline": None,
            "observed_at_utc": observed,
            "line_status": "open",
        }
        if spread is not None:
            row.update({
                "away_spread": spread[0], "away_spread_price": spread[1],
                "home_spread": spread[2], "home_spread_price": spread[3],
            })
        if moneyline is not None:
            row.update({"away_moneyline": moneyline[0], "home_moneyline": moneyline[1]})
        rows.append(row)
    rows.sort(key=lambda row: (identity._canonical(row["away_team"]), identity._canonical(row["home_team"])))
    return rows


def collect_fanduel_game_markets(*, now_provider=lambda: datetime.now(timezone.utc)) -> list[dict[str, Any]]:
    return normalize_fanduel_game_markets(
        fanduel.fetch_fanduel_ncaaf_page(), observed_at_utc=now_provider()
    )


def _kickoff_close(game: Mapping[str, Any], quote: Mapping[str, Any]) -> bool:
    left = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    right = _clean(quote.get("start_time_utc"))
    if not left or not right:
        return True
    try:
        ldt = datetime.fromisoformat(left.replace("Z", "+00:00"))
        rdt = datetime.fromisoformat(right.replace("Z", "+00:00"))
    except ValueError:
        return False
    if ldt.tzinfo is None or rdt.tzinfo is None:
        return False
    return abs((ldt.astimezone(timezone.utc) - rdt.astimezone(timezone.utc)).total_seconds()) <= 3 * 3600


def match_market_rows_to_ncaa_games(
    games: Iterable[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        pair = (identity._canonical(row.get("away_team")), identity._canonical(row.get("home_team")))
        if all(pair):
            by_pair.setdefault(pair, []).append(row)
    out: dict[str, list[dict[str, Any]]] = {}
    for game in games:
        game_id = _clean(game.get("game_id") or game.get("identity_key"))
        if not game_id:
            continue
        pair = (identity._canonical(game.get("away_team")), identity._canonical(game.get("home_team")))
        candidates = [row for row in by_pair.get(pair, []) if _kickoff_close(game, row)]
        seen: set[tuple[str, str, str]] = set()
        accepted: list[dict[str, Any]] = []
        for row in candidates:
            ident = (_clean(row.get("sportsbook")), _clean(row.get("provider_event_id")), _clean(row.get("provider_market_id")))
            if not all(ident) or ident in seen:
                continue
            seen.add(ident)
            accepted.append(dict(row))
        if accepted:
            accepted.sort(key=lambda row: (_clean(row.get("sportsbook")), _clean(row.get("provider_market_id"))))
            out[game_id] = accepted
    return out


def collect_the_odds_api_game_markets(
    *, now_provider=lambda: datetime.now(timezone.utc), env: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    env = dict(os.environ if env is None else env)
    api_key = _clean(env.get("THE_ODDS_API_KEY") or env.get("ODDS_API_KEY"))
    if not api_key:
        return []
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    request = Request(
        THE_ODDS_API_URL + "?" + urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "KyreSportsAPI/CFB-GameTotal-V1"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    observed_default = now_provider().astimezone(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for event in payload:
        if not isinstance(event, Mapping):
            continue
        event_id = _clean(event.get("id"))
        away_team, home_team = _clean(event.get("away_team")), _clean(event.get("home_team"))
        if not event_id or not away_team or not home_team:
            continue
        for bookmaker in event.get("bookmakers") or []:
            if not isinstance(bookmaker, Mapping):
                continue
            book_key = _clean(bookmaker.get("key")).casefold()
            sportsbook = _ALLOWED_BOOK_KEYS.get(book_key)
            if not sportsbook:
                continue
            row: dict[str, Any] = {
                "sportsbook": sportsbook,
                "market": "game_total",
                "provider_event_id": event_id,
                "provider_market_id": "",
                "away_team": away_team,
                "home_team": home_team,
                "start_time_utc": _clean(event.get("commence_time")) or None,
                "total_line": None, "over_price": None, "under_price": None,
                "away_spread": None, "away_spread_price": None,
                "home_spread": None, "home_spread_price": None,
                "away_moneyline": None, "home_moneyline": None,
                "observed_at_utc": _clean(bookmaker.get("last_update")) or observed_default,
                "line_status": "open",
            }
            market_ids: list[str] = []
            for market in bookmaker.get("markets") or []:
                if not isinstance(market, Mapping):
                    continue
                key = _clean(market.get("key")).casefold()
                outcomes = [o for o in market.get("outcomes") or [] if isinstance(o, Mapping)]
                market_ids.append(key)
                if key == "totals":
                    for outcome in outcomes:
                        name = _clean(outcome.get("name")).casefold()
                        point, price = _finite(outcome.get("point")), _american(outcome.get("price"))
                        if name == "over":
                            row["total_line"], row["over_price"] = point, price
                        elif name == "under" and row["total_line"] in (None, point):
                            row["total_line"], row["under_price"] = point, price
                elif key == "spreads":
                    for outcome in outcomes:
                        team = identity._canonical(outcome.get("name"))
                        point, price = _finite(outcome.get("point")), _american(outcome.get("price"))
                        if team == identity._canonical(away_team):
                            row["away_spread"], row["away_spread_price"] = point, price
                        elif team == identity._canonical(home_team):
                            row["home_spread"], row["home_spread_price"] = point, price
                elif key == "h2h":
                    for outcome in outcomes:
                        team = identity._canonical(outcome.get("name"))
                        price = _american(outcome.get("price"))
                        if team == identity._canonical(away_team):
                            row["away_moneyline"] = price
                        elif team == identity._canonical(home_team):
                            row["home_moneyline"] = price
            if row["total_line"] is None:
                continue
            row["provider_market_id"] = "+".join(sorted(set(market_ids))) + ":" + book_key
            rows.append(row)
    return rows


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "collect_fanduel_game_markets",
    "collect_the_odds_api_game_markets",
    "match_market_rows_to_ncaa_games",
    "normalize_fanduel_game_markets",
]
