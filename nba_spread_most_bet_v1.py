"""NBA Spread Step 4 — fail-closed Most Bet Game feature layer.

The page may publish a "Most Bet Game" only when the frozen Universal Sports
Source + Finalization architecture produces a legitimate PUBLIC_BET_COUNT
route. Public bet percentages and money percentages are never substituted for
absolute bet count. The legacy Action Network parser/selector remains available
for regression compatibility, but it is not a source-authority bypass.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import requests

from devsystem.universal_sports_field_router_v1 import load_router_policy, route_field
from devsystem.universal_sports_provider_registry_v1 import load_registry

MODEL_VERSION = "NBA_SPREAD_STEP4_MOST_BET_FEATURE_V2_UNIVERSAL_ROUTE"
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

_ROOT = Path(__file__).resolve().parent
_PROVIDER_REGISTRY_PATH = _ROOT / "devsystem" / "contracts" / "universal-sports-provider-registry-v1.json"
_FIELD_ROUTER_PATH = _ROOT / "devsystem" / "contracts" / "universal-sports-field-router-v1.json"
PUBLIC_BET_COUNT_FIELD = "public_bet_count"
PUBLIC_BET_COUNT_METRIC = "PUBLIC_BET_COUNT"

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


class _TableParser(HTMLParser):
    """Small dependency-free HTML table reader used by the legacy parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag == "table" and self._table is None:
            self._table = []
        elif self._table is not None and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"th", "td"}:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._cell_parts is not None and tag in {"th", "td"}:
            assert self._row is not None
            self._row.append(" ".join(self._cell_parts).strip())
            self._cell_parts = None
        elif self._row is not None and tag == "tr":
            if any(cell for cell in self._row):
                assert self._table is not None
                self._table.append(self._row)
            self._row = None
            self._cell_parts = None
        elif self._table is not None and tag == "table":
            if self._table:
                self.tables.append(self._table)
            self._table = None
            self._row = None
            self._cell_parts = None


def _table_rows(html: str) -> list[list[list[str]]]:
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []
    return parser.tables


def parse_action_network_html(html: str) -> list[dict]:
    """Parse the historical Action public-table shape without granting authority."""
    if not str(html or "").strip():
        return []

    parsed: list[dict] = []
    for table in _table_rows(str(html)):
        header_index = None
        column_indexes: dict[str, int] = {}
        for index, row in enumerate(table):
            normalized = [_clean(cell) for cell in row]
            candidate = {label: pos for pos, label in enumerate(normalized)}
            if all(label in candidate for label in ("scheduled", "of bets", "of money", "bets")):
                header_index = index
                column_indexes = candidate
                break
        if header_index is None:
            continue

        required_max = max(
            column_indexes["scheduled"],
            column_indexes["of bets"],
            column_indexes["of money"],
            column_indexes["bets"],
        )
        for row in table[header_index + 1 :]:
            if len(row) <= required_max:
                continue
            scheduled = row[column_indexes["scheduled"]]
            tricodes = [
                token
                for token in re.findall(r"\b[A-Z]{2,4}\b", scheduled.upper())
                if token in _TEAM_NAMES
            ]
            if len(tricodes) < 2:
                continue
            bet_pair = _split_pair(row[column_indexes["of bets"]])
            money_pair = _split_pair(row[column_indexes["of money"]])
            count = _bet_count(row[column_indexes["bets"]])
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
    """Legacy fetch helper retained for parser regression coverage only."""
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


def _schedule_index(
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
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
    rows: Iterable[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
) -> dict:
    """Pure selector for already-authorized absolute-count observations."""
    schedule = _schedule_index(schedule_games)
    matched: list[tuple[int, Mapping[str, object], Mapping[str, object]]] = []
    invalid_match = False

    for row in rows:
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


def resolve_public_bet_count_route(
    *,
    registry: Mapping[str, Any] | None = None,
    router_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the frozen universal DATA_FIELD route for absolute public bet count."""
    resolved_registry = (
        dict(registry)
        if registry is not None
        else load_registry(_PROVIDER_REGISTRY_PATH)
    )
    resolved_policy = (
        dict(router_policy)
        if router_policy is not None
        else load_router_policy(_FIELD_ROUTER_PATH)
    )
    return route_field(
        resolved_registry,
        resolved_policy,
        sport="nba",
        field=PUBLIC_BET_COUNT_FIELD,
    )


def _unavailable_from_route(route: Mapping[str, Any], diagnostic: str) -> dict:
    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": diagnostic,
        "semantic_metric_id": str(route.get("semantic_metric_id") or PUBLIC_BET_COUNT_METRIC),
        "route_id": route.get("route_id"),
        "eligible_provider_ids": list(route.get("eligible_provider_ids") or []),
        "blocked_providers": list(route.get("blocked_providers") or []),
        "active_provider_ids": list(route.get("active_provider_ids") or []),
        "page_wide_source_authority": bool(route.get("page_wide_source_authority", False)),
        "fabrication": False,
    }


def load_most_bet_feature(schedule_games: Sequence[Mapping[str, object]]) -> dict:
    """Load Step 4 through the universal PUBLIC_BET_COUNT route.

    The current frozen registry has no configured provider that can legally
    supply absolute public bet count for NBA. Therefore the correct current
    behavior is fail-closed. The legacy Action parser is intentionally not
    consulted because public split percentages are not compatible substitutes.
    """
    del schedule_games
    try:
        route = resolve_public_bet_count_route()
    except (OSError, ValueError, TypeError):
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "PUBLIC_BET_COUNT_ROUTE_INVALID",
            "semantic_metric_id": PUBLIC_BET_COUNT_METRIC,
            "eligible_provider_ids": [],
            "blocked_providers": [],
            "active_provider_ids": [],
            "page_wide_source_authority": False,
            "fabrication": False,
        }

    if route.get("status") != "ROUTE_READY":
        return _unavailable_from_route(route, "PUBLIC_BET_COUNT_ROUTE_UNAVAILABLE")

    # A route becoming READY is not permission to invent a provider adapter.
    # Until an eligible absolute-count adapter is explicitly implemented and
    # certified, fail closed rather than falling back to percentage sources.
    return _unavailable_from_route(route, "PUBLIC_BET_COUNT_ADAPTER_UNAVAILABLE")


__all__ = [
    "MODEL_VERSION",
    "SOURCE_NAME",
    "SOURCE_URL",
    "PUBLIC_BET_COUNT_FIELD",
    "PUBLIC_BET_COUNT_METRIC",
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
    "resolve_public_bet_count_route",
    "load_most_bet_feature",
]
