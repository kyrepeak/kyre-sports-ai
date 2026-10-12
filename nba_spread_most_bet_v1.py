"""NBA Spread Step 4 — fail-closed Most Bet Game feature layer.

This module does one thing: identify the unique highest tracked-bet NBA spread
matchup from Action Network and reconcile it to the already-verified Step-3
Phoenix schedule. It does not infer sharp money, injuries, projections,
probability, edge, picks, or rankings.
"""
from __future__ import annotations

from io import StringIO
import re
from typing import Iterable, Mapping, Sequence

import pandas as pd
import requests

MODEL_VERSION = "NBA_SPREAD_STEP4_MOST_BET_FEATURE_V1"
SOURCE_NAME = "Action Network"
SOURCE_URL = "https://www.actionnetwork.com/nba/public-betting"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_SHARP_MONEY = False
MAY_ACTIVATE_INJURIES = False
MAY_ACTIVATE_RANKING = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}

_TEAM_NAMES = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}
_NAME_TO_CODE = {
    re.sub(r"[^a-z0-9]+", " ", name.lower()).strip(): code
    for code, name in _TEAM_NAMES.items()
}
_NAME_TO_CODE.update(
    {
        "76ers": "PHI",
        "sixers": "PHI",
        "clippers": "LAC",
        "lakers": "LAL",
        "knicks": "NYK",
        "nets": "BKN",
        "pelicans": "NOP",
        "suns": "PHX",
        "spurs": "SAS",
        "timberwolves": "MIN",
        "trail blazers": "POR",
        "warriors": "GSW",
        "wizards": "WAS",
    }
)


def _clean(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _team_code(value: object) -> str | None:
    raw = str(value or "").strip().upper()
    if raw in _TEAM_NAMES:
        return raw
    clean = _clean(value)
    if clean in _NAME_TO_CODE:
        return _NAME_TO_CODE[clean]
    for name, code in _NAME_TO_CODE.items():
        if clean and (clean == name or clean.endswith(" " + name) or name.endswith(" " + clean)):
            return code
    return None


def _split_pair(value: object) -> tuple[int, int] | None:
    found = [int(item) for item in re.findall(r"(\d{1,3})\s*%", str(value or ""))]
    if len(found) < 2:
        return None
    pair = (found[0], found[1])
    if min(pair) < 0 or max(pair) > 100 or sum(pair) != 100:
        return None
    return pair


def _bet_count(value: object) -> int | None:
    text = re.sub(r"[^0-9]", "", str(value or ""))
    if not text:
        return None
    count = int(text)
    return count if count > 0 else None


def _flat_columns(frame: pd.DataFrame) -> dict[str, object]:
    out: dict[str, object] = {}
    for column in frame.columns:
        if isinstance(column, tuple):
            label = " ".join(str(part) for part in column if str(part).lower() != "nan")
        else:
            label = str(column)
        out[_clean(label)] = column
    return out


def parse_action_network_html(html: str) -> list[dict]:
    """Parse Action Network's public NBA spread table into neutral rows.

    The parser intentionally requires the documented public-table columns and
    returns no rows when the page shape is incomplete. It never invents splits.
    """
    if not str(html or "").strip():
        return []
    try:
        tables = pd.read_html(StringIO(html))
    except (ValueError, ImportError):
        return []

    parsed: list[dict] = []
    for frame in tables:
        columns = _flat_columns(frame)
        scheduled_col = next((raw for key, raw in columns.items() if key == "scheduled"), None)
        bets_pct_col = next((raw for key, raw in columns.items() if "% of bets" in key), None)
        money_pct_col = next((raw for key, raw in columns.items() if "% of money" in key), None)
        bet_count_col = next((raw for key, raw in columns.items() if key == "bets"), None)
        if None in (scheduled_col, bets_pct_col, money_pct_col, bet_count_col):
            continue

        for _, row in frame.iterrows():
            scheduled = str(row.get(scheduled_col) or "")
            tricodes = [
                token
                for token in re.findall(r"\b[A-Z]{2,4}\b", scheduled.upper())
                if token in _TEAM_NAMES
            ]
            if len(tricodes) < 2:
                continue
            bet_pair = _split_pair(row.get(bets_pct_col))
            money_pair = _split_pair(row.get(money_pct_col))
            count = _bet_count(row.get(bet_count_col))
            if bet_pair is None or money_pair is None or count is None:
                continue
            away_code, home_code = tricodes[0], tricodes[1]
            parsed.append(
                {
                    "away": _TEAM_NAMES[away_code],
                    "home": _TEAM_NAMES[home_code],
                    "away_tricode": away_code,
                    "home_tricode": home_code,
                    "bet_count": count,
                    "away_bet_pct": bet_pair[0],
                    "home_bet_pct": bet_pair[1],
                    "away_money_pct": money_pair[0],
                    "home_money_pct": money_pair[1],
                }
            )
        if parsed:
            break
    return parsed


def fetch_action_network_rows(*, timeout_seconds: float = 12.0) -> list[dict]:
    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0; +public-data-verification)",
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return parse_action_network_html(response.text)


