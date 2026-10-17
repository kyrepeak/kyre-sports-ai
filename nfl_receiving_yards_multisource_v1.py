"""NFL Receiving Yards multi-source exact-ID reconciliation.

ESPN owns event identity and historical receiving evidence. Current roster
identity is accepted only when ESPN and nflverse agree on the exact ESPN athlete
ID and receiving-eligible position. FanDuel is optional market display evidence
and never enters projection math.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Mapping

import requests

import nfl_prop_analytics_roster_truth_v1 as roster_truth

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RECEIVING_POSITIONS = frozenset({"WR", "TE", "RB", "FB"})
SOURCE_OWNERSHIP = {
    "event_identity": ("ESPN",),
    "historical_receiving": ("ESPN",),
    "current_roster_identity": ("ESPN", "NFLVERSE"),
    "market_lines": ("FANDUEL",),
}
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
_HEADERS = {"User-Agent": "KyreSportsAI/1.0 receiving-multisource", "Accept": "application/json"}


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _team_key(value: Any) -> str:
    team = _text(value).upper()
    return {"JAC": "JAX", "LA": "LAR", "WSH": "WAS"}.get(team, team)


def _summary(event_id: str) -> dict[str, Any]:
    try:
        response = requests.get(ESPN_SUMMARY_URL, params={"event": event_id}, headers=_HEADERS, timeout=10)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _handoff(event_id: str, raw: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    header = dict(summary.get("header") or {}) if isinstance(summary, Mapping) else {}
    if _text(header.get("id")) not in {"", event_id}:
        return {"state": "fail-closed", "reason": "ESPN summary event mismatch"}
    teams = [t for t in (raw.get("teams") or []) if isinstance(t, Mapping)]
    away = next((_team_key(t.get("team_abbreviation")) for t in teams if _text(t.get("home_away")).lower() == "away"), "")
    home = next((_team_key(t.get("team_abbreviation")) for t in teams if _text(t.get("home_away")).lower() == "home"), "")
    competition = (header.get("competitions") or [{}])[0]
    date_text = _text((competition or {}).get("date"))
    week_raw = header.get("week")
    if isinstance(week_raw, Mapping):
        week_raw = week_raw.get("number") or week_raw.get("value")
    try:
        week = int(week_raw)
    except (TypeError, ValueError):
        week = 0
    if not (away and home and week > 0 and len(date_text) >= 10):
        return {"state": "fail-closed", "reason": "ESPN matchup metadata incomplete"}
    return {
        "state": "ready",
        "away": away,
        "home": home,
        "target_date": date_text[:10],
        "week": week,
        "selection_key": event_id,
    }


def reconcile_exact_id_rosters(raw: Mapping[str, Any], truth: Mapping[str, Any]) -> dict[str, Any]:
    """Filter stale rows by exact ID; never synthesize a player from roster truth."""
    out = deepcopy(dict(raw or {}))
    if out.get("ready") is not True:
        return out
    sources = tuple(str(x).upper() for x in (truth.get("sources_available") or ()))
    if not {"ESPN", "NFLVERSE"}.issubset(set(sources)) or int(truth.get("source_count") or 0) < 2:
        out.update({
            "ready": False,
            "data_available": False,
            "reason": _text(truth.get("reason"), "independent roster verification unavailable"),
            "identity_sources": sources,
            "source_count": len(sources),
        })
        return out

    verified_by_team: dict[str, dict[str, dict[str, Any]]] = {}
    for team_abbr, team_truth in (truth.get("teams") or {}).items():
        team_key = _team_key(team_abbr)
        verified_by_team[team_key] = {
            _text(row.get("espn_id")): dict(row)
            for row in (team_truth or {}).get("verified") or []
            if isinstance(row, Mapping)
            and _text(row.get("espn_id")).isdigit()
            and _text(row.get("position")).upper() in RECEIVING_POSITIONS
        }

    filtered = 0
    kept_total = 0
    reconciled_teams: list[dict[str, Any]] = []
    for raw_team in out.get("teams") or []:
        if not isinstance(raw_team, Mapping):
            continue
        team = deepcopy(dict(raw_team))
        team_key = _team_key(team.get("team_abbreviation"))
        verified = verified_by_team.get(team_key, {})
        kept: list[dict[str, Any]] = []
        for raw_player in team.get("players") or []:
            if not isinstance(raw_player, Mapping):
                filtered += 1
                continue
            athlete_id = _text(raw_player.get("official_athlete_id"))
            row = verified.get(athlete_id)
            if row is None:
                filtered += 1
                continue
            player = deepcopy(dict(raw_player))
            player["player_name"] = _text(player.get("player_name"), _text(row.get("name")))
            player["position"] = _text(row.get("position"), _text(player.get("position"))).upper()
            if _text(row.get("jersey_number")):
                player["jersey_number"] = _text(row.get("jersey_number"))
            if _text(row.get("gsis_id")):
                player["gsis_id"] = _text(row.get("gsis_id"))
            if not _text(player.get("headshot_url")) and _text(row.get("headshot_url")):
                player["headshot_url"] = _text(row.get("headshot_url"))
            player["identity_verified"] = True
            player["identity_sources"] = ("ESPN", "NFLVERSE")
            player["identity_source_count"] = 2
            kept.append(player)
        team["players"] = kept
        team["identity_sources"] = ("ESPN", "NFLVERSE")
        team["identity_source_count"] = 2
        kept_total += len(kept)
        reconciled_teams.append(team)

    out["teams"] = reconciled_teams
    out["ready"] = len(reconciled_teams) == 2 and all(bool(t.get("players")) for t in reconciled_teams)
    out["data_available"] = out["ready"] and kept_total > 0
    out["reason"] = "" if out["ready"] else "no exact ESPN+nflverse receiving identities survived for one or more teams"
    out["identity_sources"] = ("ESPN", "NFLVERSE")
    out["sources_available"] = ("ESPN", "NFLVERSE")
    out["source_count"] = 2
    out["filtered_stale_player_count"] = filtered
    out["multisource_identity_verified"] = out["ready"]
    out["source_ownership"] = SOURCE_OWNERSHIP
    out["sportsbook_influence"] = 0.0
    return out


def load_multisource_context(
    event_id: str,
    *,
    raw_loader: Callable[[str], dict[str, Any]],
    market_loader: Callable[[str], dict[str, Any]] | None = None,
    truth_loader: Callable[[dict[str, Any]], dict[str, Any]] = roster_truth.load_verified_roster_truth,
    summary_loader: Callable[[str], dict[str, Any]] = _summary,
) -> dict[str, Any]:
    event_id = _text(event_id)
    raw = raw_loader(event_id)
    if not isinstance(raw, Mapping) or raw.get("ready") is not True:
        return dict(raw or {})
    handoff = _handoff(event_id, raw, summary_loader(event_id))
    if handoff.get("state") != "ready":
        return {**dict(raw), "ready": False, "data_available": False, "reason": _text(handoff.get("reason"))}
    truth = truth_loader(handoff)
    out = reconcile_exact_id_rosters(raw, truth)
    sources = list(out.get("sources_available") or ())
    if market_loader is not None:
        try:
            market = market_loader(event_id)
        except Exception:
            market = {}
        if isinstance(market, Mapping) and market.get("ready") is True:
            sources.append("FANDUEL")
            out["market_source_verified"] = True
        else:
            out["market_source_verified"] = False
    out["sources_available"] = tuple(dict.fromkeys(sources))
    out["source_count"] = len(out["sources_available"])
    out["source_ownership"] = SOURCE_OWNERSHIP
    out["roster_truth_state"] = _text(truth.get("state"))
    out["roster_truth_verified_count"] = int(truth.get("verified_count") or 0)
    return out


__all__ = [
    "RECEIVING_POSITIONS", "SOURCE_OWNERSHIP", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "load_multisource_context", "reconcile_exact_id_rosters",
]
