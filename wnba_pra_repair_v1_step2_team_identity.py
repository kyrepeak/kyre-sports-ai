"""WNBA PRA Repair V1 Step 2 — canonical Page-2 team identity guard.

This module is intentionally lightweight and deterministic.  It translates a
selected WNBA schedule game's team identity into the canonical numeric IDs used
by the already-frozen WNBA roster/role stack.

It never fetches data, never imports model code, and never changes projections.
If numeric ID, display name, and tricode disagree, it fails closed instead of
guessing.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

VERSION = "WNBA_PRA_REPAIR_V1_STEP2_TEAM_IDENTITY_V1"
SEASON = 2026

# Canonical 2026 WNBA IDs already used by the frozen WNBA roster/role stack.
TEAM_BY_ID: dict[int, tuple[str, str]] = {
    1611661330: ("Atlanta Dream", "ATL"),
    1611661329: ("Chicago Sky", "CHI"),
    1611661323: ("Connecticut Sun", "CON"),
    1611661321: ("Dallas Wings", "DAL"),
    1611661325: ("Indiana Fever", "IND"),
    1611661319: ("Las Vegas Aces", "LVA"),
    1611661320: ("Los Angeles Sparks", "LAS"),
    1611661324: ("Minnesota Lynx", "MIN"),
    1611661313: ("New York Liberty", "NYL"),
    1611661317: ("Phoenix Mercury", "PHX"),
    1611661328: ("Seattle Storm", "SEA"),
    1611661322: ("Washington Mystics", "WAS"),
    1611661331: ("Golden State Valkyries", "GSV"),
    1611661327: ("Portland Fire", "POR"),
    1611661332: ("Toronto Tempo", "TOR"),
}

_EXTRA_ALIASES: dict[str, int] = {
    "LV": 1611661319,
    "LA": 1611661320,
    "NY": 1611661313,
    "PHO": 1611661317,
    "WSH": 1611661322,
    "GS": 1611661331,
    "PDX": 1611661327,
}


class WNBATeamIdentityError(RuntimeError):
    pass


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _as_int(value: Any) -> int | None:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


ALIAS_TO_ID: dict[str, int] = {}
for _team_id, (_full_name, _tricode) in TEAM_BY_ID.items():
    for _alias in (_full_name, _tricode):
        ALIAS_TO_ID[_key(_alias)] = _team_id
for _alias, _team_id in _EXTRA_ALIASES.items():
    ALIAS_TO_ID[_key(_alias)] = _team_id


def is_canonical_team_id(value: Any) -> bool:
    team_id = _as_int(value)
    return bool(team_id in TEAM_BY_ID)


def resolve_team_identity(
    *,
    raw_team_id: Any,
    team_name: Any,
    team_tricode: Any,
) -> dict[str, Any]:
    raw_id = _as_int(raw_team_id)
    evidence: dict[str, int] = {}

    if raw_id in TEAM_BY_ID:
        evidence["raw_id"] = int(raw_id)

    name_key = _key(team_name)
    if name_key and name_key in ALIAS_TO_ID:
        evidence["name"] = ALIAS_TO_ID[name_key]

    tricode_key = _key(team_tricode)
    if tricode_key and tricode_key in ALIAS_TO_ID:
        evidence["tricode"] = ALIAS_TO_ID[tricode_key]

    candidates = set(evidence.values())
    if not candidates:
        raise WNBATeamIdentityError(
            "WNBA team identity could not be mapped to the canonical 2026 registry."
        )
    if len(candidates) != 1:
        raise WNBATeamIdentityError(
            "WNBA team identity fields disagree; refusing to guess."
        )

    canonical_id = next(iter(candidates))
    full_name, canonical_tricode = TEAM_BY_ID[canonical_id]
    return {
        "team_id": canonical_id,
        "full_name": full_name,
        "tricode": canonical_tricode,
        "source_team_id": raw_id,
        "numeric_id_repaired": raw_id != canonical_id,
        "evidence": tuple(sorted(evidence)),
    }


def reconcile_game_identity(game: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(game, Mapping):
        raise WNBATeamIdentityError("WNBA selected game must be an object.")

    out = dict(game)
    away = resolve_team_identity(
        raw_team_id=game.get("away_team_id"),
        team_name=game.get("away_team"),
        team_tricode=game.get("away_tricode"),
    )
    home = resolve_team_identity(
        raw_team_id=game.get("home_team_id"),
        team_name=game.get("home_team"),
        team_tricode=game.get("home_tricode"),
    )
    if away["team_id"] == home["team_id"]:
        raise WNBATeamIdentityError("WNBA matchup resolved both sides to one team.")

    out["away_source_team_id"] = away["source_team_id"]
    out["home_source_team_id"] = home["source_team_id"]
    out["away_team_id"] = int(away["team_id"])
    out["home_team_id"] = int(home["team_id"])
    out["away_identity_repaired"] = bool(away["numeric_id_repaired"])
    out["home_identity_repaired"] = bool(home["numeric_id_repaired"])
    out["team_identity_version"] = VERSION
    out["team_identity_state"] = "CANONICAL"
    return out


def reconcile_slate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WNBATeamIdentityError("WNBA slate payload must be an object.")
    out = dict(payload)
    raw_games = payload.get("games")
    if not isinstance(raw_games, list):
        raise WNBATeamIdentityError("WNBA slate payload is missing games.")

    games = []
    repaired_sides = 0
    for raw in raw_games:
        game = reconcile_game_identity(raw)
        repaired_sides += int(bool(game.get("away_identity_repaired")))
        repaired_sides += int(bool(game.get("home_identity_repaired")))
        games.append(game)

    out["games"] = games
    out["team_identity_state"] = "CANONICAL"
    out["team_identity_version"] = VERSION
    out["team_identity_repaired_sides"] = repaired_sides
    return out


__all__ = [
    "ALIAS_TO_ID",
    "SEASON",
    "TEAM_BY_ID",
    "VERSION",
    "WNBATeamIdentityError",
    "is_canonical_team_id",
    "reconcile_game_identity",
    "reconcile_slate_payload",
    "resolve_team_identity",
]
