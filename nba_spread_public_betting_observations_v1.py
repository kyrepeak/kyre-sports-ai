"""NBA Spread Step 2 — verified public betting observation transport."""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any, Callable, Mapping, Sequence

import requests

ACTION_PUBLIC_BETTING_URL = "https://www.actionnetwork.com/nba/public-betting"
SOURCE_NAME = "Action Network"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_RANKING = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _percent_pair(value: object) -> tuple[int, int] | None:
    values = [int(x) for x in re.findall(r"(\d{1,3})\s*%", str(value or ""))]
    if len(values) < 2:
        return None
    pair = values[0], values[1]
    if min(pair) < 0 or max(pair) > 100 or sum(pair) != 100:
        return None
    return pair


def _positive_count(value: object) -> int | None:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    if not digits:
        return None
    count = int(digits)
    return count if count > 0 else None


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        del attrs
        if tag == "table" and self._table is None:
            self._table = []
        elif self._table is not None and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"th", "td"}:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            text = _clean(data)
            if text:
                self._cell.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._cell is not None and tag in {"th", "td"}:
            assert self._row is not None
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif self._row is not None and tag == "tr":
            if any(self._row):
                assert self._table is not None
                self._table.append(self._row)
            self._row = None
            self._cell = None
        elif self._table is not None and tag == "table":
            if self._table:
                self.tables.append(self._table)
            self._table = None
            self._row = None
            self._cell = None


def _parse_action_rows(html: str) -> list[dict[str, object]]:
    parser = _TableParser()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:
        return []

    for table in parser.tables:
        header_idx: int | None = None
        columns: dict[str, int] = {}
        for idx, row in enumerate(table):
            normalized = [re.sub(r"[^a-z0-9]+", " ", cell.casefold()).strip() for cell in row]
            candidate = {label: pos for pos, label in enumerate(normalized)}
            if all(label in candidate for label in ("scheduled", "of bets", "of money", "bets")):
                header_idx = idx
                columns = candidate
                break
        if header_idx is None:
            continue

        required = max(columns["scheduled"], columns["of bets"], columns["of money"], columns["bets"])
        rows: list[dict[str, object]] = []
        for row in table[header_idx + 1 :]:
            if len(row) <= required:
                continue
            scheduled = row[columns["scheduled"]]
            tricodes = re.findall(r"\b[A-Z]{3}\b", scheduled.upper())
            if len(tricodes) < 2:
                continue
            bets = _percent_pair(row[columns["of bets"]])
            money = _percent_pair(row[columns["of money"]])
            count = _positive_count(row[columns["bets"]])
            if bets is None or money is None or count is None:
                continue
            rows.append({
                "away_tricode": tricodes[0],
                "home_tricode": tricodes[1],
                "bet_count": count,
                "away_bet_pct": bets[0],
                "home_bet_pct": bets[1],
                "away_money_pct": money[0],
                "home_money_pct": money[1],
            })
        if rows:
            return rows
    return []


def _schedule_pairs(schedule_games: Sequence[Mapping[str, object]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for game in schedule_games:
        if str(game.get("status") or "").strip().upper() not in ELIGIBLE_STATES:
            continue
        away = str(game.get("away_tricode") or "").strip().upper()
        home = str(game.get("home_tricode") or "").strip().upper()
        if len(away) == 3 and len(home) == 3 and away.isalpha() and home.isalpha():
            pairs.add((away, home))
    return pairs


def normalize_action_network_public_betting_observations(
    html: str,
    schedule_games: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    eligible = _schedule_pairs(schedule_games)
    output: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in _parse_action_rows(html):
        key = (str(row["away_tricode"]), str(row["home_tricode"]))
        if key not in eligible or key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def load_verified_public_betting_observations(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    request_get: Callable[..., Any] = requests.get,
    timeout: float = 12.0,
) -> dict[str, object]:
    base = {
        "source": SOURCE_NAME,
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }
    try:
        response = request_get(
            ACTION_PUBLIC_BETTING_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0; +public-data-verification)",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        return {
            **base,
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"ACTION_NETWORK_PROVIDER_ERROR:{type(exc).__name__}",
        }

    observations = normalize_action_network_public_betting_observations(html, schedule_games)
    if not observations:
        return {
            **base,
            "verification": "UNAVAILABLE",
            "diagnostic_state": "ACTION_NETWORK_NO_VERIFIED_PUBLIC_BETTING_ROWS",
        }
    return {
        **base,
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "observations": observations,
    }


__all__ = [
    "ACTION_PUBLIC_BETTING_URL",
    "SOURCE_NAME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_RANKING",
    "load_verified_public_betting_observations",
    "normalize_action_network_public_betting_observations",
]
