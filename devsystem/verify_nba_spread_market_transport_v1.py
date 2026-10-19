"""Safe NBA Spread market-transport verifier.

The default CLI path is deterministic and suitable for Runless static proof.
Use ``--live`` only in an environment that owns the production provider
credential/network. Credential material is never printed or returned.
"""
from __future__ import annotations

import argparse
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
        "source": str(payload.get("source") or "SportsGameOdds+ESPN Public Scoreboard"),
        "source_chain": list(payload.get("source_chain") or []),
        "primary_source_state": str(payload.get("primary_source_state") or "") or None,
        "stale_observation_count": int(payload.get("stale_observation_count") or 0),
        "games": games,
    }


def run_probe(schedule_games: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    """Run the real production V2 market source chain for an already-resolved slate."""
    import nba_spread_live_data_repair_v2 as live_v2

    key = live_v2.resolve_sgo_api_key()
    try:
        payload = live_v2.load_market_payload_v2(schedule_games)
    except Exception as exc:
        payload = {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"MARKET_SOURCE_CHAIN_ERROR:{type(exc).__name__}",
            "source": "SportsGameOdds+ESPN Public Scoreboard",
            "observations": [],
            "source_chain": ["SportsGameOdds", "ESPN Public Scoreboard"],
        }
    return summarize_transport_result(payload, credential_resolved=bool(key))


def run_static_contract_probe() -> dict[str, Any]:
    """Verify deterministic transport ownership/safety without live provider I/O."""
    import nba_spread_live_data_repair_v2 as live_v2

    fixture = {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "source": "SportsGameOdds",
        "observations": [
            {
                "game_key": "BOS@DET:2026-10-20",
                "sportsbook": "FanDuel",
                "observed_at_utc": "2026-10-19T22:00:00Z",
            },
            {
                "game_key": "BOS@DET:2026-10-20",
                "sportsbook": "DraftKings",
                "observed_at_utc": "2026-10-19T22:00:00Z",
            },
        ],
    }
    summary = summarize_transport_result(fixture, credential_resolved=True)
    bos_det = dict(summary.get("games", {}).get("BOS@DET:2026-10-20") or {})
    checks = {
        "projection_influence_zero": live_v2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0,
        "model_immutable": live_v2.MAY_MODIFY_MODEL is False,
        "projection_immutable": live_v2.MAY_MODIFY_PROJECTION is False,
        "probability_immutable": live_v2.MAY_MODIFY_PROBABILITY is False,
        "ranking_immutable": live_v2.MAY_MODIFY_RANKING is False,
        "credential_resolver_bound": callable(live_v2.resolve_sgo_api_key),
        "transport_loader_bound": callable(live_v2.load_market_payload_v2),
        "two_book_fixture": int(bos_det.get("book_count") or 0) == 2,
    }
    ok = all(checks.values())
    return {
        "verification": "VERIFIED" if ok else "BLOCKED",
        "mode": "STATIC_CONTRACT",
        "checks": checks,
        "sportsbook_projection_influence": 0.0,
    }


def run_live_probe() -> dict[str, Any]:
    """Run the real production-shaped schedule + market source-chain probe."""
    try:
        from nba_spread_schedule_provider_resilience_step2_r1 import load_verified_nba_schedule

        schedule = load_verified_nba_schedule()
        games = list(schedule.get("games") or []) if isinstance(schedule, Mapping) else []
        opener = [game for game in games if str(game.get("game_date_phoenix") or "") == "2026-10-20"]
        return run_probe(opener)
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"LIVE_PROBE_ERROR:{type(exc).__name__}",
            "credential_resolved": False,
            "source": "SportsGameOdds+ESPN Public Scoreboard",
            "source_chain": ["SportsGameOdds", "ESPN Public Scoreboard"],
            "games": {},
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--live", action="store_true")
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)
    result = run_live_probe() if args.live else run_static_contract_probe()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("verification") == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())