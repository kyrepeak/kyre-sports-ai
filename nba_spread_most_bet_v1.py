"""NBA Spread Step 4 — fail-closed Most Bet Game selector.

Action Network's NBA public-betting table is used only as a read-only market
popularity source. A row may render only after its matchup binds to the already
verified Step-3 NBA schedule. No projection, probability, injury, sharp-money,
or ranking behavior is activated here.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
import requests
from typing import Iterable, Mapping

SOURCE = "Action Network"
SOURCE_URL = "https://www.actionnetwork.com/nba/public-betting"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_SHARP_MONEY = False
MAY_ACTIVATE_INJURIES = False
MAY_ACTIVATE_RANKINGS = False


class MostBetUnavailable(RuntimeError):
    pass


class _TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        low = tag.lower()
        if low in {"td", "th"} and self._row is not None and self._cell is not None:
            text = " ".join(" ".join(self._cell).split())
            self._row.append(text)
            self._cell = None
        elif low == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def _percent_pair(value: str) -> list[int] | None:
    vals = [int(x) for x in re.findall(r"(?<!\d)(\d{1,3})\s*%", str(value or ""))]
    if len(vals) < 2:
        return None
    pair = vals[:2]
    if any(x < 0 or x > 100 for x in pair) or sum(pair) != 100:
        return None
    return pair


def _bet_count(value: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    if not digits:
        return None
    try:
        count = int(digits)
    except ValueError:
        return None
    return count if count >= 0 else None


def _header_index(headers: list[str], needle: str) -> int | None:
    norm = [" ".join(str(x).lower().split()) for x in headers]
    target = " ".join(needle.lower().split())
    try:
        return norm.index(target)
    except ValueError:
        return None


def _schedule_match(cell: str, schedule: Iterable[Mapping]) -> Mapping | None:
    upper = f" {str(cell or '').upper()} "
    matches = []
    for game in schedule:
        away = str(game.get("away_tricode") or "").strip().upper()
        home = str(game.get("home_tricode") or "").strip().upper()
        if not away or not home:
            continue
        if re.search(rf"\b{re.escape(away)}\b", upper) and re.search(rf"\b{re.escape(home)}\b", upper):
            matches.append(game)
    if len(matches) == 1:
        return matches[0]
    return None


def select_most_bet_game_from_html(html: str, verified_schedule: Iterable[Mapping]) -> dict:
    parser = _TableRows()
    parser.feed(str(html or ""))
    if not parser.rows:
        raise MostBetUnavailable("ACTION_NETWORK_TABLE_MISSING")

    header_pos = None
    indexes = None
    for i, row in enumerate(parser.rows):
        sched = _header_index(row, "Scheduled")
        bets_pct = _header_index(row, "% of Bets")
        money_pct = _header_index(row, "% of Money")
        bets = _header_index(row, "Bets")
        if None not in {sched, bets_pct, money_pct, bets}:
            header_pos = i
            indexes = (sched, bets_pct, money_pct, bets)
            break
    if header_pos is None or indexes is None:
        raise MostBetUnavailable("ACTION_NETWORK_COLUMNS_MISSING")

    schedule = list(verified_schedule)
    raw_candidates: list[dict] = []
    max_idx = max(indexes)
    for row in parser.rows[header_pos + 1:]:
        if len(row) <= max_idx:
            continue
        count = _bet_count(row[indexes[3]])
        if count is None:
            continue
        raw_candidates.append({
            "row": row,
            "tracked_bets": count,
            "game": _schedule_match(row[indexes[0]], schedule),
        })
    if not raw_candidates:
        raise MostBetUnavailable("ACTION_NETWORK_BET_COUNTS_MISSING")

    highest = max(raw_candidates, key=lambda x: x["tracked_bets"])
    game = highest["game"]
    if game is None:
        raise MostBetUnavailable("UNBOUND_HIGHEST_VOLUME_ROW")

    row = highest["row"]
    bet_pct = _percent_pair(row[indexes[1]])
    money_pct = _percent_pair(row[indexes[2]])
    if bet_pct is None or money_pct is None:
        raise MostBetUnavailable("HIGHEST_VOLUME_SPLITS_MISSING")

    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "away_tricode": str(game.get("away_tricode") or ""),
        "home_tricode": str(game.get("home_tricode") or ""),
        "away_name": str(game.get("away_name") or game.get("away_tricode") or ""),
        "home_name": str(game.get("home_name") or game.get("home_tricode") or ""),
        "game_date_phoenix": str(game.get("game_date_phoenix") or ""),
        "tip_phoenix": str(game.get("tip_phoenix") or ""),
        "status": str(game.get("status") or ""),
        "tracked_bets": int(highest["tracked_bets"]),
        "bet_pct": bet_pct,
        "money_pct": money_pct,
        "verification": "VERIFIED",
    }


def load_most_bet_game(verified_schedule: Iterable[Mapping], *, timeout: float = 12.0) -> dict:
    try:
        response = requests.get(
            SOURCE_URL,
            headers={"User-Agent": "KyreSportsAI/1.0 (+read-only featured-market card)"},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise MostBetUnavailable("ACTION_NETWORK_UNAVAILABLE") from exc
    return select_most_bet_game_from_html(response.text, verified_schedule)


__all__ = [
    "SOURCE", "SOURCE_URL", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL", "MAY_MODIFY_PROJECTION", "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_SHARP_MONEY", "MAY_ACTIVATE_INJURIES", "MAY_ACTIVATE_RANKINGS",
    "MostBetUnavailable", "select_most_bet_game_from_html", "load_most_bet_game",
]
