"""Canonical FanDuel NFL Rushing Yards collector V2.

Additive over frozen collector V1. V2 changes only FanDuel market-family
classification so standard two-way Rushing Yards props are not polluted by
alternate ladders, Rushing + Receiving, or Most Rushing Yards markets.

All event/player identity, roster reconciliation, odds parsing, line validation,
and safety semantics remain owned by frozen V1. Exact ESPN IDs only; no player
name matching, fuzzy matching, synthetic IDs, projection influence, grading, EV,
stake sizing, or wager actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from sports_api.collectors import nfl_fanduel_passing_yards as base
from sports_api.collectors import nfl_fanduel_rushing_yards_v1 as frozen
from sports_api import nfl_prop_market_eligibility_v1 as market_elig
from sports_api.collectors import nfl_passing_yards_render_espn_v2 as hosted

MODEL_VERSION = "NFL RUSHING YARDS MARKET COLLECTOR V2 • CANONICAL MARKET FILTER"
SCHEMA_VERSION = frozen.SCHEMA_VERSION
FROZEN_COLLECTOR = "sports_api.collectors.nfl_fanduel_rushing_yards_v1"
KNOWN_PROP_TABS = frozen.KNOWN_PROP_TABS
NFLRushingYardsCollectorError = frozen.NFLRushingYardsCollectorError

_STANDARD_TYPE_RE = re.compile(r"^PLAYER_X_RUSHING_YARDS(?:_(?:LOW|MEDIUM|HIGH))?$")


def _text(value: Any) -> str:
    return frozen._text(value)


def _market_type(market: Mapping[str, Any]) -> str:
    return _text(
        market.get("marketType")
        or market.get("marketTypeCode")
        or market.get("type")
    ).upper()


def is_canonical_rushing_yards_market(market: Mapping[str, Any]) -> bool:
    """Admit only FanDuel's standard two-way player Rushing Yards family.

    The provider market type is authoritative here. Live FanDuel evidence uses
    PLAYER_X_RUSHING_YARDS_LOW/MEDIUM/HIGH for standard two-way props. Alt
    ladders, Rushing + Receiving, Most Rushing Yards, team/period/longest
    markets and unknown families fail closed before frozen V1 normalization.
    """
    market_type = _market_type(market)
    if not _STANDARD_TYPE_RE.fullmatch(market_type):
        return False

    name = _text(
        market.get("marketName")
        or market.get("name")
        or market.get("displayName")
    ).lower()
    if name:
        blocked_name_tokens = (
            "alt rushing",
            "alternate rushing",
            "rushing + receiving",
            "rushing & receiving",
            "most rushing",
            "longest rushing",
            "team rushing",
            "1st half",
            "first half",
            "quarter",
        )
        if any(token in name for token in blocked_name_tokens):
            return False
        if "rushing" not in name or ("yd" not in name and "yard" not in name):
            return False
    return True


def _canonical_markets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    return [
        row
        for row in base._rows(attachments.get("markets"))
        if is_canonical_rushing_yards_market(row)
    ]


def _unavailable_payload(
    official: dict[str, Any],
    provider_event: dict[str, Any],
    now: datetime,
    selected_tab: str,
    attempted_tabs: list[str],
    espn_sources: list[str],
) -> dict[str, Any]:
    payload = frozen._market_unavailable_payload(
        official,
        provider_event,
        now,
        selected_tab,
        attempted_tabs,
        espn_sources,
    )
    diagnostics = payload.setdefault("provider_diagnostics", {})
    diagnostics["collector_version"] = MODEL_VERSION
    diagnostics["canonical_filter"] = "standard FanDuel PLAYER_X_RUSHING_YARDS LOW/MEDIUM/HIGH only"
    return payload


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

    summary, summary_source = frozen.fetch_espn_event_summary_hosted(
        official_event_id, timeout=timeout
    )
    official = base.parse_official_event(summary)
    if official["event_id"] != _text(official_event_id):
        raise NFLRushingYardsCollectorError("hosted ESPN summary event identity mismatch")

    landing = base.fetch_fanduel_nfl_landing(timeout=timeout)
    provider_event = base.reconcile_fanduel_event(landing, official)

    base_page = base.fetch_fanduel_event_page(
        provider_event["provider_event_id"], timeout=timeout
    )
    selected_tab = "default"
    markets = _canonical_markets(base_page)
    attempted_tabs: list[str] = ["default"]
    if not markets:
        for tab in frozen.discover_rushing_tab_candidates(base_page):
            attempted_tabs.append(tab)
            try:
                candidate = base.fetch_fanduel_event_page(
                    provider_event["provider_event_id"], tab, timeout=timeout
                )
            except base.NFLPassingYardsCollectorError:
                continue
            candidate_markets = _canonical_markets(candidate)
            if candidate_markets:
                selected_tab = tab
                markets = candidate_markets
                break

    espn_sources = [summary_source]
    if not markets:
        return _unavailable_payload(
            official, provider_event, now, selected_tab, attempted_tabs, espn_sources
        )

    fdx_players = base.fetch_fanduel_event_players(
        provider_event["provider_event_id"], timeout=timeout
    )
    players, by_selection = base._provider_player_maps(fdx_players)

    rosters_by_team: dict[str, list[dict[str, str]]] = {}
    roster_payloads_by_team: dict[str, dict[str, Any]] = {}
    for side in ("away", "home"):
        team_id = official[side]["team_id"]
        roster_payload, roster_source = frozen.fetch_espn_team_roster_hosted(
            team_id, timeout=timeout
        )
        espn_sources.append(roster_source)
        roster_payloads_by_team[team_id] = roster_payload
        rosters_by_team[team_id] = frozen.parse_espn_rusher_roster(
            roster_payload, team_id
        )

    eligibility = market_elig.build_event_market_eligibility(
        summary=summary,
        official=official,
        roster_payloads_by_team=roster_payloads_by_team,
        allowed_positions=frozenset({"QB", "RB", "FB", "WR", "TE"}),
        espn_get=hosted._espn_get,
        timeout=timeout,
    )
    espn_sources.extend(eligibility.get("espn_sources", []))

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for market in markets:
        market_id = _text(
            market.get("marketId")
            or market.get("id")
            or market.get("_attachment_key")
        )
        try:
            row = frozen.normalize_rushing_yards_market(
                market,
                official_event_id=official["event_id"],
                provider_event_id=provider_event["provider_event_id"],
                players=players,
                by_selection=by_selection,
                rosters_by_team=rosters_by_team,
                captured_at_utc=now,
            )
            if row:
                if market_elig.market_row_eligible(row, eligibility):
                    accepted.append(row)
                else:
                    rejected.append({
                        "provider_market_id": market_id,
                        "reason": "Step 6 market player eligibility gate rejected athlete",
                    })
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
        signatures = {
            (row["line"], row["over_odds"], row["under_odds"])
            for row in rows
        }
        if len(signatures) != 1:
            rejected.append({
                "provider_market_id": ",".join(
                    _text(row.get("provider_market_id")) for row in rows
                ),
                "reason": (
                    "ambiguous multiple canonical Rushing Yards prices for "
                    f"ESPN athlete {athlete_id}"
                ),
            })
            continue
        final_props.append(rows[0])

    final_props.sort(
        key=lambda row: (row["official_team_id"], row["official_athlete_id"])
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "market_available": bool(final_props),
        "official_event_id": official["event_id"],
        "sportsbook": "FanDuel",
        "captured_at_utc": base._utc_iso(now),
        "props": final_props,
        "reason": "" if final_props else (
            "Canonical Rushing Yards markets were present but exact player/price "
            "certification failed closed"
        ),
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
            "collector_version": MODEL_VERSION,
            "canonical_filter": (
                "standard FanDuel PLAYER_X_RUSHING_YARDS LOW/MEDIUM/HIGH only"
            ),
            "http_methods": ["GET"],
            "sportsbook_credentials_required": False,
            "wager_actions": False,
            "espn_transport_sources": sorted(set(espn_sources)),
            "espn_transport_version": "NFL PASSING YARDS RENDER ESPN TRANSPORT V2",
            "market_eligibility_version": market_elig.MODEL_VERSION,
            "availability_state": eligibility.get("availability_state"),
            "eligible_player_count": market_elig.eligible_player_count(eligibility),
        },
        "identity": frozen._identity_contract(),
        "market_semantics": frozen._market_semantics(),
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
    "FROZEN_COLLECTOR",
    "KNOWN_PROP_TABS",
    "MODEL_VERSION",
    "NFLRushingYardsCollectorError",
    "SCHEMA_VERSION",
    "collect_fanduel_nfl_rushing_yards_hosted",
    "is_canonical_rushing_yards_market",
]
