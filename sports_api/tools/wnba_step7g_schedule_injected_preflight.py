"""Run the existing Step 7G official-data preflight through certified first-party
WNBA.com diagnostic adapters.

This wrapper is OFF-only. It never replaces the frozen production providers.
It injects the already-certified first-party schedule source plus the already-
certified WNBA.com Step-4D box-score / Step-4K play-by-play bridge only into the
local preflight module, then reports the next dependency boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

import httpx

from sports_api import wnba_schedule as frozen_schedule
from sports_api.tools import wnba_step7g_official_data_preflight as preflight
from sports_api.wnba_step7g_first_party_history import (
    HTTP_HEADERS as FIRST_PARTY_HTTP_HEADERS,
    _parse_page_props,
    get_first_party_game_box_score_dataset,
    get_first_party_play_by_play_dataset,
)
from sports_api.wnba_step7g_first_party_schedule import (
    _fetch_first_party_schedule_payload,
)


def _first_party_season_schedule_dataset(season: int) -> dict[str, Any]:
    """Build the season dataset with frozen Step-4C normalization semantics."""
    payload, retrieved_at_utc, source_variant, source_url, cache_hit = (
        _fetch_first_party_schedule_payload(season)
    )
    root = frozen_schedule._schedule_root(payload)

    games: list[dict[str, Any]] = []
    source_date_block_count = 0
    source_game_count = 0
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        target_date = frozen_schedule._date_block_iso(block.get("gameDate"))
        if target_date is None:
            continue
        source_date_block_count += 1
        raw_games = block.get("games")
        if not isinstance(raw_games, list):
            continue
        valid_raw_games = [game for game in raw_games if isinstance(game, dict)]
        source_game_count += len(valid_raw_games)
        games.extend(
            frozen_schedule._normalize_game(game, target_date, season)
            for game in valid_raw_games
        )

    games.sort(
        key=lambda game: (
            game.get("official_schedule_date") or "",
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )

    return {
        "source": frozen_schedule.WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": source_variant,
        "league_id": frozen_schedule.WNBA_LEAGUE_ID,
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "source_date_block_count": source_date_block_count,
        "source_game_count": source_game_count,
        "game_count": len(games),
        "games": games,
    }


def _preflight_player_view(player: dict[str, Any]) -> dict[str, Any]:
    """Expose certified Step-4D fields under the legacy preflight view only."""
    return {
        **player,
        "name": player.get("full_name"),
        "starter": "1" if player.get("is_starter") is True else "0",
        "played": player.get("appeared") is True,
        "statistics": player.get("stats") if isinstance(player.get("stats"), dict) else {},
    }


def _preflight_team_view(team: dict[str, Any]) -> dict[str, Any]:
    players = [
        _preflight_player_view(player)
        for player in team.get("players", [])
        if isinstance(player, dict)
    ]
    return {
        **team,
        "player_count": len(players),
        "players": players,
    }


def _first_party_preflight_game_state(game_id: str, season: int) -> dict[str, Any]:
    """Adapt the certified Step-4D box contract to the old preflight-only view.

    The old preflight only calls this function for games already filtered as
    final by the certified schedule dataset, so the status marker below records
    that diagnostic context rather than creating a new production status source.
    """
    box = get_first_party_game_box_score_dataset(game_id, season)
    return {
        "source": box.get("source"),
        "source_url": box.get("source_url"),
        "source_endpoint": box.get("source_endpoint"),
        "season": season,
        "game_id": game_id,
        "status": {
            "category": "final",
            "diagnostic_context": "caller_pre_filtered_by_certified_schedule_final_status",
        },
        "home": _preflight_team_view(box["home"]),
        "away": _preflight_team_view(box["away"]),
        "verification": {
            "source_contract": box.get("contract_shape"),
            "diagnostic_compatibility_view_only": True,
            "production_provider_replaced": False,
        },
    }


def _resolve_official_team_identity(team_key: str) -> tuple[int, str] | None:
    """Resolve the official team ID + slug from certified first-party schedule data."""
    dataset = _first_party_season_schedule_dataset(preflight.SEASON)
    for game in dataset.get("games", []):
        if not isinstance(game, dict):
            continue
        for side in ("away", "home"):
            team = game.get(side)
            if not isinstance(team, dict) or team.get("team_key") != team_key:
                continue
            team_id = team.get("official_team_id")
            slug = team.get("team_slug") or team.get("team_key")
            if isinstance(team_id, int) and team_id > 0 and isinstance(slug, str) and slug:
                return team_id, slug
    return None


def _first_party_team_page_roster_probe(
    team_key: str,
    sample_player_name: str | None,
) -> dict[str, Any]:
    """Verify roster evidence on the real WNBA team-page route.

    WNBA.com's route is /team/{official_team_id}/{slug}; the legacy preflight's
    /team/{slug}/roster route is not a valid current WNBA.com route.
    """
    identity = _resolve_official_team_identity(team_key)
    if identity is None:
        return {
            "url": None,
            "reachable": False,
            "error_type": "OfficialTeamIdentityNotResolved",
            "route_shape": "/team/{official_team_id}/{slug}",
        }

    team_id, slug = identity
    url = f"https://www.wnba.com/team/{team_id}/{slug}"
    started = datetime.now(timezone.utc)
    try:
        response = httpx.get(
            url,
            headers=FIRST_PARTY_HTTP_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        response.raise_for_status()
        page_props = _parse_page_props(response.text, url=str(response.url))
        serialized = json.dumps(page_props, sort_keys=True).casefold()
        needle = " ".join(str(sample_player_name or "").strip().split()).casefold()
        player_present = bool(needle and needle in serialized)
        return {
            "url": str(response.url),
            "http_status": response.status_code,
            "elapsed_seconds": round(elapsed, 3),
            "html_bytes": len(response.content),
            "route_shape": "/team/{official_team_id}/{slug}",
            "official_team_id": team_id,
            "team_slug": slug,
            "structured_next_data_available": True,
            "sample_player_name_present": player_present,
            "reachable": player_present,
        }
    except (httpx.HTTPError, RuntimeError, LookupError, ValueError) as exc:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return {
            "url": url,
            "http_status": getattr(getattr(exc, "response", None), "status_code", None),
            "elapsed_seconds": round(elapsed, 3),
            "route_shape": "/team/{official_team_id}/{slug}",
            "official_team_id": team_id,
            "team_slug": slug,
            "reachable": False,
            "error_type": type(exc).__name__,
        }


def _is_first_party_wnba_url(value: Any) -> bool:
    return str(value or "").startswith("https://www.wnba.com/")


def main() -> int:
    # Inject only into this diagnostic module's local dependency references.
    preflight._season_schedule_dataset = _first_party_season_schedule_dataset
    preflight.get_live_game_state_dataset = _first_party_preflight_game_state
    preflight.get_play_by_play_dataset = get_first_party_play_by_play_dataset
    preflight._official_roster_web_probe = _first_party_team_page_roster_probe

    report = preflight.build_report()

    schedule_first_party = _is_first_party_wnba_url(
        (report.get("schedule") or {}).get("source_url")
    )
    probe = report.get("probe_game") or {}
    box_first_party = _is_first_party_wnba_url(probe.get("box_score_source_url"))
    pbp_first_party = _is_first_party_wnba_url(probe.get("play_by_play_source_url"))

    report["data_type"] = "wnba_step7g_official_data_preflight_v3_first_party_injected"
    report["diagnostic_injections"] = {
        "certified_first_party_schedule": True,
        "certified_first_party_box_score": True,
        "certified_first_party_play_by_play": True,
        "official_team_page_roster_route": True,
        "diagnostic_compatibility_view_only": True,
        "frozen_production_provider_replaced": False,
    }
    report["schedule"]["official_first_party_wnba_com"] = schedule_first_party
    report["probe_game"]["official_first_party_wnba_com"] = (
        box_first_party and pbp_first_party
    )

    feasibility = report["feasibility"]
    feasibility["schedule_raw_evidence_available_without_stats_host"] = schedule_first_party
    feasibility["boxscore_and_pbp_raw_evidence_available_without_stats_host"] = (
        box_first_party and pbp_first_party
    )
    feasibility["production_activation_safe_now"] = False
    report["next_required_step"] = (
        "Keep production OFF. Use the certified first-party schedule/history/PBP/team-page "
        "surfaces plus the separately certified rotation fallback in an isolated Step-7G "
        "dependency-injection test. Do not replace frozen shared providers."
    )

    preflight.REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    required = (
        "schedule_raw_evidence_available_without_stats_host",
        "boxscore_and_pbp_raw_evidence_available_without_stats_host",
        "player_game_log_reconstruction_raw_evidence_available",
        "team_workload_reconstruction_raw_evidence_available",
        "rotation_reconstruction_raw_evidence_available",
        "official_roster_web_reachable",
    )
    missing = [name for name in required if feasibility.get(name) is not True]
    if missing:
        raise RuntimeError(
            "Step 7G first-party injected preflight is not yet source-feasible: "
            + ", ".join(missing)
        )
    if feasibility.get("production_activation_safe_now") is not False:
        raise RuntimeError("Preflight must never certify production activation directly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
