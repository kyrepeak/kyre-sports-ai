"""Read-only ESPN NFL Receiving Yards player + matchup context.

Receiving context only: verified event/team/athlete identity, recent receiving
workload and opponent pass-defense context. No projection, sportsbook market,
EV, ranking, staking or wagering. Targets are exposed only when ESPN explicitly
publishes a target column in the receiving game book.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NFL-Receiving/1.0; read-only)",
}
DEFAULT_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 12_000_000
RECENT_GAME_LIMIT = 5
MAX_PARALLEL_ESPN_REQUESTS = 6
MODEL_VERSION = "nfl_receiving_yards_context_v1"
ELIGIBLE_RECEIVER_POSITIONS = frozenset({"WR", "TE", "RB", "FB"})
TARGET_LABELS = ("TGTS", "TGT", "TARGETS")


class NFLReceivingYardsContextError(RuntimeError):
    """Raised when exact-ID receiving context cannot be proven safely."""


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
    """Map only the certified ESPN site origin to its equivalent web origin."""
    if not target.startswith(ESPN_SITE_BASE):
        return ""
    return ESPN_SITE_ALTERNATE_BASE + target[len(ESPN_SITE_BASE):]


def _read_espn_bytes(target: str) -> bytes:
    request = Request(target, headers=ESPN_HEADERS, method="GET")
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise NFLReceivingYardsContextError(f"ESPN GET returned HTTP {status}")
        return response.read(MAX_RESPONSE_BYTES + 1)


def _get_json(url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    try:
        raw = _read_espn_bytes(target)
    except (HTTPError, URLError, TimeoutError) as primary_exc:
        alternate_target = _alternate_espn_target(target)
        if not alternate_target:
            raise NFLReceivingYardsContextError(
                f"ESPN read failed: {_transport_error_label(primary_exc)}"
            ) from primary_exc
        try:
            raw = _read_espn_bytes(alternate_target)
        except (HTTPError, URLError, TimeoutError) as alternate_exc:
            raise NFLReceivingYardsContextError(
                "ESPN read failed on both certified transports: "
                f"primary {_transport_error_label(primary_exc)}; "
                f"alternate {_transport_error_label(alternate_exc)}"
            ) from alternate_exc
    except NFLReceivingYardsContextError:
        raise
    except Exception as exc:
        raise NFLReceivingYardsContextError(f"ESPN read failed: {type(exc).__name__}") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise NFLReceivingYardsContextError("ESPN response exceeded safe size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NFLReceivingYardsContextError("ESPN response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise NFLReceivingYardsContextError("ESPN response was not a JSON object")
    return payload


def _event_identity(summary: dict[str, Any], requested_event_id: str) -> tuple[int, list[dict[str, str]]]:
    header = summary.get("header") or {}
    header_id = _text(header.get("id"))
    if header_id and header_id != requested_event_id:
        raise NFLReceivingYardsContextError("official ESPN event identity mismatch")
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
        raise NFLReceivingYardsContextError("exact two-team ESPN event identity unavailable")
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
        pos = _text(position.get("abbreviation") if isinstance(position, dict) else "").upper()
        name = _text(value.get("displayName") or value.get("fullName"))
        if athlete_id.isdigit() and name and pos in ELIGIBLE_RECEIVER_POSITIONS:
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
        raise NFLReceivingYardsContextError(f"current ESPN receiving roster unavailable for team {team_id}")
    return found


def _completed_game_ids(team_id: str, season: int) -> list[str]:
    """Return recent completed regular-season ESPN event IDs for one exact season."""
    payload = _get_json(
        f"{ESPN_SITE_BASE}/teams/{team_id}/schedule",
        {"season": season, "seasontype": 2},
    )
    out: list[tuple[str, str]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _text(event.get("id"))
        event_season = event.get("season") or {}
        season_type = event.get("seasonType") or {}
        try:
            event_year = int(event_season.get("year") or 0)
        except (TypeError, ValueError):
            event_year = 0
        try:
            event_season_type = int(season_type.get("type") or season_type.get("id") or 0)
        except (TypeError, ValueError):
            event_season_type = 0
        comps = event.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], dict) else {}
        status_type = (comp.get("status") or {}).get("type") or {}
        state = _text(status_type.get("state")).lower()
        completed = status_type.get("completed") is True
        date = _text(event.get("date"))
        if (
            event_id.isdigit()
            and event_year == int(season)
            and event_season_type == 2
            and state == "post"
            and completed
        ):
            out.append((date, event_id))
    out.sort(reverse=True)
    return [event_id for _, event_id in out[:RECENT_GAME_LIMIT]]


def _baseline_game_ids(team_id: str, season: int) -> tuple[int, list[str]]:
    current = _completed_game_ids(team_id, season)
    if current:
        return season, current
    prior = _completed_game_ids(team_id, season - 1)
    return season - 1, prior


def _receiving_rows(summary: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    players = ((summary.get("boxscore") or {}).get("players") or [])
    block = next(
        (x for x in players if _text(((x.get("team") or {}).get("id"))) == team_id),
        None,
    )
    if not isinstance(block, dict):
        return []
    category = next(
        (x for x in block.get("statistics") or [] if _text(x.get("name")).lower() == "receiving"),
        None,
    )
    if not isinstance(category, dict):
        return []
    labels = [str(x).upper() for x in (category.get("labels") or [])]
    target_label = next((label for label in TARGET_LABELS if label in labels), None)
    rows: list[dict[str, Any]] = []
    for row in category.get("athletes") or []:
        if not isinstance(row, dict):
            continue
        athlete = row.get("athlete") or {}
        athlete_id = _text(athlete.get("id"))
        stats = row.get("stats") or []
        if not athlete_id.isdigit() or not isinstance(stats, list):
            continue
        values = {
            label: _number(stats[i]) if i < len(stats) else None
            for i, label in enumerate(labels)
        }
        receptions = values.get("REC")
        yards = values.get("YDS")
        touchdowns = values.get("TD")
        targets = values.get(target_label) if target_label else None
        if receptions is None or yards is None:
            continue
        rows.append({
            "official_athlete_id": athlete_id,
            "receptions": receptions,
            "yards": yards,
            "touchdowns": touchdowns or 0.0,
            "targets": targets,
            "targets_explicit": target_label is not None and targets is not None,
        })
    return rows


def _summary(event_id: str, memo: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if event_id not in memo:
        memo[event_id] = _get_json(f"{ESPN_SITE_BASE}/summary", {"event": event_id})
    return memo[event_id]


def _player_profiles_from_games(
    team_id: str,
    baseline_season: int,
    game_ids: list[str],
    roster: dict[str, dict[str, str]],
    memo: dict[str, dict[str, Any]],
) -> tuple[int, int, list[dict[str, Any]]]:
    agg: dict[str, dict[str, float]] = {}
    for game_id in game_ids:
        for row in _receiving_rows(_summary(game_id, memo), team_id):
            athlete_id = row["official_athlete_id"]
            if athlete_id not in roster:
                continue
            slot = agg.setdefault(
                athlete_id,
                {
                    "receptions": 0.0,
                    "yards": 0.0,
                    "touchdowns": 0.0,
                    "games": 0.0,
                    "targets": 0.0,
                    "target_games": 0.0,
                },
            )
            slot["receptions"] += row["receptions"]
            slot["yards"] += row["yards"]
            slot["touchdowns"] += row["touchdowns"]
            slot["games"] += 1.0
            if row["targets_explicit"]:
                slot["targets"] += float(row["targets"])
                slot["target_games"] += 1.0

    profiles: list[dict[str, Any]] = []
    for athlete_id, totals in agg.items():
        receptions = int(totals["receptions"])
        if receptions <= 0:
            continue
        games = max(1, int(totals["games"]))
        yards = int(totals["yards"])
        target_games = int(totals["target_games"])
        explicit_targets = int(totals["targets"]) if target_games > 0 else None
        info = roster[athlete_id]
        profiles.append({
            "official_athlete_id": athlete_id,
            "official_team_id": team_id,
            "player_name": info["player_name"],
            "position": info["position"],
            "sample_games": games,
            "receptions": receptions,
            "receiving_yards": yards,
            "yards_per_reception": round(yards / receptions, 2),
            "receptions_per_game": round(receptions / games, 2),
            "receiving_yards_per_game": round(yards / games, 2),
            "receiving_touchdowns": int(totals["touchdowns"]),
            "targets_data_available": target_games > 0,
            "target_sample_games": target_games,
            "targets": explicit_targets,
            "targets_per_game": (
                round(explicit_targets / target_games, 2)
                if explicit_targets is not None and target_games > 0
                else None
            ),
            "baseline_season": baseline_season,
        })
    profiles.sort(
        key=lambda x: (x["receiving_yards_per_game"], x["receptions_per_game"]),
        reverse=True,
    )
    return baseline_season, len(game_ids), profiles


def _pass_defense_from_games(
    defense_team_id: str,
    baseline_season: int,
    game_ids: list[str],
    memo: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    receptions = yards = touchdowns = 0.0
    valid_games = 0
    targets = 0.0
    target_games = 0

    for game_id in game_ids:
        game = _summary(game_id, memo)
        header = game.get("header") or {}
        comps = header.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], dict) else {}
        competitors = comp.get("competitors") or []
        opponent_ids = [
            _text(((x.get("team") or {}).get("id")))
            for x in competitors
            if _text(((x.get("team") or {}).get("id"))) != defense_team_id
        ]
        opponent_id = next((x for x in opponent_ids if x.isdigit()), "")
        if not opponent_id:
            continue
        rows = _receiving_rows(game, opponent_id)
        if not rows:
            continue

        game_receptions = sum(float(row["receptions"]) for row in rows)
        game_yards = sum(float(row["yards"]) for row in rows)
        game_touchdowns = sum(float(row["touchdowns"]) for row in rows)
        receptions += game_receptions
        yards += game_yards
        touchdowns += game_touchdowns
        valid_games += 1

        # Target context is considered complete for a game only when ESPN
        # explicitly supplied targets on every receiving row used above.
        if all(row["targets_explicit"] for row in rows):
            targets += sum(float(row["targets"]) for row in rows)
            target_games += 1

    if valid_games == 0 or receptions <= 0:
        return {
            "baseline_season": baseline_season,
            "sample_games": 0,
            "receptions_allowed_per_game": None,
            "receiving_yards_allowed_per_game": None,
            "yards_per_reception_allowed": None,
            "receiving_touchdowns_allowed_per_game": None,
            "targets_data_available": False,
            "target_sample_games": 0,
            "targets_allowed_per_game": None,
            "data_available": False,
        }

    return {
        "baseline_season": baseline_season,
        "sample_games": valid_games,
        "receptions_allowed_per_game": round(receptions / valid_games, 2),
        "receiving_yards_allowed_per_game": round(yards / valid_games, 2),
        "yards_per_reception_allowed": round(yards / receptions, 2),
        "receiving_touchdowns_allowed_per_game": round(touchdowns / valid_games, 2),
        "targets_data_available": target_games > 0,
        "target_sample_games": target_games,
        "targets_allowed_per_game": round(targets / target_games, 2) if target_games > 0 else None,
        "data_available": True,
    }


def _parallel_team_inputs(
    team_ids: list[str],
    season: int,
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, tuple[int, list[str]]]]:
    """Fetch independent current-roster + schedule-baseline inputs concurrently."""
    rosters: dict[str, dict[str, dict[str, str]]] = {}
    baselines: dict[str, tuple[int, list[str]]] = {}
    workers = max(1, min(MAX_PARALLEL_ESPN_REQUESTS, len(team_ids) * 2))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nfl-recv-input") as pool:
        roster_futures = {team_id: pool.submit(_roster, team_id) for team_id in team_ids}
        baseline_futures = {
            team_id: pool.submit(_baseline_game_ids, team_id, season)
            for team_id in team_ids
        }
        for team_id in team_ids:
            rosters[team_id] = roster_futures[team_id].result()
            baselines[team_id] = baseline_futures[team_id].result()
    return rosters, baselines


def _prefetch_summaries(game_ids: list[str], memo: dict[str, dict[str, Any]]) -> None:
    """Fetch each unique ESPN game book once with bounded concurrency."""
    pending = list(
        dict.fromkeys(
            game_id for game_id in game_ids if game_id.isdigit() and game_id not in memo
        )
    )
    if not pending:
        return
    workers = max(1, min(MAX_PARALLEL_ESPN_REQUESTS, len(pending)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nfl-recv-summary") as pool:
        futures = {
            game_id: pool.submit(
                _get_json,
                f"{ESPN_SITE_BASE}/summary",
                {"event": game_id},
            )
            for game_id in pending
        }
        fetched = {game_id: futures[game_id].result() for game_id in pending}
    memo.update(fetched)


def collect_nfl_receiving_yards_context(event_id: str) -> dict[str, Any]:
    event_id = _text(event_id)
    if not event_id.isdigit():
        raise NFLReceivingYardsContextError(
            "event_id must be an official numeric ESPN NFL event ID"
        )

    memo: dict[str, dict[str, Any]] = {}
    event = _summary(event_id, memo)
    season, teams = _event_identity(event, event_id)
    team_ids = [row["official_team_id"] for row in teams]

    rosters, baselines = _parallel_team_inputs(team_ids, season)

    all_game_ids: list[str] = []
    for team_id in team_ids:
        all_game_ids.extend(baselines[team_id][1])
    _prefetch_summaries(all_game_ids, memo)

    team_blocks: list[dict[str, Any]] = []
    total_profiles = 0
    for row in teams:
        team_id = row["official_team_id"]
        opponent_id = next(x for x in team_ids if x != team_id)
        baseline_season, game_ids = baselines[team_id]
        _, sample_games, profiles = _player_profiles_from_games(
            team_id,
            baseline_season,
            game_ids,
            rosters[team_id],
            memo,
        )
        total_profiles += len(profiles)

        opponent_baseline_season, opponent_game_ids = baselines[opponent_id]
        team_blocks.append({
            **row,
            "opponent_official_team_id": opponent_id,
            "player_baseline_season": baseline_season,
            "player_sample_games": sample_games,
            "players": profiles,
            "opponent_pass_defense": {
                "official_team_id": opponent_id,
                **_pass_defense_from_games(
                    opponent_id,
                    opponent_baseline_season,
                    opponent_game_ids,
                    memo,
                ),
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
            "targets_inferred": False,
        },
        "source_note": (
            "Recent completed regular-season ESPN game books; if the current season has no "
            "completed games, the prior regular season is used as an explicitly labeled "
            "baseline. Current-roster ESPN athlete IDs remain authoritative. Targets are "
            "included only when explicitly published by ESPN in the receiving table."
        ),
    }


__all__ = [
    "ELIGIBLE_RECEIVER_POSITIONS",
    "MODEL_VERSION",
    "NFLReceivingYardsContextError",
    "collect_nfl_receiving_yards_context",
]
