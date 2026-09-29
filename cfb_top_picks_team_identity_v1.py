"""CFB Top Picks Research V2 Step 2 — ranked-team identity + logo resolver.

Only the already-ranked Top Picks rows are enriched. Ranking, probability,
reliability, sportsbook inputs, projection math, and selection are untouched.

Resolution order per side:
1. exact ESPN team ID already carried by the certified CFB slate;
2. exact ESPN NCAA logo CDN from that ID;
3. independent existing multi-source logo resolver only when the exact logo
   path is unavailable.

API 2 is intentionally not imported or called by this module.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import cfb_over_under_logo_resolver_v2 as multisource
import cfb_over_under_logo_resolver_v3 as exact_logo

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 2 • TEAM IDENTITY + REAL LOGOS"
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_PROJECTION = False
API2_USED = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_http_url(value: Any) -> str:
    text = _clean(value)
    return text if text.startswith(("https://", "http://")) else ""


def _slug(value: Any) -> str:
    text = _clean(value).casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _team_id(game: Mapping[str, Any], side: str, visual: Mapping[str, Any]) -> str:
    for value in (
        visual.get("team_id"),
        game.get(f"{side}_espn_team_id"),
        game.get(f"{side}_team_id"),
    ):
        text = _clean(value)
        if text.isdigit():
            return text
    return ""


def _side_name(row: Mapping[str, Any], game: Mapping[str, Any], side: str) -> str:
    return _clean(game.get(f"{side}_team") or row.get(side))


def _side_slug(row: Mapping[str, Any], game: Mapping[str, Any], side: str) -> str:
    return _clean(game.get(f"{side}_team_slug")) or _slug(_side_name(row, game, side))


def _side_conference(game: Mapping[str, Any], side: str) -> str:
    return _clean(game.get(f"{side}_conference"))


def resolve_ranked_pick(
    row: Mapping[str, Any],
    game: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach canonical team IDs and real logo provenance to one ranked pick."""
    out = dict(row)
    try:
        exact = exact_logo.resolve_visuals(game)
    except Exception:
        exact = {"away": {}, "home": {}}

    all_attempts: list[dict[str, Any]] = []
    ready_sides = 0

    for side in ("away", "home"):
        visual = dict((exact or {}).get(side) or {})
        team_id = _team_id(game, side, visual)
        logo = _safe_http_url(visual.get("logo"))
        provider = _clean(visual.get("logo_provider"))
        source = _clean(visual.get("source"))
        source_url = _safe_http_url(visual.get("logo_source_url") or logo)
        confidence = _clean(visual.get("confidence"))
        method = _clean(visual.get("resolution_method"))

        attempts: list[dict[str, Any]] = [{
            "provider": "espn_exact_team_id",
            "team_id": team_id,
            "status": "resolved" if logo else "unavailable",
        }]

        if not logo:
            name = _side_name(row, game, side)
            fallback = multisource.resolve_team_logo(
                name,
                _side_slug(row, game, side),
                _side_conference(game, side),
            ) if name else {}
            logo = _safe_http_url(fallback.get("logo"))
            provider = _clean(fallback.get("logo_provider"))
            source = _clean(fallback.get("source"))
            source_url = _safe_http_url(fallback.get("logo_source_url") or logo)
            confidence = _clean(fallback.get("confidence"))
            provider_attempts = fallback.get("provider_attempts")
            if isinstance(provider_attempts, list):
                attempts.extend(dict(item) for item in provider_attempts if isinstance(item, Mapping))
            attempts.append({
                "provider": provider or "multi_source_fallback",
                "status": "resolved" if logo else "unavailable",
            })

        canonical_ready = bool(team_id.isdigit() and logo)
        if canonical_ready:
            ready_sides += 1

        out[f"{side}_team_id"] = team_id
        out[f"{side}_logo_url"] = logo
        out[f"{side}_logo_provider"] = provider
        out[f"{side}_logo_source"] = source
        out[f"{side}_logo_source_url"] = source_url
        out[f"{side}_logo_confidence"] = confidence
        out[f"{side}_logo_resolution_method"] = method or (
            "exact_espn_team_id" if provider.startswith("espn") else "multi_source_fallback"
        )
        out[f"{side}_logo_ready"] = canonical_ready
        out[f"{side}_logo_attempts"] = attempts
        all_attempts.extend(attempts)

    out["logo_identity_ready"] = ready_sides == 2
    out["logo_ready_sides"] = ready_sides
    out["logo_resolution_status"] = "GREEN" if ready_sides == 2 else "INCOMPLETE"
    out["logo_resolution_model"] = MODEL_VERSION
    out["logo_provider_attempts"] = all_attempts
    out["api2_used_for_logos"] = API2_USED
    return out


def enrich_ranked_picks(
    picks: list[Mapping[str, Any]],
    games_by_event: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich only the final ranked rows; never re-rank or alter probabilities."""
    out: list[dict[str, Any]] = []
    for raw in picks:
        row = dict(raw)
        event_id = _clean(row.get("event_id"))
        game = dict(games_by_event.get(event_id) or {})
        if not game:
            game = {
                "espn_event_id": event_id,
                "away_team": _clean(row.get("away")),
                "home_team": _clean(row.get("home")),
                "away_espn_team_id": _clean(row.get("away_team_id")),
                "home_espn_team_id": _clean(row.get("home_team_id")),
            }
        out.append(resolve_ranked_pick(row, game))
    return out


__all__ = [
    "API2_USED",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MODEL_VERSION",
    "enrich_ranked_picks",
    "resolve_ranked_pick",
]
