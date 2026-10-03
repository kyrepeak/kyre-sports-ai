"""CFB Game Total clean page V16 — Step 4 Matchup V2 activation.

Additive over frozen V164 Page V15. Only the Step 4 presentation owner advances.
Steps 1-3, selector identity, logos, model math, distribution math, qualification,
Top-5 behavior, APIs, and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import cfb_game_total_clean_page_v15 as prior_v164
import cfb_schedule_v3 as frozen_schedule
import cfb_game_total_step4_matchup_v2 as step4_owner

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V16 • V165 STEP4 MATCHUP BOARD"
MARKET = prior_v164.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v15"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • V165 STEP4 MATCHUP ACTIVE"
STEP4_PRESENTATION_MARKER = step4_owner.STEP4_PRESENTATION_MARKER
STEP4_DATA_MARKER = step4_owner.STEP4_DATA_MARKER
STEP4_DEPLOYMENT_MARKER = step4_owner.STEP4_DEPLOYMENT_MARKER
STEP4_VISUAL_MARKER = step4_owner.STEP4_VISUAL_MARKER
STEP4_GRADE_MARKER = step4_owner.STEP4_GRADE_MARKER
SCHEDULE_FAILOVER_MARKER = "CFB_GAME_TOTAL_V168_SELECTOR_SCHEDULE_FAILOVER_ACTIVE"

# Re-export the V164 identity helpers for source-level certification and rollback.
_resolve_visuals_v164 = prior_v164._resolve_visuals_v164
_team_identity_v164 = prior_v164._team_identity_v164
_reconcile_display_bundle_v164 = prior_v164._reconcile_display_bundle_v164
_selector_payload_for_day = prior_v164._selector_payload_for_day
_selector_payload_for_game = prior_v164._selector_payload_for_game
_query_selected_day = prior_v164._query_selected_day


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _selector_seed_games_v168(selected_day: Any) -> list[dict[str, Any]]:
    """Build verified schedule identities from the existing selector contract."""
    day = (
        selected_day.isoformat()
        if hasattr(selected_day, "isoformat")
        else _clean(selected_day)[:10]
    )
    if not day:
        return []

    try:
        payload = prior_v164._selector_payload_for_day(day)
    except Exception:
        return []
    if not isinstance(payload, Mapping):
        return []
    if payload.get("synthetic_ids") is not False:
        return []
    try:
        if float(payload.get("projection_weight") or 0.0) != 0.0:
            return []
    except (TypeError, ValueError):
        return []
    if payload.get("may_modify_projection") not in (None, False):
        return []

    seeds: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.get("games") or []:
        if not isinstance(raw, Mapping):
            continue
        event_id = _clean(raw.get("event_id"))
        game_date = _clean(raw.get("game_date"))[:10]
        away_team = _clean(raw.get("away_team"))
        home_team = _clean(raw.get("home_team"))
        if (
            not event_id.isdigit()
            or game_date != day
            or not away_team
            or not home_team
            or event_id in seen
            or raw.get("identity_verified") is not True
        ):
            continue
        seen.add(event_id)
        away_id = _clean(raw.get("away_team_id"))
        home_id = _clean(raw.get("home_team_id"))
        seeds.append(
            {
                "game_id": event_id,
                "identity_key": f"espn:{event_id}",
                "identity_fingerprint": f"espn:{event_id}",
                "game_date": day,
                "kickoff_et": "TBD",
                "kickoff_iso": "",
                "away_team": away_team,
                "away_team_slug": _slug(away_team),
                "away_conference": "Conference unavailable",
                "away_rank": None,
                "away_espn_team_id": away_id if away_id.isdigit() else "",
                "home_team": home_team,
                "home_team_slug": _slug(home_team),
                "home_conference": "Conference unavailable",
                "home_rank": None,
                "home_espn_team_id": home_id if home_id.isdigit() else "",
                "venue": _clean(raw.get("venue")) or "Venue unavailable",
                "status": _clean(raw.get("status")) or "Status unavailable",
                "broadcast": _clean(raw.get("broadcast")) or "Broadcast unavailable",
                "neutral_site": False,
                "ncaa_url": "",
                "espn_event_id": event_id,
                "schedule_source": "Kyre Sports API verified selector failover",
                "enrichment_source": _clean(raw.get("identity_source"))
                or "verified selector contract",
                "identity_verified": True,
                "date_matches_query": True,
                "identity_provider": "ESPN",
                "schedule_v168_selector_failover": True,
            }
        )

    seeds.sort(
        key=lambda game: (
            _clean(game.get("away_team")).casefold(),
            _clean(game.get("home_team")).casefold(),
            _clean(game.get("espn_event_id")),
        )
    )
    return seeds


def _load_schedule_with_selector_failover_v168(
    original_loader,
    target_date: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use frozen Schedule V3 normally; recover only when it raises."""
    try:
        return original_loader(target_date)
    except Exception as exc:
        seeds = _selector_seed_games_v168(target_date)
        day = (
            target_date.isoformat()
            if hasattr(target_date, "isoformat")
            else _clean(target_date)[:10]
        )
        venue_missing = sum(
            1
            for game in seeds
            if _clean(game.get("venue")) in {"", "Venue unavailable"}
        )
        broadcast_missing = sum(
            1
            for game in seeds
            if _clean(game.get("broadcast")) in {"", "Broadcast unavailable"}
        )
        return seeds, {
            "version": "CFB GAME TOTAL V168 • SELECTOR SCHEDULE FAILOVER",
            "requested_date": day,
            "source": (
                "Kyre Sports API verified selector failover"
                if seeds
                else "none"
            ),
            "games": len(seeds),
            "identity_ready": bool(seeds)
            and all(
                bool(
                    game.get("identity_verified")
                    and game.get("date_matches_query")
                )
                for game in seeds
            ),
            "venue_missing": venue_missing,
            "broadcast_missing": broadcast_missing,
            "schedule_v168_selector_failover_active": True,
            "schedule_v3_failure": f"{type(exc).__name__}: {exc}"[:500],
            "fail_closed": True,
            "synthetic_ids": False,
            "fuzzy_matching": False,
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "attempts": [
                {
                    "provider": "frozen cfb_schedule_v3",
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                },
                {
                    "provider": "Kyre Sports API verified selector",
                    "ok": bool(seeds),
                    "games": len(seeds),
                    "error": "" if seeds else "verified selector returned no usable games",
                },
            ],
        }



