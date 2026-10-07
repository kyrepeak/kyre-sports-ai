"""WNBA PRA Game Center observed-stat hydration adapter.

Pure-Python helpers used only by the WNBA PRA Game Center. Existing observed
production is never overwritten. Known roster-only/zero-production rows may be
hydrated from either the hosted Kyre Sports API aggregate statistics or, when
that bulk transport is unavailable, official WNBA team/player pages.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping


ZERO_SOURCE_MARKERS = (
    "no matched production row",
    "no completed-game rows",
    "no completed-game stats",
)

TEAM_ROSTER_URLS_BY_ID = {
    1611661330: "https://dream.wnba.com/roster",
    1611661329: "https://sky.wnba.com/roster",
    1611661323: "https://sun.wnba.com/roster",
    1611661321: "https://wings.wnba.com/roster",
    1611661331: "https://valkyries.wnba.com/roster",
    1611661325: "https://fever.wnba.com/roster",
    1611661319: "https://aces.wnba.com/roster",
    1611661320: "https://sparks.wnba.com/roster",
    1611661324: "https://lynx.wnba.com/roster",
    1611661313: "https://liberty.wnba.com/roster",
    1611661317: "https://mercury.wnba.com/roster",
    1611661327: "https://fire.wnba.com/roster",
    1611661328: "https://storm.wnba.com/roster",
    1611661332: "https://tempo.wnba.com/roster",
    1611661322: "https://mystics.wnba.com/roster",
}


def normalize_player_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return re.sub(r"[^a-z0-9]", "", text)


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _minutes(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("PT"):
        match = re.fullmatch(
            r"PT(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?",
            text,
        )
        if not match:
            return None
        return (
            float(match.group("h") or 0.0) * 60.0
            + float(match.group("m") or 0.0)
            + float(match.group("s") or 0.0) / 60.0
        )
    if ":" in text:
        try:
            minutes, seconds = text.split(":", 1)
            return float(minutes) + float(seconds) / 60.0
        except (TypeError, ValueError):
            return None
    return _num(text)


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    try:
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _zeroish(value: Any) -> bool:
    number = _num(value)
    return number is None or abs(number) < 1e-12


def is_zero_production_candidate(row: Mapping[str, Any], allowed_team_ids: Iterable[int]) -> bool:
    allowed = {int(x) for x in allowed_team_ids}
    team_id = _int(row.get("TEAM_ID"))
    if team_id not in allowed:
        return False
    source = str(row.get("DATA_SOURCE") or "").casefold()
    marked = any(marker in source for marker in ZERO_SOURCE_MARKERS)
    all_zero = all(_zeroish(row.get(key)) for key in ("MIN", "PTS", "REB", "AST", "PRA"))
    return marked or all_zero


def count_zero_production_candidates(rows: Iterable[Mapping[str, Any]], allowed_team_ids: Iterable[int]) -> int:
    allowed = tuple(int(x) for x in allowed_team_ids)
    return sum(1 for row in rows if is_zero_production_candidate(row, allowed))


def _payload_index(payload: Mapping[str, Any] | None, allowed_team_ids: set[int]) -> dict[tuple[int, str], dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return {}
    if str(payload.get("data_type") or "") != "official_player_season_statistics":
        return {}
    players = payload.get("players")
    if not isinstance(players, list):
        return {}
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for item in players:
        if not isinstance(item, Mapping):
            continue
        team_id = _int(item.get("official_team_id"))
        name = normalize_player_name(item.get("player_name"))
        if team_id in allowed_team_ids and name:
            out[(int(team_id), name)] = dict(item)
    return out


def _apply_window(row: dict[str, Any], item: Mapping[str, Any] | None, prefix: str) -> None:
    if not isinstance(item, Mapping):
        return
    stats = item.get("stats") if isinstance(item.get("stats"), Mapping) else {}
    gp_key = "GP" if not prefix else f"{prefix}GP"
    row[gp_key] = _int(item.get("games_played")) or 0
    values = {
        "MIN": _num(stats.get("minutes")),
        "PTS": _num(stats.get("points")),
        "REB": _num(stats.get("rebounds")),
        "AST": _num(stats.get("assists")),
    }
    for stat, value in values.items():
        if value is not None:
            row[stat if not prefix else f"{prefix}{stat}"] = value
    if all(values[key] is not None for key in ("PTS", "REB", "AST")):
        pra = round(float(values["PTS"]) + float(values["REB"]) + float(values["AST"]), 4)
        row["PRA" if not prefix else f"{prefix}PRA"] = pra


def hydrate_zero_production_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    season_payload: Mapping[str, Any] | None,
    l10_payload: Mapping[str, Any] | None,
    l5_payload: Mapping[str, Any] | None,
    allowed_team_ids: Iterable[int],
    data_source: str = "Kyre Sports API • official WNBA Stats season/L10/L5",
    player_id_source: str = "WNBA Stats via Kyre Sports API",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    allowed = {int(x) for x in allowed_team_ids}
    season = _payload_index(season_payload, allowed)
    l10 = _payload_index(l10_payload, allowed)
    l5 = _payload_index(l5_payload, allowed)

    result: list[dict[str, Any]] = []
    candidates = hydrated = unresolved = 0
    for original in rows:
        row = dict(original)
        if not is_zero_production_candidate(row, allowed):
            result.append(row)
            continue
        candidates += 1
        team_id = _int(row.get("TEAM_ID"))
        name = normalize_player_name(row.get("PLAYER_NAME"))
        key = (int(team_id), name) if team_id is not None and name else None
        season_item = season.get(key) if key else None
        if season_item is None:
            unresolved += 1
            result.append(row)
            continue

        official_id = _int(season_item.get("player_id"))
        if official_id is not None:
            row["PLAYER_ID"] = official_id
        abbr = str(season_item.get("team_abbreviation") or "").strip()
        if abbr:
            row["TEAM_ABBREVIATION"] = abbr
        _apply_window(row, season_item, "")
        _apply_window(row, l10.get(key), "L10_")
        _apply_window(row, l5.get(key), "L5_")
        row["DATA_SOURCE"] = str(data_source)
        row["PLAYER_ID_SOURCE"] = str(player_id_source)
        hydrated += 1
        result.append(row)

    return result, {"candidates": candidates, "hydrated": hydrated, "unresolved": unresolved}


def roster_url_for_team(team_id: int) -> str:
    return TEAM_ROSTER_URLS_BY_ID.get(int(team_id), "")


def _decode_flight_html(html: str) -> str:
    return re.sub(r"\\+(?=\")", "", str(html or ""))


def parse_first_party_roster_html(html: str, expected_team_id: int) -> list[dict[str, Any]]:
    """Extract official player ID/name identity from one WNBA team roster page."""
    normalized = _decode_flight_html(html)
    pattern = re.compile(
        r'"playerId":(?P<player_id>\d+)'
        r'(?P<body>.{0,1800}?)'
        r'"playerLink":"https://www\.wnba\.com/player/(?P<link_id>\d+)"',
        re.S,
    )
    name_re = re.compile(r'"playerName":"([^"]+)"')
    team_re = re.compile(r'"teamId":"?(\d+)"?')
    abbr_re = re.compile(r'"teamAbbreviation":"([^"]+)"')
    by_id: dict[int, dict[str, Any]] = {}
    for match in pattern.finditer(normalized):
        player_id = int(match.group("player_id"))
        if player_id != int(match.group("link_id")):
            continue
        body = match.group("body")
        name_match = name_re.search(body)
        team_match = team_re.search(body)
        if not name_match or not team_match:
            continue
        team_id = int(team_match.group(1))
        if team_id != int(expected_team_id):
            continue
        abbr_match = abbr_re.search(body)
        row = {
            "player_id": player_id,
            "player_name": name_match.group(1),
            "official_team_id": team_id,
            "team_abbreviation": abbr_match.group(1) if abbr_match else "",
        }
        existing = by_id.get(player_id)
        if existing is not None and existing != row:
            raise ValueError(f"Conflicting WNBA roster identity for player {player_id}")
        by_id[player_id] = row
    return sorted(by_id.values(), key=lambda row: (normalize_player_name(row["player_name"]), row["player_id"]))


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self.capture:
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)


def parse_first_party_player_latest_games_html(
    html: str,
    *,
    expected_player_id: int,
    season: int,
) -> list[dict[str, Any]]:
    """Return observed P/R/A/MIN rows from WNBA.com player.latestGames."""
    parser = _NextDataParser()
    parser.feed(str(html or ""))
    raw = "".join(parser.parts).strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    props = payload.get("props") if isinstance(payload, dict) else None
    page_props = props.get("pageProps") if isinstance(props, dict) else None
    player = page_props.get("player") if isinstance(page_props, dict) else None
    if not isinstance(player, dict):
        return []

    identities = []
    for key in ("playerId", "personId", "id"):
        value = _int(player.get(key))
        if value is not None:
            identities.append(value)
    if identities and any(value != int(expected_player_id) for value in identities):
        return []

    games = player.get("latestGames")
    if not isinstance(games, list):
        return []
    result: list[dict[str, Any]] = []
    for source in games:
        if not isinstance(source, Mapping):
            continue
        season_id = str(source.get("SEASON_ID") or "")
        if season_id and not season_id.endswith(str(int(season))):
            continue
        returned_id = _int(source.get("PLAYER_ID") if "PLAYER_ID" in source else source.get("Player_ID"))
        if returned_id is not None and returned_id != int(expected_player_id):
            continue
        values = {
            "MIN": _minutes(source.get("MIN")),
            "PTS": _num(source.get("PTS")),
            "REB": _num(source.get("REB")),
            "AST": _num(source.get("AST")),
        }
        if all(value is None for value in values.values()):
            continue
        result.append({
            "game_id": str(source.get("Game_ID") or source.get("GAME_ID") or ""),
            "game_date": str(source.get("GAME_DATE") or ""),
            **values,
        })
    return result


def _average_games(games: list[Mapping[str, Any]]) -> dict[str, float] | None:
    if not games:
        return None
    result: dict[str, float] = {}
    for key in ("MIN", "PTS", "REB", "AST"):
        values = [_num(game.get(key)) for game in games]
        values = [value for value in values if value is not None]
        if not values:
            return None
        result[key] = sum(values) / len(values)
    return result


def build_first_party_recent_stat_payloads(
    histories: Iterable[Mapping[str, Any]],
    *,
    season: int,
) -> dict[int, dict[str, Any]]:
    """Build season/L10/L5-shaped payloads from observed WNBA.com recent history.

    The 0-window intentionally means all observed ``latestGames`` rows available
    on the first-party player page; it is not claimed to be full-season history.
    """
    windows: dict[int, list[dict[str, Any]]] = {0: [], 10: [], 5: []}
    for history in histories:
        games = history.get("games") if isinstance(history.get("games"), list) else []
        if not games:
            continue
        for last_n in (0, 10, 5):
            selected = list(games if last_n == 0 else games[:last_n])
            averages = _average_games(selected)
            if averages is None:
                continue
            windows[last_n].append({
                "player_id": int(history["player_id"]),
                "player_name": str(history["player_name"]),
                "official_team_id": int(history["official_team_id"]),
                "team_abbreviation": str(history.get("team_abbreviation") or ""),
                "games_played": len(selected),
                "stats": {
                    "minutes": round(averages["MIN"], 4),
                    "points": round(averages["PTS"], 4),
                    "rebounds": round(averages["REB"], 4),
                    "assists": round(averages["AST"], 4),
                },
            })
    return {
        last_n: {
            "data_type": "official_player_season_statistics",
            "season": int(season),
            "last_n_games": int(last_n),
            "history_scope": "wnba.com player.latestGames recent observed history",
            "player_count": len(players),
            "players": players,
        }
        for last_n, players in windows.items()
    }


__all__ = [
    "TEAM_ROSTER_URLS_BY_ID",
    "build_first_party_recent_stat_payloads",
    "count_zero_production_candidates",
    "hydrate_zero_production_rows",
    "is_zero_production_candidate",
    "normalize_player_name",
    "parse_first_party_player_latest_games_html",
    "parse_first_party_roster_html",
    "roster_url_for_team",
]
