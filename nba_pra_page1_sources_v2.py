"""NBA PRA Page 1 V2 source routing and upcoming-only eligibility."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

PHOENIX_TZ = ZoneInfo("America/Phoenix")
SOURCE_POLICY = {
    "player_props": {"primary": ("FanDuel", "DraftKings", "BetMGM", "Caesars", "ESPN BET", "bet365"), "transport": ("SportsGameOdds", "Odds-API.io"), "secondary_limit": 2},
    "official_player_stats": {"primary": ("NBA Stats",), "secondary": ("Sportradar", "SportsDataIO"), "backup": ("ESPN", "CBS Sports")},
    "game_history": {"primary": ("NBA Stats", "Basketball-Reference", "Stathead"), "backup": ("ESPN",)},
    "game_state": {"primary": ("NBA Official",), "secondary": ("Sportradar", "SportsDataIO"), "backup": ("ESPN NBA", "CBS Sports")},
    "injuries": {"primary": ("NBA Official Injury Report",), "secondary": ("RotoWire",)},
}
APPROVED_PRA_BOOKS = ("FanDuel", "DraftKings", "BetMGM", "Caesars", "ESPN BET", "bet365")
SPORTSBOOK_PRIORITY = APPROVED_PRA_BOOKS
_BLOCKED_STATUS_TOKENS = ("live", "in progress", "halftime", "quarter", "qtr", "final", "completed", "canceled", "cancelled", "postponed", "suspended", "delayed")
_SCHEDULED_STATUS_TOKENS = ("upcoming", "scheduled", "pregame", "pre-game", "not started")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _parse_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _game_tip_utc(game: Mapping[str, Any]) -> datetime | None:
    for key in ("tip_utc", "start_time_utc", "game_time_utc", "tipoff_utc", "game_time"):
        parsed = _parse_utc(game.get(key))
        if parsed is not None:
            return parsed
    return None


def _phoenix_day(game: Mapping[str, Any]) -> str:
    for key in ("game_date_phoenix", "phoenix_date", "game_date"):
        text = _text(game.get(key))[:10]
        if len(text) == 10:
            return text
    tip = _game_tip_utc(game)
    return tip.astimezone(PHOENIX_TZ).date().isoformat() if tip else ""


def is_upcoming_game(game: Mapping[str, Any], now_utc: datetime) -> bool:
    now = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    status_text = _text(game.get("gameStatusText") or game.get("status") or game.get("state"))
    normalized = status_text.casefold()
    if any(token in normalized for token in _BLOCKED_STATUS_TOKENS):
        return False
    raw_code = game.get("gameStatus")
    try:
        code = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        code = None
    if code in {2, 3}:
        return False
    explicitly_scheduled = code == 1 or any(token in normalized for token in _SCHEDULED_STATUS_TOKENS)
    if not explicitly_scheduled:
        return False
    tip = _game_tip_utc(game)
    if tip is not None:
        return tip > now
    day = _phoenix_day(game)
    if not day:
        return False
    return day > now.astimezone(PHOENIX_TZ).date().isoformat()


def select_next_upcoming_slate(games: Sequence[Mapping[str, Any]], now_utc: datetime) -> tuple[str | None, list[dict[str, Any]]]:
    eligible: dict[str, list[dict[str, Any]]] = {}
    for raw in games:
        if not is_upcoming_game(raw, now_utc):
            continue
        game = dict(raw)
        day = _phoenix_day(game)
        if day:
            eligible.setdefault(day, []).append(game)
    if not eligible:
        return None, []
    day = min(eligible)
    return day, sorted(eligible[day], key=lambda g: (_game_tip_utc(g) or datetime.max.replace(tzinfo=timezone.utc), _text(g.get("away_tricode"))))


def _canonical_book(value: Any) -> str | None:
    return {"fanduel": "FanDuel", "draftkings": "DraftKings", "betmgm": "BetMGM", "caesars": "Caesars", "espnbet": "ESPN BET", "bet365": "bet365"}.get(_norm(value))


def build_sportsbook_board(*payloads: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    players: dict[str, dict[str, Any]] = {}
    grouped: dict[tuple[str, str, float], dict[str, Any]] = {}
    for payload in payloads:
        for raw in payload.get("observations", []) or []:
            if not isinstance(raw, Mapping):
                continue
            name, book, line, side = _text(raw.get("player_name")), _canonical_book(raw.get("sportsbook")), _num(raw.get("line")), _text(raw.get("side")).casefold()
            if not name or book not in APPROVED_PRA_BOOKS or line is None or side not in {"over", "under"}:
                continue
            key = _norm(name)
            players.setdefault(key, {"player_name": name, "quotes": []})
            quote = grouped.setdefault((key, book, float(line)), {"sportsbook": book, "line": float(line), "over_price": None, "under_price": None, "provider": _text(raw.get("provider")), "observed_at_utc": _text(raw.get("observed_at_utc")), "_side_times": {}})
            stamp = _text(raw.get("observed_at_utc"))
            if stamp >= quote["_side_times"].get(side, ""):
                quote[f"{side}_price"] = raw.get("price")
                quote["_side_times"][side] = stamp
            if stamp >= quote.get("observed_at_utc", ""):
                quote["observed_at_utc"] = stamp
                quote["provider"] = _text(raw.get("provider")) or quote["provider"]
    per_book: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (key, book, _), quote in grouped.items():
        per_book.setdefault((key, book), []).append({k: v for k, v in quote.items() if not k.startswith("_")})
    for key, entry in players.items():
        quotes = []
        for book in SPORTSBOOK_PRIORITY:
            options = per_book.get((key, book), [])
            if options:
                quotes.append(max(options, key=lambda q: (q.get("observed_at_utc") or "", q.get("line") or 0.0)))
        entry["quotes"] = quotes
    return {key: value for key, value in players.items() if value["quotes"]}


def select_featured_quote(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    by_book = {q.get("sportsbook"): q for q in entry.get("quotes", []) or [] if isinstance(q, Mapping)}
    for book in SPORTSBOOK_PRIORITY:
        if book in by_book:
            return dict(by_book[book])
    return None


def normalize_nba_stats_league_gamelog(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, Mapping):
        sets = [sets]
    if not isinstance(sets, list) or not sets:
        return {}
    block = sets[0] if isinstance(sets[0], Mapping) else {}
    headers, rows = [str(x) for x in block.get("headers", [])], block.get("rowSet") or []
    idx = {name: i for i, name in enumerate(headers)}
    if any(name not in idx for name in ("PLAYER_ID", "PLAYER_NAME", "PTS", "REB", "AST")):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, (list, tuple)):
            continue
        def value(name: str):
            pos = idx.get(name)
            return raw[pos] if pos is not None and pos < len(raw) else None
        name = _text(value("PLAYER_NAME"))
        if not name:
            continue
        profile = out.setdefault(_norm(name), {"player_name": name, "team": _text(value("TEAM_ABBREVIATION")), "player_id": _text(value("PLAYER_ID")), "games": [], "stats_source": "NBA Stats"})
        profile["games"].append({"game_date": _text(value("GAME_DATE")), "minutes": _num(value("MIN")), "points": _num(value("PTS")), "rebounds": _num(value("REB")), "assists": _num(value("AST"))})
    return out


def route_player_profiles(player_names: Sequence[str], slate_date: Any, *, official_loader, backup_loader) -> dict[str, dict[str, Any]]:
    official = official_loader(slate_date) or {}
    result, missing = {}, []
    for name in [x for x in player_names if _text(x)]:
        key = _norm(name)
        if key in official:
            result[key] = dict(official[key])
        else:
            missing.append(name)
    if missing:
        backup = backup_loader(missing, slate_date) or {}
        for name in missing:
            key = _norm(name)
            if key in backup:
                result[key] = dict(backup[key])
    return result

NBA_STATS_LEAGUE_GAMELOG_URL = "https://stats.nba.com/stats/leaguegamelog"
NBA_STATS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "Accept": "application/json, text/plain, */*"}
ODDS_API_APPROVED_BOOKMAKERS = "FanDuel,DraftKings,BetMGM,Caesars,ESPN BET,Bet365"


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _load_nba_stats_season(end_year: int, *, request_get=None, timeout: float = 8.0) -> dict[str, dict[str, Any]]:
    if request_get is None:
        import requests
        request_get = requests.get
    response = request_get(NBA_STATS_LEAGUE_GAMELOG_URL, params={"Counter": 0, "DateFrom": "", "DateTo": "", "Direction": "DESC", "LeagueID": "00", "PlayerOrTeam": "P", "Season": _season_label(end_year), "SeasonType": "Regular Season", "Sorter": "DATE"}, headers=NBA_STATS_HEADERS, timeout=timeout)
    response.raise_for_status()
    return normalize_nba_stats_league_gamelog(response.json())


def load_nba_stats_profiles(slate_date, *, request_get=None, timeout: float = 8.0) -> dict[str, dict[str, Any]]:
    from nba_pra_page1_common_v1 import nba_season_end_year
    end_year = nba_season_end_year(slate_date)
    try:
        current = _load_nba_stats_season(end_year, request_get=request_get, timeout=timeout)
    except Exception:
        return {}
    try:
        prior = _load_nba_stats_season(end_year - 1, request_get=request_get, timeout=timeout)
    except Exception:
        prior = {}
    out = {}
    for key in sorted(set(current) | set(prior)):
        source = current.get(key) or prior.get(key) or {}
        player_id = _text(source.get("player_id"))
        out[key] = {"player_name": _text(source.get("player_name")), "team": _text(source.get("team")), "position": "", "player_id": player_id, "headshot": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else "", "current_games": list((current.get(key) or {}).get("games") or []), "prior_games": list((prior.get(key) or {}).get("games") or []), "stats_source": "NBA Stats"}
    return out


def _event_date_text(event: Mapping[str, Any]) -> str:
    for key in ("startTime", "commence_time", "commenceTime", "date", "start_date"):
        value = _text(event.get(key))
        if len(value) >= 10:
            parsed = _parse_utc(value)
            return parsed.astimezone(PHOENIX_TZ).date().isoformat() if parsed else value[:10]
    return ""


def load_approved_odds_api_pra_observations(slate_date, *, request_get=None, secret_getter=None, timeout: float = 6.0) -> dict[str, Any]:
    from nba_pra_page1_common_v1 import _default_get, _default_secret
    from nba_pra_page1_odds_v1 import ODDS_API_BASE, normalize_odds_api_pra
    from nba_pra_page1_sgo_v1 import _list_payload
    request_get, secret_getter = request_get or _default_get, secret_getter or _default_secret
    base = {"source": "Odds-API.io", "observations": [], "fabrication": False, "sportsbook_projection_influence": 0.0}
    key = _text(secret_getter("ODDS_API_IO_KEY") or secret_getter("ODDS_API_KEY"))
    if not key:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "ODDS_API_IO_CREDENTIAL_UNAVAILABLE"}
    try:
        response = request_get(f"{ODDS_API_BASE}/events", params={"apiKey": key, "sport": "nba", "status": "pending", "limit": 100}, timeout=timeout)
        response.raise_for_status()
        events = [x for x in _list_payload(response.json()) if isinstance(x, Mapping) and x.get("id")]
        target = slate_date.isoformat()
        dated = [x for x in events if _event_date_text(x) == target]
        selected = dated if dated else [x for x in events if not _event_date_text(x)]
        rows = []
        for event in selected:
            odds = request_get(f"{ODDS_API_BASE}/odds", params={"apiKey": key, "eventId": _text(event.get("id")), "bookmakers": ODDS_API_APPROVED_BOOKMAKERS, "markets": "Player Props"}, timeout=timeout)
            odds.raise_for_status()
            rows.extend(normalize_odds_api_pra(odds.json()))
    except Exception as exc:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": f"ODDS_API_IO_ERROR:{type(exc).__name__}"}
    approved = [r for r in rows if _canonical_book(r.get("sportsbook")) in APPROVED_PRA_BOOKS]
    return {**base, "verification": "VERIFIED" if approved else "UNAVAILABLE", "diagnostic_state": "OK" if approved else "ODDS_API_IO_NO_PRA", "observations": approved}
