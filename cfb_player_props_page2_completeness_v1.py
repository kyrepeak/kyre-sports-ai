"""CFB Player Props Page 2 market-completeness owner.

Field-specific source policy for player props:
1) Direct FanDuel (primary direct sportsbook)
2) SportsGameOdds multi-book observations (DraftKings/FanDuel/BetMGM/Caesars)
3) Odds-API.io gap-fill using the app's existing connected key

Sources fail independently. Missing values are never converted to zero. The
sportsbook layer is market context only and has zero projection influence.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

import cfb_player_props_fanduel_bound_v2 as fanduel
import cfb_player_props_odds_api_v1 as odds_api
import cfb_player_props_page2_market_v1 as legacy_market
import cfb_player_props_sportsgameodds_v1 as sgo
from cfb_player_props_market_v1 import PropObservation, SUPPORTED_MARKETS, merge_prop_observations
from cfb_player_props_page2_roster_v1 import Page2Player

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SOURCE_ORDER = ("FanDuel", "SportsGameOdds", "Odds-API.io")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _verified_game(context: Mapping[str, Any]) -> dict[str, Any]:
    return legacy_market._verified_game(context)


def _normalize_source_rows(
    rows: Sequence[Mapping[str, Any]],
    game: Mapping[str, Any],
    players: Sequence[Page2Player],
) -> list[PropObservation]:
    return legacy_market._normalize_raw_rows(rows, game, players)


def build_coverage_summary(
    observations: Sequence[PropObservation],
    players: Sequence[Page2Player],
) -> dict[str, Any]:
    verified = [row for row in observations if row.identity_verified is True]
    player_ids = {row.canonical_player_id for row in verified}
    markets = {(row.canonical_player_id, row.market_key) for row in verified}
    books = {row.sportsbook for row in verified if _text(row.sportsbook)}
    providers = {row.provider for row in verified if _text(row.provider)}
    stamps = [_text(row.observed_at_utc) for row in verified if _text(row.observed_at_utc)]
    return {
        "players_with_markets": len(player_ids),
        "roster_players": len(players),
        "market_count": len(markets),
        "sportsbook_count": len(books),
        "provider_count": len(providers),
        "freshest_observed_at_utc": max(stamps) if stamps else "",
    }


def load_game_prop_observations_with_diagnostics(
    context: Mapping[str, Any],
    players: Sequence[Page2Player],
) -> tuple[list[PropObservation], dict[str, Any]]:
    if _text(context.get("state")) not in {"", "ready"}:
        summary = build_coverage_summary([], players)
        return [], {**summary, "source_errors": {}, "source_counts": {name: 0 for name in SOURCE_ORDER}}

    game = _verified_game(context)
    official_game_id = _text(game.get("official_game_id"))
    if not official_game_id:
        summary = build_coverage_summary([], players)
        return [], {**summary, "source_errors": {}, "source_counts": {name: 0 for name in SOURCE_ORDER}}

    try:
        slate_date = date.fromisoformat(_text(context.get("slate_date") or game.get("game_date"))[:10])
    except ValueError:
        summary = build_coverage_summary([], players)
        return [], {**summary, "source_errors": {}, "source_counts": {name: 0 for name in SOURCE_ORDER}}

    source_errors: dict[str, str] = {}
    source_counts: dict[str, int] = {name: 0 for name in SOURCE_ORDER}
    normalized_sources: list[list[PropObservation]] = []

    fetchers = (
        ("FanDuel", lambda: fanduel.fetch_fanduel_cfb_player_props([game])),
        ("SportsGameOdds", lambda: sgo.fetch_sgo_cfb_player_props(slate_date)),
        ("Odds-API.io", lambda: odds_api.fetch_odds_api_cfb_player_props([game])),
    )

    for source_name, fetch in fetchers:
        try:
            raw_rows = list(fetch() or [])
        except Exception as exc:
            source_errors[source_name] = type(exc).__name__
            raw_rows = []
        normalized = _normalize_source_rows(raw_rows, game, players)
        source_counts[source_name] = len(normalized)
        normalized_sources.append(normalized)

    merged = merge_prop_observations(*normalized_sources)
    allowed_players = {player.official_player_id for player in players}
    observations = [
        row for row in merged
        if row.official_game_id == official_game_id
        and row.canonical_player_id in allowed_players
        and row.market_key in SUPPORTED_MARKETS
        and row.line is not None
    ]

    summary = build_coverage_summary(observations, players)
    diagnostics = {
        **summary,
        "source_errors": source_errors,
        "source_counts": source_counts,
        "source_order": SOURCE_ORDER,
    }
    return observations, diagnostics


def load_game_prop_observations(
    context: Mapping[str, Any], players: Sequence[Page2Player]
) -> list[PropObservation]:
    observations, _ = load_game_prop_observations_with_diagnostics(context, players)
    return observations


__all__ = [
    "SOURCE_ORDER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_coverage_summary",
    "load_game_prop_observations",
    "load_game_prop_observations_with_diagnostics",
]
