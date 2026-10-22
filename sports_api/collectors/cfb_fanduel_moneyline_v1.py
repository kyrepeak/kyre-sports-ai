"""Approved CFB Moneyline sportsbook collection for Kyre Sports API.

FanDuel is the direct primary sportsbook. An optional The Odds API reader is
available only when its key is configured and the caller needs a secondary
source. Quotes stay book-specific and are never combined into one synthetic
price.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import re
import unicodedata
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sports_api.collectors import cfb_fanduel_direct as fanduel

MODEL_VERSION = "CFB FANDUEL MONEYLINE V1 • KYRE SPORTS API"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds"
_ALLOWED_BOOK_KEYS = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "williamhill_us": "Caesars",
    "caesars": "Caesars",
    "bet365": "bet365",
    "fanatics": "Fanatics",
}
_EXACT_ALIASES = {
    "appalachian state": "app state",
    "appalachian state mountaineers": "app state",
    "app state mountaineers": "app state",
    "southern california": "usc",
    "southern california trojans": "usc",
    "usc trojans": "usc",
    "connecticut": "uconn",
    "connecticut huskies": "uconn",
    "uconn huskies": "uconn",
    "central florida": "ucf",
    "central florida knights": "ucf",
    "ucf knights": "ucf",
    "southern methodist": "smu",
    "southern methodist mustangs": "smu",
    "smu mustangs": "smu",
    "brigham young": "byu",
    "brigham young cougars": "byu",
    "byu cougars": "byu",
    "texas christian": "tcu",
    "texas christian horned frogs": "tcu",
    "tcu horned frogs": "tcu",
    "north carolina state": "nc state",
    "north carolina state wolfpack": "nc state",
    "nc state wolfpack": "nc state",
    "mississippi rebels": "ole miss",
    "ole miss rebels": "ole miss",
    "miami florida": "miami",
    "miami hurricanes": "miami",
    "miami florida hurricanes": "miami",
    "miami ohio": "miami oh",
    "miami oh redhawks": "miami oh",
    "fiu": "florida international",
    "fiu panthers": "florida international",
    "florida international panthers": "florida international",
    "sam houston state": "sam houston",
    "sam houston state bearkats": "sam houston",
    "sam houston bearkats": "sam houston",
    "utrgv": "ut rio grande valley",
    "ut rio grande valley vaqueros": "ut rio grande valley",
    "hawai i": "hawaii",
    "hawai i rainbow warriors": "hawaii",
    "hawaii rainbow warriors": "hawaii",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _canonical(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value)).encode("ascii", "ignore").decode("ascii")
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bst\.?\b", "state", text) if text not in _EXACT_ALIASES and not text.endswith(" state") else text
    text = re.sub(r"\s+", " ", text).strip()
    return _EXACT_ALIASES.get(text, text)


def _american(runner: Mapping[str, Any]) -> int | None:
    win = runner.get("winRunnerOdds") if isinstance(runner.get("winRunnerOdds"), Mapping) else {}
    display = win.get("americanDisplayOdds") if isinstance(win.get("americanDisplayOdds"), Mapping) else {}
    candidates = (
        runner.get("americanOdds"),
        runner.get("american_odds"),
        display.get("americanOddsInt"),
        display.get("americanOdds"),
        win.get("americanOddsInt"),
        win.get("americanOdds"),
    )
    for raw in candidates:
        try:
            number = float(raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(number) or number == 0 or abs(number) < 100 or abs(number) > 100_000:
            continue
        return int(round(number))
    return None


def _active(runner: Mapping[str, Any]) -> bool:
    return _clean(runner.get("runnerStatus") or runner.get("status")).upper() in {"", "ACTIVE"}


def _role(runner: Mapping[str, Any]) -> str:
    side = _clean(runner.get("side")).upper()
    if side in {"AWAY", "HOME"}:
        return side
    result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
    side = _clean(result.get("type")).upper()
    return side if side in {"AWAY", "HOME"} else ""


def normalize_fanduel_moneylines(
    payload: Mapping[str, Any], *, observed_at_utc: datetime
) -> list[dict[str, Any]]:
    if observed_at_utc.tzinfo is None or observed_at_utc.utcoffset() is None:
        raise ValueError("observed_at_utc must be timezone-aware")
    attachments = payload.get("attachments")
    if not isinstance(attachments, Mapping):
        return []
    events = fanduel._rows(attachments.get("events"))
    markets = fanduel._rows(attachments.get("markets"))
    event_map = {fanduel._event_id(event): event for event in events if fanduel._event_id(event)}
    rows: list[dict[str, Any]] = []
    for market in markets:
        name = fanduel._text(market.get("marketName") or market.get("name") or market.get("displayName"))
        if name != "Moneyline":
            continue
        if fanduel._text(market.get("marketStatus") or market.get("status")).upper() != "OPEN":
            continue
        if market.get("inPlay") is True:
            continue
        event_id = fanduel._text(market.get("eventId") or market.get("eventID") or market.get("event_id"))
        event = event_map.get(event_id)
        if not event:
            continue
        event_name = fanduel._event_name(event)
        try:
            away_team, home_team = fanduel.parse_matchup(event_name)
        except Exception:
            continue
        sides: dict[str, Mapping[str, Any]] = {}
        invalid = False
        for runner in fanduel._rows(market.get("runners")):
            if not _active(runner):
                continue
            role = _role(runner)
            if role not in {"AWAY", "HOME"}:
                continue
            if role in sides:
                invalid = True
                break
            sides[role] = runner
        if invalid or set(sides) != {"AWAY", "HOME"}:
            continue
        away_price = _american(sides["AWAY"])
        home_price = _american(sides["HOME"])
        if away_price is None or home_price is None:
            continue
        market_id = fanduel._text(market.get("marketId") or market.get("id") or market.get("_attachment_key"))
        if not event_id or not market_id:
            continue
        rows.append({
            "sportsbook": "FanDuel",
            "market": "moneyline",
            "provider_event_id": event_id,
            "provider_market_id": market_id,
            "away_team": away_team,
            "home_team": home_team,
            "away_price": away_price,
            "home_price": home_price,
            "observed_at_utc": observed_at_utc.astimezone(timezone.utc).isoformat(),
            "line_status": "open",
        })
    rows.sort(key=lambda row: (row["away_team"], row["home_team"], row["provider_event_id"]))
    return rows


def collect_fanduel_moneylines(*, now_provider=lambda: datetime.now(timezone.utc)) -> list[dict[str, Any]]:
    payload = fanduel.fetch_fanduel_ncaaf_page()
    return normalize_fanduel_moneylines(payload, observed_at_utc=now_provider())


def match_moneylines_to_ncaa_games(
    games: Iterable[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        away = _canonical(row.get("away_team"))
        home = _canonical(row.get("home_team"))
        if not away or not home:
            continue
        by_pair.setdefault((away, home), []).append(row)
    out: dict[str, list[dict[str, Any]]] = {}
    for game in games:
        game_id = _clean(game.get("game_id") or game.get("identity_key"))
        if not game_id:
            continue
        key = (_canonical(game.get("away_team")), _canonical(game.get("home_team")))
        candidates = by_pair.get(key) or []
        if not candidates:
            continue
        # Multiple books are valid. Duplicate rows from the same book/event/market are not.
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


def collect_the_odds_api_moneylines(
    *, now_provider=lambda: datetime.now(timezone.utc), env: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    env = dict(os.environ if env is None else env)
    api_key = _clean(env.get("THE_ODDS_API_KEY") or env.get("ODDS_API_KEY"))
    if not api_key:
        return []
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    request = Request(
        THE_ODDS_API_URL + "?" + urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "KyreSportsAPI/CFB-Moneyline-V1"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    observed = now_provider().astimezone(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for event in payload:
        if not isinstance(event, Mapping):
            continue
        event_id = _clean(event.get("id"))
        away_team = _clean(event.get("away_team"))
        home_team = _clean(event.get("home_team"))
        if not event_id or not away_team or not home_team:
            continue
        for bookmaker in event.get("bookmakers") or []:
            if not isinstance(bookmaker, Mapping):
                continue
            book_key = _clean(bookmaker.get("key")).casefold()
            sportsbook = _ALLOWED_BOOK_KEYS.get(book_key)
            if not sportsbook or sportsbook == "FanDuel":
                continue
            for market in bookmaker.get("markets") or []:
                if not isinstance(market, Mapping) or _clean(market.get("key")).casefold() != "h2h":
                    continue
                prices: dict[str, int] = {}
                for outcome in market.get("outcomes") or []:
                    if not isinstance(outcome, Mapping):
                        continue
                    team = _canonical(outcome.get("name"))
                    try:
                        price = int(outcome.get("price"))
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if abs(price) < 100 or price == 0:
                        continue
                    if team == _canonical(away_team):
                        prices["away"] = price
                    elif team == _canonical(home_team):
                        prices["home"] = price
                if set(prices) != {"away", "home"}:
                    continue
                updated = _clean(market.get("last_update") or bookmaker.get("last_update")) or observed
                rows.append({
                    "sportsbook": sportsbook,
                    "market": "moneyline",
                    "provider_event_id": event_id,
                    "provider_market_id": _clean(market.get("key")) + ":" + book_key,
                    "away_team": away_team,
                    "home_team": home_team,
                    "away_price": prices["away"],
                    "home_price": prices["home"],
                    "observed_at_utc": updated,
                    "line_status": "open",
                })
    return rows


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "collect_fanduel_moneylines",
    "collect_the_odds_api_moneylines",
    "match_moneylines_to_ncaa_games",
    "normalize_fanduel_moneylines",
]
