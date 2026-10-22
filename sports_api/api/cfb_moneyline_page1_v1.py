"""Kyre Sports API CFB Moneyline Page 1 contract.

This route owns application delivery for the Moneyline discovery page. Schedule
identity and team evidence are official NCAA inputs, the certified frozen
Moneyline model remains price-independent, and sportsbook observations remain
book-specific context with zero model weight.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

import cfb_schedule_v3 as ncaa_schedule
import cfb_team_data_v1 as team_data
import cfb_moneyline_model_v1 as raw_model
import cfb_moneyline_final_v1 as final_model
from sports_api.collectors.cfb_fanduel_moneyline_v1 import (
    collect_fanduel_moneylines,
    collect_the_odds_api_moneylines,
    match_moneylines_to_ncaa_games,
)

router = APIRouter(prefix="/api/v1/cfb/moneyline", tags=["cfb"])
MODEL_VERSION = "CFB MONEYLINE PAGE1 API V1 • KYRE SPORTS API"
SCHEMA_VERSION = "cfb_moneyline_page1_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PHOENIX = ZoneInfo("America/Phoenix")
MAX_AUTO_SCAN_DAYS = 14


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _kickoff(game: Mapping[str, Any]) -> datetime | None:
    text = _clean(game.get("kickoff_iso"))
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _load_ncaa_games(day: str) -> list[dict[str, Any]]:
    selected = date.fromisoformat(day).isoformat()
    payload, _attempts = ncaa_schedule._fetch_ncaa_scoreboard_payload(selected)
    if not payload:
        return []
    games, _diag = ncaa_schedule._official_scoreboard_games(payload, selected)
    out = [dict(game) for game in games if game.get("identity_verified") is True and game.get("date_matches_query") is True]
    out.sort(key=lambda game: (_clean(game.get("kickoff_iso")), _clean(game.get("game_id"))))
    return out


def _resolve_slate_date(
    *, requested: str | None, now: datetime
) -> tuple[str, list[dict[str, Any]]]:
    if requested:
        selected = date.fromisoformat(requested).isoformat()
        return selected, _load_ncaa_games(selected)
    local_now = now.astimezone(PHOENIX)
    for offset in range(MAX_AUTO_SCAN_DAYS + 1):
        day = (local_now.date() + timedelta(days=offset)).isoformat()
        games = _load_ncaa_games(day)
        if not games:
            continue
        future = [game for game in games if (_kickoff(game) is None or _kickoff(game) >= now.astimezone(timezone.utc))]
        if future:
            return day, future
    return local_now.date().isoformat(), []


def collect_market_rows() -> list[dict[str, Any]]:
    try:
        return collect_fanduel_moneylines()
    except Exception:
        return []


def _secondary_market_rows() -> list[dict[str, Any]]:
    if not _clean(os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")):
        return []
    try:
        return collect_the_odds_api_moneylines()
    except Exception:
        return []


def _market_state(
    games: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    consulted: list[str] = []
    primary_rows = collect_market_rows()
    consulted.append("FanDuel")
    matched = match_moneylines_to_ncaa_games(games, primary_rows)
    missing = [
        game for game in games
        if _clean(game.get("game_id") or game.get("identity_key")) not in matched
    ]
    if missing and _clean(os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")):
        secondary_rows = _secondary_market_rows()
        consulted.append("The Odds API")
        secondary = match_moneylines_to_ncaa_games(missing, secondary_rows)
        for game_id, rows in secondary.items():
            matched.setdefault(game_id, []).extend(rows)
    return matched, consulted


def _book_mapping(quotes: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for quote in quotes:
        book = _clean(quote.get("sportsbook"))
        away = quote.get("away_price")
        home = quote.get("home_price")
        if not book or away is None or home is None:
            continue
        out[book] = {
            "away": away,
            "home": home,
            "updated_at": _clean(quote.get("observed_at_utc")) or None,
            "market": "moneyline",
            "provider_event_id": _clean(quote.get("provider_event_id")) or None,
            "provider_market_id": _clean(quote.get("provider_market_id")) or None,
        }
    return out


def _public_game(game: Mapping[str, Any], quotes: list[dict[str, Any]]) -> dict[str, Any]:
    row = dict(game)
    row["market_quotes"] = [dict(quote) for quote in quotes]
    row["sportsbook_moneylines"] = _book_mapping(quotes)
    return row


def _official_number(item: Mapping[str, Any]) -> float | None:
    for key in ("value_numeric", "value"):
        raw = item.get(key)
        try:
            number = float(raw)
        except (TypeError, ValueError, OverflowError):
            continue
        return number
    return None


def _games_from_official_stats(stats: Mapping[str, Mapping[str, Any]]) -> int:
    for item in stats.values():
        headers = [_clean(value).casefold() for value in item.get("headers") or []]
        row = list(item.get("row") or [])
        for idx, header in enumerate(headers):
            if header not in {"g", "gp", "games", "games played"} or idx >= len(row):
                continue
            try:
                games = int(float(row[idx]))
            except (TypeError, ValueError, OverflowError):
                continue
            if games > 0:
                return games
    return 0


def _repair_ncaa_stats_profile(
    side: str,
    game: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    official = dict(profile.get("official_stats") or {})
    scoring_off = official.get("scoring_offense") if isinstance(official.get("scoring_offense"), Mapping) else {}
    scoring_def = official.get("scoring_defense") if isinstance(official.get("scoring_defense"), Mapping) else {}
    ppg = _official_number(scoring_off)
    allowed = _official_number(scoring_def)
    games = _games_from_official_stats(official)
    if games <= 0 or ppg is None or allowed is None:
        return dict(profile), False

    repaired = dict(profile)
    repaired.update({
        "side": side,
        "team": _clean(game.get(f"{side}_team")) or _clean(profile.get("team")) or side.title(),
        "team_slug": _clean(game.get(f"{side}_team_slug")) or _clean(profile.get("team_slug")),
        "conference": _clean(game.get(f"{side}_conference")) or _clean(profile.get("conference")) or "Conference unavailable",
        "official_stats": official,
        "record": {"games": games},
        "record_text": f"{games} GAME SAMPLE • W-L UNAVAILABLE",
        "ppg": float(ppg),
        "points_allowed_pg": float(allowed),
        "point_diff_pg": float(ppg - allowed),
        "home_record": {},
        "away_record": {},
        "neutral_record": {},
        "recent_form": "—",
        "recent_record": {},
        "recent_ppg": None,
        "recent_points_allowed_pg": None,
        "recent_point_diff_pg": None,
        "sos_opponent_win_pct": None,
        "sos_coverage": 0.0,
        "completed_games": [],
        "data_source": "NCAA.com official team stats + NCAA official event record • stats-only repair",
    })
    repaired["data_quality"] = team_data._quality(repaired)
    return repaired, True


def _analysis(game: Mapping[str, Any], selected_day: str) -> dict[str, Any]:
    profiles, team_diag = team_data.load_matchup_team_data(game, selected_day)
    away = dict(profiles.get("away") or {})
    home = dict(profiles.get("home") or {})
    repaired_count = 0
    if _clean((away.get("data_quality") or {}).get("grade")).upper() == "CHECK":
        away, repaired = _repair_ncaa_stats_profile("away", game, away)
        repaired_count += int(repaired)
    if _clean((home.get("data_quality") or {}).get("grade")).upper() == "CHECK":
        home, repaired = _repair_ncaa_stats_profile("home", game, home)
        repaired_count += int(repaired)
    team_diag = dict(team_diag)
    team_diag["stats_only_repair_attempted"] = True
    team_diag["stats_only_profiles_repaired"] = repaired_count
    team_diag["ready_profiles"] = sum(
        1 for profile in (away, home)
        if _clean((profile.get("data_quality") or {}).get("grade")).upper() != "CHECK"
    )
    raw = dict(raw_model.project_matchup(game, away, home))
    final = dict(final_model.synthesize(game, away, home, raw))
    return {
        "game_id": _clean(game.get("game_id") or game.get("identity_key")),
        "away": away,
        "home": home,
        "raw": raw,
        "final": final,
        "team_diag": dict(team_diag),
    }


def build_page1_payload(
    *,
    game_date: str | None = None,
    game_id: str | None = None,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    now = now_provider()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        selected_day, games = _resolve_slate_date(requested=game_date, now=now)
    except ValueError as exc:
        raise ValueError("game_date must be YYYY-MM-DD") from exc

    market_map, consulted = _market_state(games)
    public_games: list[dict[str, Any]] = []
    for game in games:
        gid = _clean(game.get("game_id") or game.get("identity_key"))
        public_games.append(_public_game(game, market_map.get(gid, [])))

    selected_game: dict[str, Any] | None = None
    requested_id = _clean(game_id)
    if requested_id:
        selected_game = next((row for row in public_games if _clean(row.get("game_id") or row.get("identity_key")) == requested_id), None)
        if selected_game is None:
            raise ValueError("game_id is not in the verified selected slate")
    elif public_games:
        selected_game = public_games[0]

    analysis = _analysis(selected_game, selected_day) if selected_game else {}
    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_date": selected_day,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "games": public_games,
        "analysis": analysis,
        "routing": {
            "application_gateway": "Kyre Sports API",
            "schedule_primary": "NCAA",
            "stats_primary": "NCAA",
            "market_primary": "FanDuel",
            "market_secondary": "The Odds API",
            "provider_calls": consulted,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_INFLUENCE,
            "consensus_averaging": False,
            "forbidden_providers": [],
            "fabrication": False,
            "null_to_zero": False,
        },
    }


@router.get("/page1")
def page1(
    game_date: str | None = Query(None, min_length=10, max_length=10),
    game_id: str | None = Query(None, min_length=1, max_length=160),
) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date, game_id=game_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_page1_payload",
    "collect_market_rows",
    "page1",
    "router",
]
