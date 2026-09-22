"""Step 7G first-party adapter for frozen Step 4O officiating context.

This module is deliberately descriptive and pre-model only. It replaces the
unreachable ``stats.wnba.com`` transport only when the default-OFF Step 7G
integration explicitly installs it. Current-game official assignments come from
the exact official WNBA.com game page. Team foul/free-throw environment is
reconstructed from certified WNBA.com completed-game boxes, with team fouls
drawn defined exactly as the opponent's personal fouls in the same paired game.

No referee tendency, whistle probability, sportsbook value, projection,
persistence, scheduler, Supabase, or production behavior exists here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any

from sports_api import wnba_officiating_context as frozen
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_step7g_first_party_history import (
    BOX_SCORE_CACHE_TTL_SECONDS,
    WNBA_FIRST_PARTY_SOURCE,
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    _game_page,
    get_first_party_game_box_score_dataset,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)
from sports_api import wnba_step7g_first_party_team_history as team_history_base
from sports_api.wnba_step7g_first_party_team_history_cup_safe import (
    install_exact_cup_exclusion,
)

WNBA_LEAGUE_ID = "10"
CERTIFIED_SEASON = 2026
CERTIFIED_SEASON_TYPE = "Regular Season"
MIN_CERTIFIED_LAST_N = 1
MAX_CERTIFIED_LAST_N = 20
LEAGUE_CACHE_TTL_SECONDS = 90
LEAGUE_CACHE_MAX_ENTRIES = 64
MAX_BOX_WORKERS = 8

SOURCE = "WNBA.com First-Party Game Page + Certified Completed Box Scores"
SOURCE_URL = "https://www.wnba.com/"
SOURCE_ENDPOINT = (
    "wnba.com/game/[game_id]::__NEXT_DATA__.props.pageProps.game + "
    "certified Step 4N season schedule"
)
SOURCE_VARIANT = "pregame_official_assignment_plus_exact_paired_box_whistle_environment_v1"

_LEAGUE_CACHE: dict[tuple[int, int, str], dict[str, Any]] = {}
_LEAGUE_CACHE_LOCK = Lock()


class _OfficiatingAdapterError(frozen.WNBAOfficiatingUpstreamError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    return frozen._clean(value)


def _to_int(value: Any) -> int | None:
    return frozen._to_int(value)


def _to_float(value: Any) -> float | None:
    return frozen._to_float(value)


def _raise(message: str, exc: BaseException | None = None) -> None:
    error = _OfficiatingAdapterError(message)
    if exc is None:
        raise error
    raise error from exc


def _validate_scope(season: int, season_type: str, last_n_games: int) -> tuple[str, int]:
    if season != CERTIFIED_SEASON:
        _raise(
            f"Step 7G first-party officiating is certified only for {CERTIFIED_SEASON}; "
            f"received {season}."
        )
    normalized_type = frozen._choice(
        season_type,
        frozen.ALLOWED_SEASON_TYPES,
        "season_type",
    )
    if normalized_type != CERTIFIED_SEASON_TYPE:
        _raise(
            "Step 7G first-party officiating is certified only for Regular Season."
        )
    if (
        not isinstance(last_n_games, int)
        or isinstance(last_n_games, bool)
        or not MIN_CERTIFIED_LAST_N <= last_n_games <= MAX_CERTIFIED_LAST_N
    ):
        _raise(
            "Step 7G first-party officiating is certified for last_n_games from "
            f"{MIN_CERTIFIED_LAST_N} through {MAX_CERTIFIED_LAST_N}."
        )
    return normalized_type, last_n_games


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _schedule_game(schedule: dict[str, Any], game_id: str) -> dict[str, Any]:
    rows = schedule.get("games")
    if not isinstance(rows, list):
        _raise("Certified Step 4N season schedule is missing game rows.")
    matching = [
        row for row in rows
        if isinstance(row, dict) and _clean(row.get("game_id")) == game_id
    ]
    if not matching:
        raise frozen.WNBAOfficiatingNotFoundError(
            f"WNBA game {game_id} was not found in certified {CERTIFIED_SEASON} schedule."
        )
    if len(matching) != 1:
        _raise(f"Certified Step 4N schedule returned duplicate game rows for {game_id}.")
    game = matching[0]
    verification = game.get("verification")
    if not isinstance(verification, dict):
        _raise("Certified Step 4N game row is missing verification metadata.")
    for key in ("game_id_valid", "teams_mapped_to_registry", "home_away_distinct"):
        if verification.get(key) is not True:
            _raise(f"Certified Step 4N game verification flag {key!r} is not true.")
    away = game.get("away")
    home = game.get("home")
    if not isinstance(away, dict) or not isinstance(home, dict):
        _raise("Certified Step 4N game row is missing away/home team identity.")
    if not _clean(away.get("team_key")) or not _clean(home.get("team_key")):
        _raise("Certified Step 4N game row has blank away/home team keys.")
    return game


def _validate_current_page_identity(
    schedule_game: dict[str, Any],
    box: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    game_id = _clean(schedule_game.get("game_id"))
    if box.get("game_id") != game_id:
        _raise("Current WNBA.com game page returned the wrong game ID.")
    for side in ("away", "home"):
        scheduled = schedule_game.get(side)
        boxed = box.get(side)
        if not isinstance(scheduled, dict) or not isinstance(boxed, dict):
            _raise(f"Current WNBA.com identity is missing {side} team context.")
        if boxed.get("team_key") != scheduled.get("team_key"):
            _raise(f"Current WNBA.com {side} team key disagrees with Step 4N schedule.")
        if boxed.get("official_team_id") != scheduled.get("official_team_id"):
            _raise(
                f"Current WNBA.com {side} official team ID disagrees with Step 4N schedule."
            )
    return box["away"], box["home"]


def _normalize_official_rows(raw_officials: Any, game_id: str) -> list[dict[str, Any]]:
    if raw_officials is None:
        raw_officials = []
    if not isinstance(raw_officials, list):
        _raise("Official WNBA.com game page officials field is malformed.")

    rows: list[dict[str, Any]] = []
    for raw in raw_officials:
        if not isinstance(raw, dict):
            _raise("Official WNBA.com game page contains a malformed official row.")
        person_id = _to_int(raw.get("personId"))
        name = _clean(raw.get("name"))
        if person_id is None or person_id <= 0:
            _raise("Official WNBA.com game page contains an invalid official person ID.")
        if name is None:
            _raise("Official WNBA.com game page contains an official without a name.")
        rows.append(
            {
                "person_id": person_id,
                "name": name,
                "name_initial": _clean(raw.get("nameI")),
                "first_name": _clean(raw.get("firstName")),
                "family_name": _clean(raw.get("familyName")),
                "jersey_number": _clean(raw.get("jerseyNum")),
            }
        )

    person_ids = [row["person_id"] for row in rows]
    duplicates = sorted(
        person_id for person_id in set(person_ids) if person_ids.count(person_id) > 1
    )
    if duplicates:
        _raise(
            "Official WNBA.com game page returned duplicate official person IDs: "
            + ", ".join(str(item) for item in duplicates)
            + "."
        )
    return rows


def _summary_team(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_team_id": team.get("official_team_id"),
        "team_key": team.get("team_key"),
        "team_full_name": team.get("full_name"),
        "team_abbreviation": team.get("team_abbreviation"),
        "source_team_city": team.get("team_city"),
        "source_team_name": team.get("team_name"),
        "source_team_tricode": team.get("team_abbreviation"),
        "mapped_to_registry": True,
    }


def _official_assignment_dataset(
    game_id: str,
    season: int,
    schedule_game: dict[str, Any],
) -> dict[str, Any]:
    try:
        box = get_first_party_game_box_score_dataset(game_id, season)
        _, game, retrieved_at_utc, cache_hit, _, url = _game_page(
            game_id,
            ttl_seconds=BOX_SCORE_CACHE_TTL_SECONDS,
        )
    except WNBAStep7GFirstPartyNotFoundError as exc:
        raise frozen.WNBAOfficiatingNotFoundError(str(exc)) from exc
    except WNBAStep7GFirstPartyUpstreamError as exc:
        _raise(f"Current first-party officiating page could not be consumed: {exc}", exc)

    away_box, home_box = _validate_current_page_identity(schedule_game, box)
    officials = _normalize_official_rows(game.get("officials"), game_id)
    officials_available = bool(officials)

    return {
        "source": WNBA_FIRST_PARTY_SOURCE,
        "source_url": url,
        "source_endpoint": "wnba.com/game/[game_id]::__NEXT_DATA__.props.pageProps.game.officials",
        "data_type": "official_game_official_assignment",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game_id": game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "game_status": {
            "code": _to_int(game.get("gameStatus")),
            "text": _clean(game.get("gameStatusText")),
            "period": _to_int(game.get("period")),
            "clock": _clean(game.get("gameClock")),
        },
        "away": _summary_team(away_box),
        "home": _summary_team(home_box),
        "official_count": len(officials),
        "officials_available": officials_available,
        "assignment_status": (
            "assigned_from_official_wnba_game_page"
            if officials_available
            else "not_available_from_official_wnba_game_page"
        ),
        "officials": officials,
        "verification": {
            "requested_game_id_matches_source": True,
            "home_away_teams_mapped": True,
            "current_page_teams_match_certified_schedule": True,
            "official_person_ids_unique": True,
            "official_names_present_for_returned_rows": all(bool(row.get("name")) for row in officials),
            "officials_are_current_game_assignment_only": True,
            "pending_assignment_is_valid_frozen_step4o_state": not officials_available,
            "referee_tendencies_or_bias_inferred": False,
            "third_party_sources_used": False,
        },
    }


def _completed_regular_games_before(
    schedule: dict[str, Any],
    *,
    season: int,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    install_exact_cup_exclusion()
    rows = schedule.get("games")
    if not isinstance(rows, list):
        _raise("Certified Step 4N season schedule is missing games for whistle history.")

    selected: list[tuple[datetime, dict[str, Any]]] = []
    for game in rows:
        if not isinstance(game, dict):
            _raise("Certified Step 4N schedule contains a malformed game row.")
        away = game.get("away")
        if not isinstance(away, dict) or not _clean(away.get("team_key")):
            _raise("Certified Step 4N schedule game is missing away team identity.")
        status = game.get("status")
        if not isinstance(status, dict) or status.get("category") != "final":
            continue
        if not team_history_base._validate_schedule_game(
            game,
            str(away["team_key"]),
            season,
        ):
            continue
        tip = _parse_dt(game.get("game_datetime_utc"))
        if tip is None:
            _raise(
                "Certified Step 4N completed regular-season game is missing a valid UTC tip time."
            )
        if tip >= cutoff:
            continue
        selected.append((tip, game))

    selected.sort(key=lambda item: (item[0], str(item[1].get("game_id"))), reverse=True)
    return [game for _, game in selected]


def _team_recent_game_ids(
    completed: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    last_n_games: int,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for team in teams:
        key = str(team["team_key"])
        ids: list[str] = []
        for game in completed:
            away_key = _clean((game.get("away") or {}).get("team_key"))
            home_key = _clean((game.get("home") or {}).get("team_key"))
            if key not in {away_key, home_key}:
                continue
            game_id = _clean(game.get("game_id"))
            if game_id is None:
                _raise("Completed Step 4N game is missing game ID.")
            ids.append(game_id)
            if len(ids) == last_n_games:
                break
        if not ids:
            _raise(f"No completed regular-season whistle-history games were found for {key}.")
        result[key] = ids
    return result


def _fetch_unique_boxes(
    game_by_id: dict[str, dict[str, Any]],
    game_ids: list[str],
) -> tuple[dict[str, tuple[dict[str, Any], dict[str, Any]]], int]:
    install_exact_cup_exclusion()
    resolved: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    cache_hits = 0

    def load(game_id: str) -> tuple[str, dict[str, Any]]:
        try:
            return game_id, team_history_base.get_first_party_game_box_score_dataset(
                game_id, CERTIFIED_SEASON
            )
        except (WNBAStep7GFirstPartyNotFoundError, WNBAStep7GFirstPartyUpstreamError) as exc:
            _raise(f"Completed first-party box unavailable for whistle history {game_id}: {exc}", exc)
        raise AssertionError("unreachable")

    worker_count = min(MAX_BOX_WORKERS, max(1, len(game_ids)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(load, game_id): game_id for game_id in game_ids}
        for future in as_completed(futures):
            game_id = futures[future]
            loaded_id, box = future.result()
            if loaded_id != game_id:
                _raise("Concurrent whistle-history box loader returned the wrong game ID.")
            schedule_game = game_by_id.get(game_id)
            if schedule_game is None:
                _raise(f"Whistle-history box {game_id} has no certified schedule row.")
            away, home = team_history_base._validate_schedule_box_identity_and_score(
                schedule_game, box
            )
            resolved[game_id] = (away, home)
            if box.get("cache_hit") is True:
                cache_hits += 1

    if set(resolved) != set(game_ids):
        _raise("Whistle-history unique box set did not resolve completely.")
    return resolved, cache_hits


def _game_stat_row(
    team_key: str,
    game_id: str,
    pair: tuple[dict[str, Any], dict[str, Any]],
) -> dict[str, float]:
    away, home = pair
    if away.get("team_key") == team_key:
        team, opponent = away, home
    elif home.get("team_key") == team_key:
        team, opponent = home, away
    else:
        _raise(f"Whistle-history game {game_id} does not contain team {team_key}.")

    stats = team.get("stats")
    opponent_stats = opponent.get("stats")
    if not isinstance(stats, dict) or not isinstance(opponent_stats, dict):
        _raise(f"Whistle-history game {game_id} is missing paired team statistics.")

    required = (
        "minutes",
        "field_goals_attempted",
        "free_throws_made",
        "free_throws_attempted",
        "personal_fouls",
        "points",
    )
    values: dict[str, float] = {}
    for field in required:
        value = _to_float(stats.get(field))
        if value is None:
            _raise(f"Whistle-history game {game_id} is missing numeric {field} for {team_key}.")
        values[field] = value
    opponent_pf = _to_float(opponent_stats.get("personal_fouls"))
    if opponent_pf is None:
        _raise(
            f"Whistle-history game {game_id} cannot derive fouls drawn because opponent PF is missing."
        )
    values["personal_fouls_drawn"] = opponent_pf
    # WNBA.com traditional team box minutes are the sum of five players on court.
    # LeagueDashTeamStats MIN is team clock minutes, so divide the exact five-player
    # total by five; overtime naturally remains represented.
    values["minutes"] = round(values["minutes"] / 5.0, 4)
    return values


def _average(rows: list[dict[str, float]], field: str) -> float:
    return round(sum(row[field] for row in rows) / len(rows), 4)


def _profile_stats(rows: list[dict[str, float]]) -> dict[str, float | None]:
    games = len(rows)
    if games <= 0:
        _raise("Cannot build whistle profile from zero games.")
    ftm_total = sum(row["free_throws_made"] for row in rows)
    fta_total = sum(row["free_throws_attempted"] for row in rows)
    return {
        "minutes": _average(rows, "minutes"),
        "field_goals_attempted": _average(rows, "field_goals_attempted"),
        "free_throws_made": _average(rows, "free_throws_made"),
        "free_throws_attempted": _average(rows, "free_throws_attempted"),
        "free_throw_percentage": (
            round(ftm_total / fta_total, 4) if fta_total > 0 else None
        ),
        "personal_fouls": _average(rows, "personal_fouls"),
        "personal_fouls_drawn": _average(rows, "personal_fouls_drawn"),
        "points": _average(rows, "points"),
    }


def _build_league_profiles_uncached(
    schedule: dict[str, Any],
    *,
    season: int,
    last_n_games: int,
    cutoff: datetime,
) -> dict[str, Any]:
    teams = get_wnba_teams(season)
    completed = _completed_regular_games_before(schedule, season=season, cutoff=cutoff)
    recent_ids = _team_recent_game_ids(completed, teams, last_n_games)

    needed_ids = sorted({game_id for ids in recent_ids.values() for game_id in ids})
    needed_id_set = set(needed_ids)
    game_by_id = {
        str(game["game_id"]): game
        for game in completed
        if _clean(game.get("game_id")) in needed_id_set
    }
    boxes, box_cache_hits = _fetch_unique_boxes(game_by_id, needed_ids)

    rows: list[dict[str, Any]] = []
    for team in teams:
        key = str(team["team_key"])
        ids = recent_ids[key]
        game_rows = [_game_stat_row(key, game_id, boxes[game_id]) for game_id in ids]
        stats = _profile_stats(game_rows)
        rows.append(
            {
                "official_team_id": team.get("official_team_id"),
                "team_key": key,
                "team_full_name": team.get("full_name"),
                "team_abbreviation": team.get("abbreviation"),
                "games_played": len(game_rows),
                "selected_game_ids": ids,
                "stats": stats,
            }
        )

    if len(rows) != len(teams):
        _raise("Whistle-history league profile did not cover the full registered league.")
    keys = [row["team_key"] for row in rows]
    if len(keys) != len(set(keys)):
        _raise("Whistle-history league profile contains duplicate team keys.")

    retrieved_at_utc = _utc_now_iso()
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "source_endpoint": SOURCE_ENDPOINT,
        "source_variant": SOURCE_VARIANT,
        "season": season,
        "season_type": CERTIFIED_SEASON_TYPE,
        "last_n_games": last_n_games,
        "window_scope": f"last_{last_n_games}_games",
        "retrieved_at_utc": retrieved_at_utc,
        "team_count": len(rows),
        "unique_box_count": len(needed_ids),
        "box_cache_hit_count": box_cache_hits,
        "teams": rows,
        "verification": {
            "all_registered_teams_covered": True,
            "all_history_games_final_regular_season": True,
            "all_history_games_before_requested_tip": True,
            "schedule_box_identity_and_scores_reconciled": True,
            "personal_fouls_drawn_derived_only_from_paired_opponent_personal_fouls": True,
            "team_clock_minutes_derived_from_exact_five_player_box_minutes": True,
            "third_party_sources_used": False,
        },
    }


def _league_profiles(
    schedule: dict[str, Any],
    *,
    season: int,
    last_n_games: int,
    requested_game_id: str,
    cutoff: datetime,
) -> tuple[dict[str, Any], bool]:
    key = (season, last_n_games, requested_game_id)
    now = monotonic()
    with _LEAGUE_CACHE_LOCK:
        cached = _LEAGUE_CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return deepcopy(cached["payload"]), True
        if cached:
            _LEAGUE_CACHE.pop(key, None)

    payload = _build_league_profiles_uncached(
        schedule,
        season=season,
        last_n_games=last_n_games,
        cutoff=cutoff,
    )
    with _LEAGUE_CACHE_LOCK:
        for expired_key in [
            cache_key
            for cache_key, item in _LEAGUE_CACHE.items()
            if item["expires_at"] <= now
        ]:
            _LEAGUE_CACHE.pop(expired_key, None)
        if len(_LEAGUE_CACHE) >= LEAGUE_CACHE_MAX_ENTRIES:
            _LEAGUE_CACHE.pop(next(iter(_LEAGUE_CACHE)), None)
        _LEAGUE_CACHE[key] = {
            "payload": deepcopy(payload),
            "expires_at": now + LEAGUE_CACHE_TTL_SECONDS,
        }
    return deepcopy(payload), False


def _team_context(
    league: dict[str, Any],
    team_key: str,
    *,
    cache_hit: bool,
) -> dict[str, Any]:
    rows = league.get("teams")
    if not isinstance(rows, list):
        _raise("Whistle-history league payload is missing team rows.")
    matching = [row for row in rows if isinstance(row, dict) and row.get("team_key") == team_key]
    if len(matching) != 1:
        _raise(
            f"Whistle-history league payload returned {len(matching)} rows for {team_key}."
        )
    row = matching[0]
    stats = row.get("stats")
    if not isinstance(stats, dict):
        _raise(f"Whistle-history team {team_key} is missing profile statistics.")
    profile = frozen._foul_ft_profile(stats)
    league_context = {
        "free_throws_attempted_per_game": frozen._league_measure(
            rows, team_key, "free_throws_attempted"
        ),
        "personal_fouls_per_game": frozen._league_measure(
            rows, team_key, "personal_fouls"
        ),
        "personal_fouls_drawn_per_game": frozen._league_measure(
            rows, team_key, "personal_fouls_drawn"
        ),
    }
    return {
        "source": league.get("source"),
        "source_url": league.get("source_url"),
        "source_endpoint": league.get("source_endpoint"),
        "data_type": "observed_team_foul_free_throw_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": league.get("season"),
        "season_type": league.get("season_type"),
        "last_n_games": league.get("last_n_games"),
        "window_scope": league.get("window_scope"),
        "team": {
            "team_key": row.get("team_key"),
            "team_full_name": row.get("team_full_name"),
            "team_abbreviation": row.get("team_abbreviation"),
            "official_team_id": row.get("official_team_id"),
            "games_played": row.get("games_played"),
        },
        "profile": profile,
        "league_context": league_context,
        "retrieved_at_utc": league.get("retrieved_at_utc"),
        "cache_hit": cache_hit,
        "selected_game_ids": deepcopy(row.get("selected_game_ids")),
        "verification": {
            "official_base_stats_used": True,
            "team_row_unique": True,
            "rates_are_observed_not_predictive": True,
            "higher_value_rank_is_not_a_quality_rank": True,
            "personal_fouls_drawn_equals_paired_opponent_personal_fouls": True,
            "team_clock_minutes_normalized_from_five_player_box_total": True,
            "third_party_sources_used": False,
        },
    }


def _combined(left: Any, right: Any) -> float | None:
    l = _to_float(left)
    r = _to_float(right)
    if l is None or r is None:
        return None
    return round(l + r, 4)


def get_first_party_game_whistle_context(
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
) -> dict[str, Any]:
    """Return frozen-Step-4O-compatible first-party whistle context.

    Certification scope is 2026 Regular Season with recent windows from 1 to 20
    games. Current-game officials are returned when WNBA.com has published them;
    before publication the assignment remains a valid frozen Step-4O pending
    state with an empty officials list while the observed team environment stays
    available. Malformed or conflicting identity still fails closed.
    """
    game_id = frozen._game_id(game_id)
    season_type, last_n_games = _validate_scope(season, season_type, last_n_games)
    try:
        schedule = get_step7g_step4n_season_schedule_dataset(season)
    except Exception as exc:
        _raise(f"Certified Step 4N schedule unavailable for officiating: {exc}", exc)
    requested = _schedule_game(schedule, game_id)
    tip = _parse_dt(requested.get("game_datetime_utc"))
    if tip is None:
        _raise("Requested certified Step 4N game is missing a valid UTC tip time.")

    officials = _official_assignment_dataset(game_id, season, requested)
    away_key = _clean((officials.get("away") or {}).get("team_key"))
    home_key = _clean((officials.get("home") or {}).get("team_key"))
    if not away_key or not home_key or away_key == home_key:
        _raise("First-party official assignment did not resolve two distinct mapped teams.")

    league, league_cache_hit = _league_profiles(
        schedule,
        season=season,
        last_n_games=last_n_games,
        requested_game_id=game_id,
        cutoff=tip,
    )
    away = _team_context(league, away_key, cache_hit=league_cache_hit)
    home = _team_context(league, home_key, cache_hit=league_cache_hit)

    away_profile = away["profile"]
    home_profile = home["profile"]
    away_fta = _to_float(away_profile.get("free_throws_attempted"))
    home_fta = _to_float(home_profile.get("free_throws_attempted"))
    away_pf = _to_float(away_profile.get("personal_fouls"))
    home_pf = _to_float(home_profile.get("personal_fouls"))
    away_pfd = _to_float(away_profile.get("personal_fouls_drawn"))
    home_pfd = _to_float(home_profile.get("personal_fouls_drawn"))

    return {
        "source": "Kyre Sports API composition of first-party WNBA.com sources",
        "data_type": "observed_game_whistle_environment_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "last_n_games": last_n_games,
        "game_id": game_id,
        "official_assignment": officials,
        "away_team_context": away,
        "home_team_context": home,
        "combined_observed_team_rates": {
            "sum_free_throw_attempts_per_game": _combined(away_fta, home_fta),
            "sum_personal_fouls_per_game": _combined(away_pf, home_pf),
            "sum_personal_fouls_drawn_per_game": _combined(away_pfd, home_pfd),
            "away_minus_home_free_throw_attempts_per_game": frozen._difference(
                away_fta, home_fta
            ),
        },
        "verification": {
            "both_team_contexts_match_game": (
                away["team"]["team_key"] == away_key
                and home["team"]["team_key"] == home_key
            ),
            "current_game_page_matches_certified_schedule": True,
            "officials_are_current_game_assignment_only": True,
            "officials_published_pregame_source_supported": True,
            "historical_referee_tendencies_included": False,
            "team_environment_from_completed_games_before_requested_tip": True,
            "personal_fouls_drawn_derived_only_from_paired_opponent_personal_fouls": True,
            "combined_rates_are_not_expected_game_totals": True,
            "no_whistle_probability_created": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
        "step7g_adapter": {
            "source_variant": SOURCE_VARIANT,
            "history_unique_box_count": league.get("unique_box_count"),
            "history_box_cache_hit_count": league.get("box_cache_hit_count"),
            "league_profile_cache_hit": league_cache_hit,
            "officials_currently_available": officials.get("officials_available") is True,
            "production_provider_replaced": False,
        },
    }
