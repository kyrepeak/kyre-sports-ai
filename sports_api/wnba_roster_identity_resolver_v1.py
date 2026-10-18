"""Resilient exact WNBA roster identity for sportsbook prop normalization.

Official WNBA/Kyre player IDs remain canonical. If the live official roster
transport fails, a fresh durable snapshot of a previously verified official
roster may be used only after exact current ESPN name+team corroboration.
ESPN IDs never replace canonical official IDs and fuzzy matching is forbidden.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import unicodedata
from typing import Any, Callable, Mapping

import httpx

from sports_api.wnba_rosters import WNBAStatsUpstreamError, get_current_players_dataset

ROSTER_CACHE_KEY = "wnba/fanduel/canonical-roster-v1.json"
ROSTER_CACHE_TTL_SECONDS = 3600
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team}/roster"
ESPN_TIMEOUT_SECONDS = 8.0
TEAM_SLUGS = {
    "dream": "atl", "sky": "chi", "sun": "con", "wings": "dal",
    "valkyries": "gs", "fever": "ind", "aces": "lv", "sparks": "la",
    "lynx": "min", "liberty": "ny", "mercury": "phx", "storm": "sea",
    "mystics": "wsh", "fire": "por", "tempo": "tor",
}

class WNBARosterIdentityError(RuntimeError):
    pass

class WNBARosterIdentityNotReadyError(WNBARosterIdentityError):
    pass

def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return current.astimezone(timezone.utc)

def _name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("’", "").replace("'", "")
    return " ".join(re.findall(r"[a-z0-9]+", text))

def _iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)

def _playable_team_keys(playable_games: list[dict[str, Any]]) -> tuple[str, ...]:
    keys = []
    for game in playable_games or []:
        if not isinstance(game, Mapping):
            continue
        for side in ("away", "home"):
            team = game.get(side)
            key = str((team or {}).get("team_key") or "").strip() if isinstance(team, Mapping) else ""
            if key and key not in keys:
                keys.append(key)
    return tuple(keys)

def _validate_official(payload: Mapping[str, Any], season: int) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or int(payload.get("season", -1)) != int(season):
        raise WNBARosterIdentityNotReadyError("official roster payload is malformed or wrong season")
    players = payload.get("players")
    if not isinstance(players, list):
        raise WNBARosterIdentityNotReadyError("official roster player list is missing")
    rows = []
    for raw in players:
        if not isinstance(raw, Mapping):
            continue
        try:
            player_id = int(raw.get("player_id"))
        except (TypeError, ValueError):
            continue
        full_name = str(raw.get("full_name") or "").strip()
        team_key = str(raw.get("team_key") or "").strip()
        if player_id <= 0 or not full_name or not team_key:
            continue
        row = dict(raw)
        row.update(player_id=player_id, full_name=full_name, team_key=team_key)
        rows.append(row)
    if not rows:
        raise WNBARosterIdentityNotReadyError("official roster contains no usable canonical players")
    return rows

def _default_storage():
    try:
        from sports_api.wnba_step6r_supabase_storage import build_step6r_durable_storage
        return build_step6r_durable_storage()
    except Exception:
        return None

def _cache_payload(season: int, players: list[dict[str, Any]], now: datetime) -> bytes:
    return json.dumps({
        "schema_version": 1, "season": int(season), "stored_at_utc": now.isoformat(),
        "source": "WNBA Stats API", "players": players,
    }, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

def _read_cache(storage, season: int, now: datetime) -> list[dict[str, Any]]:
    if storage is None:
        raise WNBARosterIdentityNotReadyError("durable canonical roster cache is unavailable")
    try:
        raw = storage.read_bytes(ROSTER_CACHE_KEY)
    except Exception as exc:
        raise WNBARosterIdentityNotReadyError("durable canonical roster cache is missing") from exc
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise WNBARosterIdentityNotReadyError("durable canonical roster cache is malformed") from exc
    stored = _iso(body.get("stored_at_utc") if isinstance(body, Mapping) else None)
    if stored is None:
        raise WNBARosterIdentityNotReadyError("durable canonical roster cache has no valid timestamp")
    if max(0.0, (now - stored).total_seconds()) > ROSTER_CACHE_TTL_SECONDS:
        raise WNBARosterIdentityNotReadyError("durable canonical roster cache is stale")
    return _validate_official(body, season)

def _flatten_athletes(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("athletes") or (payload.get("team") or {}).get("athletes") or []
    stack = list(raw) if isinstance(raw, list) else []
    out = []
    while stack:
        item = stack.pop(0)
        if not isinstance(item, Mapping):
            continue
        nested = item.get("items") or item.get("athletes")
        if isinstance(nested, list):
            stack[0:0] = nested
            continue
        athlete = item.get("athlete") if isinstance(item.get("athlete"), Mapping) else item
        name = str(athlete.get("displayName") or athlete.get("fullName") or "").strip()
        if name:
            out.append({"full_name": name})
    return out

def _default_espn_roster_getter(team_key: str, season: int) -> list[dict[str, Any]]:
    del season
    slug = TEAM_SLUGS.get(str(team_key or "").strip())
    if not slug:
        return []
    try:
        response = httpx.get(ESPN_ROSTER_URL.format(team=slug), headers={"accept":"application/json","user-agent":"KyreSportsAPI-WNBA-identity/1"}, timeout=ESPN_TIMEOUT_SECONDS, follow_redirects=False)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    if not isinstance(payload, Mapping):
        return []
    return [{**row, "team_key": team_key} for row in _flatten_athletes(payload)]

def resolve_verified_roster(
    season: int,
    playable_games: list[dict[str, Any]],
    *,
    primary_getter: Callable[..., dict[str, Any]] = get_current_players_dataset,
    storage=None,
    espn_roster_getter: Callable[[str, int], list[dict[str, Any]]] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    current = _now(now_utc)
    resolved_storage = storage
    try:
        official = primary_getter(int(season), current_roster_only=True)
        players = _validate_official(official, season)
        for row in players:
            row["identity_source"] = "OFFICIAL_PRIMARY"
        if resolved_storage is None:
            resolved_storage = _default_storage()
        if resolved_storage is not None:
            try:
                resolved_storage.write_bytes_atomic(ROSTER_CACHE_KEY, _cache_payload(season, players, current))
            except Exception:
                pass
        return {
            **dict(official), "season": int(season), "players": players,
            "player_count": len(players),
            "retrieved_at_utc": official.get("retrieved_at_utc") or current.isoformat(),
            "resolution": {"mode":"OFFICIAL_PRIMARY","accepted_player_count":len(players),"rejected_player_count":0},
        }
    except WNBAStatsUpstreamError as primary_exc:
        primary_error = str(primary_exc)
    if resolved_storage is None:
        resolved_storage = _default_storage()
    cached = _read_cache(resolved_storage, season, current)
    team_keys = set(_playable_team_keys(playable_games))
    if not team_keys:
        raise WNBARosterIdentityNotReadyError("no playable teams are available for roster corroboration")
    corroborator = espn_roster_getter or _default_espn_roster_getter
    live_names = {}
    source_errors = []
    for team_key in sorted(team_keys):
        try:
            rows = corroborator(team_key, int(season)) or []
        except Exception as exc:
            rows = []
            source_errors.append(f"{team_key}:{type(exc).__name__}")
        names = {_name_key(row.get("full_name") or row.get("displayName") or row.get("fullName")) for row in rows if isinstance(row, Mapping)}
        live_names[team_key] = {name for name in names if name}
    groups = {}
    for row in cached:
        team_key = str(row.get("team_key") or "").strip()
        if team_key not in team_keys:
            continue
        name = _name_key(row.get("full_name"))
        if name:
            groups.setdefault((team_key, name), []).append(row)
    accepted = []
    rejected = 0
    for (team_key, name), rows in groups.items():
        if len(rows) != 1 or name not in live_names.get(team_key, set()):
            rejected += len(rows)
            continue
        row = dict(rows[0])
        row["identity_source"] = "DURABLE_OFFICIAL_ID+ESPN_CURRENT_MEMBERSHIP"
        accepted.append(row)
    if not accepted:
        raise WNBARosterIdentityNotReadyError("cached official roster has no exact current ESPN-corroborated players")
    return {
        "source":"fresh durable official WNBA roster + ESPN current membership corroboration",
        "season":int(season), "current_roster_only":True, "retrieved_at_utc":current.isoformat(),
        "players":accepted, "player_count":len(accepted),
        "resolution":{"mode":"DURABLE_OFFICIAL_PLUS_ESPN_CORROBORATION","primary_error":primary_error,"accepted_player_count":len(accepted),"rejected_player_count":rejected,"corroboration_source_errors":source_errors},
    }

__all__ = ["ROSTER_CACHE_KEY","ROSTER_CACHE_TTL_SECONDS","WNBARosterIdentityError","WNBARosterIdentityNotReadyError","resolve_verified_roster"]