def _valid_splits(row: Mapping[str, object]) -> bool:
    try:
        values = [
            int(row["away_bet_pct"]),
            int(row["home_bet_pct"]),
            int(row["away_money_pct"]),
            int(row["home_money_pct"]),
        ]
    except (KeyError, TypeError, ValueError):
        return False
    return (
        all(0 <= item <= 100 for item in values)
        and values[0] + values[1] == 100
        and values[2] + values[3] == 100
        and _bet_count(row.get("bet_count")) is not None
    )


def _schedule_index(schedule_games: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], Mapping[str, object]]:
    out: dict[tuple[str, str], Mapping[str, object]] = {}
    for game in schedule_games:
        if str(game.get("status") or "").upper() not in ELIGIBLE_STATES:
            continue
        away = _team_code(game.get("away_tricode") or game.get("away_name"))
        home = _team_code(game.get("home_tricode") or game.get("home_name"))
        if away and home:
            out[(away, home)] = game
    return out


def select_most_bet_game(
    action_rows: Iterable[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
) -> dict:
    """Return the unique highest-volume Action matchup bound to Step-3 identity."""
    schedule = _schedule_index(schedule_games)
    matched: list[tuple[int, Mapping[str, object], Mapping[str, object]]] = []
    invalid_match = False

    for row in action_rows:
        away = _team_code(row.get("away_tricode") or row.get("away"))
        home = _team_code(row.get("home_tricode") or row.get("home"))
        if not away or not home:
            continue
        game = schedule.get((away, home))
        if game is None:
            continue
        if not _valid_splits(row):
            invalid_match = True
            continue
        count = _bet_count(row.get("bet_count"))
        assert count is not None
        matched.append((count, row, game))

    if invalid_match:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "INVALID_BETTING_SPLITS"}
    if not matched:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "NO_VERIFIED_SCHEDULE_MATCH"}

    top_count = max(item[0] for item in matched)
    winners = [item for item in matched if item[0] == top_count]
    if len(winners) != 1:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "AMBIGUOUS_MOST_BET_GAME"}

    count, row, game = winners[0]
    away_code = str(game.get("away_tricode") or _team_code(row.get("away")) or "")
    home_code = str(game.get("home_tricode") or _team_code(row.get("home")) or "")
    return {
        "verification": "VERIFIED",
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "away_tricode": away_code,
        "home_tricode": home_code,
        "away_name": str(game.get("away_name") or _TEAM_NAMES.get(away_code, away_code)),
        "home_name": str(game.get("home_name") or _TEAM_NAMES.get(home_code, home_code)),
        "game_date_phoenix": str(game.get("game_date_phoenix") or ""),
        "tip_phoenix": str(game.get("tip_phoenix") or ""),
        "status": str(game.get("status") or "UPCOMING"),
        "bet_count": count,
        "away_bet_pct": int(row["away_bet_pct"]),
        "home_bet_pct": int(row["home_bet_pct"]),
        "away_money_pct": int(row["away_money_pct"]),
        "home_money_pct": int(row["home_money_pct"]),
    }


def load_most_bet_feature(schedule_games: Sequence[Mapping[str, object]]) -> dict:
    try:
        rows = fetch_action_network_rows()
    except (requests.RequestException, ValueError, TypeError):
        return {"verification": "UNAVAILABLE", "diagnostic_state": "SOURCE_UNAVAILABLE"}
    if not rows:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "SOURCE_DATA_UNAVAILABLE"}
    return select_most_bet_game(rows, schedule_games)


__all__ = [
    "MODEL_VERSION",
    "SOURCE_NAME",
    "SOURCE_URL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_SHARP_MONEY",
    "MAY_ACTIVATE_INJURIES",
    "MAY_ACTIVATE_RANKING",
    "parse_action_network_html",
    "fetch_action_network_rows",
    "select_most_bet_game",
    "load_most_bet_feature",
]
