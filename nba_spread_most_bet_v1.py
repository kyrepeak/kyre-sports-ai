"""NBA Spread Step 4 — fail-closed Most Bet Game feature layer.

This module identifies the unique highest tracked-bet NBA spread matchup and
reconciles it to the already-verified Step-3 Phoenix schedule. Step 4 owns only
betting-volume context; schedule/game identity remains owned by the frozen
Step-3 NBA Official + ESPN quorum.

Universal Sports Multi-Source Architecture V1 rules are enforced here:
- providers declare field capabilities before they may be used;
- a fallback may replace the primary only when it exposes the SAME required
  game-level absolute bet-count metric;
- ticket/money percentages are never treated as absolute game volume;
- provider health is tracked independently from page health;
- incompatible fallbacks are not queried just to create latency;
- no missing game, split, count, ID, timestamp, or analytic is invented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from typing import Callable, Iterable, Mapping, Sequence

import requests

MODEL_VERSION = "NBA_SPREAD_STEP4_MOST_BET_FEATURE_V1"
SOURCE_NAME = "Action Network"
SOURCE_URL = "https://www.actionnetwork.com/nba/public-betting"
REQUIRED_VOLUME_METRIC = "tracked_game_bet_count"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_SHARP_MONEY = False
MAY_ACTIVATE_INJURIES = False
MAY_ACTIVATE_RANKING = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}

# SportsDataIO and VSiN are useful independent betting-split sources, but their
# published NBA contracts expose bet/ticket percentages and money percentages,
# not a comparable absolute per-game tracked-bet count. They therefore remain
# valid split sources while being explicitly ineligible to manufacture a
# replacement value for REQUIRED_VOLUME_METRIC.
BETTING_VOLUME_SOURCE_CONTRACTS: tuple[dict[str, object], ...] = (
    {
        "role": "PRIMARY",
        "name": SOURCE_NAME,
        "url": SOURCE_URL,
        "capabilities": (REQUIRED_VOLUME_METRIC, "spread_bet_pct", "spread_money_pct"),
        "selection_capable": True,
        "incompatibility": None,
    },
    {
        "role": "SECONDARY",
        "name": "SportsDataIO",
        "url": "https://sportsdata.io/developers/api-documentation/nba",
        "capabilities": ("spread_bet_pct", "spread_money_pct", "split_timestamp"),
        "selection_capable": False,
        "incompatibility": "ABSOLUTE_GAME_BET_COUNT_NOT_EXPOSED",
    },
    {
        "role": "TERTIARY",
        "name": "VSiN / DraftKings",
        "url": "https://data.vsin.com/betting-splits/?source=DK&sport=NBA",
        "capabilities": ("spread_bet_pct", "spread_money_pct"),
        "selection_capable": False,
        "incompatibility": "ABSOLUTE_GAME_BET_COUNT_NOT_EXPOSED",
    },
)

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


def source_ownership_manifest(
    provider_contracts: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Expose field ownership without pretending incompatible fields are equal."""
    contracts = provider_contracts or BETTING_VOLUME_SOURCE_CONTRACTS
    return {
        "schedule_identity": {
            "owner": "NBA Spread Step 3 canonical schedule",
            "sources": ("NBA Official", "ESPN NBA"),
            "quorum": 2,
            "timezone": "America/Phoenix",
            "state": "FROZEN_DEPENDENCY",
        },
        "betting_volume": {
            "owner": "NBA Spread Step 4 Most Bet feature",
            "required_metric": REQUIRED_VOLUME_METRIC,
            "sources": [dict(contract) for contract in contracts],
            "fallback_policy": "SAME_METRIC_ONLY_THEN_FAIL_CLOSED",
        },
    }


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
    """Small dependency-free HTML table reader for the public betting page."""

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
    """Parse Action Network's public NBA spread table into neutral rows.

    The parser intentionally requires the documented public-table columns and
    returns no rows when the page shape is incomplete. It never invents splits.
    """
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


def _canonical_ids(game: Mapping[str, object], away_code: str, home_code: str) -> dict[str, str]:
    phoenix_date = str(game.get("game_date_phoenix") or "")
    game_key = str(game.get("game_key") or f"{away_code}@{home_code}:{phoenix_date}")
    return {
        "kyre_game_id": str(game.get("kyre_game_id") or f"KYRE:NBA:GAME:{game_key}"),
        "kyre_away_team_id": str(game.get("kyre_away_team_id") or f"KYRE:NBA:TEAM:{away_code}"),
        "kyre_home_team_id": str(game.get("kyre_home_team_id") or f"KYRE:NBA:TEAM:{home_code}"),
    }