def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    original_step4_owner = prior_v164.step4_owner
    original_step4_marker = prior_v164.STEP4_PRESENTATION_MARKER
    original_schedule_loader = frozen_schedule.load_with_diagnostics

    def schedule_loader_v168(target_date):
        return _load_schedule_with_selector_failover_v168(
            original_schedule_loader,
            target_date,
        )

    frozen_schedule.load_with_diagnostics = schedule_loader_v168
    prior_v164.step4_owner = step4_owner
    prior_v164.STEP4_PRESENTATION_MARKER = (
        f"{STEP4_PRESENTATION_MARKER} • {STEP4_DEPLOYMENT_MARKER} • {STEP4_VISUAL_MARKER} • {STEP4_GRADE_MARKER} • {SCHEDULE_FAILOVER_MARKER}"
    )
    try:
        return prior_v164.render_game_total_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_schedule.load_with_diagnostics = original_schedule_loader
        prior_v164.step4_owner = original_step4_owner
        prior_v164.STEP4_PRESENTATION_MARKER = original_step4_marker


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V165 Game Total V16 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SCHEDULE_FAILOVER_MARKER",
    "STEP4_DATA_MARKER",
    "STEP4_DEPLOYMENT_MARKER",
    "STEP4_GRADE_MARKER",
    "STEP4_PRESENTATION_MARKER",
    "STEP4_VISUAL_MARKER",
    "_load_schedule_with_selector_failover_v168",
    "_query_selected_day",
    "_selector_seed_games_v168",
    "_reconcile_display_bundle_v164",
    "_resolve_visuals_v164",
    "_selector_payload_for_day",
    "_selector_payload_for_game",
    "_team_identity_v164",
    "render_cfb_hub",
    "render_game_total_hub",
]
