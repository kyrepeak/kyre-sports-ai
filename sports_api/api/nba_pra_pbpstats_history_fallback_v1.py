"""Kyre Sports API NBA PRA PBP Stats history fallback V1.

Field-specific server-side fallback only. Existing verified player history remains
primary. PBP Stats is consulted only for requested players whose production
profile still has no verified current/prior game history after the existing
NBA/Basketball-Reference/CBS routing chain.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any, Callable, Mapping, Sequence

import httpx

VERSION = "KYRE_NBA_PRA_PBPSTATS_HISTORY_FALLBACK_V1"
PBP_ROOT = "https://api.pbpstats.com"
HEADERS = {"User-Agent": "KyreSportsAPI/1.0", "Accept": "application/json"}
TEAM_ALIASES = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "PHO": "PHX"}


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _team(value: Any) -> str:
    code = _text(value).upper()
    return TEAM_ALIASES.get(code, code)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _minutes(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = _text(value)
    if not text:
        return None
    if ":" in text:
        left, right = text.split(":", 1)
        try:
            return float(left) + float(right) / 60.0
        except ValueError:
            return None
    return _number(text)


def _season_labels(day: date) -> tuple[str, str]:
    end_year = day.year + 1 if day.month >= 10 else day.year
    current = f"{end_year - 1}-{str(end_year)[-2:]}"
    prior_end = end_year - 1
    prior = f"{prior_end - 1}-{str(prior_end)[-2:]}"
    return current, prior


def _identity_index(payload: Mapping[str, Any]) -> dict[str, str]:
    players = payload.get("players") if isinstance(payload, Mapping) else None
    if not isinstance(players, Mapping):
        return {}
    out: dict[str, str] = {}
    for raw_id, raw_name in players.items():
        key = _norm(raw_name)
        player_id = _text(raw_id)
        if not key or not player_id:
            continue
        old = out.get(key)
        if old is None:
            out[key] = player_id
            continue
        try:
            if int(player_id) > int(old):
                out[key] = player_id
        except ValueError:
            pass
    return out


def _parse_game_logs(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_rows = payload.get("multi_row_table_data") if isinstance(payload, Mapping) else None
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        game_date = _text(raw.get("Date"))
        opponent = _team(raw.get("Opponent"))
        minutes = _minutes(raw.get("Minutes"))
        points = _number(raw.get("Points"))
        rebounds = _number(raw.get("Rebounds"))
        assists = _number(raw.get("Assists"))
        if not game_date or not opponent or minutes is None or points is None or rebounds is None or assists is None:
            continue
        rows.append({
            "game_date": game_date,
            "team": _team(raw.get("Team")),
            "opponent": opponent,
            "minutes": minutes,
            "points": points,
            "rebounds": rebounds,
            "assists": assists,
            "pra": points + rebounds + assists,
        })
    rows.sort(key=lambda row: row["game_date"], reverse=True)
    return rows[:40]


def _get_json(path: str, *, params: Mapping[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(timeout, connect=3.0), follow_redirects=True) as client:
        response = client.get(f"{PBP_ROOT}{path}", params=dict(params or {}))
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("PBPSTATS_PAYLOAD_INVALID")
    return payload


@lru_cache(maxsize=1)
def _live_identity_index() -> dict[str, str]:
    return _identity_index(_get_json("/get-all-players-for-league/nba"))


def _live_history(season: str, player_id: str) -> dict[str, Any]:
    return _get_json(
        "/get-game-logs/nba",
        params={
            "Season": season,
            "SeasonType": "Regular Season",
            "EntityType": "Player",
            "EntityId": player_id,
        },
        timeout=12.0,
    )


def install(base: Any) -> Any:
    """Install an additive fallback around the currently active production collector."""
    prior_collect = base.collect_nba_pra_player_context

    def collect_nba_pra_player_context(
        slate_date: date,
        player_names: Sequence[str],
        *,
        pbp_identity_loader: Callable[[], Mapping[str, str]] | None = None,
        pbp_history_loader: Callable[[str, str], Mapping[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = prior_collect(slate_date, player_names, **kwargs)
        profiles = result.get("profiles") if isinstance(result.get("profiles"), dict) else {}
        names = [_text(name) for name in player_names if _text(name)]
        missing = []
        for name in names:
            profile = profiles.get(_norm(name))
            if not isinstance(profile, dict):
                continue
            if not (profile.get("current_games") or profile.get("prior_games")):
                missing.append(name)

        health = result.setdefault("provider_health", {})
        if not missing:
            health["pbpstats_history"] = base._health("HEALTHY", "NOT_NEEDED", False)
            result["schema_version"] = "KYRE_NBA_PLAYER_CONTEXT_V4"
            return result

        try:
            identity = dict((pbp_identity_loader or _live_identity_index)())
        except Exception as exc:
            health["pbpstats_history"] = base._health("DEGRADED", f"IDENTITY_{type(exc).__name__}", True)
            result["schema_version"] = "KYRE_NBA_PLAYER_CONTEXT_V4"
            return result

        history_loader = pbp_history_loader or _live_history
        current_season, prior_season = _season_labels(slate_date)
        resolved = 0
        errors: list[str] = []
        for name in missing:
            key = _norm(name)
            profile = profiles.get(key)
            if not isinstance(profile, dict):
                continue
            player_id = _text(identity.get(key))
            if not player_id:
                errors.append(f"{key}:IDENTITY_MISSING")
                continue
            try:
                current_rows = _parse_game_logs(history_loader(current_season, player_id))
                prior_rows = _parse_game_logs(history_loader(prior_season, player_id))
            except Exception as exc:
                errors.append(f"{key}:{type(exc).__name__}")
                continue
            if not current_rows and not prior_rows:
                errors.append(f"{key}:NO_GAME_LOGS")
                continue
            provider_ids = dict(profile.get("provider_ids") or {})
            provider_ids["nba"] = player_id
            provider_ids["pbpstats"] = player_id
            profile["provider_ids"] = provider_ids
            profile["current_games"] = current_rows
            profile["prior_games"] = prior_rows
            if not _text(profile.get("team")):
                first = (current_rows or prior_rows)[0]
                profile["team"] = _team(first.get("team"))
            profile["data_state"] = "VERIFIED"
            profile["stats_source"] = "PBP Stats"
            resolved += 1

        status = "HEALTHY" if resolved == len(missing) else "DEGRADED"
        detail = f"RESOLVED_{resolved}_OF_{len(missing)}"
        if errors:
            detail += ":" + ":".join(errors[:8])
        health["pbpstats_history"] = base._health(status, detail, True)

        verified = sum(1 for row in profiles.values() if isinstance(row, Mapping) and row.get("data_state") == "VERIFIED")
        identified = sum(1 for row in profiles.values() if isinstance(row, Mapping) and row.get("data_state") in {"VERIFIED", "IDENTITY_ONLY"})
        result["verification"] = "VERIFIED" if names and verified == len(names) else "PARTIAL" if identified else "DATA_UNAVAILABLE"
        result["schema_version"] = "KYRE_NBA_PLAYER_CONTEXT_V4"
        return result

    base.collect_nba_pra_player_context = collect_nba_pra_player_context
    return base
