"""Render-safe ESPN transport for the NFL Passing Yards market collector.

The certified V1 market parser, FanDuel transport, event reconciliation, player
identity rules, line/price validation, and market semantics remain unchanged.
This module only hardens the two ESPN reads used by the shared Render host:
summary and team roster. It tries ESPN's canonical site API first and the
same-shape ESPN web-site API second. Both are official ESPN domains and both
must still satisfy the frozen exact-ID parsers.

No fuzzy/name identity, synthetic IDs, projection influence, stake sizing, or
wager actions are introduced.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sports_api.collectors import nfl_fanduel_passing_yards as base

MODEL_VERSION = "NFL PASSING YARDS RENDER ESPN TRANSPORT V2"
ESPN_SITE_BASES = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl",
)


def _espn_get(path: str, params: dict[str, Any] | None = None, *, timeout: int) -> tuple[dict[str, Any], str]:
    failures: list[str] = []
    for root in ESPN_SITE_BASES:
        try:
            payload = base._get_json(
                f"{root}/{path.lstrip('/')}",
                params,
                headers=base.ESPN_HEADERS,
                timeout=timeout,
            )
            return payload, root
        except base.NFLPassingYardsCollectorError as exc:
            failures.append(f"{root.split('/')[2]}:{exc}")
    raise base.NFLPassingYardsCollectorError(
        "official ESPN transport failed closed across site.api + site.web.api"
    )


def fetch_espn_event_summary_hosted(event_id: str, *, timeout: int = base.DEFAULT_TIMEOUT_SECONDS) -> tuple[dict[str, Any], str]:
    event_id = base._text(event_id)
    if not event_id.isdigit():
        raise base.NFLPassingYardsCollectorError("official ESPN event_id must be numeric")
    return _espn_get("summary", {"event": event_id}, timeout=timeout)


def fetch_espn_team_roster_hosted(team_id: str, *, timeout: int = base.DEFAULT_TIMEOUT_SECONDS) -> tuple[dict[str, Any], str]:
    team_id = base._text(team_id)
    if not team_id.isdigit():
        raise base.NFLPassingYardsCollectorError("official ESPN team ID must be numeric")
    return _espn_get(f"teams/{team_id}/roster", timeout=timeout)


def _market_unavailable_payload(official: dict[str, Any], provider_event: dict[str, Any], now: datetime, selected_tab: str, attempted_tabs: list[str], espn_sources: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "nfl_passing_yards_market_v1",
        "ready": True,
        "market_available": False,
        "official_event_id": official["event_id"],
        "sportsbook": "FanDuel",
        "captured_at_utc": base._utc_iso(now),
        "props": [],
        "reason": "FanDuel returned no open canonical Passing Yards market for this exact event",
        "provider_diagnostics": {
            "provider_event_id": provider_event["provider_event_id"],
            "selected_tab": selected_tab,
            "attempted_tabs": attempted_tabs,
            "espn_transport_sources": sorted(set(espn_sources)),
            "espn_transport_version": MODEL_VERSION,
        },
        "identity": {
            "official_authority": "ESPN",
            "event_identity": "exact ESPN event ID + exact team IDs + bounded kickoff equality",
            "player_identity": "FanDuel selection -> FDX player -> exact team/jersey/QB ESPN roster row",
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "stake_sizing_enabled": False,
        },
    }


def collect_fanduel_nfl_passing_yards_hosted(
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
    if official["event_id"] != base._text(official_event_id):
        raise base.NFLPassingYardsCollectorError("hosted ESPN summary event identity mismatch")

    landing = base.fetch_fanduel_nfl_landing(timeout=timeout)
    provider_event = base.reconcile_fanduel_event(landing, official)

    base_page = base.fetch_fanduel_event_page(provider_event["provider_event_id"], timeout=timeout)
    selected_tab = "default"
    markets = base._passing_markets(base_page)
    attempted_tabs: list[str] = ["default"]
    if not markets:
        for tab in base.discover_passing_tab_candidates(base_page):
            attempted_tabs.append(tab)
            try:
                candidate = base.fetch_fanduel_event_page(provider_event["provider_event_id"], tab, timeout=timeout)
            except base.NFLPassingYardsCollectorError:
                continue
            candidate_markets = base._passing_markets(candidate)
            if candidate_markets:
                selected_tab = tab
                markets = candidate_markets
                break

    espn_sources = [summary_source]
    if not markets:
        return _market_unavailable_payload(
            official,
            provider_event,
            now,
            selected_tab,
            attempted_tabs,
            espn_sources,
        )

    fdx_players = base.fetch_fanduel_event_players(provider_event["provider_event_id"], timeout=timeout)
    players, by_selection = base._provider_player_maps(fdx_players)

    rosters_by_team: dict[str, list[dict[str, str]]] = {}
    for side in ("away", "home"):
        team_id = official[side]["team_id"]
        roster_payload, roster_source = fetch_espn_team_roster_hosted(team_id, timeout=timeout)
        espn_sources.append(roster_source)
        rosters_by_team[team_id] = base.parse_espn_qb_roster(roster_payload, team_id)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for market in markets:
        market_id = base._text(market.get("marketId") or market.get("id") or market.get("_attachment_key"))
        try:
            row = base.normalize_passing_yards_market(
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
                "provider_market_id": ",".join(base._text(row.get("provider_market_id")) for row in rows),
                "reason": f"ambiguous multiple canonical Passing Yards prices for ESPN athlete {athlete_id}",
            })
            continue
        final_props.append(rows[0])

    final_props.sort(key=lambda row: (row["official_team_id"], row["official_athlete_id"]))
    return {
        "schema_version": "nfl_passing_yards_market_v1",
        "ready": True,
        "market_available": bool(final_props),
        "official_event_id": official["event_id"],
        "sportsbook": "FanDuel",
        "captured_at_utc": base._utc_iso(now),
        "props": final_props,
        "reason": "" if final_props else "Passing Yards markets were present but exact player/price certification failed closed",
        "provider_diagnostics": {
            "provider_event_id": provider_event["provider_event_id"],
            "provider_event_name": provider_event["provider_event_name"],
            "kickoff_delta_seconds": provider_event["kickoff_delta_seconds"],
            "selected_tab": selected_tab,
            "attempted_tabs": attempted_tabs,
            "passing_market_count": len(markets),
            "accepted_prop_count": len(final_props),
            "rejected_market_count": len(rejected),
            "rejected_markets": rejected,
            "http_methods": ["GET"],
            "sportsbook_credentials_required": False,
            "wager_actions": False,
            "espn_transport_sources": sorted(set(espn_sources)),
            "espn_transport_version": MODEL_VERSION,
        },
        "identity": {
            "official_authority": "ESPN",
            "event_identity": "exact ESPN event ID + exact team IDs + bounded kickoff equality",
            "player_identity": "FanDuel selection -> FDX player -> exact team/jersey/QB ESPN roster row",
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "stake_sizing_enabled": False,
        },
    }


__all__ = [
    "ESPN_SITE_BASES",
    "MODEL_VERSION",
    "collect_fanduel_nfl_passing_yards_hosted",
    "fetch_espn_event_summary_hosted",
    "fetch_espn_team_roster_hosted",
]
