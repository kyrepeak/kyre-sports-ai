"""CFB Player Props Page 3 — exact-ID completed game-book history recovery.

Read-only recovery path used only when the frozen athlete-gamelog owner returns an
insufficient sample. ESPN roster athlete/team IDs remain authoritative. The
helper accepts only completed events, exact team membership, and exact athlete
rows from ESPN game books. It never creates synthetic player results and never
uses sportsbook data in the projection path.
"""
from __future__ import annotations

from functools import lru_cache
import math
from typing import Any, Mapping

import requests

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import canonical_market_key

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
SOURCE = "ESPN CFB completed game books"
HEADERS = {
    "User-Agent": "KyreSportsAI/CFB-Player-Props-Page3-Recovery-V1",
    "Accept": "application/json",
}
TIMEOUT_SECONDS = 8
MAX_GAMES = 8
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        out = float(str(value).replace(",", "").strip())
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _pair(value: Any) -> tuple[float, float] | None:
    text = _text(value)
    if "/" not in text:
        return None
    left, right = text.split("/", 1)
    first = _finite(left)
    second = _finite(right)
    if first is None or second is None or first < 0 or second < 0:
        return None
    return first, second


def _event_team_ids(event: Mapping[str, Any]) -> tuple[str, ...]:
    comps = event.get("competitions") or []
    comp = comps[0] if comps and isinstance(comps[0], Mapping) else {}
    ids = []
    for raw in comp.get("competitors") or []:
        if not isinstance(raw, Mapping):
            continue
        team_id = _text((raw.get("team") or {}).get("id"))
        if team_id and team_id not in ids:
            ids.append(team_id)
    return tuple(ids)


def _completed(event: Mapping[str, Any]) -> bool:
    comps = event.get("competitions") or []
    comp = comps[0] if comps and isinstance(comps[0], Mapping) else {}
    status = comp.get("status") or event.get("status") or {}
    kind = status.get("type") if isinstance(status, Mapping) else {}
    if isinstance(kind, Mapping):
        if kind.get("completed") is True:
            return True
        state = _text(kind.get("state") or kind.get("name") or kind.get("description")).lower()
    else:
        state = _text(kind).lower()
    return state in {"post", "final", "completed", "complete", "closed"} or "final" in state


def _game_date(event: Mapping[str, Any]) -> str:
    return _text(event.get("date"))[:10]


@lru_cache(maxsize=64)
def _fetch_schedule(team_id: str, season: int) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{ESPN_SITE_BASE}/teams/{team_id}/schedule",
            params={"season": int(season)},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=256)
