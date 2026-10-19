"""Safe NBA Spread market-transport diagnostic.

This verifier reports only transport state and exact game/book coverage. It never
returns or prints credential material.
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def summarize_transport_result(payload: Mapping[str, Any], *, credential_resolved: bool) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"books": set(), "observed_at_utc": []})
    observations = payload.get("observations") or []
    if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)):
        for raw in observations:
            if not isinstance(raw, Mapping):
                continue
            game_key = str(raw.get("game_key") or "").strip()
            book = str(raw.get("sportsbook") or "").strip()
            if not game_key or not book:
                continue
            grouped[game_key]["books"].add(book)
            observed = str(raw.get("observed_at_utc") or raw.get("retrieved_at_utc") or "").strip()
            if observed:
                grouped[game_key]["observed_at_utc"].append(observed)
    games: dict[str, dict[str, Any]] = {}
    for game_key in sorted(grouped):
        books = sorted(grouped[game_key]["books"])
        times = sorted(grouped[game_key]["observed_at_utc"])
        games[game_key] = {
            "book_count": len(books),
            "books": books,
            "latest_observed_at_utc": times[-1] if times else None,
        }
    return {
        "credential_resolved": bool(credential_resolved),
        "verification": str(payload.get("verification") or "UNAVAILABLE"),
        "diagnostic_state": str(payload.get("diagnostic_state") or "UNKNOWN"),
        "source": str(payload.get("source") or "SportsGameOdds"),
        "stale_observation_count": int(payload.get("stale_observation_count") or 0),
        "games": games,
    }


def run_probe(schedule_games: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    from nba_spread_live_data_repair_v2 import resolve_sgo_api_key
    from nba_spread_sportsbook_observations_v2 import load_verified_sportsbook_observations_v2

    key = resolve_sgo_api_key()
    if not key:
        payload = {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE",
            "source": "SportsGameOdds",
            "observations": [],
        }
        return summarize_transport_result(payload, credential_resolved=False)

    def getter(name: str) -> str | None:
        return key if name == "SPORTSGAMEODDS_API_KEY" else None

    payload = load_verified_sportsbook_observations_v2(schedule_games, secret_getter=getter)
    return summarize_transport_result(payload, credential_resolved=True)


def main() -> None:
    from nba_spread_schedule_provider_resilience_step2_r1 import load_verified_nba_schedule

    schedule = load_verified_nba_schedule()
    games = list(schedule.get("games") or []) if isinstance(schedule, Mapping) else []
    opener = [game for game in games if str(game.get("game_date_phoenix") or "") == "2026-10-20"]
    print(json.dumps(run_probe(opener), sort_keys=True))


if __name__ == "__main__":
    main()
