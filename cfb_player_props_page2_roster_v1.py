"""CFB Player Props Page 2 V1 — verified offensive roster owner."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import cfb_over_under_environment_engine_v1 as environment
from cfb_player_props_identity_v1 import CanonicalPlayerIdentity, player_identity_from_roster_row

OFFENSIVE_POSITIONS = ("QB", "RB", "WR", "TE")
_POSITION_ORDER = {position: index for index, position in enumerate(OFFENSIVE_POSITIONS)}


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class Page2Player:
    identity: CanonicalPlayerIdentity
    jersey_number: str = ""
    class_year: str = ""
    headshot_url: str = ""

    @property
    def official_player_id(self) -> str:
        return self.identity.official_player_id

    @property
    def official_team_id(self) -> str:
        return self.identity.official_team_id

    @property
    def canonical_name(self) -> str:
        return self.identity.canonical_name

    @property
    def position(self) -> str:
        return self.identity.position

    @property
    def team_name(self) -> str:
        return self.identity.team_name

    @property
    def team_abbr(self) -> str:
        return self.identity.team_abbr


def _walk_rows(node: Any):
    if isinstance(node, Mapping):
        athlete = node.get("athlete")
        candidate = dict(athlete) if isinstance(athlete, Mapping) else dict(node)
        if isinstance(athlete, Mapping):
            for key in ("position", "jersey", "experience", "class", "year", "headshot", "status"):
                if key not in candidate and key in node:
                    candidate[key] = node.get(key)
        athlete_id = _text(candidate.get("id") or candidate.get("athleteId") or candidate.get("athlete_id"))
        name = _text(candidate.get("fullName") or candidate.get("displayName") or candidate.get("name"))
        if athlete_id and name and candidate.get("position") is not None:
            yield candidate
        for value in node.values():
            yield from _walk_rows(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_rows(value)


def _position(row: Mapping[str, Any]) -> str:
    raw = row.get("position")
    if isinstance(raw, Mapping):
        return _text(raw.get("abbreviation") or raw.get("shortName") or raw.get("name")).upper()
    return _text(raw).upper()


def _class_year(row: Mapping[str, Any]) -> str:
    for key in ("experience", "class", "year", "academicClass"):
        raw = row.get(key)
        if isinstance(raw, Mapping):
            value = _text(raw.get("displayValue") or raw.get("name") or raw.get("abbreviation") or raw.get("description"))
        else:
            value = _text(raw)
        if value:
            return value
    return ""


def _headshot(row: Mapping[str, Any]) -> str:
    raw = row.get("headshot") or row.get("headshotUrl") or row.get("image")
    if isinstance(raw, Mapping):
        value = _text(raw.get("href") or raw.get("url"))
    else:
        value = _text(raw)
    return value if value.startswith(("https://", "http://")) else ""


def _player_from_row(
    row: Mapping[str, Any], *, team_id: str, team_name: str, team_abbr: str
) -> Page2Player | None:
    if _position(row) not in OFFENSIVE_POSITIONS:
        return None
    identity = player_identity_from_roster_row(
        row,
        official_team_id=team_id,
        team_name=team_name,
        team_abbr=team_abbr,
    )
    if identity is None or identity.position not in OFFENSIVE_POSITIONS:
        return None
    return Page2Player(
        identity=identity,
        jersey_number=_text(row.get("jersey") or row.get("jerseyNumber")),
        class_year=_class_year(row),
        headshot_url=_headshot(row),
    )


def _team_roster(context: Mapping[str, Any], side: str) -> list[Page2Player]:
    team_id = _text(context.get(f"{side}_team_id"))
    if not team_id:
        return []
    try:
        payload, _ = environment._fetch_roster(team_id)
    except Exception:
        payload = {}
    chosen: dict[str, Page2Player] = {}
    for row in _walk_rows(payload):
        player = _player_from_row(
            row,
            team_id=team_id,
            team_name=_text(context.get(f"{side}_team")),
            team_abbr=_text(context.get(f"{side}_abbr")),
        )
        if player is None:
            continue
        current = chosen.get(player.official_player_id)
        if current is None:
            chosen[player.official_player_id] = player
            continue
        # Preserve the richer verified metadata when duplicate ESPN rows exist.
        current_score = sum(bool(x) for x in (current.jersey_number, current.class_year, current.headshot_url))
        candidate_score = sum(bool(x) for x in (player.jersey_number, player.class_year, player.headshot_url))
        if candidate_score > current_score:
            chosen[player.official_player_id] = player
    return sorted(
        chosen.values(),
        key=lambda player: (_POSITION_ORDER.get(player.position, 99), player.canonical_name.casefold()),
    )


def load_offensive_roster(context: Mapping[str, Any]) -> dict[str, list[Page2Player]]:
    if _text(context.get("state")) not in {"", "ready"}:
        return {"away": [], "home": []}
    # The inherited ESPN roster owner is already TTL cached. This function calls
    # it exactly once per selected team per render.
    return {
        "away": _team_roster(context, "away"),
        "home": _team_roster(context, "home"),
    }


__all__ = ["OFFENSIVE_POSITIONS", "Page2Player", "load_offensive_roster"]
