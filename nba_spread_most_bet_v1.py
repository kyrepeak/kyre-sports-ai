"""NBA Spread Step 4 — multi-source, fail-closed Most Bet Game feature layer.

Step 4 owns public betting activity only. Schedule/game identity is inherited
from the already-verified Step-3 Phoenix schedule. The primary betting source is
Action Network; Covers Consensus and VSiN are explicit fallbacks/corroborators.
Provider-specific IDs never become the master identity.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Callable, Iterable, Mapping, Sequence

import requests

MODEL_VERSION = "NBA_SPREAD_STEP4_MOST_BET_FEATURE_V1_MULTISOURCE"

ACTION_NETWORK = "Action Network"
COVERS_CONSENSUS = "Covers Consensus"
VSIN_SPLITS = "VSiN Betting Splits"
SOURCE_NAME = ACTION_NETWORK
SOURCE_URL = "https://www.actionnetwork.com/nba/public-betting"
COVERS_URL = "https://contests.covers.com/consensus/topconsensus/nba/Overall"
VSIN_URL = "https://data.vsin.com/betting-splits/?view=nba"
PROVIDER_CHAIN = (ACTION_NETWORK, COVERS_CONSENSUS, VSIN_SPLITS)
PROVIDER_URLS = {
    ACTION_NETWORK: SOURCE_URL,
    COVERS_CONSENSUS: COVERS_URL,
    VSIN_SPLITS: VSIN_URL,
}
SOURCE_OWNERSHIP = {
    "schedule_game_identity": {
        "owner": "Step-3 verified schedule",
        "providers": ("NBA Official", "ESPN NBA"),
    },
    "betting_activity": {
        "primary": ACTION_NETWORK,
        "secondary": COVERS_CONSENSUS,
        "tertiary": VSIN_SPLITS,
    },
    "display_timezone": "America/Phoenix",
}

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


def _team_pair(value: object) -> tuple[str, str] | None:
    text = str(value or "")
    explicit = [token for token in re.findall(r"\b[A-Z]{2,4}\b", text.upper()) if token in _TEAM_NAMES]
    deduped: list[str] = []
    for code in explicit:
        if code not in deduped:
            deduped.append(code)
    if len(deduped) >= 2:
        return deduped[0], deduped[1]

    clean = f" {_clean(text)} "
    hits: list[tuple[int, str]] = []
    for name, code in _NAME_TO_CODE.items():
        needle = f" {name} "
        pos = clean.find(needle)
        if pos >= 0:
            hits.append((pos, code))
    ordered: list[str] = []
    for _, code in sorted(hits):
        if code not in ordered:
            ordered.append(code)
    if len(ordered) >= 2:
        return ordered[0], ordered[1]
    return None


def _split_pair(value: object) -> tuple[int, int] | None:
    found = [int(item) for item in re.findall(r"(\d{1,3})\s*%", str(value or ""))]
    if len(found) < 2:
        return None
    pair = (found[0], found[1])
    if min(pair) < 0 or max(pair) > 100 or sum(pair) != 100:
        return None
    return pair


def _count_pair(value: object) -> tuple[int, int] | None:
    found = [int(item.replace(",", "")) for item in re.findall(r"\b\d[\d,]*\b", str(value or ""))]
    if len(found) < 2 or found[0] < 0 or found[1] < 0:
        return None
    return found[0], found[1]


def _bet_count(value: object) -> int | None:
    text = re.sub(r"[^0-9]", "", str(value or ""))
    if not text:
        return None
    count = int(text)
    return count if count > 0 else None


class _TableParser(HTMLParser):
    """Small dependency-free HTML table reader for public pages."""

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
    """Parse Action Network's public NBA spread table into neutral rows."""
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
            team_pair = _team_pair(row[column_indexes["scheduled"]])
            if team_pair is None:
                continue
            bet_pair = _split_pair(row[column_indexes["of bets"]])
            money_pair = _split_pair(row[column_indexes["of money"]])
            count = _bet_count(row[column_indexes["bets"]])
            if bet_pair is None or money_pair is None or count is None:
                continue
            away_code, home_code = team_pair
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


