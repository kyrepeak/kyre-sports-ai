"""CFB Player Props Page 2 V1 — exact-game multi-book market aggregation."""
from __future__ import annotations

from datetime import date
import math
import re
from typing import Any, Mapping, Sequence

import cfb_player_props_fanduel_v1 as fanduel
import cfb_player_props_sportsgameodds_v1 as sgo
from cfb_player_props_identity_v1 import build_identity_index
from cfb_player_props_market_v1 import (
    PropObservation,
    SUPPORTED_MARKETS,
    merge_prop_observations,
    normalize_prop_observation,
)
from cfb_player_props_model_v1 import build_market_consensus
from cfb_player_props_page2_roster_v1 import Page2Player
from sports_api.api import cfb_market_identity_v1 as game_identity

MARKET_ORDER = (
    "passing_yards", "rushing_yards", "receiving_yards",
    "receiving_receptions", "passing_touchdowns", "touchdowns",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _text(value).casefold()))


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _verified_game(context: Mapping[str, Any]) -> dict[str, Any]:
    game = context.get("game")
    out = dict(game) if isinstance(game, Mapping) else {}
    out.setdefault("official_game_id", _text(context.get("official_game_id")))
    out.setdefault("game_date", _text(context.get("slate_date")))
    for side in ("away", "home"):
        out.setdefault(f"{side}_team_id", _text(context.get(f"{side}_team_id")))
        out.setdefault(f"{side}_team", _text(context.get(f"{side}_team")))
    out.setdefault("kickoff_iso", _text(context.get("kickoff_iso")))
    return out


def _bind_game(raw: Mapping[str, Any], game: Mapping[str, Any]) -> bool:
    official_game_id = _text(game.get("official_game_id"))
    raw_official = _text(raw.get("official_game_id"))
    if raw_official:
        return raw_official == official_game_id

    provider_game = {
        "start_time_utc": raw.get("event_start"),
        "away_team": raw.get("away_team"),
        "home_team": raw.get("home_team"),
    }
    if not all(_text(provider_game.get(key)) for key in ("start_time_utc", "away_team", "home_team")):
        return False
    verified = [{
        "event_id": official_game_id,
        "game_date": _text(game.get("game_date")),
        "away_team": _text(game.get("away_team")),
        "home_team": _text(game.get("home_team")),
        "away_team_id": _text(game.get("away_team_id")),
        "home_team_id": _text(game.get("home_team_id")),
    }]
    try:
        _, candidates = game_identity._qualified_candidates(provider_game, verified)
    except Exception:
        return False
    if len(candidates) != 1:
        return False
    candidate = candidates[0].get("verified") if isinstance(candidates[0], Mapping) else None
    return isinstance(candidate, Mapping) and _text(candidate.get("event_id")) == official_game_id


def _bind_player(raw: Mapping[str, Any], players: Sequence[Page2Player]) -> Page2Player | None:
    official_id = _text(raw.get("official_player_id"))
    if official_id:
        matches = [player for player in players if player.official_player_id == official_id]
        return matches[0] if len(matches) == 1 else None

    team_id = _text(raw.get("official_team_id") or raw.get("team_id"))
    name = _norm(raw.get("player_name"))
    if not name:
        return None
    matches = [
        player for player in players
        if _norm(player.canonical_name) == name
        and (not team_id or player.official_team_id == team_id)
    ]
    return matches[0] if len(matches) == 1 else None


def _normalize_raw_rows(
    raws: Sequence[Mapping[str, Any]],
    game: Mapping[str, Any],
    players: Sequence[Page2Player],
) -> list[PropObservation]:
    out: list[PropObservation] = []
    official_game_id = _text(game.get("official_game_id"))
    for raw in raws:
        if not _bind_game(raw, game):
            continue
        player = _bind_player(raw, players)
        if player is None:
            continue
        enriched = dict(raw)
        enriched.update({
            "official_game_id": official_game_id,
            "official_player_id": player.official_player_id,
            "official_team_id": player.official_team_id,
        })
        observation = normalize_prop_observation(enriched, build_identity_index([player.identity]))
        if observation is not None:
            out.append(observation)
    return out


