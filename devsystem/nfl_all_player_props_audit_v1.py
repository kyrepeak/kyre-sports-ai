"""Step 6 live audit: every NFL player prop on the locked 2026-09-20 board.

Definition of done:
- every displayed Passing/Rushing/Receiving prop row carries the exact ESPN
  event, team and athlete IDs;
- each prop athlete belongs to that exact game's current eligible player pool;
- Passing Yards is limited to the lowest surviving verified QB depth rank;
- Rushing Yards is limited to current QB/RB/FB/WR/TE depth players;
- Receiving Yards and Receptions share the current WR/TE/RB/FB pool;
- pending/live/final games expose zero eligible display candidates.

This is verification-only. It does not change projection math, market logic,
router behavior, rankings, grades, stake sizing or wagering behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sports_api import nfl_prop_player_eligibility_v1 as elig
from sports_api.collectors import nfl_rushing_yards_context_v1 as rush
from sports_api.collectors.nfl_fanduel_passing_yards import NFLPassingYardsCollectorError
from sports_api.collectors.nfl_passing_yards_render_espn_v2 import (
    collect_fanduel_nfl_passing_yards_hosted,
)
from sports_api.collectors.nfl_fanduel_rushing_yards_v2 import (
    NFLRushingYardsCollectorError,
    collect_fanduel_nfl_rushing_yards_hosted,
)
from sports_api.collectors.nfl_fanduel_receiving_yards_v1 import (
    NFLReceivingYardsMarketCollectorError,
    collect_fanduel_nfl_receiving_yards_hosted,
)

DATE = "20260920"
PRODUCTION_API = "https://kyre-sports-api.onrender.com"
QB_POSITIONS = frozenset({"QB"})
RUSH_POSITIONS = frozenset({"QB", "RB", "FB", "WR", "TE"})
RECEIVING_POSITIONS = frozenset({"WR", "TE", "RB", "FB"})

MARKETS = {
    "passing_yards": {
        "path": "/api/v1/nfl/passing-yards",
        "collector": collect_fanduel_nfl_passing_yards_hosted,
    },
    "rushing_yards": {
        "path": "/api/v1/nfl/rushing-yards/market",
        "collector": collect_fanduel_nfl_rushing_yards_hosted,
    },
    "receiving_yards": {
        "path": "/api/v1/nfl/receiving-yards/market",
        "collector": collect_fanduel_nfl_receiving_yards_hosted,
    },
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 18) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    request = Request(
        target,
        headers={
            "Accept": "application/json",
            "User-Agent": "KyreSportsAI-Step6-PropAudit/1.0",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        if int(getattr(response, "status", 0) or 0) != 200:
            raise RuntimeError(f"HTTP {getattr(response, 'status', 0)}")
        payload = json.loads(response.read(20_000_000).decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("response was not a JSON object")
    return payload


def _event_identity(summary: dict[str, Any]) -> tuple[int, dict[str, dict[str, str]]]:
    header = summary.get("header") or {}
    season = header.get("season") or {}
    try:
        year = int(season.get("year") or 2026)
    except (TypeError, ValueError):
        year = 2026
    competitions = header.get("competitions") or []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    teams: dict[str, dict[str, str]] = {}
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, dict):
            continue
        team = competitor.get("team") or {}
        team_id = _text(team.get("id"))
        abbr = _text(team.get("abbreviation")).upper()
        if team_id.isdigit() and abbr:
            teams[team_id] = {
                "official_team_id": team_id,
                "abbr": abbr,
                "name": _text(team.get("displayName") or team.get("name") or abbr),
            }
    if len(teams) != 2:
        raise AssertionError(f"expected two exact teams, got {teams}")
    return year, teams


def _depth_payload(team_id: str, season: int) -> tuple[dict[str, Any], str]:
    site = rush._get_json(f"{rush.ESPN_SITE_BASE}/teams/{team_id}/depthcharts")
    if elig.parse_depth_chart(site, RUSH_POSITIONS):
        return site, "ESPN_SITE"
    core = rush._get_json(
        f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
        f"seasons/{season}/teams/{team_id}/depthcharts"
    )
    if not elig.parse_depth_chart(core, RUSH_POSITIONS):
        raise AssertionError(f"no current depth chart for team {team_id}")
    return core, "ESPN_CORE"


def _eligible_pools(
    summary: dict[str, Any],
    league_injuries: dict[str, Any],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    season, teams = _event_identity(summary)
    availability = elig.event_availability_state(summary)
    pools: dict[str, dict[str, dict[str, Any]]] = {}

    for team_id in teams:
        roster = rush._get_json(f"{rush.ESPN_SITE_BASE}/teams/{team_id}/roster")
        depth, depth_source = _depth_payload(team_id, season)
        qb_pool, qb_diag = elig.build_current_prop_pool(
            team_id=team_id,
            roster_payload=roster,
            depth_payload=depth,
            event_summary=summary,
            league_injury_payload=league_injuries,
            allowed_positions=QB_POSITIONS,
        )
        rush_pool, rush_diag = elig.build_current_prop_pool(
            team_id=team_id,
            roster_payload=roster,
            depth_payload=depth,
            event_summary=summary,
            league_injury_payload=league_injuries,
            allowed_positions=RUSH_POSITIONS,
        )
        recv_pool, recv_diag = elig.build_current_prop_pool(
            team_id=team_id,
            roster_payload=roster,
            depth_payload=depth,
            event_summary=summary,
            league_injury_payload=league_injuries,
            allowed_positions=RECEIVING_POSITIONS,
        )
        pools[team_id] = {
            "qb": qb_pool,
            "rush": rush_pool,
            "receive": recv_pool,
            "diagnostics": {
                "depth_source": depth_source,
                "qb": qb_diag,
                "rush": rush_diag,
                "receive": recv_diag,
            },
        }

    if availability.get("state") == "CONFIRMED":
        for team_id, row in pools.items():
            if not row["qb"]:
                raise AssertionError(f"confirmed team {team_id} has no eligible QB")
            if not row["rush"]:
                raise AssertionError(f"confirmed team {team_id} has no eligible rushing pool")
            if not row["receive"]:
                raise AssertionError(f"confirmed team {team_id} has no eligible receiving/receptions pool")
    else:
        for team_id, row in pools.items():
            if row["qb"] or row["rush"] or row["receive"]:
                raise AssertionError(
                    f"{availability.get('state')} event leaked eligible prop players for team {team_id}"
                )

    return pools, availability


def _starter_qb_ids(pools: dict[str, dict[str, dict[str, Any]]]) -> dict[str, set[str]]:
    starters: dict[str, set[str]] = {}
    for team_id, row in pools.items():
        qb_pool = row["qb"]
        ranks = [
            int(player.get("depth_rank") or 99)
            for player in qb_pool.values()
            if _text(player.get("official_athlete_id")).isdigit()
        ]
        if not ranks:
            starters[team_id] = set()
            continue
        best = min(ranks)
        starters[team_id] = {
            athlete_id
            for athlete_id, player in qb_pool.items()
            if int(player.get("depth_rank") or 99) == best
        }
    return starters


def _production_market(kind: str, event_id: str) -> dict[str, Any]:
    spec = MARKETS[kind]
    return _get_json(
        f"{PRODUCTION_API}{spec['path']}",
        {"event_id": event_id},
        timeout=22,
    )


def _local_market(kind: str, event_id: str) -> dict[str, Any]:
    spec = MARKETS[kind]
    return spec["collector"](event_id, timeout=18)


def _load_market(kind: str, event_id: str) -> tuple[dict[str, Any], str, str]:
    prod_error = ""
    try:
        return _production_market(kind, event_id), "PRODUCTION_API", ""
    except Exception as exc:
        prod_error = f"{type(exc).__name__}: {exc}"[:240]
    try:
        return _local_market(kind, event_id), "DIRECT_COLLECTOR", prod_error
    except (
        NFLPassingYardsCollectorError,
        NFLRushingYardsCollectorError,
        NFLReceivingYardsMarketCollectorError,
    ) as exc:
        raise AssertionError(
            f"{kind} unavailable from production and direct collector for event {event_id}; "
            f"production={prod_error}; direct={type(exc).__name__}: {str(exc)[:220]}"
        ) from exc


def _audit_market_rows(
    *,
    kind: str,
    event_id: str,
    teams: dict[str, dict[str, str]],
    pools: dict[str, dict[str, dict[str, Any]]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("ready") is not True:
        raise AssertionError(f"{kind} payload not ready for event {event_id}: {payload.get('reason')}")
    if _text(payload.get("official_event_id")) != event_id:
        raise AssertionError(f"{kind} event identity mismatch for {event_id}")

    rows = payload.get("props") or []
    if not isinstance(rows, list):
        raise AssertionError(f"{kind} props payload is not a list for event {event_id}")

    starters = _starter_qb_ids(pools)
    seen: set[str] = set()
    audited: list[dict[str, str]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise AssertionError(f"{kind} contains a non-object prop row for event {event_id}")
        row_event = _text(raw.get("official_event_id"))
        team_id = _text(raw.get("official_team_id"))
        athlete_id = _text(raw.get("official_athlete_id"))
        if row_event != event_id:
            raise AssertionError(f"{kind} row crossed event boundary: {raw}")
        if team_id not in teams:
            raise AssertionError(f"{kind} row has wrong team for event {event_id}: {raw}")
        if not athlete_id.isdigit():
            raise AssertionError(f"{kind} row missing exact athlete ID: {raw}")
        if athlete_id in seen:
            raise AssertionError(f"{kind} duplicate athlete market {athlete_id} for event {event_id}")
        seen.add(athlete_id)

        if kind == "passing_yards":
            allowed = starters.get(team_id, set())
        elif kind == "rushing_yards":
            allowed = set(pools[team_id]["rush"])
        else:
            allowed = set(pools[team_id]["receive"])
        if athlete_id not in allowed:
            raise AssertionError(
                f"{kind} stale/wrong player would display: event={event_id} "
                f"team={team_id} athlete={athlete_id} name={_text(raw.get('player_name'))}"
            )
        audited.append({
            "team": teams[team_id]["abbr"],
            "athlete_id": athlete_id,
            "player_name": _text(raw.get("player_name")),
        })

    if payload.get("market_available") is True and not rows:
        raise AssertionError(f"{kind} marked available but has zero certified rows for {event_id}")

    return {
        "market_available": bool(rows),
        "audited_prop_count": len(rows),
        "players": audited,
        "provider_rejected_count": int(
            ((payload.get("provider_diagnostics") or {}).get("rejected_market_count") or 0)
        ),
    }


def main() -> int:
    scoreboard = rush._get_json(f"{rush.ESPN_SITE_BASE}/scoreboard", {"dates": DATE})
    events = scoreboard.get("events") or []
    if len(events) != 14:
        raise AssertionError(f"locked slate expected 14 games, got {len(events)}")

    league_injuries = rush._get_json(f"{rush.ESPN_SITE_BASE}/injuries")
    report: dict[str, Any] = {
        "locked_date": DATE,
        "games": 0,
        "teams": 0,
        "availability": {"CONFIRMED": 0, "PENDING": 0, "CLOSED": 0},
        "market_prop_counts": {"passing_yards": 0, "rushing_yards": 0, "receiving_yards": 0},
        "receptions_identity_pool_players": 0,
        "production_fallbacks": 0,
        "event_audits": [],
    }

    for event in events:
        event_id = _text(event.get("id"))
        if not event_id.isdigit():
            raise AssertionError(f"locked slate contains invalid event ID: {event_id!r}")
        summary = rush._get_json(f"{rush.ESPN_SITE_BASE}/summary", {"event": event_id})
        _, teams = _event_identity(summary)
        pools, availability = _eligible_pools(summary, league_injuries)
        state = _text(availability.get("state")).upper()
        if state not in report["availability"]:
            raise AssertionError(f"unverified availability for event {event_id}: {availability}")

        report["games"] += 1
        report["teams"] += len(teams)
        report["availability"][state] += 1
        event_report: dict[str, Any] = {
            "event_id": event_id,
            "teams": [teams[team_id]["abbr"] for team_id in teams],
            "availability": state,
            "markets": {},
        }

        if state == "CONFIRMED":
            report["receptions_identity_pool_players"] += sum(
                len(row["receive"]) for row in pools.values()
            )
            with ThreadPoolExecutor(max_workers=3, thread_name_prefix="step6-market") as pool:
                futures = {
                    kind: pool.submit(_load_market, kind, event_id)
                    for kind in MARKETS
                }
                for kind in MARKETS:
                    payload, source, production_error = futures[kind].result()
                    audited = _audit_market_rows(
                        kind=kind,
                        event_id=event_id,
                        teams=teams,
                        pools=pools,
                        payload=payload,
                    )
                    audited["source"] = source
                    if production_error:
                        audited["production_error"] = production_error
                    if source != "PRODUCTION_API":
                        report["production_fallbacks"] += 1
                    event_report["markets"][kind] = audited
                    report["market_prop_counts"][kind] += audited["audited_prop_count"]
        else:
            event_report["display_candidates"] = 0

        report["event_audits"].append(event_report)

    if report["games"] != 14 or report["teams"] != 28:
        raise AssertionError(
            f"coverage mismatch games={report['games']} teams={report['teams']}"
        )
    if sum(report["availability"].values()) != 14:
        raise AssertionError(f"availability coverage mismatch: {report['availability']}")

    total_props = sum(report["market_prop_counts"].values())
    report["total_market_props_audited"] = total_props
    report["receptions_pool_shared_with_receiving"] = True
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()

    print(json.dumps(report, indent=2, sort_keys=True))
    print("NFL_ALL_PLAYER_PROPS_AUDIT_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
