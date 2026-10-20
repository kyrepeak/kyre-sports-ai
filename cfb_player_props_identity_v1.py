"""CFB Player Props V1 — exact official/player identity contract."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CanonicalPlayerIdentity:
    official_player_id: str
    official_team_id: str
    canonical_name: str
    position: str
    team_name: str
    team_abbr: str
    provider_aliases: tuple[tuple[str, str], ...] = ()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _provider(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _text(value).lower())


def player_identity_from_roster_row(
    row: Mapping[str, Any], *, official_team_id: str, team_name: str, team_abbr: str = ""
) -> CanonicalPlayerIdentity | None:
    player_id = _text(row.get("id") or row.get("athleteId") or row.get("athlete_id"))
    team_id = _text(official_team_id)
    if not player_id or not team_id:
        return None
    name = _text(
        row.get("fullName") or row.get("displayName") or row.get("name")
        or ((row.get("athlete") or {}).get("displayName") if isinstance(row.get("athlete"), Mapping) else "")
    )
    if not name:
        return None
    position_raw = row.get("position") or {}
    position = _text(position_raw.get("abbreviation") if isinstance(position_raw, Mapping) else position_raw).upper()
    return CanonicalPlayerIdentity(
        player_id, team_id, name, position, _text(team_name), _text(team_abbr), ()
    )


def with_provider_alias(
    player: CanonicalPlayerIdentity, provider: str, provider_player_id: str
) -> CanonicalPlayerIdentity:
    key = (_provider(provider), _text(provider_player_id))
    if not all(key):
        return player
    aliases = tuple(sorted(set((*player.provider_aliases, key))))
    return replace(player, provider_aliases=aliases)


def build_identity_index(players: Iterable[CanonicalPlayerIdentity]) -> dict[str, CanonicalPlayerIdentity]:
    index: dict[str, CanonicalPlayerIdentity] = {}
    ambiguous: set[str] = set()
    for player in players:
        entries = [f"official:{player.official_player_id}"]
        entries.extend(f"provider:{provider}:{pid}" for provider, pid in player.provider_aliases)
        entries.append(f"team-name:{player.official_team_id}:{_norm(player.canonical_name)}")
        for key in entries:
            existing = index.get(key)
            if existing is not None and existing != player:
                ambiguous.add(key)
                index.pop(key, None)
            elif key not in ambiguous:
                index[key] = player
    return index


def resolve_player_identity(
    raw: Mapping[str, Any], index: Mapping[str, CanonicalPlayerIdentity]
) -> CanonicalPlayerIdentity | None:
    official = _text(raw.get("official_player_id"))
    if official:
        return index.get(f"official:{official}")
    provider = _provider(raw.get("provider"))
    provider_id = _text(raw.get("provider_player_id") or raw.get("player_id"))
    if provider and provider_id:
        found = index.get(f"provider:{provider}:{provider_id}")
        if found is not None:
            return found
    team_id = _text(raw.get("official_team_id") or raw.get("team_id"))
    name = _norm(raw.get("player_name"))
    if team_id and name:
        return index.get(f"team-name:{team_id}:{name}")
    return None


__all__ = [
    "CanonicalPlayerIdentity", "build_identity_index", "player_identity_from_roster_row",
    "resolve_player_identity", "with_provider_alias",
]
