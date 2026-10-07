"""WNBA PRA Game Center hosted-stat hydration adapter.

Pure-Python adapter used only by the WNBA PRA Game Center. It repairs rows that
are known roster-only/zero-production fallbacks by matching them to the hosted
Kyre Sports API official WNBA season/L10/L5 statistics. Existing observed
production is never overwritten.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Iterable, Mapping


ZERO_SOURCE_MARKERS = (
    "no matched production row",
    "no completed-game rows",
    "no completed-game stats",
)


def _norm_name(value: Any) -> str:
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
        name = _norm_name(item.get("player_name"))
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
        name = _norm_name(row.get("PLAYER_NAME"))
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
        row["DATA_SOURCE"] = "Kyre Sports API • official WNBA Stats season/L10/L5"
        row["PLAYER_ID_SOURCE"] = "WNBA Stats via Kyre Sports API"
        hydrated += 1
        result.append(row)

    return result, {"candidates": candidates, "hydrated": hydrated, "unresolved": unresolved}


__all__ = [
    "count_zero_production_candidates",
    "hydrate_zero_production_rows",
    "is_zero_production_candidate",
]
