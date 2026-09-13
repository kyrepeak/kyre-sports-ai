"""Read-only ESPN NFL Rushing Yards player + matchup context.

Step 2 only: verified identity, recent rushing workload and opponent run-front
context. No projection, sportsbook market, EV, ranking, staking or wagering.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_SITE_ALTERNATE_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NFL-Rushing/1.0; read-only)",
}
DEFAULT_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 12_000_000
RECENT_GAME_LIMIT = 5
MODEL_VERSION = "nfl_rushing_yards_context_v1"


class NFLRushingYardsContextError(RuntimeError):
    """Raised when exact-ID rushing context cannot be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    text = _text(value).replace(",", "")
    if not text or text in {"--", "-"}:
        return None
    try:
        out = float(text)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _transport_error_label(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {int(exc.code)}"
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        return f"URLError({type(reason).__name__ if reason is not None else 'unknown'})"
    return type(exc).__name__


def _alternate_espn_target(target: str) -> str:
    """Map only the certified ESPN site origin to the equivalent ESPN web origin.

    Path and query string are preserved byte-for-byte. This is a transport
    fallback only; it never changes event/team/athlete identity or data source.
    """
    if not target.startswith(ESPN_SITE_BASE):
        return ""
    return ESPN_SITE_ALTERNATE_BASE + target[len(ESPN_SITE_BASE):]


def _read_espn_bytes(target: str) -> bytes:
    request = Request(target, headers=ESPN_HEADERS, method="GET")
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise NFLRushingYardsContextError(f"ESPN GET returned HTTP {status}")
        return response.read(MAX_RESPONSE_BYTES + 1)


def _get_json(url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    try:
        raw = _read_espn_bytes(target)
    except (HTTPError, URLError, TimeoutError) as primary_exc:
        alternate_target = _alternate_espn_target(target)
        if not alternate_target:
            raise NFLRushingYardsContextError(
                f"ESPN read failed: {_transport_error_label(primary_exc)}"
            ) from primary_exc
        try:
            raw = _read_espn_bytes(alternate_target)
        except (HTTPError, URLError, TimeoutError) as alternate_exc:
            raise NFLRushingYardsContextError(
                "ESPN read failed on both certified transports: "
                f"primary {_transport_error_label(primary_exc)}; "
                f"alternate {_transport_error_label(alternate_exc)}"
            ) from alternate_exc
    except NFLRushingYardsContextError:
        raise
    except Exception as exc:
        raise NFLRushingYardsContextError(f"ESPN read failed: {type(exc).__name__}") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise NFLRushingYardsContextError("ESPN response exceeded safe size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NFLRushingYardsContextError("ESPN response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise NFLRushingYardsContextError("ESPN response was not a JSON object")
    return payload


def _event_identity(summary: dict[str, Any], requested_event_id: str) -> tuple[int, list[dict[str, str]]]:
    header = summary.get("header") or {}
    header_id = _text(header.get("id"))
    if header_id and header_id != requested_event_id:
        raise NFLRushingYardsContextError("official ESPN event identity mismatch")
    competitions = header.get("competitions") or []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    competitors = comp.get("competitors") or []
    teams: list[dict[str, str]] = []
    for row in competitors:
        if not isinstance(row, dict):
            continue
        team = row.get("team") or {}
        team_id = _text(team.get("id"))
        if not team_id.isdigit():
            continue
        teams.append({
            "official_team_id": team_id,
            "team_name": _text(team.get("displayName") or team.get("name")),
            "team_abbreviation": _text(team.get("abbreviation")),
            "home_away": _text(row.get("homeAway")),
        })
    if len(teams) != 2 or len({t["official_team_id"] for t in teams}) != 2:
        raise NFLRushingYardsContextError("exact two-team ESPN event identity unavailable")
    season = header.get("season") or {}
    year = int(season.get("year") or datetime.now(timezone.utc).year)
    return year, teams


def _roster(team_id: str) -> dict[str, dict[str, str]]:
    payload = _get_json(f"{ESPN_SITE_BASE}/teams/{team_id}/roster")
    found: dict[str, dict[str, str]] = {}

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        athlete_id = _text(value.get("id"))
        position = value.get("position") or {}
        pos = _text(position.get("abbreviation") if isinstance(position, dict) else "")
        name = _text(value.get("displayName") or value.get("fullName"))
        if athlete_id.isdigit() and name and pos:
            found[athlete_id] = {
                "official_athlete_id": athlete_id,
                "player_name": name,
                "position": pos,
            }
        for child in value.values():
            if isinstance(child, (dict, list)):
                walk(child)

    walk(payload.get("athletes") or [])
    if not found:
        raise NFLRushingYardsContextError(f"current ESPN roster unavailable for team {team_id}")
    return found


def _completed_game_ids(team_id: str, season: int) -> list[str]:
    payload = _get_json(f"{ESPN_SITE_BASE}/teams/{team_id}/schedule", {"season": season})
    out: list[tuple[str, str]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _text(event.get("id"))
        comps = event.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], dict) else {}
        state = _text((((comp.get("status") or {}).get("type") or {}).get("state"))).lower()
        season_type = int((event.get("season") or {}).get("type") or 0)
        date = _text(event.get("date"))
        if event_id.isdigit() and state == "post" and season_type == 2:
            out.append((date, event_id))
    out.sort(reverse=True)
    return [event_id for _, event_id in out[:RECENT_GAME_LIMIT]]


def _baseline_game_ids(team_id: str, season: int) -> tuple[int, list[str]]:
    current = _completed_game_ids(team_id, season)
    if current:
        return season, current
    prior = _completed_game_ids(team_id, season - 1)
    return season - 1, prior


def _rushing_rows(summary: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    players = ((summary.get("boxscore") or {}).get("players") or [])
    block = next((x for x in players if _text(((x.get("team") or {}).get("id"))) == team_id), None)
    if not isinstance(block, dict):
        return []
    category = next((x for x in block.get("statistics") or [] if _text(x.get("name")).lower() == "rushing"), None)
    if not isinstance(category, dict):
        return []
    labels = [str(x).upper() for x in (category.get("labels") or [])]
    rows: list[dict[str, Any]] = []
    for row in category.get("athletes") or []:
        if not isinstance(row, dict):
            continue
        athlete = row.get("athlete") or {}
        athlete_id = _text(athlete.get("id"))
        stats = row.get("stats") or []
        if not athlete_id.isdigit() or not isinstance(stats, list):
            continue
        values = {label: _number(stats[i]) if i < len(stats) else None for i, label in enumerate(labels)}
        attempts = values.get("CAR")
        yards = values.get("YDS")
        tds = values.get("TD")
        if attempts is None or yards is None:
            continue
        rows.append({"official_athlete_id": athlete_id, "attempts": attempts, "yards": yards, "touchdowns": tds or 0.0})
    return rows


def _team_stat_map(summary: dict[str, Any], team_id: str) -> dict[str, float]:
    teams = ((summary.get("boxscore") or {}).get("teams") or [])
    block = next((x for x in teams if _text(((x.get("team") or {}).get("id"))) == team_id), None)
    out: dict[str, float] = {}
    if not isinstance(block, dict):
        return out
    for row in block.get("statistics") or []:
        if not isinstance(row, dict):
            continue
        name = _text(row.get("name"))
        value = _number(row.get("displayValue") if row.get("displayValue") is not None else row.get("value"))
        if name and value is not None:
            out[name.lower()] = value
    return out


def _summary(event_id: str, memo: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if event_id not in memo:
        memo[event_id] = _get_json(f"{ESPN_SITE_BASE}/summary", {"event": event_id})
    return memo[event_id]


def _player_profiles(team_id: str, season: int, roster: dict[str, dict[str, str]], memo: dict[str, dict[str, Any]]) -> tuple[int, int, list[dict[str, Any]]]:
    baseline_season, game_ids = _baseline_game_ids(team_id, season)
    agg: dict[str, dict[str, float]] = {}
    for game_id in game_ids:
        for row in _rushing_rows(_summary(game_id, memo), team_id):
            athlete_id = row["official_athlete_id"]
            if athlete_id not in roster:
                continue
            slot = agg.setdefault(athlete_id, {"attempts": 0.0, "yards": 0.0, "touchdowns": 0.0, "games": 0.0})
            slot["attempts"] += row["attempts"]
            slot["yards"] += row["yards"]
            slot["touchdowns"] += row["touchdowns"]
            slot["games"] += 1.0
    profiles: list[dict[str, Any]] = []
    for athlete_id, totals in agg.items():
        attempts = int(totals["attempts"])
        if attempts <= 0:
            continue
        games = max(1, int(totals["games"]))
        yards = int(totals["yards"])
        info = roster[athlete_id]
        profiles.append({
            "official_athlete_id": athlete_id,
            "official_team_id": team_id,
            "player_name": info["player_name"],
            "position": info["position"],
            "sample_games": games,
            "carries": attempts,
            "rushing_yards": yards,
            "yards_per_carry": round(yards / attempts, 2),
            "carries_per_game": round(attempts / games, 2),
            "rushing_yards_per_game": round(yards / games, 2),
            "rushing_touchdowns": int(totals["touchdowns"]),
            "baseline_season": baseline_season,
        })
    profiles.sort(key=lambda x: (x["carries_per_game"], x["rushing_yards_per_game"]), reverse=True)
    return baseline_season, len(game_ids), profiles


def _run_front(defense_team_id: str, season: int, memo: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline_season, game_ids = _baseline_game_ids(defense_team_id, season)
    attempts = yards = touchdowns = 0.0
    valid_games = 0
    for game_id in game_ids:
        game = _summary(game_id, memo)
        header = game.get("header") or {}
        comps = header.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], dict) else {}
        competitors = comp.get("competitors") or []
        opponent_ids = [_text(((x.get("team") or {}).get("id"))) for x in competitors if _text(((x.get("team") or {}).get("id"))) != defense_team_id]
        opponent_id = next((x for x in opponent_ids if x.isdigit()), "")
        if not opponent_id:
            continue
        stats = _team_stat_map(game, opponent_id)
        att = stats.get("rushingattempts")
        yds = stats.get("rushingyards")
        td = stats.get("rushingtouchdowns", 0.0)
        if att is None or yds is None:
            continue
        attempts += att
        yards += yds
        touchdowns += td
        valid_games += 1
    if valid_games == 0 or attempts <= 0:
        return {
            "baseline_season": baseline_season,
            "sample_games": 0,
            "rush_attempts_allowed_per_game": None,
            "rush_yards_allowed_per_game": None,
            "yards_per_carry_allowed": None,
            "rushing_touchdowns_allowed_per_game": None,
            "data_available": False,
        }
    return {
        "baseline_season": baseline_season,
        "sample_games": valid_games,
        "rush_attempts_allowed_per_game": round(attempts / valid_games, 2),
        "rush_yards_allowed_per_game": round(yards / valid_games, 2),
        "yards_per_carry_allowed": round(yards / attempts, 2),
        "rushing_touchdowns_allowed_per_game": round(touchdowns / valid_games, 2),
        "data_available": True,
    }


def collect_nfl_rushing_yards_context(event_id: str) -> dict[str, Any]:
    event_id = _text(event_id)
    if not event_id.isdigit():
        raise NFLRushingYardsContextError("event_id must be an official numeric ESPN NFL event ID")
    memo: dict[str, dict[str, Any]] = {}
    event = _summary(event_id, memo)
    season, teams = _event_identity(event, event_id)
    team_ids = [row["official_team_id"] for row in teams]
    team_blocks: list[dict[str, Any]] = []
    total_profiles = 0
    for row in teams:
        team_id = row["official_team_id"]
        opponent_id = next(x for x in team_ids if x != team_id)
        roster = _roster(team_id)
        baseline_season, sample_games, profiles = _player_profiles(team_id, season, roster, memo)
        total_profiles += len(profiles)
        team_blocks.append({
            **row,
            "opponent_official_team_id": opponent_id,
            "player_baseline_season": baseline_season,
            "player_sample_games": sample_games,
            "players": profiles,
            "opponent_run_front": {
                "official_team_id": opponent_id,
                **_run_front(opponent_id, season, memo),
            },
        })
    return {
        "schema_version": MODEL_VERSION,
        "ready": total_profiles > 0,
        "official_event_id": event_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "official_authority": "ESPN",
        "season": season,
        "teams": team_blocks,
        "identity": {
            "official_event_id_required": True,
            "official_athlete_id_required": True,
            "official_team_id_required": True,
            "player_name_display_only": True,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
        "source_note": "Recent completed regular-season ESPN game books; if the current season has no completed games, the prior regular season is used as an explicitly labeled baseline and current-roster exact athlete IDs remain authoritative.",
    }


__all__ = ["MODEL_VERSION", "NFLRushingYardsContextError", "collect_nfl_rushing_yards_context"]