def select_most_bet_game(
    action_rows: Iterable[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
    *,
    source_name: str = SOURCE_NAME,
    source_url: str = SOURCE_URL,
) -> dict:
    """Return the unique highest-volume matchup bound to frozen Step-3 identity."""
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
    observed_at = str(row.get("source_observed_at_utc") or "")
    feature = {
        "verification": "VERIFIED",
        "source": source_name,
        "source_url": source_url,
        "source_metric": REQUIRED_VOLUME_METRIC,
        "source_observed_at_utc": observed_at,
        "source_timestamp_status": "EXPOSED" if observed_at else "NOT_EXPOSED",
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
    feature.update(_canonical_ids(game, away_code, home_code))
    return feature


def _retrieved_at_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_most_bet_feature(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    provider_contracts: Sequence[Mapping[str, object]] | None = None,
    provider_fetchers: Mapping[str, Callable[[], list[dict]]] | None = None,
) -> dict:
    """Resolve Step 4 through one ordered, metric-compatible provider chain.

    Production currently has one provider that publishes the exact absolute
    game-level tracked-bet-count metric. Independent split-only sources are
    recorded as secondary/tertiary contracts but are intentionally skipped for
    this field. The resolver itself supports a future equivalent secondary or
    tertiary without any UI or identity rewrite.
    """
    contracts = tuple(provider_contracts or BETTING_VOLUME_SOURCE_CONTRACTS)
    if provider_fetchers is None:
        fetchers: dict[str, Callable[[], list[dict]]] = {
            SOURCE_NAME: lambda: fetch_action_network_rows(),
        }
    else:
        fetchers = dict(provider_fetchers)

    provider_health = {str(contract.get("name") or "UNKNOWN"): "NOT_QUERIED" for contract in contracts}
    attempts: list[dict[str, str]] = []
    active_providers: list[str] = []
    last_provider_diagnostic = ""

    for contract in contracts:
        name = str(contract.get("name") or "UNKNOWN")
        role = str(contract.get("role") or "FALLBACK")
        source_url = str(contract.get("url") or "")
        capabilities = {str(item) for item in (contract.get("capabilities") or ())}
        selection_capable = bool(contract.get("selection_capable"))

        if REQUIRED_VOLUME_METRIC not in capabilities or not selection_capable:
            provider_health[name] = "NOT_QUERIED_CAPABILITY_MISMATCH"
            attempts.append(
                {
                    "source": name,
                    "role": role,
                    "status": "SKIPPED_INCOMPATIBLE_METRIC",
                    "reason": str(contract.get("incompatibility") or "REQUIRED_METRIC_NOT_EXPOSED"),
                }
            )
            continue

        fetcher = fetchers.get(name)
        if fetcher is None:
            provider_health[name] = "UNCONFIGURED"
            attempts.append(
                {
                    "source": name,
                    "role": role,
                    "status": "UNCONFIGURED",
                    "reason": "NO_FETCHER_CONFIGURED",
                }
            )
            continue

        active_providers.append(name)
        try:
            rows = fetcher()
        except Exception as exc:
            provider_health[name] = "DEGRADED"
            attempts.append(
                {
                    "source": name,
                    "role": role,
                    "status": "FETCH_FAILED",
                    "reason": type(exc).__name__,
                }
            )
            continue

        if not rows:
            provider_health[name] = "DEGRADED"
            attempts.append(
                {
                    "source": name,
                    "role": role,
                    "status": "EMPTY_DATA",
                    "reason": "NO_PROVIDER_ROWS",
                }
            )
            continue

        provider_health[name] = "HEALTHY"
        candidate = select_most_bet_game(
            rows,
            schedule_games,
            source_name=name,
            source_url=source_url,
        )
        if candidate.get("verification") == "VERIFIED":
            candidate.update(
                {
                    "retrieved_at_utc": _retrieved_at_utc(),
                    "source_ownership": source_ownership_manifest(contracts),
                    "active_providers": active_providers,
                    "provider_health": provider_health,
                    "fallback_attempts": attempts,
                    "consensus_status": "STEP3_IDENTITY_QUORUM_PLUS_FIELD_AUTHORITY",
                    "page_impact": "NONE",
                }
            )
            return candidate

        last_provider_diagnostic = str(candidate.get("diagnostic_state") or "SOURCE_DATA_UNAVAILABLE")
        attempts.append(
            {
                "source": name,
                "role": role,
                "status": "DATA_REJECTED",
                "reason": last_provider_diagnostic,
            }
        )

    incompatible_fallback_exists = any(
        attempt.get("status") == "SKIPPED_INCOMPATIBLE_METRIC" for attempt in attempts
    )
    diagnostic = (
        "NO_COMPARABLE_VOLUME_FALLBACK"
        if incompatible_fallback_exists
        else (last_provider_diagnostic or "SOURCE_DATA_UNAVAILABLE")
    )
    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": diagnostic,
        "last_provider_diagnostic": last_provider_diagnostic,
        "required_metric": REQUIRED_VOLUME_METRIC,
        "retrieved_at_utc": _retrieved_at_utc(),
        "source_ownership": source_ownership_manifest(contracts),
        "active_providers": active_providers,
        "provider_health": provider_health,
        "fallback_attempts": attempts,
        "consensus_status": "FALLBACKS_EXHAUSTED_NO_FALSE_SUBSTITUTION",
        "page_impact": "FEATURE_ONLY",
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE_NAME",
    "SOURCE_URL",
    "REQUIRED_VOLUME_METRIC",
    "BETTING_VOLUME_SOURCE_CONTRACTS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_SHARP_MONEY",
    "MAY_ACTIVATE_INJURIES",
    "MAY_ACTIVATE_RANKING",
    "source_ownership_manifest",
    "parse_action_network_html",
    "fetch_action_network_rows",
    "select_most_bet_game",
    "load_most_bet_feature",
]
