"""Isolated Step 7G first-party adapter for the frozen Step 4J team history.

The frozen Step 4J provider reads ``leaguegamelog`` from stats.wnba.com. That
transport is not reachable from the Step 7G execution environment, while the
already-certified WNBA.com first-party season schedule and server-rendered game
pages are reachable.

This module does not replace or modify the frozen provider. It builds the exact
Step 4J row contract by combining:

* the certified first-party Step 4N season schedule (game/date/home/away/status),
* the certified first-party Step 4D traditional box-score page for each completed
  regular-season game, and
* Step 4J's own frozen row normalizer, opponent-pairing, filtering, and summary
  helpers.

The adapter is deliberately 2026/Regular-Season scoped because the project team
registry is currently 2026-only and that is the dependency boundary being
certified. Any identity, score, season marker, or box/schedule disagreement
fails closed. No sportsbook, scheduler, persistence, Supabase, or production
runtime is touched.
"""
from __future__ import annotations

from copy import deepcopy
from threading import Lock
from time import monotonic
from typing import Any, Callable

from sports_api import wnba_team_history as frozen
from sports_api.wnba_step7g_first_party_history import (
    WNBA_FIRST_PARTY_SOURCE,
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_game_box_score_dataset,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

STEP7G_STEP4J_SOURCE = "WNBA.com First-Party Schedule + Game Page Data"
STEP7G_STEP4J_SOURCE_ENDPOINT = (
    "wnba.com first-party season schedule + "
    "wnba.com/game/[game_id]::__NEXT_DATA__.props.pageProps.game"
)
STEP7G_STEP4J_CONTRACT = "Step 4J official_team_game_log"
STEP7G_STEP4J_CACHE_TTL_SECONDS = frozen.CACHE_TTL_SECONDS
STEP7G_STEP4J_CACHE_MAX_ENTRIES = 32
SUPPORTED_ADAPTER_SEASON_TYPE = "Regular Season"

# The WNBA game-id family observed and certified for the requested 2026 Regular
# Season is 10226xxxxx. This is intentionally season-scoped; it is not treated as
# a universal rule for future seasons. The live certification verifies every row
# admitted by this marker against the official schedule and official box page.
_REGULAR_SEASON_GAME_ID_PREFIX_BY_SEASON = {2026: "10226"}
_KNOWN_NON_REGULAR_GAME_ID_PREFIXES = {"101", "103", "104"}

# A synthetic LeagueGameLog-shaped row is used only as an input to the frozen
# Step 4J normalizer. Every value comes from the official schedule or official
# box score; no model value is inserted.
_SYNTHETIC_HEADERS = (
    "SEASON_ID",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "TEAM_NAME",
    "GAME_ID",
    "GAME_DATE",
    "MATCHUP",
    "WL",
    "MIN",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "PTS",
    "PLUS_MINUS",
    "VIDEO_AVAILABLE",
)

_REQUIRED_BOX_STATS = (
    "minutes",
    "field_goals_made",
    "field_goals_attempted",
    "three_pointers_made",
    "three_pointers_attempted",
    "free_throws_made",
    "free_throws_attempted",
    "offensive_rebounds",
    "defensive_rebounds",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "personal_fouls",
    "points",
)

_CACHE: dict[tuple[str, int, str], dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class _NoValue:
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _raise(message: str, exc: Exception | None = None) -> None:
    error = frozen.WNBATeamHistoryUpstreamError(message)
    if exc is None:
        raise error
    raise error from exc


def _regular_season_marker(game: dict[str, Any], season: int) -> bool:
    """Return True only for the certified season-scoped regular-season ID family.

    Known preseason/All-Star/playoff families are excluded. An unknown completed
    game family fails closed rather than being silently assigned to Regular Season.
    """
    game_id = _clean(game.get("game_id"))
    if game_id is None or len(game_id) != 10 or not game_id.isdigit():
        _raise("Step 7G Step 4J received an invalid completed-game ID from schedule.")

    expected = _REGULAR_SEASON_GAME_ID_PREFIX_BY_SEASON.get(season)
    if expected is None:
        _raise(
            f"Step 7G Step 4J has no certified Regular Season game-ID marker for {season}."
        )

    if game_id.startswith(expected):
        label = _clean(((game.get("competition") or {}).get("game_label")))
        if label and label.casefold() in {"preseason", "all-star", "all star", "playoffs"}:
            _raise(
                "Official WNBA schedule season label conflicts with the certified "
                f"Regular Season game-ID marker for {game_id}."
            )
        return True

    if game_id[:3] in _KNOWN_NON_REGULAR_GAME_ID_PREFIXES:
        return False

    _raise(
        "Official WNBA schedule exposed an unrecognized completed-game ID family "
        f"for Step 4J Regular Season history: {game_id}."
    )
    return False  # pragma: no cover - _raise always raises


def _validate_schedule_game(game: dict[str, Any], team_key: str, season: int) -> bool:
    if not isinstance(game, dict):
        _raise("Step 7G Step 4J season schedule contains a malformed game row.")

    verification = game.get("verification") or {}
    if not verification.get("game_id_valid"):
        _raise("Step 7G Step 4J season schedule contains an invalid game ID.")
    if not verification.get("teams_mapped_to_registry"):
        _raise("Step 7G Step 4J season schedule contains an unmapped franchise game.")
    if not verification.get("home_away_distinct"):
        _raise("Step 7G Step 4J season schedule contains invalid home/away identity.")

    away = game.get("away") or {}
    home = game.get("home") or {}
    if away.get("team_key") != team_key and home.get("team_key") != team_key:
        return False

    status = game.get("status") or {}
    if status.get("category") != "final":
        return False

    return _regular_season_marker(game, season)


def _box_side(box: dict[str, Any], side: str) -> dict[str, Any]:
    team = box.get(side)
    if not isinstance(team, dict):
        _raise(f"Official WNBA.com box score is missing the {side} team.")
    stats = team.get("stats")
    if not isinstance(stats, dict):
        _raise(f"Official WNBA.com box score is missing {side} team statistics.")
    missing = [field for field in _REQUIRED_BOX_STATS if not _numeric(stats.get(field))]
    if missing:
        _raise(
            f"Official WNBA.com box score {side} team is missing numeric Step 4J "
            "statistics: " + ", ".join(missing) + "."
        )
    if float(stats["minutes"]) <= 0.0:
        _raise("Official WNBA.com box score returned non-positive team minutes.")
    return team


def _validate_schedule_box_identity_and_score(
    game: dict[str, Any],
    box: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    game_id = str(game["game_id"])
    if box.get("game_id") != game_id:
        _raise("Official WNBA.com box-score game ID disagrees with schedule game ID.")

    schedule_away = game.get("away") or {}
    schedule_home = game.get("home") or {}
    box_away = _box_side(box, "away")
    box_home = _box_side(box, "home")

    for side, scheduled, boxed in (
        ("away", schedule_away, box_away),
        ("home", schedule_home, box_home),
    ):
        if scheduled.get("team_key") != boxed.get("team_key"):
            _raise(
                f"Official WNBA schedule/box {side} team key mismatch for game {game_id}."
            )
        if scheduled.get("official_team_id") != boxed.get("official_team_id"):
            _raise(
                f"Official WNBA schedule/box {side} official team ID mismatch for game {game_id}."
            )
        schedule_score = scheduled.get("score")
        box_score = (boxed.get("stats") or {}).get("points")
        if not _numeric(schedule_score) or not _numeric(box_score):
            _raise(f"Official WNBA final score is missing for game {game_id}.")
        if int(schedule_score) != int(box_score):
            _raise(
                f"Official WNBA schedule/box {side} score mismatch for game {game_id}."
            )

    away_points = float(box_away["stats"]["points"])
    home_points = float(box_home["stats"]["points"])
    if away_points == home_points:
        _raise(f"Official WNBA final game {game_id} has a tied final score.")
    return box_away, box_home


def _raw_step4j_row(
    *,
    game: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
    side: str,
    season: int,
) -> dict[str, Any]:
    stats = team["stats"]
    opponent_points = float(opponent["stats"]["points"])
    team_points = float(stats["points"])
    team_abbreviation = _clean(team.get("team_abbreviation"))
    opponent_abbreviation = _clean(opponent.get("team_abbreviation"))
    if not team_abbreviation or not opponent_abbreviation:
        _raise("Official WNBA.com box score is missing a team abbreviation.")

    marker = "vs." if side == "home" else "@"
    matchup = f"{team_abbreviation} {marker} {opponent_abbreviation}"
    result = "W" if team_points > opponent_points else "L"

    return {
        "SEASON_ID": f"2{season}",
        "TEAM_ID": team.get("official_team_id"),
        "TEAM_ABBREVIATION": team_abbreviation,
        "TEAM_NAME": team.get("full_name"),
        "GAME_ID": game.get("game_id"),
        "GAME_DATE": game.get("official_schedule_date"),
        "MATCHUP": matchup,
        "WL": result,
        "MIN": stats.get("minutes"),
        "FGM": stats.get("field_goals_made"),
        "FGA": stats.get("field_goals_attempted"),
        "FG_PCT": stats.get("field_goal_percentage"),
        "FG3M": stats.get("three_pointers_made"),
        "FG3A": stats.get("three_pointers_attempted"),
        "FG3_PCT": stats.get("three_point_percentage"),
        "FTM": stats.get("free_throws_made"),
        "FTA": stats.get("free_throws_attempted"),
        "FT_PCT": stats.get("free_throw_percentage"),
        "OREB": stats.get("offensive_rebounds"),
        "DREB": stats.get("defensive_rebounds"),
        "REB": stats.get("rebounds"),
        "AST": stats.get("assists"),
        "STL": stats.get("steals"),
        "BLK": stats.get("blocks"),
        "TOV": stats.get("turnovers"),
        "PF": stats.get("personal_fouls"),
        "PTS": stats.get("points"),
        "PLUS_MINUS": stats.get("plus_minus"),
        "VIDEO_AVAILABLE": None,
    }


def _build_team_history_base(
    schedule: dict[str, Any],
    team_key: str,
    season: int,
    *,
    box_loader: Callable[[str, int], dict[str, Any]],
) -> dict[str, Any]:
    schedule_games = schedule.get("games")
    if not isinstance(schedule_games, list):
        _raise("Step 7G Step 4J schedule adapter returned no games list.")

    seen_schedule_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    for game in schedule_games:
        if not isinstance(game, dict):
            _raise("Step 7G Step 4J schedule adapter returned a malformed game row.")
        game_id = _clean(game.get("game_id"))
        if game_id:
            if game_id in seen_schedule_ids:
                _raise(f"Step 7G Step 4J schedule contains duplicate game ID {game_id}.")
            seen_schedule_ids.add(game_id)
        if _validate_schedule_game(game, team_key, season):
            selected.append(game)

    rows: list[dict[str, Any]] = []
    source_urls: list[str] = []
    box_cache_hits = 0
    for game in selected:
        game_id = str(game["game_id"])
        try:
            box = box_loader(game_id, season)
        except (WNBAStep7GFirstPartyNotFoundError, WNBAStep7GFirstPartyUpstreamError) as exc:
            _raise(
                f"Official WNBA.com box score could not supply Step 4J game {game_id}: "
                f"{type(exc).__name__}.",
                exc,
            )
        except frozen.WNBATeamHistoryUpstreamError:
            raise
        except Exception as exc:
            _raise(
                f"Unexpected first-party box-score failure for Step 4J game {game_id}: "
                f"{type(exc).__name__}.",
                exc,
            )

        away, home = _validate_schedule_box_identity_and_score(game, box)
        source_url = _clean(box.get("source_url"))
        if source_url:
            source_urls.append(source_url)
        box_cache_hits += int(bool(box.get("cache_hit")))

        raw_away = _raw_step4j_row(
            game=game,
            team=away,
            opponent=home,
            side="away",
            season=season,
        )
        raw_home = _raw_step4j_row(
            game=game,
            team=home,
            opponent=away,
            side="home",
            season=season,
        )
        try:
            rows.append(frozen._normalize_team_game(raw_away, season))
            rows.append(frozen._normalize_team_game(raw_home, season))
        except Exception as exc:
            _raise(
                f"Official WNBA.com game {game_id} could not be normalized by the "
                "frozen Step 4J row contract.",
                exc,
            )

    pair_verification = frozen._pair_game_rows(rows)
    if not pair_verification["all_game_ids_have_two_team_rows"]:
        _raise("Step 7G Step 4J could not pair both official team rows for every game.")
    if not pair_verification["opponent_identity_matches_pair"]:
        _raise("Step 7G Step 4J paired opponent identity does not match matchup identity.")

    invalid_game_ids = sorted(
        {
            row.get("game_id")
            for row in rows
            if row.get("game_id") is not None and not row.get("game_id_valid")
        }
    )
    unmapped = sum(not bool(row.get("mapped_to_registry")) for row in rows)
    target_rows = [row for row in rows if row.get("team_key") == team_key]
    if len(target_rows) != len(selected):
        _raise("Step 7G Step 4J target-team row count does not match selected schedule games.")
    if unmapped or invalid_game_ids:
        _raise("Step 7G Step 4J normalized rows failed team/game identity validation.")

    return {
        "source": STEP7G_STEP4J_SOURCE,
        "source_url": schedule.get("source_url"),
        "source_endpoint": STEP7G_STEP4J_SOURCE_ENDPOINT,
        "source_variant": "wnba_com_first_party_step4j_team_history",
        "upstream_schedule_source_variant": schedule.get("source_variant"),
        "contract_shape": STEP7G_STEP4J_CONTRACT,
        "season": season,
        "season_type": SUPPORTED_ADAPTER_SEASON_TYPE,
        "team_key": team_key,
        "retrieved_at_utc": schedule.get("retrieved_at_utc"),
        "source_header_count": len(_SYNTHETIC_HEADERS),
        "season_team_game_count": len(target_rows),
        "rows": rows,
        "source_box_score_count": len(selected),
        "source_box_score_urls": source_urls,
        "source_box_score_cache_hits": box_cache_hits,
        "verification": {
            "schema_verified": True,
            "normalized_with_frozen_step4j_row_contract": True,
            "paired_with_frozen_step4j_pairing_semantics": True,
            "filtered_and_summarized_with_frozen_step4j_semantics": True,
            "all_rows_mapped_to_registry": unmapped == 0,
            "unmapped_team_count": unmapped,
            "all_game_ids_valid": not invalid_game_ids,
            "invalid_game_ids": invalid_game_ids,
            "selected_completed_regular_season_schedule_game_count": len(selected),
            "source_box_score_count_matches_selected_games": len(selected) == len(source_urls),
            "schedule_box_identity_match": True,
            "schedule_box_score_match": True,
            "regular_season_marker_verified_for_2026": season == 2026,
            "official_first_party_box_source_reused": WNBA_FIRST_PARTY_SOURCE,
            "frozen_team_history_module_modified": False,
            "production_provider_replaced": False,
            **pair_verification,
        },
    }


def _cached_base(team_key: str, season: int, season_type: str) -> tuple[dict[str, Any], bool]:
    key = (team_key, season, season_type)
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return deepcopy(cached["dataset"]), True
        if cached:
            _CACHE.pop(key, None)

    try:
        schedule = get_step7g_step4n_season_schedule_dataset(season)
        base = _build_team_history_base(
            schedule,
            team_key,
            season,
            box_loader=get_first_party_game_box_score_dataset,
        )
    except frozen.WNBATeamHistoryUpstreamError:
        raise
    except Exception as exc:
        _raise(
            f"Step 7G Step 4J first-party team-history build failed: {type(exc).__name__}.",
            exc,
        )

    with _CACHE_LOCK:
        expired = [cache_key for cache_key, item in _CACHE.items() if item["expires_at"] <= now]
        for cache_key in expired:
            _CACHE.pop(cache_key, None)
        if len(_CACHE) >= STEP7G_STEP4J_CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[key] = {
            "dataset": deepcopy(base),
            "expires_at": now + STEP7G_STEP4J_CACHE_TTL_SECONDS,
        }
    return deepcopy(base), False


def get_first_party_team_game_log_dataset(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    location: str = "All",
    opponent_team_key: str | None = None,
) -> dict[str, Any]:
    """Return a first-party dataset compatible with frozen Step 4J.

    Input validation, row normalization, pairing, filtering, and summary semantics
    are delegated to the frozen Step 4J module. Only the transport/source assembly
    is different.
    """
    stable_team_key = frozen._validate_team_key(team_key, season)
    stable_opponent_key = (
        frozen._validate_team_key(opponent_team_key, season)
        if opponent_team_key is not None
        else None
    )
    if stable_opponent_key == stable_team_key:
        raise ValueError("WNBA opponent_team_key must be different from team_key.")

    normalized_season_type = frozen._normalize_choice(
        season_type,
        frozen.ALLOWED_SEASON_TYPES,
        "season_type",
    )
    if normalized_season_type != SUPPORTED_ADAPTER_SEASON_TYPE:
        _raise(
            "Step 7G Step 4J first-party adapter is certified only for "
            f"{SUPPORTED_ADAPTER_SEASON_TYPE}; received {normalized_season_type}."
        )
    normalized_last_n = frozen._normalize_last_n_games(last_n_games)
    normalized_location = frozen._normalize_choice(
        location,
        frozen.ALLOWED_LOCATIONS,
        "location",
    )

    base, cache_hit = _cached_base(
        stable_team_key,
        season,
        normalized_season_type,
    )
    rows = base.pop("rows")
    games = frozen._apply_filters(
        rows,
        team_key=stable_team_key,
        opponent_team_key=stable_opponent_key,
        location=normalized_location,
        last_n_games=normalized_last_n,
    )

    return {
        "source": base["source"],
        "source_url": base["source_url"],
        "source_endpoint": base["source_endpoint"],
        "data_type": "official_team_game_log",
        "league_id": frozen.WNBA_LEAGUE_ID,
        "season": season,
        "season_type": normalized_season_type,
        "team_key": stable_team_key,
        "filters": {
            "last_n_games": normalized_last_n,
            "location": normalized_location,
            "opponent_team_key": stable_opponent_key,
        },
        "retrieved_at_utc": base["retrieved_at_utc"],
        "cache_hit": cache_hit,
        "cache_ttl_seconds": STEP7G_STEP4J_CACHE_TTL_SECONDS,
        "source_header_count": base["source_header_count"],
        "season_team_game_count": base["season_team_game_count"],
        "game_count": len(games),
        "summary": frozen._summary(games),
        "games": games,
        "verification": deepcopy(base["verification"]),
        "step7g_adapter": {
            "source_variant": base["source_variant"],
            "upstream_schedule_source_variant": base["upstream_schedule_source_variant"],
            "contract_shape": base["contract_shape"],
            "source_box_score_count": base["source_box_score_count"],
            "source_box_score_cache_hits": base["source_box_score_cache_hits"],
            "production_provider_replaced": False,
        },
    }
