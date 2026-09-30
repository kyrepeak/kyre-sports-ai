"""Deterministic certification for all three Step-6 market reasoning contracts."""
from __future__ import annotations

import cfb_top_picks_market_reasoning_v1 as reasoning


def _metric(value, source):
    return {"value": value, "status": "VERIFIED", "source": source, "observed_at": "2026-09-30T04:00:00+00:00"}


def _fixtures():
    offense = {
        "observed_at": "2026-09-30T04:00:00+00:00",
        "away": {
            "team": "Away State", "observed_at": "2026-09-30T04:00:00+00:00",
            "metrics": {
                "points_per_game": _metric(34.0, "ESPN offense"),
                "recent_scoring_avg": _metric(31.0, "ESPN recent offense"),
                "yards_per_play": _metric(6.4, "NCAA offense"),
            },
            "recent_games": [{"points_for": 35, "points_against": 24}, {"points_for": 28, "points_against": 20}],
            "source_router": {"recent_scoring": {"provider": "ESPN exact-team completed-game schedule"}},
        },
        "home": {
            "team": "Home Tech", "observed_at": "2026-09-30T04:00:00+00:00",
            "metrics": {
                "points_per_game": _metric(29.0, "ESPN offense"),
                "recent_scoring_avg": _metric(27.0, "ESPN recent offense"),
                "yards_per_play": _metric(5.8, "NCAA offense"),
            },
            "recent_games": [{"points_for": 27, "points_against": 30}, {"points_for": 31, "points_against": 28}],
            "source_router": {"recent_scoring": {"provider": "ESPN exact-team completed-game schedule"}},
        },
    }
    defense = {
        "observed_at": "2026-09-30T04:00:00+00:00",
        "away": {"team": "Away State", "metrics": {
            "points_allowed_per_game": _metric(20.0, "ESPN defense"),
            "recent_points_allowed_avg": _metric(23.0, "ESPN recent defense"),
            "yards_per_play_allowed": _metric(5.0, "ESPN defense"),
            "plays_per_game": _metric(72.0, "NCAA pace"),
        }},
        "home": {"team": "Home Tech", "metrics": {
            "points_allowed_per_game": _metric(27.0, "ESPN defense"),
            "recent_points_allowed_avg": _metric(29.0, "ESPN recent defense"),
            "yards_per_play_allowed": _metric(5.9, "ESPN defense"),
            "plays_per_game": _metric(68.0, "NCAA pace"),
        }},
    }
    series = {
        "history_ready": True, "status": "VERIFIED_HISTORY",
        "source": "Verified history source", "sources_verified": ["Verified history source"],
        "observed_at": "2026-09-30T04:00:00+00:00",
        "meetings": 4, "away_wins": 3, "home_wins": 1, "avg_combined_total": 58.5,
    }
    return offense, defense, series, {"espn_event_id": "401234567"}


def main() -> int:
    offense, defense, series, game = _fixtures()
    rows = [
        {"market": "OVER/UNDER", "pick": "Over 51.5", "probability": 66, "probability_value": .66, "reliability": .88, "source": "Frozen O/U model", "away": "Away State", "home": "Home Tech", "event_id": "401234567"},
        {"market": "SPREAD", "pick": "Away State +3.5", "probability": 64, "probability_value": .64, "reliability": .84, "source": "Frozen margin distribution", "away": "Away State", "home": "Home Tech", "event_id": "401234567"},
        {"market": "MONEYLINE", "pick": "Away State", "probability": 69, "probability_value": .69, "reliability": .90, "source": "Frozen Moneyline model", "away": "Away State", "home": "Home Tech", "event_id": "401234567"},
    ]
    for row in rows:
        result = reasoning.build_market_reasoning(row, game, offense, defense, series)
        required = list(reasoning.REQUIRED_SIGNALS[row["market"]])
        if result["required_signals"] != required or set(result["signals"]) != set(required):
            raise AssertionError(f"STEP6_SIGNAL_SET:{row['market']}")
        if float(result["projection_weight"]) != 0.0 or float(result["sportsbook_projection_weight"]) != 0.0:
            raise AssertionError(f"STEP6_WEIGHT:{row['market']}")
        if result["may_modify_probability"] is not False or result["may_modify_ranking"] is not False or result["may_modify_selection"] is not False:
            raise AssertionError(f"STEP6_MUTATION_FIREWALL:{row['market']}")
        for key in required:
            signal = result["signals"][key]
            if signal["status"] not in reasoning.ALLOWED_SIGNAL_STATUSES:
                raise AssertionError(f"STEP6_STATUS:{row['market']}:{key}")
            if not str(signal["text"]).strip() or not str(signal["observed_at"]).strip():
                raise AssertionError(f"STEP6_EVIDENCE:{row['market']}:{key}")
            if signal["status"] in {"VERIFIED", "PARTIAL"} and not signal["sources"]:
                raise AssertionError(f"STEP6_SOURCE:{row['market']}:{key}")

    print("CFB_TOP_PICKS_RESEARCH_V2_STEP6_THREE_MARKETS_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP6_SIGNAL_CONTRACT_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP6_FROZEN_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