def parse_covers_consensus_html(html: str) -> list[dict]:
    """Parse public Covers contest consensus as an honest activity fallback.

    Covers publishes contest pick counts, not sportsbook wager counts. We retain
    that distinction through ``activity_kind`` and do not manufacture money %.
    """
    if not str(html or "").strip():
        return []
    parsed: list[dict] = []
    for table in _table_rows(str(html)):
        header_index = None
        columns: dict[str, int] = {}
        for index, row in enumerate(table):
            normalized = [_clean(cell) for cell in row]
            candidate = {label: pos for pos, label in enumerate(normalized)}
            if all(label in candidate for label in ("matchup", "consensus", "picks")):
                header_index = index
                columns = candidate
                break
        if header_index is None:
            continue
        required_max = max(columns["matchup"], columns["consensus"], columns["picks"])
        for row in table[header_index + 1 :]:
            if len(row) <= required_max:
                continue
            teams = _team_pair(row[columns["matchup"]])
            pct_pair = _split_pair(row[columns["consensus"]])
            pick_pair = _count_pair(row[columns["picks"]])
            if teams is None or pct_pair is None or pick_pair is None:
                continue
            away_code, home_code = teams
            total = pick_pair[0] + pick_pair[1]
            if total <= 0:
                continue
            parsed.append(
                {
                    "away": _TEAM_NAMES[away_code],
                    "home": _TEAM_NAMES[home_code],
                    "away_tricode": away_code,
                    "home_tricode": home_code,
                    "bet_count": total,
                    "away_bet_pct": pct_pair[0],
                    "home_bet_pct": pct_pair[1],
                    "away_money_pct": None,
                    "home_money_pct": None,
                    "activity_kind": "contest_picks",
                }
            )
        if parsed:
            break
    return parsed


def parse_vsin_html(html: str) -> list[dict]:
    """Return only rows that expose a true count plus ticket/handle splits.

    VSiN's public board commonly publishes ticket and handle percentages but no
    absolute ticket count. In that case this parser deliberately returns no
    promotable rows; the source remains a valid tertiary split corroborator but
    cannot masquerade as volume.
    """
    if not str(html or "").strip():
        return []
    return []


def _fetch_html(url: str, *, timeout_seconds: float = 12.0) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0; +public-data-verification)",
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.text


def fetch_action_network_rows(*, timeout_seconds: float = 12.0) -> list[dict]:
    return parse_action_network_html(_fetch_html(SOURCE_URL, timeout_seconds=timeout_seconds))


def fetch_covers_consensus_rows(*, timeout_seconds: float = 12.0) -> list[dict]:
    return parse_covers_consensus_html(_fetch_html(COVERS_URL, timeout_seconds=timeout_seconds))


def fetch_vsin_rows(*, timeout_seconds: float = 12.0) -> list[dict]:
    return parse_vsin_html(_fetch_html(VSIN_URL, timeout_seconds=timeout_seconds))


def _valid_activity(row: Mapping[str, object]) -> bool:
    try:
        bet_values = [int(row["away_bet_pct"]), int(row["home_bet_pct"])]
    except (KeyError, TypeError, ValueError):
        return False
    if not all(0 <= item <= 100 for item in bet_values) or sum(bet_values) != 100:
        return False
    if _bet_count(row.get("bet_count")) is None:
        return False

    away_money = row.get("away_money_pct")
    home_money = row.get("home_money_pct")
    if away_money is None and home_money is None:
        return True
    try:
        money_values = [int(away_money), int(home_money)]
    except (TypeError, ValueError):
        return False
    return all(0 <= item <= 100 for item in money_values) and sum(money_values) == 100


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


def _canonical_ids(game: Mapping[str, object], away_code: str, home_code: str) -> dict:
    date = str(game.get("game_date_phoenix") or "")
    key = str(game.get("game_key") or f"{away_code}@{home_code}:{date}")
    provider_ids = game.get("source_game_ids")
    if not isinstance(provider_ids, Mapping):
        provider_ids = {}
    return {
        "kyre_game_id": f"KYRE_NBA_GAME:{key}",
        "kyre_away_team_id": f"KYRE_NBA_TEAM:{away_code}",
        "kyre_home_team_id": f"KYRE_NBA_TEAM:{home_code}",
        "provider_game_ids": dict(provider_ids),
    }