def _fetch_summary(event_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{ESPN_SITE_BASE}/summary",
            params={"event": event_id},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _stat_values(category: Mapping[str, Any], athlete_id: str) -> dict[str, Any] | None:
    labels = [str(value or "").strip().upper() for value in (category.get("labels") or [])]
    for raw in category.get("athletes") or []:
        if not isinstance(raw, Mapping):
            continue
        athlete = raw.get("athlete") or {}
        if _text(athlete.get("id")) != athlete_id:
            continue
        stats = raw.get("stats") or []
        if not isinstance(stats, list):
            return None
        return {label: stats[index] if index < len(stats) else None for index, label in enumerate(labels)}
    return None


def _number_from(values: Mapping[str, Any], *labels: str) -> float | None:
    for label in labels:
        value = _finite(values.get(label))
        if value is not None:
            return value
    return None


def _player_game_row(
    summary: Mapping[str, Any], *, team_id: str, athlete_id: str, market_key: str
) -> dict[str, Any] | None:
    blocks = ((summary.get("boxscore") or {}).get("players") or [])
    block = next(
        (
            raw for raw in blocks
            if isinstance(raw, Mapping) and _text((raw.get("team") or {}).get("id")) == team_id
        ),
        None,
    )
    if not isinstance(block, Mapping):
        return None

    categories: dict[str, Mapping[str, Any]] = {}
    for raw in block.get("statistics") or []:
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("name") or raw.get("displayName")).lower()
        if name:
            categories[name] = raw

    passing = _stat_values(categories.get("passing") or {}, athlete_id) or {}
    rushing = _stat_values(categories.get("rushing") or {}, athlete_id) or {}
    receiving = _stat_values(categories.get("receiving") or {}, athlete_id) or {}
    appeared = bool(passing or rushing or receiving)
    if not appeared:
        return None

    value: float | None = None
    if market_key == "passing_yards":
        value = _number_from(passing, "YDS", "YARDS")
    elif market_key == "passing_touchdowns":
        value = _number_from(passing, "TD", "TDS")
    elif market_key == "rushing_yards":
        value = _number_from(rushing, "YDS", "YARDS")
    elif market_key == "receiving_yards":
        value = _number_from(receiving, "YDS", "YARDS")
    elif market_key == "receiving_receptions":
        value = _number_from(receiving, "REC", "RECEPTIONS")
    elif market_key == "touchdowns":
        rush_td = _number_from(rushing, "TD", "TDS")
        rec_td = _number_from(receiving, "TD", "TDS")
        if rush_td is not None or rec_td is not None:
            value = float(rush_td or 0.0) + float(rec_td or 0.0)
    if value is None or value < 0:
        return None

    out: dict[str, Any] = {"value": float(value)}
    comp_att = passing.get("C/ATT") or passing.get("CMP/ATT")
    pair = _pair(comp_att)
    if pair is not None:
        out["completions"], out["pass_attempts"] = pair
    else:
        completions = _number_from(passing, "CMP", "COMP")
        attempts = _number_from(passing, "ATT")
        if completions is not None and completions >= 0:
            out["completions"] = completions
        if attempts is not None and attempts >= 0:
            out["pass_attempts"] = attempts

    passing_td = _number_from(passing, "TD", "TDS")
    interceptions = _number_from(passing, "INT", "INTS")
    carries = _number_from(rushing, "CAR", "ATT")
    receptions = _number_from(receiving, "REC", "RECEPTIONS")
    targets = _number_from(receiving, "TGTS", "TGT", "TARGETS")
    for key, number in (
        ("passing_touchdowns", passing_td),
        ("interceptions", interceptions),
        ("carries", carries),
        ("receptions", receptions),
        ("targets", targets),
    ):
        if number is not None and number >= 0:
            out[key] = number
    return out


def load_completed_gamebook_history(
    player: CanonicalPlayerIdentity, market_key: str, *, season: int
) -> list[dict[str, Any]]:
    market = canonical_market_key(market_key)
    team_id = _text(player.official_team_id)
    athlete_id = _text(player.official_player_id)
    if market is None or not team_id or not athlete_id or int(season or 0) < 2000:
        return []

    payload = _fetch_schedule(team_id, int(season))
    events = []
    for raw in payload.get("events") or []:
        if not isinstance(raw, Mapping) or not _completed(raw):
            continue
        event_id = _text(raw.get("id"))
        team_ids = _event_team_ids(raw)
        if not event_id or team_id not in team_ids or len(team_ids) < 2:
            continue
        opponent_id = next((value for value in team_ids if value != team_id), "")
        if not opponent_id:
            continue
        events.append((_game_date(raw), event_id, opponent_id))
    events.sort(reverse=True)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game_date, event_id, opponent_id in events:
        if event_id in seen:
            continue
        seen.add(event_id)
        summary = _fetch_summary(event_id)
        row = _player_game_row(summary, team_id=team_id, athlete_id=athlete_id, market_key=market)
        if row is None:
            continue
        rows.append({
            "event_id": event_id,
            "completed": True,
            "market_key": market,
            "value": float(row.pop("value")),
            "game_date": game_date,
            "opponent_team_id": opponent_id,
            "source": SOURCE,
            **row,
        })
        if len(rows) >= MAX_GAMES:
            break
    return rows


__all__ = [
    "ESPN_SITE_BASE",
    "MAX_GAMES",
    "SOURCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "load_completed_gamebook_history",
]
