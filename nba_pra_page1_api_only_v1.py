"""NBA PRA Page 1 with Kyre Sports API as the sole application data gateway."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from nba_pra_injury_api_v1 import load_kyre_sports_api_nba_injuries
from nba_pra_market_api_v1 import load_kyre_sports_api_pra_observations
from nba_pra_player_context_api_v1 import load_kyre_sports_api_player_context
from nba_pra_schedule_api_v1 import load_kyre_sports_api_nba_schedule

PHOENIX_TZ = ZoneInfo("America/Phoenix")
APPROVED_BOOKS = ("FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics Sportsbook")


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def _num(value: Any) -> float | None:
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


def _game_tip(game: Mapping[str, Any]) -> datetime | None:
    for key in ("tip_utc", "start_time_utc", "game_time_utc", "tipoff_utc", "game_time"):
        parsed = _parse_utc(game.get(key))
        if parsed is not None:
            return parsed
    return None


def _game_day(game: Mapping[str, Any]) -> str:
    for key in ("game_date_phoenix", "phoenix_date", "game_date"):
        text = _text(game.get(key))[:10]
        if len(text) == 10:
            return text
    tip = _game_tip(game)
    return tip.astimezone(PHOENIX_TZ).date().isoformat() if tip else ""


def _is_upcoming(game: Mapping[str, Any], now_utc: datetime) -> bool:
    status = _text(game.get("gameStatusText") or game.get("status") or game.get("state")).casefold()
    if any(token in status for token in ("live", "in progress", "halftime", "quarter", "final", "completed", "cancel", "postpon", "suspend", "delay")):
        return False
    try:
        code = int(game.get("gameStatus")) if game.get("gameStatus") is not None else None
    except (TypeError, ValueError):
        code = None
    if code in {2, 3}:
        return False
    scheduled = code == 1 or any(token in status for token in ("upcoming", "scheduled", "pregame", "pre-game", "not started"))
    if not scheduled:
        return False
    tip = _game_tip(game)
    if tip is not None:
        return tip > now_utc.astimezone(timezone.utc)
    day = _game_day(game)
    return bool(day and day >= now_utc.astimezone(PHOENIX_TZ).date().isoformat())


def _select_next_upcoming_slate(games: Sequence[Mapping[str, Any]], now_utc: datetime) -> tuple[str | None, list[dict[str, Any]]]:
    eligible: dict[str, list[dict[str, Any]]] = {}
    for raw in games:
        if not isinstance(raw, Mapping) or not _is_upcoming(raw, now_utc):
            continue
        day = _game_day(raw)
        if day:
            eligible.setdefault(day, []).append(dict(raw))
    if not eligible:
        return None, []
    day = min(eligible)
    rows = sorted(eligible[day], key=lambda game: (_game_tip(game) or datetime.max.replace(tzinfo=timezone.utc), _text(game.get("away_tricode"))))
    return day, rows


def _team_matches(value: Any, game: Mapping[str, Any], side: str) -> bool:
    raw = _norm(value)
    if not raw:
        return False
    candidates = {
        _norm(game.get(f"{side}_tricode")),
        _norm(game.get(f"{side}_name")),
        _norm(game.get(f"{side}_team")),
    }
    candidates.discard("")
    return raw in candidates or any(len(raw) > 3 and (raw in item or item in raw) for item in candidates)


def _filter_payload_to_games(payload: Mapping[str, Any], games: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out = dict(payload or {})
    filtered = []
    for row in out.get("observations") or []:
        if not isinstance(row, Mapping):
            continue
        if any(_team_matches(row.get("away_team"), game, "away") and _team_matches(row.get("home_team"), game, "home") for game in games):
            filtered.append(dict(row))
    out["observations"] = filtered
    out["upcoming_match_observation_count"] = len(filtered)
    return out


def _canonical_book(value: Any) -> str | None:
    key = _norm(value)
    return {
        "fanduel": "FanDuel",
        "draftkings": "DraftKings",
        "betmgm": "BetMGM",
        "caesars": "Caesars",
        "bet365": "bet365",
        "fanaticssportsbook": "Fanatics Sportsbook",
        "fanatics": "Fanatics Sportsbook",
    }.get(key)


def _build_board(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    players: dict[str, dict[str, Any]] = {}
    grouped: dict[tuple[str, str, float], dict[str, Any]] = {}
    for raw in payload.get("observations") or []:
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("player_name"))
        book = _canonical_book(raw.get("sportsbook"))
        line = _num(raw.get("line"))
        side = _text(raw.get("side")).casefold()
        if not name or book not in APPROVED_BOOKS or line is None or side not in {"over", "under"}:
            continue
        key = _norm(name)
        players.setdefault(key, {"player_name": name, "quotes": []})
        quote = grouped.setdefault(
            (key, book, float(line)),
            {"sportsbook": book, "line": float(line), "over_price": None, "under_price": None, "provider": _text(raw.get("provider")), "observed_at_utc": "", "_times": {}},
        )
        stamp = _text(raw.get("observed_at_utc"))
        if stamp >= quote["_times"].get(side, ""):
            quote[f"{side}_price"] = raw.get("price")
            quote["_times"][side] = stamp
        if stamp >= quote.get("observed_at_utc", ""):
            quote["observed_at_utc"] = stamp
            quote["provider"] = _text(raw.get("provider")) or quote["provider"]
    per_book: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (key, book, _line), quote in grouped.items():
        clean = {k: v for k, v in quote.items() if not k.startswith("_")}
        per_book.setdefault((key, book), []).append(clean)
    result: dict[str, dict[str, Any]] = {}
    for key, entry in players.items():
        quotes: list[dict[str, Any]] = []
        for book in APPROVED_BOOKS:
            options = per_book.get((key, book), [])
            if options:
                quotes.append(max(options, key=lambda quote: (quote.get("observed_at_utc") or "", quote.get("line") or 0.0)))
        if not quotes:
            continue
        entry["quotes"] = quotes
        entry["featured_quote"] = dict(quotes[0])
        result[key] = entry
    return result


def _market_names(payload: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in payload.get("observations") or []:
        if not isinstance(row, Mapping):
            continue
        name = _text(row.get("player_name"))
        key = _norm(name)
        if name and key and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def _empty(schedule: Mapping[str, Any], slate_date: str | None, games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "verification": str(schedule.get("verification") or "UNAVAILABLE"),
        "slate_date": slate_date,
        "games": games,
        "market": {},
        "profiles": {},
        "injury_players": {},
        "sources": {"schedule": dict(schedule)},
        "sportsbook_projection_influence": 0.0,
    }


def load_page1_snapshot_v2(
    *,
    now=None,
    schedule_loader=None,
    api_loader=None,
    player_context_loader=None,
    injury_loader=None,
    **_compat,
):
    """Build the upcoming NBA PRA slate using only Kyre Sports API clients."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_utc = now_utc.astimezone(timezone.utc)

    schedule_impl = schedule_loader or load_kyre_sports_api_nba_schedule
    market_impl = api_loader or load_kyre_sports_api_pra_observations
    context_impl = player_context_loader or load_kyre_sports_api_player_context
    injury_impl = injury_loader or load_kyre_sports_api_nba_injuries

    schedule = dict(schedule_impl(now_utc=now_utc) or {})
    slate_text, games = _select_next_upcoming_slate(list(schedule.get("games") or []), now_utc)
    if not slate_text or not games:
        return _empty(schedule, slate_text, games)

    slate_date = date.fromisoformat(slate_text)
    market_payload = _filter_payload_to_games(dict(market_impl(slate_date) or {}), games)
    board = _build_board(market_payload)
    if not board:
        result = _empty(schedule, slate_text, games)
        result["sources"].update({"kyre_sports_api": market_payload})
        return result

    names = _market_names(market_payload)
    team_codes = sorted({
        _text(code).upper()
        for game in games
        for code in (game.get("away_tricode"), game.get("home_tricode"))
        if _text(code)
    })
    if player_context_loader is None:
        context = dict(context_impl(slate_date, names, team_codes=team_codes) or {})
    else:
        context = dict(context_impl(slate_date, names) or {})
    profiles = {str(k): dict(v) for k, v in (context.get("profiles") or {}).items() if isinstance(v, Mapping)}
    try:
        injuries = dict(injury_impl(games, now_utc=now_utc) or {})
    except Exception as exc:
        injuries = {"source":"Kyre Sports API — Vercel","verification":"UNAVAILABLE","diagnostic_state":f"INJURY_GATEWAY_ERROR:{type(exc).__name__}","players":{},"fabrication":False}
    injury_players = {str(k): dict(v) for k, v in (injuries.get("players") or {}).items() if isinstance(v, Mapping)}

    return {
        "verification": str(schedule.get("verification") or "UNAVAILABLE"),
        "slate_date": slate_text,
        "games": games,
        "market": board,
        "profiles": profiles,
        "injury_players": injury_players,
        "sources": {
            "schedule": schedule,
            "kyre_sports_api": market_payload,
            "kyre_player_context": {
                "source": str(context.get("source") or "Kyre Sports API — Vercel"),
                "verification": str(context.get("verification") or "DATA_UNAVAILABLE"),
                "diagnostic_state": str(context.get("diagnostic_state") or "DATA_UNAVAILABLE"),
                "provider_health": dict(context.get("provider_health") or {}),
                "requested_players": int(context.get("requested_players") or 0),
                "verified_players": int(context.get("verified_players") or 0),
                "fabrication": False,
            },
            "injuries": injuries,
        },
        "sportsbook_projection_influence": 0.0,
    }