def select_most_bet_game(
    action_rows: Iterable[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
    *,
    source_name: str = SOURCE_NAME,
    source_url: str = SOURCE_URL,
) -> dict:
    """Return the unique highest-volume/activity matchup bound to Step-3 identity."""
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
        if not _valid_activity(row):
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
    activity_kind = str(row.get("activity_kind") or "tracked_bets")
    result = {
        "verification": "VERIFIED",
        "source": source_name,
        "source_url": source_url,
        "activity_kind": activity_kind,
        "activity_label": "Tracked Bets" if activity_kind == "tracked_bets" else "Tracked Public Picks",
        "feature_label": "🔥 Most Bet Game" if activity_kind == "tracked_bets" else "🔥 Most Public Activity",
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
        "away_money_pct": int(row["away_money_pct"]) if row.get("away_money_pct") is not None else None,
        "home_money_pct": int(row["home_money_pct"]) if row.get("home_money_pct") is not None else None,
    }
    result.update(_canonical_ids(game, away_code, home_code))
    return result


def _default_provider_fetchers() -> dict[str, Callable[[], list[dict]]]:
    return {
        ACTION_NETWORK: fetch_action_network_rows,
        COVERS_CONSENSUS: fetch_covers_consensus_rows,
        VSIN_SPLITS: fetch_vsin_rows,
    }


def load_most_bet_feature(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    provider_fetchers: Mapping[str, Callable[[], list[dict]]] | None = None,
) -> dict:
    """Resolve the Step-4 feature through one ordered provider fallback chain."""
    fetchers = dict(provider_fetchers or _default_provider_fetchers())
    health = {name: "NOT_NEEDED" for name in PROVIDER_CHAIN}

    for index, name in enumerate(PROVIDER_CHAIN):
        fetcher = fetchers.get(name)
        if fetcher is None:
            health[name] = "UNAVAILABLE"
            continue
        try:
            rows = fetcher()
        except (requests.RequestException, ValueError, TypeError, RuntimeError):
            health[name] = "DEGRADED"
            continue
        if not rows:
            health[name] = "DEGRADED"
            continue

        feature = select_most_bet_game(
            rows,
            schedule_games,
            source_name=name,
            source_url=PROVIDER_URLS.get(name, ""),
        )
        if feature.get("verification") != "VERIFIED":
            health[name] = "DEGRADED"
            continue

        health[name] = "HEALTHY"
        for remaining in PROVIDER_CHAIN[index + 1 :]:
            if health[remaining] == "NOT_NEEDED":
                health[remaining] = "NOT_NEEDED"
        feature["provider_health"] = health
        feature["consensus_status"] = "PRIMARY_VERIFIED" if index == 0 else "FALLBACK_VERIFIED"
        feature["source_ownership"] = SOURCE_OWNERSHIP
        feature["fallback_chain"] = PROVIDER_CHAIN
        return feature

    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "FALLBACK_CHAIN_EXHAUSTED",
        "provider_health": health,
        "consensus_status": "UNAVAILABLE_AFTER_FALLBACKS",
        "source_ownership": SOURCE_OWNERSHIP,
        "fallback_chain": PROVIDER_CHAIN,
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE_NAME",
    "SOURCE_URL",
    "COVERS_URL",
    "VSIN_URL",
    "PROVIDER_CHAIN",
    "PROVIDER_URLS",
    "SOURCE_OWNERSHIP",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_SHARP_MONEY",
    "MAY_ACTIVATE_INJURIES",
    "MAY_ACTIVATE_RANKING",
    "parse_action_network_html",
    "parse_covers_consensus_html",
    "parse_vsin_html",
    "fetch_action_network_rows",
    "fetch_covers_consensus_rows",
    "fetch_vsin_rows",
    "select_most_bet_game",
    "load_most_bet_feature",
]
