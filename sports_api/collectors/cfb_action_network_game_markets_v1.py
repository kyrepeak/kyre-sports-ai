"""Action Network secondary CFB market collector for Kyre Sports API.

This module is backend-only. It is consulted only after the primary sportsbook
path leaves a verified NCAA game without a market quote. It preserves each
sportsbook quote independently and never averages lines or affects projections.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import json
import re
from typing import Any, Mapping
from urllib.request import Request, urlopen

from sports_api.collectors.cfb_fanduel_moneyline_v1 import _canonical as _base_canonical

ACTION_ODDS_URL = "https://www.actionnetwork.com/ncaaf/odds"
MODEL_VERSION = "CFB ACTION NETWORK GAME MARKETS V1 • KYRE SPORTS API SECONDARY"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_BOOK_ALIASES = {
    "fanduel nj": "FanDuel", "fanduel": "FanDuel",
    "dk nj": "DraftKings", "draftkings nj": "DraftKings", "draftkings": "DraftKings",
    "betmgm nj": "BetMGM", "betmgm": "BetMGM",
    "caesars nj": "Caesars", "caesars": "Caesars",
    "bet365 nj": "bet365", "bet365": "bet365",
    "fanatics nj": "Fanatics", "fanatics": "Fanatics",
    "betrivers nj": "BetRivers", "betrivers": "BetRivers",
}
_APPROVED_BOOKS = {"FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics", "BetRivers"}
_EXTRA_ALIASES = {
    "western mich": "western michigan",
    "western michigan broncos": "western michigan",
    "toledo rockets": "toledo",
    "central mich": "central michigan",
    "central michigan chippewas": "central michigan",
    "eastern mich": "eastern michigan",
    "eastern michigan eagles": "eastern michigan",
    "fla atlantic": "florida atlantic",
    "florida atlantic owls": "florida atlantic",
    "northern ill": "northern illinois",
    "northern illinois huskies": "northern illinois",
    "niu": "northern illinois",
    "niu huskies": "northern illinois",
    "la monroe": "louisiana monroe",
    "ul monroe": "louisiana monroe",
    "louisiana monroe": "louisiana monroe",
    "louisiana monroe warhawks": "louisiana monroe",
    "ulm": "louisiana monroe",
    "ulm warhawks": "louisiana monroe",
    "pitt": "pittsburgh",
    "pitt panthers": "pittsburgh",
    "pittsburgh panthers": "pittsburgh",
    "miami fl": "miami",
    "miami fl hurricanes": "miami",
    "miami hurricanes": "miami",
    "rutgers scarlet knights": "rutgers",
    "northwestern wildcats": "northwestern",
    "rice owls": "rice",
    "troy trojans": "troy",
    "ohio bobcats": "ohio",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _american(value: Any) -> int | None:
    number = _num(value)
    if number is None or number == 0 or abs(number) < 100 or abs(number) > 100000:
        return None
    return int(round(number))


def _canon(value: Any) -> str:
    base = _base_canonical(value)
    return _EXTRA_ALIASES.get(base, base)


def _book(value: Any) -> str:
    raw = _clean(value)
    return _BOOK_ALIASES.get(raw.casefold(), raw)


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)] if isinstance(value, list) else []


def _normal_row(rows: Any, side: str) -> Mapping[str, Any] | None:
    for row in _rows(rows):
        if _clean(row.get("side")).casefold() != side:
            continue
        if _clean(row.get("line_status") or "normal").casefold() != "normal":
            continue
        if row.get("is_live") is True:
            continue
        return row
    return None


def parse_action_network_html(text: str, *, observed_at_utc: str) -> list[dict[str, Any]]:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', text or "", re.S)
    if not match:
        return []
    try:
        data = json.loads(unescape(match.group(1)))
        page_props = data["props"]["pageProps"]
        board = page_props["scoreboardResponse"]
        books = page_props.get("allBooks") or {}
        games = board.get("games") or []
    except (KeyError, TypeError, json.JSONDecodeError):
        return []

    output: list[dict[str, Any]] = []
    for game in games:
        if not isinstance(game, Mapping):
            continue
        teams = [row for row in game.get("teams") or [] if isinstance(row, Mapping)]
        away_id, home_id = game.get("away_team_id"), game.get("home_team_id")
        away = next((row for row in teams if str(row.get("id")) == str(away_id)), None)
        home = next((row for row in teams if str(row.get("id")) == str(home_id)), None)
        if away is None or home is None:
            continue
        away_name = _clean(away.get("full_name") or away.get("display_name") or away.get("short_name"))
        home_name = _clean(home.get("full_name") or home.get("display_name") or home.get("short_name"))
        if not away_name or not home_name:
            continue
        for book_id, raw_pack in (game.get("markets") or {}).items():
            if not isinstance(raw_pack, Mapping):
                continue
            meta = books.get(str(book_id)) if isinstance(books, Mapping) else None
            meta = meta if isinstance(meta, Mapping) else {}
            sportsbook = _book(meta.get("display_name") or meta.get("parent_name") or book_id)
            if sportsbook not in _APPROVED_BOOKS:
                continue
            event_markets = raw_pack.get("event") if isinstance(raw_pack.get("event"), Mapping) else {}
            away_ml = _normal_row(event_markets.get("moneyline"), "away")
            home_ml = _normal_row(event_markets.get("moneyline"), "home")
            away_sp = _normal_row(event_markets.get("spread"), "away")
            home_sp = _normal_row(event_markets.get("spread"), "home")
            over = _normal_row(event_markets.get("total"), "over")
            under = _normal_row(event_markets.get("total"), "under")
            if any(row is None for row in (away_ml, home_ml, away_sp, home_sp, over, under)):
                continue
            assert away_ml is not None and home_ml is not None and away_sp is not None and home_sp is not None and over is not None and under is not None
            total_line = _num(over.get("value"))
            under_line = _num(under.get("value"))
            away_spread, home_spread = _num(away_sp.get("value")), _num(home_sp.get("value"))
            away_moneyline, home_moneyline = _american(away_ml.get("odds")), _american(home_ml.get("odds"))
            over_price, under_price = _american(over.get("odds")), _american(under.get("odds"))
            away_spread_price, home_spread_price = _american(away_sp.get("odds")), _american(home_sp.get("odds"))
            if None in {
                total_line, under_line, away_spread, home_spread,
                away_spread_price, home_spread_price,
                away_moneyline, home_moneyline, over_price, under_price,
            }:
                continue
            if abs(float(total_line) - float(under_line)) > 1e-6 or abs(float(away_spread) + float(home_spread)) > 1e-6:
                continue
            output.append({
                "sportsbook": sportsbook,
                "market": "game_total",
                "provider_event_id": _clean(game.get("id")),
                "provider_market_id": f"action:{book_id}:event",
                "away_team": away_name,
                "home_team": home_name,
                "away_key": _canon(away_name),
                "home_key": _canon(home_name),
                "start_time_utc": _clean(game.get("start_time")) or None,
                "total_line": total_line,
                "over_price": over_price,
                "under_price": under_price,
                "away_spread": away_spread,
                "away_spread_price": away_spread_price,
                "home_spread": home_spread,
                "home_spread_price": home_spread_price,
                "away_moneyline": away_moneyline,
                "home_moneyline": home_moneyline,
                "observed_at_utc": observed_at_utc,
                "line_status": "open",
                "source_provider": "Action Network",
            })
    return output


def collect_action_network_game_markets(*, timeout: float = 12.0) -> list[dict[str, Any]]:
    request = Request(
        ACTION_ODDS_URL,
        headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "KyreSportsAPI/CFB-GameTotal-Secondary-V1"},
    )
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    observed = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return parse_action_network_html(text, observed_at_utc=observed)


def match_action_rows_to_games(games: list[Mapping[str, Any]], rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        pair = (_canon(row.get("away_team")), _canon(row.get("home_team")))
        if all(pair):
            by_pair.setdefault(pair, []).append(row)
    out: dict[str, list[dict[str, Any]]] = {}
    for game in games:
        game_id = _clean(game.get("game_id") or game.get("identity_key"))
        pair = (_canon(game.get("away_team")), _canon(game.get("home_team")))
        candidates = by_pair.get(pair) or []
        if not game_id or not candidates:
            continue
        start = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
        accepted: list[dict[str, Any]] = []
        for row in candidates:
            other = _clean(row.get("start_time_utc"))
            if start and other:
                try:
                    left = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc)
                    right = datetime.fromisoformat(other.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    continue
                if abs((left - right).total_seconds()) > 3 * 3600:
                    continue
            accepted.append(dict(row))
        if accepted:
            accepted.sort(key=lambda row: (_clean(row.get("sportsbook")), _clean(row.get("provider_market_id"))))
            out[game_id] = accepted
    return out


__all__ = [
    "ACTION_ODDS_URL",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "collect_action_network_game_markets",
    "match_action_rows_to_games",
    "parse_action_network_html",
]
