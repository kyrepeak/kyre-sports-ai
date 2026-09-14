"""Read-only FanDuel NFL Rushing Yards collector for Kyre Sports API.

Step 4 is deliberately post-projection market context.  This collector reuses
only the already-certified Passing Yards transport/event-reconciliation helpers;
it owns separate Rushing Yards market discovery and player identity rules.

Permanent guardrails:
- official ESPN event/team/athlete IDs only;
- FanDuel selection -> FDX player -> exact team/jersey/position ESPN roster row;
- no player-name matching or fuzzy identity;
- no synthetic event/player IDs;
- canonical pregame two-way Rushing Yards only (no alternates/longest/team props);
- no fabricated line or price;
- sportsbook projection influence = 0.0%;
- probability/fair odds/EV/grading/stake sizing/wagering remain OFF.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping

from sports_api.collectors import nfl_fanduel_passing_yards as base
from sports_api.collectors.nfl_passing_yards_render_espn_v2 import (
    fetch_espn_event_summary_hosted,
    fetch_espn_team_roster_hosted,
)

MODEL_VERSION = "NFL RUSHING YARDS MARKET COLLECTOR V1"
SCHEMA_VERSION = "nfl_rushing_yards_market_v1"

KNOWN_PROP_TABS = (
    "rushing-props",
    "player-rushing-props",
    "player-props",
    "rushing",
    "popular",
)

# Deterministic provider/ESPN position aliases. These are explicit aliases, not
# fuzzy matching. A player must still match exact team + jersey + position.
_POSITION_ALIASES = {
    "HB": "RB",
    "HALFBACK": "RB",
    "RUNNINGBACK": "RB",
    "RUNNING BACK": "RB",
    "FULLBACK": "FB",
    "QUARTERBACK": "QB",
    "WIDERECEIVER": "WR",
    "WIDE RECEIVER": "WR",
    "TIGHTEND": "TE",
    "TIGHT END": "TE",
}
_ALLOWED_RUSHER_POSITIONS = {"RB", "FB", "QB", "WR", "TE"}


class NFLRushingYardsCollectorError(RuntimeError):
    """Raised when a live Rushing Yards market cannot be proven safely."""


def _text(value: Any) -> str:
    return base._text(value)


def _normalize_position(value: Any) -> str:
    raw = re.sub(r"\s+", " ", _text(value).upper()).strip()
    compact = raw.replace(" ", "")
    return _POSITION_ALIASES.get(raw, _POSITION_ALIASES.get(compact, raw))


def parse_espn_rusher_roster(payload: Mapping[str, Any], team_id: str) -> list[dict[str, str]]:
    """Return exact-ID offensive rushing candidates from one official ESPN roster."""
    team_id = _text(team_id)
    if not team_id.isdigit():
        raise NFLRushingYardsCollectorError("official ESPN team ID must be numeric")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in (payload or {}).get("athletes") or []:
        if not isinstance(group, Mapping):
            continue
        for item in group.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            pos = item.get("position") or {}
            position = _normalize_position((pos or {}).get("abbreviation") or (pos or {}).get("name"))
            athlete_id = _text(item.get("id"))
            jersey = _text(item.get("jersey") or item.get("jerseyNumber"))
            if position not in _ALLOWED_RUSHER_POSITIONS or not athlete_id.isdigit() or not jersey:
                continue
            if athlete_id in seen:
                raise NFLRushingYardsCollectorError("duplicate ESPN athlete ID in team roster")
            seen.add(athlete_id)
            out.append({
                "team_id": team_id,
                "athlete_id": athlete_id,
                "jersey": jersey,
                "position": position,
                "display_name": _text(item.get("displayName") or item.get("fullName")),
            })
    return out


def reconcile_provider_rusher(
    player: Mapping[str, Any],
    rosters_by_team: Mapping[str, list[dict[str, str]]],
) -> dict[str, str]:
    """Resolve FanDuel player identity without player-name matching."""
    team_id = base._provider_team_id(player)
    jersey = _text(player.get("number") or player.get("jersey") or player.get("jerseyNumber"))
    position = _normalize_position(player.get("position"))
    if not team_id or not jersey or position not in _ALLOWED_RUSHER_POSITIONS:
        raise NFLRushingYardsCollectorError("FanDuel player lacks exact team/jersey/rusher-position identity")
    matches = [
        row for row in rosters_by_team.get(team_id, [])
        if _text(row.get("jersey")) == jersey
        and _normalize_position(row.get("position")) == position
    ]
    unique = {row["athlete_id"]: row for row in matches if _text(row.get("athlete_id")).isdigit()}
    if len(unique) != 1:
        raise NFLRushingYardsCollectorError(
            f"FanDuel rusher identity did not resolve to exactly one ESPN athlete ({len(unique)})"
        )
    return next(iter(unique.values()))


def _market_text(market: Mapping[str, Any]) -> str:
    return base._market_text(market)


def is_rushing_yards_market(market: Mapping[str, Any]) -> bool:
    text = re.sub(r"[^a-z0-9]+", " ", _market_text(market).lower()).strip()
    if not text or "rushing" not in text or "yard" not in text:
        return False
    blocked = ("alternate", "alternative", "longest", "team rushing", "1st half", "first half", "quarter")
    return not any(token in text for token in blocked)


def _line(runner: Mapping[str, Any]) -> float:
    try:
        value = float(runner.get("handicap"))
    except (TypeError, ValueError) as exc:
        raise NFLRushingYardsCollectorError("Rushing Yards runner has invalid line") from exc
    if not math.isfinite(value) or value <= 0 or value > 500:
        raise NFLRushingYardsCollectorError("Rushing Yards line is outside safe NFL range")
    return value


def normalize_rushing_yards_market(
    market: Mapping[str, Any],
    *,
    official_event_id: str,
    provider_event_id: str,
    players: Mapping[str, dict[str, Any]],
    by_selection: Mapping[str, list[str]],
    rosters_by_team: Mapping[str, list[dict[str, str]]],
    captured_at_utc: datetime,
) -> dict[str, Any] | None:
    if not is_rushing_yards_market(market) or not base._market_is_open_pregame(market):
        return None
    active = base._active_player_runners(market)
    overs = [row for row in active if base._runner_role(row) == "OVER"]
    unders = [row for row in active if base._runner_role(row) == "UNDER"]
    if len(overs) != 1 or len(unders) != 1:
        raise NFLRushingYardsCollectorError("Rushing Yards market must have exactly one active OVER and UNDER")
    over, under = overs[0], unders[0]
    over_line, under_line = _line(over), _line(under)
    if over_line != under_line:
        raise NFLRushingYardsCollectorError("Rushing Yards OVER/UNDER lines do not match")

    try:
        provider_player_key, provider_player = base._provider_player_for_market(
            over, under, players, by_selection
        )
        official_player = reconcile_provider_rusher(provider_player, rosters_by_team)
        over_odds = base._american_odds(over)
        under_odds = base._american_odds(under)
    except base.NFLPassingYardsCollectorError as exc:
        raise NFLRushingYardsCollectorError(str(exc)) from exc

    return {
        "official_event_id": _text(official_event_id),
        "official_athlete_id": official_player["athlete_id"],
        "official_team_id": official_player["team_id"],
        "player_name": official_player.get("display_name") or "Verified rusher",
        "position": official_player["position"],
        "market_type": "rushing_yards",
        "line": over_line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "sportsbook": "FanDuel",
        "line_status": "active",
        "provider_event_id": _text(provider_event_id),
        "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
        "provider_player_key": provider_player_key,
        "captured_at_utc": base._utc_iso(captured_at_utc),
    }


def _rushing_markets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    return [row for row in base._rows(attachments.get("markets")) if is_rushing_yards_market(row)]


def discover_rushing_tab_candidates(payload: Mapping[str, Any]) -> list[str]:
    """Find provider-declared rushing tab slugs without player-name matching."""
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = _text(value)
        if not text or len(text) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", text):
            return
        low = text.lower()
        if "rush" not in low or ("prop" not in low and "yard" not in low):
            return
        if low not in seen:
            seen.add(low)
            found.append(text)

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if _text(key).lower() in {"tab", "tabid", "slug", "key", "id"}:
                    add(child)
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:200]:
                walk(child, depth + 1)

    walk(payload)
    for tab in KNOWN_PROP_TABS:
        if tab.lower() not in seen:
            found.append(tab)
            seen.add(tab.lower())
    return found[:8]


def _identity_contract() -> dict[str, Any]:
    return {
        "official_authority": "ESPN",
        "event_identity": "exact ESPN event ID + exact team IDs + bounded kickoff equality",
        "player_identity": "FanDuel selection -> FDX player -> exact team/jersey/position ESPN roster row",
        "player_name_matching": False,
        "fuzzy_matching": False,
        "synthetic_event_ids": False,
        "synthetic_player_ids": False,
    }


def _market_semantics() -> dict[str, Any]:
    return {
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "probability_enabled": False,
        "fair_odds_enabled": False,
        "ev_enabled": False,
        "grading_enabled": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def _market_unavailable_payload(
    official: dict[str, Any],
    provider_event: dict[str, Any],
    now: datetime,
    selected_tab: str,
    attempted_tabs: list[str],
    espn_sources: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "market_available": False,
        "official_event_id": official["event_id"],
        "sportsbook": "FanDuel",
        "captured_at_utc": base._utc_iso(now),
        "props": [],
        "reason": "FanDuel returned no open canonical Rushing Yards market for this exact event",
        "provider_diagnostics": {
            "provider_event_id": provider_event["provider_event_id"],
            "selected_tab": selected_tab,
            "attempted_tabs": attempted_tabs,
            "espn_transport_sources": sorted(set(espn_sources)),
            "espn_transport_version": "NFL PASSING YARDS RENDER ESPN TRANSPORT V2",
        },
        "identity": _identity_contract(),
        "market_semantics": _market_semantics(),
    }


def _collect_fanduel_nfl_rushing_yards_hosted(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    timeout: int = base.DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)

    summary, summary_source = fetch_espn_event_summary_hosted(official_event_id, timeout=timeout)
    official = base.parse_official_event(summary)
    if official["event_id"] != _text(official_event_id):
        raise NFLRushingYardsCollectorError("hosted ESPN summary event identity mismatch")

    landing = base.fetch_fanduel_nfl_landing(timeout=timeout)
    provider_event = base.reconcile_fanduel_event(landing, official)

    base_page = base.fetch_fanduel_event_page(provider_event["provider_event_id"], timeout=timeout)
    selected_payload = base_page
    selected_tab = "default"
    markets = _rushing_markets(base_page)
    attempted_tabs: list[str] = ["default"]
    if not markets:
        for tab in discover_rushing_tab_candidates(base_page):
            attempted_tabs.append(tab)
            try:
                candidate = base.fetch_fanduel_event_page(provider_event["provider_event_id"], tab, timeout=timeout)
            except base.NFLPassingYardsCollectorError:
                continue
            candidate_markets = _rushing_markets(candidate)
            if candidate_markets:
                selected_payload = candidate
                selected_tab = tab
                markets = candidate_markets
                break

    espn_sources = [summary_source]
    if not markets:
        return _market_unavailable_payload(
            official, provider_event, now, selected_tab, attempted_tabs, espn_sources
        )

    fdx_players = base.fetch_fanduel_event_players(provider_event["provider_event_id"], timeout=timeout)
    players, by_selection = base._provider_player_maps(fdx_players)

    rosters_by_team: dict[str, list[dict[str, str]]] = {}
    for side in ("away", "home"):
        team_id = official[side]["team_id"]
        roster_payload, roster_source = fetch_espn_team_roster_hosted(team_id, timeout=timeout)
        espn_sources.append(roster_source)
        rosters_by_team[team_id] = parse_espn_rusher_roster(roster_payload, team_id)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for market in markets:
        market_id = _text(market.get("marketId") or market.get("id") or market.get("_attachment_key"))
        try:
            row = normalize_rushing_yards_market(
                market,
                official_event_id=official["event_id"],
                provider_event_id=provider_event["provider_event_id"],
                players=players,
                by_selection=by_selection,
                rosters_by_team=rosters_by_team,
                captured_at_utc=now,
            )
            if row:
                accepted.append(row)
        except Exception as exc:
            rejected.append({
                "provider_market_id": market_id,
                "reason": f"{type(exc).__name__}: {exc}"[:300],
            })

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in accepted:
        grouped.setdefault(row["official_athlete_id"], []).append(row)
    final_props: list[dict[str, Any]] = []
    for athlete_id, rows in grouped.items():
        signatures = {(row["line"], row["over_odds"], row["under_odds"]) for row in rows}
        if len(signatures) != 1:
            rejected.append({
                "provider_market_id": ",".join(_text(row.get("provider_market_id")) for row in rows),
                "reason": f"ambiguous multiple canonical Rushing Yards prices for ESPN athlete {athlete_id}",
            })
            continue
        final_props.append(rows[0])

    final_props.sort(key=lambda row: (row["official_team_id"], row["official_athlete_id"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "market_available": bool(final_props),
        "official_event_id": official["event_id"],
        "sportsbook": "FanDuel",
        "captured_at_utc": base._utc_iso(now),
        "props": final_props,
        "reason": "" if final_props else "Rushing Yards markets were present but exact player/price certification failed closed",
        "provider_diagnostics": {
            "provider_event_id": provider_event["provider_event_id"],
            "provider_event_name": provider_event["provider_event_name"],
            "kickoff_delta_seconds": provider_event["kickoff_delta_seconds"],
            "selected_tab": selected_tab,
            "attempted_tabs": attempted_tabs,
            "rushing_market_count": len(markets),
            "accepted_prop_count": len(final_props),
            "rejected_market_count": len(rejected),
            "rejected_markets": rejected,
            "http_methods": ["GET"],
            "sportsbook_credentials_required": False,
            "wager_actions": False,
            "espn_transport_sources": sorted(set(espn_sources)),
            "espn_transport_version": "NFL PASSING YARDS RENDER ESPN TRANSPORT V2",
        },
        "identity": _identity_contract(),
        "market_semantics": _market_semantics(),
    }


def collect_fanduel_nfl_rushing_yards_hosted(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    timeout: int = base.DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        return _collect_fanduel_nfl_rushing_yards_hosted(
            official_event_id, now_utc=now_utc, timeout=timeout
        )
    except NFLRushingYardsCollectorError:
        raise
    except base.NFLPassingYardsCollectorError as exc:
        raise NFLRushingYardsCollectorError(str(exc)) from exc


__all__ = [
    "KNOWN_PROP_TABS",
    "MODEL_VERSION",
    "NFLRushingYardsCollectorError",
    "SCHEMA_VERSION",
    "collect_fanduel_nfl_rushing_yards_hosted",
    "discover_rushing_tab_candidates",
    "is_rushing_yards_market",
    "normalize_rushing_yards_market",
    "parse_espn_rusher_roster",
    "reconcile_provider_rusher",
]
