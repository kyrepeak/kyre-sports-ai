"""Step 5 live NFL starter/depth + prop-player eligibility audit."""
from __future__ import annotations

import json

from sports_api import nfl_prop_player_eligibility_v1 as elig
from sports_api.collectors import nfl_rushing_yards_context_v1 as rush


DATE = "20260920"
RUSH_POSITIONS = frozenset({"QB", "RB", "FB", "WR", "TE"})
RECEIVING_POSITIONS = frozenset({"WR", "TE", "RB", "FB"})


def main() -> int:
    scoreboard = rush._get_json(f"{rush.ESPN_SITE_BASE}/scoreboard", {"dates": DATE})
    events = scoreboard.get("events") or []
    league_injury_payload = rush._get_json(f"{rush.ESPN_SITE_BASE}/injuries")
    if len(events) != 14:
        raise AssertionError(f"expected 14 games, got {len(events)}")

    games = 0
    teams = 0
    confirmed = 0
    pending = 0
    closed = 0
    confirmed_rush_players = 0
    confirmed_receivers = 0
    atlanta = {}

    for event in events:
        event_id = str(event.get("id") or "").strip()
        if not event_id.isdigit():
            continue
        summary = rush._get_json(f"{rush.ESPN_SITE_BASE}/summary", {"event": event_id})
        availability = elig.event_availability_state(summary)
        if availability["state"] == "CONFIRMED":
            confirmed += 1
        elif availability["state"] == "PENDING":
            pending += 1
        elif availability["state"] == "CLOSED":
            closed += 1
        else:
            raise AssertionError(f"unverified availability for event {event_id}: {availability}")

        header = summary.get("header") or {}
        comps = header.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], dict) else {}
        competitors = comp.get("competitors") or []
        games += 1

        for competitor in competitors:
            team = competitor.get("team") or {}
            team_id = str(team.get("id") or "").strip()
            abbr = str(team.get("abbreviation") or "").strip().upper()
            if not team_id.isdigit():
                continue
            teams += 1
            roster = rush._get_json(f"{rush.ESPN_SITE_BASE}/teams/{team_id}/roster")
            depth = rush._get_json(f"{rush.ESPN_SITE_BASE}/teams/{team_id}/depthcharts")
            if not elig.parse_depth_chart(depth, RUSH_POSITIONS):
                season = (summary.get("header") or {}).get("season") or {}
                year = int(season.get("year") or 2026)
                depth = rush._get_json(
                    f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/teams/{team_id}/depthcharts"
                )

            rush_pool, rush_diag = elig.build_current_prop_pool(
                team_id=team_id,
                roster_payload=roster,
                depth_payload=depth,
                event_summary=summary,
                league_injury_payload=league_injury_payload,
                allowed_positions=RUSH_POSITIONS,
            )
            recv_pool, recv_diag = elig.build_current_prop_pool(
                team_id=team_id,
                roster_payload=roster,
                depth_payload=depth,
                event_summary=summary,
                league_injury_payload=league_injury_payload,
                allowed_positions=RECEIVING_POSITIONS,
            )

            if availability["state"] == "CONFIRMED":
                if not rush_pool:
                    raise AssertionError(f"confirmed team {abbr} has no rushing prop depth pool: {rush_diag}")
                if not recv_pool:
                    raise AssertionError(f"confirmed team {abbr} has no receiving prop depth pool: {recv_diag}")
                confirmed_rush_players += len(rush_pool)
                confirmed_receivers += len(recv_pool)
            else:
                if rush_pool or recv_pool:
                    raise AssertionError(
                        f"{availability['state'].lower()} team {abbr} leaked prop players"
                    )

            if abbr == "ATL":
                unavailable = {
                    str(row.get("official_athlete_id") or "")
                    for row in (availability.get("unavailable") or {}).get(team_id, [])
                }
                names = {row["player_name"]: athlete_id for athlete_id, row in rush_pool.items()}
                atlanta = {
                    "availability": availability["state"],
                    "rush_names": sorted(names),
                    "rush_ids_by_name": names,
                    "unavailable_ids": sorted(unavailable),
                    "unavailable_rows": (availability.get("unavailable") or {}).get(team_id, []),
                }
                if "Michael Penix Jr." in names:
                    raise AssertionError(
                        "Michael Penix Jr. leaked into Atlanta prop pool: "
                        + json.dumps(atlanta, sort_keys=True)
                    )
                if availability["state"] == "CONFIRMED" and "Cooper Rush" not in names:
                    raise AssertionError(f"Cooper Rush missing from confirmed Atlanta depth pool: {atlanta}")
                if availability["state"] == "CLOSED" and names:
                    raise AssertionError(f"Atlanta live/final prop pool should be closed: {atlanta}")

    if games != 14 or teams != 28:
        raise AssertionError(f"coverage mismatch games={games} teams={teams}")
    if confirmed + pending + closed != 14:
        raise AssertionError(
            f"availability coverage mismatch confirmed={confirmed} pending={pending} closed={closed}"
        )

    print(json.dumps({
        "games": games,
        "teams": teams,
        "confirmed_games": confirmed,
        "pending_games": pending,
        "closed_games": closed,
        "confirmed_rushing_prop_players": confirmed_rush_players,
        "confirmed_receiving_receptions_players": confirmed_receivers,
        "atlanta": atlanta,
    }, indent=2, sort_keys=True))
    print("NFL_STARTER_DEPTH_PROPS_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
