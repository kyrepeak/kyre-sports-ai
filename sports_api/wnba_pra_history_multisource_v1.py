"""WNBA PRA history V1 — bounded multi-source per-game completeness.

Player Intelligence previously depended on one per-game history provider even
when the official WNBA player profile published the same completed-game stats.
This module keeps ESPN as one verified provider and independently reads the
official WNBA profile in parallel.  Official WNBA values backfill only missing
MIN/PTS/REB/AST fields on the same date/opponent; an already-present provider
value is never overwritten.

This is read-only display/history transport.  It does not run or alter model,
projection, probability, market, qualification, ranking, sportsbook, or wager
logic.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from typing import Any, Mapping

import requests

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_pra_speed_v3_step3_espn_history import (
    get_step3_espn_player_game_log_dataset,
)


WNBA_PROFILE_BASE = "https://www.wnba.com/player"
OFFICIAL_SOURCE = "WNBA.com Player Profile"
OFFICIAL_SOURCE_URL = "https://www.wnba.com/"
REQUEST_TIMEOUT_SECONDS = 3.5
BACKFILL_FIELDS = ("minutes", "points", "rebounds", "assists")

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Safari/604.1"
    ),
}


class WNBAMultiSourceHistoryError(RuntimeError):
    """Raised only when every credible history provider is unavailable."""


class _HTMLTables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        name = tag.casefold()
        if name == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._rows = []
        elif self._table_depth == 1 and name == "tr":
            self._row = []
        elif self._table_depth == 1 and name in {"th", "td"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            text = str(data or "").strip()
            if text:
                self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if self._table_depth == 1 and name in {"th", "td"} and self._cell_parts is not None:
            value = " ".join(" ".join(self._cell_parts).split())
            if self._row is not None:
                self._row.append(value)
            self._cell_parts = None
        elif self._table_depth == 1 and name == "tr" and self._row is not None:
            if any(cell.strip() for cell in self._row):
                assert self._rows is not None
                self._rows.append(self._row)
            self._row = None
            self._cell_parts = None
        elif name == "table" and self._table_depth > 0:
            if self._table_depth == 1 and self._rows is not None:
                self.tables.append(self._rows)
                self._rows = None
            self._table_depth -= 1


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _number(value: Any) -> float | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    try:
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _date(value: Any) -> str | None:
    text = _clean(value)
    for fmt in ("%m.%d.%Y", "%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _header(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _clean(value).upper())


def _team_by_abbreviation(abbreviation: str | None, season: int) -> dict[str, Any] | None:
    wanted = _clean(abbreviation).upper()
    if not wanted:
        return None
    for team in get_wnba_teams(int(season)):
        if _clean(team.get("abbreviation")).upper() == wanted:
            return dict(team)
    return None


def _parse_matchup(value: Any, season: int) -> dict[str, Any]:
    text = _clean(value)
    match = re.fullmatch(r"([A-Za-z0-9]{2,5})\s+(vs\.?|@)\s+([A-Za-z0-9]{2,5})", text)
    if not match:
        return {
            "raw": text or None,
            "location": "unknown",
            "team_abbreviation": None,
            "team_key": None,
            "opponent_abbreviation": None,
            "opponent_team_key": None,
        }
    team_abbr, marker, opponent_abbr = match.groups()
    team = _team_by_abbreviation(team_abbr, season)
    opponent = _team_by_abbreviation(opponent_abbr, season)
    return {
        "raw": text,
        "location": "away" if marker == "@" else "home",
        "team_abbreviation": team_abbr.upper(),
        "team_key": None if team is None else team.get("team_key"),
        "opponent_abbreviation": opponent_abbr.upper(),
        "opponent_team_key": None if opponent is None else opponent.get("team_key"),
    }


def _find_recent_stats_table(html: str) -> tuple[list[str], list[list[str]]]:
    parser = _HTMLTables()
    parser.feed(str(html or ""))
    required = {"DATE", "MATCHUP", "MIN", "PTS", "REB", "AST"}
    for table in parser.tables:
        if not table:
            continue
        for header_index, row in enumerate(table[:3]):
            normalized = [_header(cell) for cell in row]
            if required.issubset(set(normalized)):
                return normalized, table[header_index + 1 :]
    return [], []


def normalize_official_wnba_profile_html(
    html: str,
    *,
    player_id: int,
    season: int,
) -> dict[str, Any]:
    """Normalize only a verified WNBA Recent Game Stats table."""
    headers, rows = _find_recent_stats_table(html)
    if not headers:
        raise WNBAMultiSourceHistoryError("OFFICIAL_WNBA_RECENT_GAME_TABLE_MISSING")
    index = {name: position for position, name in enumerate(headers)}
    games: list[dict[str, Any]] = []
    for raw in rows:
        if len(raw) < len(headers):
            continue
        game_date = _date(raw[index["DATE"]])
        if game_date is None or not game_date.startswith(f"{int(season):04d}-"):
            continue
        matchup = _parse_matchup(raw[index["MATCHUP"]], int(season))
        points = _integer(raw[index["PTS"]])
        rebounds = _integer(raw[index["REB"]])
        assists = _integer(raw[index["AST"]])
        minutes = _number(raw[index["MIN"]])
        if all(value is None for value in (points, rebounds, assists, minutes)):
            continue
        result_value = raw[index["RESULT"]] if "RESULT" in index else ""
        games.append(
            {
                "season_id": f"2{int(season)}",
                "player_id": int(player_id),
                "game_id": None,
                "game_id_valid": False,
                "game_date_raw": raw[index["DATE"]],
                "game_date": game_date,
                "matchup": matchup,
                "result": _clean(result_value) or None,
                "minutes": minutes,
                "points": points,
                "rebounds": rebounds,
                "assists": assists,
                "verified_provider": OFFICIAL_SOURCE,
            }
        )
    games.sort(key=lambda game: str(game.get("game_date") or ""), reverse=True)
    if not games:
        raise WNBAMultiSourceHistoryError("OFFICIAL_WNBA_RECENT_GAME_ROWS_MISSING")
    return {
        "source": OFFICIAL_SOURCE,
        "source_url": f"{WNBA_PROFILE_BASE}/{int(player_id)}/profile",
        "source_endpoint": "official_player_profile_recent_game_stats",
        "data_type": "official_player_game_log",
        "season": int(season),
        "season_type": "Regular Season",
        "player_id": int(player_id),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_count": len(games),
        "games": games,
        "verification": {
            "official_wnba_profile": True,
            "recent_game_table_verified": True,
            "stats_are_observed_not_projected": True,
        },
    }


def get_official_wnba_profile_history(player_id: int, season: int) -> dict[str, Any]:
    pid = int(player_id)
    year = int(season)
    if pid <= 0:
        raise ValueError("WNBA player_id must be positive.")
    url = f"{WNBA_PROFILE_BASE}/{pid}/profile"
    try:
        response = requests.get(
            url,
            headers=HTTP_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WNBAMultiSourceHistoryError(
            f"OFFICIAL_WNBA_PROFILE_READ_FAILED:{type(exc).__name__}"
        ) from exc
    return normalize_official_wnba_profile_html(
        response.text,
        player_id=pid,
        season=year,
    )


def _match_key(game: Mapping[str, Any]) -> tuple[str, str]:
    matchup = game.get("matchup") if isinstance(game.get("matchup"), Mapping) else {}
    return (
        _clean(game.get("game_date")),
        _clean(matchup.get("opponent_team_key")).casefold(),
    )


def merge_verified_histories(
    primary: Mapping[str, Any],
    official: Mapping[str, Any],
) -> dict[str, Any]:
    """Backfill missing row fields only when date+opponent identity matches."""
    result = deepcopy(dict(primary))
    primary_games = result.get("games") if isinstance(result.get("games"), list) else []
    official_games = official.get("games") if isinstance(official.get("games"), list) else []
    official_by_key = {
        _match_key(game): game
        for game in official_games
        if isinstance(game, Mapping) and all(_match_key(game))
    }
    backfilled = 0
    matched_games = 0
    for game in primary_games:
        if not isinstance(game, dict):
            continue
        verified = official_by_key.get(_match_key(game))
        if not isinstance(verified, Mapping):
            continue
        matched_games += 1
        for field in BACKFILL_FIELDS:
            if game.get(field) is None and verified.get(field) is not None:
                game[field] = verified.get(field)
                backfilled += 1
        if backfilled:
            game.setdefault("history_backfill_source", OFFICIAL_SOURCE)

    verification = result.get("verification")
    verification = dict(verification) if isinstance(verification, Mapping) else {}
    verification.update(
        {
            "provider_policy": "multi_source",
            "official_wnba_profile_available": True,
            "official_wnba_profile_rows": len(official_games),
            "official_wnba_matched_games": matched_games,
            "official_wnba_backfill_fields": backfilled,
            "existing_primary_values_overwritten": False,
            "match_contract": "exact_game_date_and_opponent_team_key",
        }
    )
    result["verification"] = verification
    result["game_count"] = len(primary_games)
    result["history_sources"] = [
        _clean(primary.get("source")) or "primary_history_provider",
        OFFICIAL_SOURCE,
    ]
    if backfilled:
        result["source"] = f'{_clean(primary.get("source")) or "Primary"} + {OFFICIAL_SOURCE}'
    return result


def _provider_result(future) -> tuple[dict[str, Any] | None, str]:
    try:
        value = future.result()
    except Exception as exc:
        return None, type(exc).__name__
    return (dict(value), "") if isinstance(value, Mapping) else (None, "InvalidPayload")


def _mark_single_provider(
    payload: Mapping[str, Any],
    *,
    espn_error: str,
    official_error: str,
) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    verification = result.get("verification")
    verification = dict(verification) if isinstance(verification, Mapping) else {}
    verification.update(
        {
            "provider_policy": "multi_source",
            "espn_provider_error": espn_error,
            "official_wnba_provider_error": official_error,
            "credible_provider_count_available": 1,
        }
    )
    result["verification"] = verification
    return result


def get_multisource_player_game_log_dataset(
    player_id: int,
    season: int,
) -> dict[str, Any]:
    """Read ESPN + official WNBA concurrently and preserve whichever truth exists."""
    pid = int(player_id)
    year = int(season)
    if pid <= 0:
        raise ValueError("WNBA player_id must be positive.")
    if year < 1997 or year > 2100:
        raise ValueError("WNBA season is outside the supported range.")

    with ThreadPoolExecutor(max_workers=2) as pool:
        espn_future = pool.submit(get_step3_espn_player_game_log_dataset, pid, year)
        official_future = pool.submit(get_official_wnba_profile_history, pid, year)
        espn, espn_error = _provider_result(espn_future)
        official, official_error = _provider_result(official_future)

    if espn is not None and official is not None:
        merged = merge_verified_histories(espn, official)
        verification = dict(merged.get("verification") or {})
        verification.update(
            {
                "espn_provider_error": "",
                "official_wnba_provider_error": "",
                "credible_provider_count_available": 2,
            }
        )
        merged["verification"] = verification
        return merged
    if espn is not None:
        return _mark_single_provider(
            espn,
            espn_error="",
            official_error=official_error,
        )
    if official is not None:
        return _mark_single_provider(
            official,
            espn_error=espn_error,
            official_error="",
        )
    raise WNBAMultiSourceHistoryError(
        f"WNBA_HISTORY_PROVIDERS_UNAVAILABLE:espn={espn_error or 'unknown'}:official={official_error or 'unknown'}"
    )


__all__ = [
    "BACKFILL_FIELDS",
    "OFFICIAL_SOURCE",
    "REQUEST_TIMEOUT_SECONDS",
    "WNBAMultiSourceHistoryError",
    "get_multisource_player_game_log_dataset",
    "get_official_wnba_profile_history",
    "merge_verified_histories",
    "normalize_official_wnba_profile_html",
]