def load_game_prop_observations(
    context: Mapping[str, Any], players: Sequence[Page2Player]
) -> list[PropObservation]:
    if _text(context.get("state")) not in {"", "ready"}:
        return []
    game = _verified_game(context)
    if not _text(game.get("official_game_id")):
        return []
    try:
        slate_date = date.fromisoformat(_text(context.get("slate_date") or game.get("game_date"))[:10])
    except ValueError:
        return []

    try:
        sgo_raw = list(sgo.fetch_sgo_cfb_player_props(slate_date) or [])
    except Exception:
        sgo_raw = []
    try:
        fd_raw = list(fanduel.fetch_fanduel_cfb_player_props([game]) or [])
    except Exception:
        fd_raw = []

    normalized = _normalize_raw_rows([*sgo_raw, *fd_raw], game, players)
    allowed_players = {player.official_player_id for player in players}
    official_game_id = _text(game.get("official_game_id"))
    return [
        row for row in merge_prop_observations(normalized)
        if row.official_game_id == official_game_id
        and row.canonical_player_id in allowed_players
        and row.market_key in SUPPORTED_MARKETS
    ]


def _best_row(rows: Sequence[PropObservation], side: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.side == side and _finite(row.line) is not None]
    if not candidates:
        return None

    def price_score(row: PropObservation) -> int:
        return int(row.price) if row.price is not None else -100000

    if side == "over":
        chosen = min(candidates, key=lambda row: (float(row.line), -price_score(row), row.sportsbook.casefold()))
    else:
        chosen = min(candidates, key=lambda row: (-float(row.line), -price_score(row), row.sportsbook.casefold()))
    return {"sportsbook": chosen.sportsbook, "line": float(chosen.line), "price": chosen.price}


def _movement(
    player: Page2Player,
    market_key: str,
    rows: Sequence[PropObservation],
    opening_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unavailable = {"available": False, "opening_line": None, "current_line": None, "delta": None, "source": ""}
    current_by_book: dict[str, PropObservation] = {}
    for row in rows:
        prior = current_by_book.get(row.sportsbook)
        if prior is None or row.observed_at_utc > prior.observed_at_utc:
            current_by_book[row.sportsbook] = row

    for raw in opening_rows:
        if raw.get("opening_verified") is not True and raw.get("trusted_opening") is not True:
            continue
        source = _text(raw.get("source"))
        source_lower = source.casefold()
        if "session" in source_lower or "first-seen" in source_lower or "first seen" in source_lower:
            continue
        raw_player = _text(raw.get("canonical_player_id") or raw.get("player_id"))
        if raw_player != player.official_player_id or _text(raw.get("market_key")) != market_key:
            continue
        book = _text(raw.get("sportsbook"))
        current = current_by_book.get(book)
        opening = _finite(raw.get("opening_line"))
        if current is None or opening is None:
            continue
        current_line = float(current.line)
        return {
            "available": True,
            "sportsbook": book,
            "opening_line": float(opening),
            "current_line": current_line,
            "delta": current_line - float(opening),
            "source": source,
        }
    return unavailable


def build_player_market_view(
    player: Page2Player,
    market_key: str,
    observations: Sequence[PropObservation],
    *,
    opening_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if market_key not in SUPPORTED_MARKETS:
        return {
            "market_key": market_key, "observations": [], "book_count": 0,
            "consensus_line": None, "best_over": None, "best_under": None,
            "movement": {"available": False, "opening_line": None, "current_line": None, "delta": None, "source": ""},
        }
    filtered = [
        row for row in observations
        if row.identity_verified is True
        and row.canonical_player_id == player.official_player_id
        and row.market_key == market_key
    ]
    rows = merge_prop_observations(filtered)
    consensus = build_market_consensus(rows)
    return {
        "market_key": market_key,
        "observations": rows,
        "book_count": int(consensus.get("book_count") or 0),
        "consensus_line": consensus.get("line"),
        "market_probability": consensus.get("market_probability") or {},
        "paired_books": consensus.get("paired_books") or (),
        "best_over": _best_row(rows, "over"),
        "best_under": _best_row(rows, "under"),
        "movement": _movement(player, market_key, rows, opening_rows),
    }


def group_player_markets(
    players: Sequence[Page2Player], observations: Sequence[PropObservation]
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for player in players:
        views = []
        for market_key in MARKET_ORDER:
            if any(
                row.canonical_player_id == player.official_player_id and row.market_key == market_key
                for row in observations
            ):
                views.append(build_player_market_view(player, market_key, observations))
        out[player.official_player_id] = views
    return out


__all__ = [
    "MARKET_ORDER", "build_player_market_view", "group_player_markets",
    "load_game_prop_observations",
]
