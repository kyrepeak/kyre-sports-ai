"""Step 9B read-only official MLB live-game-state collector.

The collector talks only to MLB Stats API over HTTPS GET. Official ``gamePk`` is
the only game identity; no team/player name matching or synthetic IDs are used.
"""

from __future__ import annotations

from datetime import date as date_type, datetime, timezone
import json
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_LIVE_FEED_URLS = (
    "https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live",
    "https://statsapi.mlb.com/api/v1/game/{game_id}/feed/live",
)
SOURCE = "MLB Stats API"
TRANSPORT = "HTTPS GET"
HTTP_METHODS = ("GET",)
DEFAULT_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 25_000_000

PREGAME = "PREGAME"
LIVE = "LIVE"
DELAYED = "DELAYED"
FINAL = "FINAL"


class MLBLiveGameStateCollectorError(RuntimeError):
    """Raised when official MLB live state cannot be normalized safely."""


def _strict_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text and text.isascii() and text.isdecimal():
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def _strict_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text and text.isascii() and text.isdecimal():
            return int(text)
    return None


def _get_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    full_url = f"{url}?{query}" if query else url
    request = Request(
        full_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "KyreSportsAPI-MLB-LiveState/1.0 (read-only)",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise MLBLiveGameStateCollectorError(f"GET {url} returned HTTP {status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise MLBLiveGameStateCollectorError(
            f"GET {url} exceeded {MAX_RESPONSE_BYTES} bytes"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MLBLiveGameStateCollectorError(
            f"GET {url} did not return valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise MLBLiveGameStateCollectorError(f"GET {url} did not return a JSON object")
    return payload


def fetch_mlb_live_schedule(
    slate_date: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        MLB_SCHEDULE_URL,
        {
            "sportId": 1,
            "date": slate_date,
            "hydrate": "linescore,team,probablePitcher",
        },
        timeout=timeout,
    )


def fetch_mlb_live_feed(
    official_game_id: int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    game_id = _strict_positive_int(official_game_id)
    if game_id is None:
        raise MLBLiveGameStateCollectorError("official_game_id must be a positive integer")
    last_error: Exception | None = None
    for template in MLB_LIVE_FEED_URLS:
        try:
            return _get_json(template.format(game_id=game_id), timeout=timeout)
        except Exception as exc:
            last_error = exc
    raise MLBLiveGameStateCollectorError(
        f"official MLB live feed unavailable for game {game_id}"
    ) from last_error


def canonical_live_state(status: Any) -> str:
    text = str(status or "Unknown")
    low = text.casefold()
    if any(token in low for token in ("final", "game over", "completed")):
        return FINAL
    if any(
        token in low
        for token in ("in progress", "live", "warmup", "manager challenge", "review")
    ):
        return LIVE
    if "delayed" in low:
        return DELAYED
    return PREGAME


def _name(obj: Any) -> str | None:
    if not isinstance(obj, Mapping):
        return None
    value = str(obj.get("fullName") or obj.get("name") or "").strip()
    return value or None


def _player_id(obj: Any) -> int | None:
    if not isinstance(obj, Mapping):
        return None
    return _strict_positive_int(obj.get("id"))


def _runner(offense: Mapping[str, Any], base: str) -> tuple[int | None, str | None]:
    obj = offense.get(base)
    if not isinstance(obj, Mapping):
        return None, None
    return _player_id(obj), _name(obj)


def _last_pitch(current: Mapping[str, Any]) -> dict[str, Any] | None:
    events = current.get("playEvents") or []
    if not isinstance(events, list):
        return None
    pitches = [event for event in events if isinstance(event, Mapping) and event.get("isPitch")]
    return dict(pitches[-1]) if pitches else None


def _recent_plays(
    plays: Mapping[str, Any],
    away_runs: int,
    home_runs: int,
) -> list[dict[str, Any]]:
    all_plays = plays.get("allPlays") or []
    if not isinstance(all_plays, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in all_plays[-5:]:
        if not isinstance(raw, Mapping):
            continue
        about = raw.get("about") or {}
        result = raw.get("result") or {}
        if not isinstance(about, Mapping):
            about = {}
        if not isinstance(result, Mapping):
            result = {}
        inning = about.get("inning")
        half = str(about.get("halfInning") or "").title()
        out.append(
            {
                "Inning": f"{half} {inning}".strip() if inning is not None else half,
                "Play": str(result.get("description") or result.get("event") or "—"),
                "Score": (
                    f"{result.get('awayScore', away_runs)}-"
                    f"{result.get('homeScore', home_runs)}"
                ),
            }
        )
    return out


def _schedule_game_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in payload.get("dates") or []:
        if not isinstance(block, Mapping):
            continue
        for game in block.get("games") or []:
            if isinstance(game, Mapping):
                rows.append(dict(game))
    return rows


def normalize_schedule_game(game: Mapping[str, Any]) -> dict[str, Any]:
    game_id = _strict_positive_int(game.get("gamePk"))
    if game_id is None:
        raise MLBLiveGameStateCollectorError("schedule game is missing a valid official gamePk")

    status = str((game.get("status") or {}).get("detailedState") or "Unknown").strip()
    state = canonical_live_state(status)
    teams = game.get("teams") or {}
    away_row = teams.get("away") or {} if isinstance(teams, Mapping) else {}
    home_row = teams.get("home") or {} if isinstance(teams, Mapping) else {}
    away_team = away_row.get("team") or {} if isinstance(away_row, Mapping) else {}
    home_team = home_row.get("team") or {} if isinstance(home_row, Mapping) else {}
    away_name = _name(away_team)
    home_name = _name(home_team)
    if not away_name or not home_name:
        raise MLBLiveGameStateCollectorError(
            f"official game {game_id} is missing official team metadata"
        )

    linescore = game.get("linescore") or {}
    if not isinstance(linescore, Mapping):
        linescore = {}
    line_teams = linescore.get("teams") or {}
    if not isinstance(line_teams, Mapping):
        line_teams = {}
    away_line = line_teams.get("away") or {}
    home_line = line_teams.get("home") or {}
    if not isinstance(away_line, Mapping):
        away_line = {}
    if not isinstance(home_line, Mapping):
        home_line = {}

    away_runs = _strict_nonnegative_int(away_row.get("score"))
    home_runs = _strict_nonnegative_int(home_row.get("score"))
    if away_runs is None:
        away_runs = _strict_nonnegative_int(away_line.get("runs"))
    if home_runs is None:
        home_runs = _strict_nonnegative_int(home_line.get("runs"))
    away_runs = 0 if away_runs is None else away_runs
    home_runs = 0 if home_runs is None else home_runs

    return {
        "official_game_id": game_id,
        "status": status or "Unknown",
        "state": state,
        "away_team": away_name,
        "home_team": home_name,
        "away_runs": away_runs,
        "home_runs": home_runs,
        "away_hits": _strict_nonnegative_int(away_line.get("hits")),
        "home_hits": _strict_nonnegative_int(home_line.get("hits")),
        "away_errors": _strict_nonnegative_int(away_line.get("errors")),
        "home_errors": _strict_nonnegative_int(home_line.get("errors")),
        "inning": str(
            linescore.get("currentInningOrdinal")
            or linescore.get("currentInning")
            or ""
        ).strip() or None,
        "inning_state": str(linescore.get("inningState") or "").strip() or None,
        "balls": _strict_nonnegative_int(linescore.get("balls")),
        "strikes": _strict_nonnegative_int(linescore.get("strikes")),
        "outs": _strict_nonnegative_int(linescore.get("outs")),
        "batter_id": None,
        "batter": None,
        "pitcher_id": None,
        "pitcher": None,
        "on_deck": None,
        "in_hole": None,
        "runner_first_id": None,
        "first": None,
        "runner_second_id": None,
        "second": None,
        "runner_third_id": None,
        "third": None,
        "last_play": None,
        "last_pitch_desc": None,
        "last_pitch_type": None,
        "last_pitch_speed": None,
        "recent_plays": [],
    }


def normalize_live_feed(
    feed: Mapping[str, Any],
    *,
    official_game_id: int,
) -> dict[str, Any]:
    game_id = _strict_positive_int(official_game_id)
    if game_id is None:
        raise MLBLiveGameStateCollectorError("official_game_id must be a positive integer")
    feed_game_id = _strict_positive_int(feed.get("gamePk"))
    if feed_game_id is not None and feed_game_id != game_id:
        raise MLBLiveGameStateCollectorError(
            f"live feed gamePk {feed_game_id} does not match requested official game {game_id}"
        )

    game_data = feed.get("gameData") or {}
    live_data = feed.get("liveData") or {}
    if not isinstance(game_data, Mapping) or not isinstance(live_data, Mapping):
        raise MLBLiveGameStateCollectorError(
            f"official game {game_id} live feed is missing gameData/liveData"
        )
    teams = game_data.get("teams") or {}
    linescore = live_data.get("linescore") or {}
    plays = live_data.get("plays") or {}
    if not isinstance(teams, Mapping) or not isinstance(linescore, Mapping) or not isinstance(plays, Mapping):
        raise MLBLiveGameStateCollectorError(
            f"official game {game_id} live feed has invalid state containers"
        )

    away = teams.get("away") or {}
    home = teams.get("home") or {}
    if not isinstance(away, Mapping) or not isinstance(home, Mapping):
        raise MLBLiveGameStateCollectorError(f"official game {game_id} is missing teams")
    away_name = _name(away)
    home_name = _name(home)
    if not away_name or not home_name:
        raise MLBLiveGameStateCollectorError(f"official game {game_id} is missing team names")

    status = str((game_data.get("status") or {}).get("detailedState") or "Unknown").strip()
    state = canonical_live_state(status)

    line_teams = linescore.get("teams") or {}
    if not isinstance(line_teams, Mapping):
        line_teams = {}
    away_line = line_teams.get("away") or {}
    home_line = line_teams.get("home") or {}
    if not isinstance(away_line, Mapping):
        away_line = {}
    if not isinstance(home_line, Mapping):
        home_line = {}
    away_runs = _strict_nonnegative_int(away_line.get("runs"))
    home_runs = _strict_nonnegative_int(home_line.get("runs"))
    away_runs = 0 if away_runs is None else away_runs
    home_runs = 0 if home_runs is None else home_runs

    current = plays.get("currentPlay") or {}
    if not isinstance(current, Mapping):
        current = {}
    matchup = current.get("matchup") or {}
    count = current.get("count") or {}
    if not isinstance(matchup, Mapping):
        matchup = {}
    if not isinstance(count, Mapping):
        count = {}
    offense = linescore.get("offense") or {}
    defense = linescore.get("defense") or {}
    if not isinstance(offense, Mapping):
        offense = {}
    if not isinstance(defense, Mapping):
        defense = {}

    batter = matchup.get("batter") or offense.get("batter")
    pitcher = matchup.get("pitcher") or defense.get("pitcher")
    first_id, first_name = _runner(offense, "first")
    second_id, second_name = _runner(offense, "second")
    third_id, third_name = _runner(offense, "third")

    pitch = _last_pitch(current)
    pitch_desc = pitch_type = None
    pitch_speed = None
    if pitch:
        details = pitch.get("details") or {}
        if not isinstance(details, Mapping):
            details = {}
        pitch_desc = str(details.get("description") or "").strip() or None
        type_row = details.get("type") or {}
        if isinstance(type_row, Mapping):
            pitch_type = str(type_row.get("description") or "").strip() or None
        pitch_data = pitch.get("pitchData") or {}
        raw_speed = pitch_data.get("startSpeed") if isinstance(pitch_data, Mapping) else None
        if raw_speed is not None:
            try:
                parsed_speed = float(raw_speed)
            except (TypeError, ValueError):
                parsed_speed = None
            if parsed_speed is not None and parsed_speed >= 0:
                pitch_speed = parsed_speed

    inning = str(
        linescore.get("currentInningOrdinal")
        or linescore.get("currentInning")
        or ""
    ).strip() or None
    inning_state = str(linescore.get("inningState") or "").strip() or None
    balls = _strict_nonnegative_int(count.get("balls"))
    strikes = _strict_nonnegative_int(count.get("strikes"))
    outs = _strict_nonnegative_int(count.get("outs"))
    if balls is None:
        balls = _strict_nonnegative_int(linescore.get("balls"))
    if strikes is None:
        strikes = _strict_nonnegative_int(linescore.get("strikes"))
    if outs is None:
        outs = _strict_nonnegative_int(linescore.get("outs"))

    if state == LIVE and (
        inning is None
        or inning_state is None
        or balls is None
        or strikes is None
        or outs is None
    ):
        raise MLBLiveGameStateCollectorError(
            f"official live game {game_id} is missing inning/count state"
        )

    result = current.get("result") or {}
    if not isinstance(result, Mapping):
        result = {}
    return {
        "official_game_id": game_id,
        "status": status or "Unknown",
        "state": state,
        "away_team": away_name,
        "home_team": home_name,
        "away_runs": away_runs,
        "home_runs": home_runs,
        "away_hits": _strict_nonnegative_int(away_line.get("hits")),
        "home_hits": _strict_nonnegative_int(home_line.get("hits")),
        "away_errors": _strict_nonnegative_int(away_line.get("errors")),
        "home_errors": _strict_nonnegative_int(home_line.get("errors")),
        "inning": inning,
        "inning_state": inning_state,
        "balls": balls,
        "strikes": strikes,
        "outs": outs,
        "batter_id": _player_id(batter),
        "batter": _name(batter),
        "pitcher_id": _player_id(pitcher),
        "pitcher": _name(pitcher),
        "on_deck": _name(offense.get("onDeck")),
        "in_hole": _name(offense.get("inHole")),
        "runner_first_id": first_id,
        "first": first_name,
        "runner_second_id": second_id,
        "second": second_name,
        "runner_third_id": third_id,
        "third": third_name,
        "last_play": str(result.get("description") or "").strip() or None,
        "last_pitch_desc": pitch_desc,
        "last_pitch_type": pitch_type,
        "last_pitch_speed": pitch_speed,
        "recent_plays": _recent_plays(plays, away_runs, home_runs),
    }


def _normalize_slate_date(value: str | date_type) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date_type):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        parsed = date_type.fromisoformat(text)
    except ValueError as exc:
        raise MLBLiveGameStateCollectorError(
            "slate_date must use YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != text:
        raise MLBLiveGameStateCollectorError("slate_date must use YYYY-MM-DD")
    return text


def collect_live_mlb_game_state(
    *,
    slate_date: str | date_type,
    official_game_id: int | str | None = None,
    now_utc: datetime | None = None,
    max_games: int = 30,
    schedule_fetcher: Callable[[str], Mapping[str, Any]] = fetch_mlb_live_schedule,
    feed_fetcher: Callable[[int], Mapping[str, Any]] = fetch_mlb_live_feed,
) -> dict[str, Any]:
    """Collect one official MLB slate or one exact official game.

    Detailed live feeds are fetched for LIVE games and for an explicitly selected
    official game. Pregame/final slate rows may use the official hydrated schedule
    summary, minimizing external requests while preserving the Step 9A schema.
    """
    day = _normalize_slate_date(slate_date)
    requested_id = None
    if official_game_id is not None:
        requested_id = _strict_positive_int(official_game_id)
        if requested_id is None:
            raise MLBLiveGameStateCollectorError(
                "official_game_id must be a positive ASCII integer"
            )
    if isinstance(max_games, bool) or not isinstance(max_games, int) or not 1 <= max_games <= 50:
        raise MLBLiveGameStateCollectorError("max_games must be an integer from 1 to 50")

    collected = now_utc or datetime.now(timezone.utc)
    if collected.tzinfo is None:
        collected = collected.replace(tzinfo=timezone.utc)
    collected = collected.astimezone(timezone.utc)

    payload = schedule_fetcher(day)
    if not isinstance(payload, Mapping):
        raise MLBLiveGameStateCollectorError("schedule_fetcher did not return a mapping")
    schedule_rows = _schedule_game_rows(payload)

    seen: set[int] = set()
    official_rows: list[tuple[int, dict[str, Any]]] = []
    for raw in schedule_rows:
        game_id = _strict_positive_int(raw.get("gamePk"))
        if game_id is None:
            continue
        if game_id in seen:
            raise MLBLiveGameStateCollectorError(
                f"duplicate official MLB gamePk {game_id} in schedule"
            )
        seen.add(game_id)
        if requested_id is not None and game_id != requested_id:
            continue
        official_rows.append((game_id, raw))
        if len(official_rows) >= max_games:
            break

    games: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    detailed_feed_count = 0

    for game_id, raw in official_rows:
        try:
            summary = normalize_schedule_game(raw)
            needs_detail = requested_id == game_id or summary["state"] == LIVE
            if needs_detail:
                feed = feed_fetcher(game_id)
                if not isinstance(feed, Mapping):
                    raise MLBLiveGameStateCollectorError(
                        f"live feed for {game_id} did not return a mapping"
                    )
                summary = normalize_live_feed(feed, official_game_id=game_id)
                detailed_feed_count += 1
            games.append(summary)
        except Exception as exc:
            rejected.append(
                {
                    "official_game_id": game_id,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "provider": SOURCE,
        "transport": TRANSPORT,
        "http_methods": list(HTTP_METHODS),
        "collected_at_utc": collected.isoformat().replace("+00:00", "Z"),
        "slate_date": day,
        "requested_official_game_id": requested_id,
        "schedule_game_count": len(schedule_rows),
        "candidate_game_count": len(official_rows),
        "detailed_feed_count": detailed_feed_count,
        "game_count": len(games),
        "rejected_game_count": len(rejected),
        "team_name_matching_used": False,
        "player_name_matching_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "games": games,
        "rejected_games": rejected,
    }


__all__ = [
    "MLBLiveGameStateCollectorError",
    "SOURCE",
    "TRANSPORT",
    "HTTP_METHODS",
    "PREGAME",
    "LIVE",
    "DELAYED",
    "FINAL",
    "fetch_mlb_live_schedule",
    "fetch_mlb_live_feed",
    "canonical_live_state",
    "normalize_schedule_game",
    "normalize_live_feed",
    "collect_live_mlb_game_state",
]
