"""CFB Player Props Page 2 V1 — fail-closed player availability evidence."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import cfb_over_under_environment_engine_v1 as environment
from cfb_player_props_page2_roster_v1 import Page2Player

_STATES = ("OUT", "DOUBTFUL", "QUESTIONABLE", "AVAILABLE")
_PRIORITY = {"OUT": 4, "DOUBTFUL": 3, "QUESTIONABLE": 2, "AVAILABLE": 1}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row_player_id(row: Mapping[str, Any]) -> str:
    direct = _text(row.get("id") or row.get("athleteId") or row.get("athlete_id") or row.get("playerId") or row.get("player_id"))
    if direct:
        return direct
    athlete = row.get("athlete")
    if isinstance(athlete, Mapping):
        return _text(athlete.get("id") or athlete.get("athleteId") or athlete.get("playerId"))
    player = row.get("player")
    if isinstance(player, Mapping):
        return _text(player.get("id") or player.get("athleteId") or player.get("playerId"))
    return ""


def _walk(node: Any):
    if isinstance(node, Mapping):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _status_labels(row: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in ("status", "injuryStatus", "availability", "designation"):
        raw = row.get(key)
        if isinstance(raw, Mapping):
            for field in ("name", "type", "description", "displayName", "abbreviation", "state"):
                value = _text(raw.get(field))
                if value:
                    labels.append(value)
        else:
            value = _text(raw)
            if value:
                labels.append(value)
    return labels


def _canonical_status(label: str) -> str | None:
    value = " ".join(_text(label).casefold().replace("_", " ").replace("-", " ").split())
    if not value:
        return None
    if value in {"out", "inactive", "ruled out"} or "ruled out" in value:
        return "OUT"
    if "doubtful" in value:
        return "DOUBTFUL"
    if "questionable" in value:
        return "QUESTIONABLE"
    if value in {"active", "available", "healthy"}:
        return "AVAILABLE"
    return None


def normalize_availability(*payloads: Mapping[str, Any], player_id: str) -> dict[str, Any]:
    pid = _text(player_id)
    evidence: list[dict[str, str]] = []
    if not pid:
        return {"state": "UNVERIFIED", "verified": False, "raw_label": "", "source": ""}
    for payload in payloads:
        for row in _walk(payload):
            if _row_player_id(row) != pid:
                continue
            for label in _status_labels(row):
                state = _canonical_status(label)
                if state:
                    evidence.append({"state": state, "raw_label": label})
    if not evidence:
        return {"state": "UNVERIFIED", "verified": False, "raw_label": "", "source": ""}
    selected = max(evidence, key=lambda item: _PRIORITY[item["state"]])
    return {
        "state": selected["state"],
        "verified": True,
        "raw_label": selected["raw_label"],
        "source": "ESPN exact player status evidence",
    }


def _event_id(context: Mapping[str, Any]) -> str:
    direct = _text(context.get("espn_event_id"))
    if direct:
        return direct
    game = context.get("game")
    if isinstance(game, Mapping):
        return _text(game.get("espn_event_id"))
    return ""


def load_game_availability(
    context: Mapping[str, Any], players: Sequence[Page2Player]
) -> dict[str, dict[str, Any]]:
    event_id = _event_id(context)
    summary: Mapping[str, Any] = {}
    if event_id:
        try:
            raw, _ = environment._fetch_summary(event_id)
            summary = raw if isinstance(raw, Mapping) else {}
        except Exception:
            summary = {}
    return {
        player.official_player_id: normalize_availability(summary, player_id=player.official_player_id)
        for player in players
    }


__all__ = ["load_game_availability", "normalize_availability"]
