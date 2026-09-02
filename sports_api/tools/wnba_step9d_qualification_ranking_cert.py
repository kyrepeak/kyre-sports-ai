"""Offline certification for Step 9D WNBA prop qualification + ranking.

Uses deterministic, hash-covered Step-9C-shaped fixtures only. No sportsbook or
network call occurs. The certificate locks conservative qualification, transparent
probability/value rankings, one-player-per-game Top-card diversification, no-force
Top-5 behavior, frozen lineage, and production-off safety.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import copy
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step9_multisportsbook_consensus as step9c
from sports_api import wnba_step9_qualification_ranking as ranking

REPORT_PATH = Path("step9d-qualification-ranking-cert.json")
STEP9C_FROZEN_SHA = "7372d5a22665e84cd0179c2346939d953e52c31a"
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = [name for name in _OFF_ENV_KEYS if _truthy(os.getenv(name))]
    if bad:
        raise RuntimeError("Step 9D cert refuses production switches: " + ", ".join(bad))
    if not _truthy(os.getenv(ranking.STEP9D_QUALIFICATION_RANKING_ENABLED_ENV)):
        raise RuntimeError("Step 9D cert requires its isolated CI flag.")


def _offer(
    side: str,
    *,
    line: float,
    sportsbook: str,
    model_probability: float,
    market_probability: float,
    ev: float,
    captured_at: str,
    salt: str,
) -> dict[str, Any]:
    return {
        "sportsbook": sportsbook,
        "line": line,
        "american_odds": -110,
        "decimal_odds": 1.90909091,
        "model_raw_win_probability": model_probability,
        "model_raw_push_probability": 0.0,
        "model_resolved_fair_win_probability": model_probability,
        "market_no_vig_probability": market_probability,
        "no_vig_edge_probability": model_probability - market_probability,
        "no_vig_edge_percentage_points": (model_probability - market_probability) * 100.0,
        "ev_per_unit": ev,
        "ev_roi_percentage": ev * 100.0,
        "captured_at_utc": captured_at,
        "comparison_content_sha256": salt * 64,
        "pricing_content_sha256": chr(ord(salt) + 1) * 64,
        "selection_method": "cert_fixture",
        "cross_prop_ranking_applied": False,
    }


def _consensus(
    *,
    player_id: int,
    stat: str,
    side: str,
    model_probability: float,
    ev: float,
    edge: float,
    captured_at: datetime,
) -> dict[str, Any]:
    line_by_stat = {"points": 20.5, "rebounds": 10.5, "assists": 5.5, "pra": 35.5}
    line = line_by_stat[stat]
    if side == "over":
        model_over = model_probability
        model_under = 1.0 - model_probability
        market_over = model_over - edge
        market_under = 1.0 - market_over
        over_ev, under_ev = ev, -0.08
    else:
        model_under = model_probability
        model_over = 1.0 - model_probability
        market_under = model_under - edge
        market_over = 1.0 - market_under
        over_ev, under_ev = -0.08, ev
    captured = captured_at.isoformat()
    over = _offer(
        "over",
        line=line,
        sportsbook="CertBookA",
        model_probability=model_over,
        market_probability=market_over,
        ev=over_ev,
        captured_at=captured,
        salt="a",
    )
    under = _offer(
        "under",
        line=line,
        sportsbook="CertBookB",
        model_probability=model_under,
        market_probability=market_under,
        ev=under_ev,
        captured_at=captured,
        salt="c",
    )
    payload: dict[str, Any] = {
        "data_type": "post_projection_multisportsbook_consensus",
        "schema_version": step9c.SCHEMA_VERSION,
        "source": step9c.SOURCE,
        "model_version": step9c.MODEL_VERSION,
        "release_id": step9c.RELEASE_ID,
        "generated_at_utc": captured,
        "game_id": "1022600291",
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "prop": {
            "stat": stat,
            "unique_lines": [line],
            "reference_line": line,
            "reference_line_method": "most_sportsbooks_then_lower_line_tiebreak",
            "different_lines_are_never_probability_averaged": True,
        },
        "snapshot": {
            "offer_count": 3,
            "unique_sportsbook_count": 3,
            "unique_sportsbooks": ["CertBookA", "CertBookB", "CertBookC"],
            "earliest_captured_at_utc": captured,
            "latest_captured_at_utc": captured,
            "snapshot_spread_seconds": 20.0,
            "max_snapshot_spread_seconds": 120,
            "require_fresh_quotes": True,
            "require_synchronized_snapshot": True,
            "all_quotes_fresh": True,
        },
        "same_line_consensus": [
            {
                "line": line,
                "book_count": 3,
                "sportsbooks": ["CertBookA", "CertBookB", "CertBookC"],
                "consensus_available": True,
                "consensus_method": "median_of_same_line_book_no_vig_probabilities",
                "no_vig_over": {
                    "median_probability": market_over,
                    "median_percentage": market_over * 100.0,
                    "mean_probability": market_over,
                    "minimum_probability": market_over - 0.01,
                    "maximum_probability": market_over + 0.01,
                    "range_percentage_points": 2.0,
                },
                "no_vig_under": {
                    "median_probability": market_under,
                    "median_percentage": market_under * 100.0,
                    "mean_probability": market_under,
                    "minimum_probability": market_under - 0.01,
                    "maximum_probability": market_under + 0.01,
                    "range_percentage_points": 2.0,
                },
                "model": {
                    "resolved_fair_over_probability": model_over,
                    "resolved_fair_under_probability": model_under,
                },
                "consensus_edge": {
                    "over_probability": model_over - market_over,
                    "over_percentage_points": (model_over - market_over) * 100.0,
                    "under_probability": model_under - market_under,
                    "under_percentage_points": (model_under - market_under) * 100.0,
                },
                "guardrail": "probabilities from different statistical lines are never blended",
            }
        ],
        "best_available": {
            "over": copy.deepcopy(over),
            "under": copy.deepcopy(under),
            "reference_line_best_price": {
                "line": line,
                "over": copy.deepcopy(over),
                "under": copy.deepcopy(under),
            },
            "selection_scope": "within_one_player_prop_only; cross-prop qualification/ranking is Step 9D",
        },
        "lineage": {
            "step8_result_content_sha256": f"{player_id:064x}"[-64:],
            "step9a_release_id": "wnba_step9a_threshold_pricing_2026_regular_season_v1",
            "step9a_model_version": "wnba_step9a_post_step8_threshold_pricing_2026_regular_v1",
            "step9a_frozen_git_sha": "3b9acde91250d0e7a1767f3861765d4366f510ba",
            "step9b_release_id": "wnba_step9b_sportsbook_market_comparison_2026_regular_season_v1",
            "step9b_model_version": "wnba_step9b_post_projection_market_comparison_2026_regular_v1",
            "step9b_frozen_git_sha": "45cd3b43ca2771ae01f6fa3c7345ef0b9a444394",
            "comparison_content_sha256s": ["a" * 64, "c" * 64],
            "pricing_content_sha256s": ["b" * 64, "d" * 64],
        },
        "guardrails": {
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9a_probabilities_changed": False,
            "step9b_comparisons_changed": False,
            "sportsbook_called": False,
            "cross_sportsbook_consensus_calculated": True,
            "different_lines_blended_into_consensus": False,
            "best_offer_selected_within_prop": True,
            "cross_prop_ranking_calculated": False,
            "qualification_applied": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    surface = dict(payload)
    surface.pop("generated_at_utc", None)
    payload["consensus_content_sha256"] = ranking._canonical_hash(surface)
    return payload


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    if ranking.STEP9C_FROZEN_SHA != STEP9C_FROZEN_SHA:
        raise RuntimeError("Step 9D frozen Step-9C SHA constant drifted.")
    if step9c.RELEASE_ID != "wnba_step9c_multisportsbook_consensus_2026_regular_season_v1":
        raise RuntimeError("Step 9C release identity drifted.")

    base = datetime(2026, 8, 28, 4, 50, 0, tzinfo=timezone.utc)
    inputs = [
        _consensus(player_id=1642301, stat="points", side="over", model_probability=0.64, ev=0.10, edge=0.06, captured_at=base),
        _consensus(player_id=1642302, stat="rebounds", side="under", model_probability=0.61, ev=0.15, edge=0.07, captured_at=base + timedelta(seconds=10)),
        _consensus(player_id=1642303, stat="assists", side="over", model_probability=0.58, ev=0.20, edge=0.05, captured_at=base + timedelta(seconds=20)),
        _consensus(player_id=1642301, stat="pra", side="over", model_probability=0.60, ev=0.18, edge=0.08, captured_at=base + timedelta(seconds=30)),
        _consensus(player_id=1642304, stat="points", side="over", model_probability=0.54, ev=0.25, edge=0.10, captured_at=base + timedelta(seconds=40)),
        _consensus(player_id=1642305, stat="rebounds", side="over", model_probability=0.59, ev=0.03, edge=0.05, captured_at=base + timedelta(seconds=50)),
    ]
    result = ranking.build_step9d_qualification_ranking(inputs)

    summary = result["qualification_summary"]
    if summary["input_prop_count"] != 6:
        raise RuntimeError("Step 9D certification input count changed.")
    if summary["qualified_prop_count"] != 4:
        raise RuntimeError("Step 9D qualification count changed.")
    if summary["top_card_count"] != 3:
        raise RuntimeError("Step 9D one-player diversification behavior changed.")
    if summary["full_requested_board_available"] is not False:
        raise RuntimeError("Step 9D must not force a five-card board.")

    pure = result["rankings"]["pure_probability"]
    value = result["rankings"]["value"]
    expected_pure_players = [1642301, 1642302, 1642301, 1642303]
    if [row["player_id"] for row in pure] != expected_pure_players:
        raise RuntimeError("Step 9D pure-probability ranking order changed.")
    expected_value_players = [1642303, 1642301, 1642302, 1642301]
    if [row["player_id"] for row in value] != expected_value_players:
        raise RuntimeError("Step 9D value ranking order changed.")
    if pure[1]["side"] != "under":
        raise RuntimeError("Step 9D Under-side qualification support changed.")

    top_cards = result["top_cards"]["primary"]
    if [row["player_id"] for row in top_cards] != [1642301, 1642302, 1642303]:
        raise RuntimeError("Step 9D Top-card diversification order changed.")
    if len(result["top_cards"]["diversification_skips"]) != 1:
        raise RuntimeError("Step 9D expected one same-player diversification skip.")

    guards = result["guardrails"]
    for key in (
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9a_probabilities_changed",
        "step9b_comparisons_changed",
        "step9c_consensus_changed",
        "sportsbook_called",
        "cross_sportsbook_consensus_recomputed",
        "top_n_forced",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        if guards.get(key) is not False:
            raise RuntimeError(f"Step 9D safety guard {key!r} is not false.")
    for key in ("qualification_applied", "cross_prop_ranking_calculated"):
        if guards.get(key) is not True:
            raise RuntimeError(f"Step 9D capability guard {key!r} is not true.")

    report = {
        "data_type": "wnba_step9d_qualification_ranking_cert_v1",
        "certification_result": "STEP9D_QUALIFICATION_RANKING_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step9d": {
            "release_id": ranking.RELEASE_ID,
            "schema_version": ranking.SCHEMA_VERSION,
            "model_version": ranking.MODEL_VERSION,
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "branch": os.getenv("GITHUB_REF_NAME"),
            "ranking_content_sha256": result["ranking_content_sha256"],
        },
        "frozen_step9c": {
            "git_sha": STEP9C_FROZEN_SHA,
            "release_id": step9c.RELEASE_ID,
            "model_version": step9c.MODEL_VERSION,
        },
        "qualification_policy": result["qualification_policy"],
        "board_snapshot": result["board_snapshot"],
        "qualification_summary": summary,
        "pure_probability_ranking": [
            {
                "rank": row["rank"],
                "player_id": row["player_id"],
                "stat": row["stat"],
                "side": row["side"],
                "model_probability": row["model_probability"],
                "ev_roi_percentage": row["ev_roi_percentage"],
                "consensus_edge_percentage_points": row["same_line_consensus_edge_percentage_points"],
            }
            for row in pure
        ],
        "value_ranking": [
            {
                "rank": row["rank"],
                "player_id": row["player_id"],
                "stat": row["stat"],
                "side": row["side"],
                "model_probability": row["model_probability"],
                "ev_roi_percentage": row["ev_roi_percentage"],
            }
            for row in value
        ],
        "top_cards": [
            {
                "rank": row["top_card_rank"],
                "player_id": row["player_id"],
                "stat": row["stat"],
                "side": row["side"],
                "model_probability": row["model_probability"],
                "ev_roi_percentage": row["ev_roi_percentage"],
            }
            for row in top_cards
        ],
        "safety": {
            "sportsbook_called": False,
            "basketball_projection_changed": False,
            "step9c_consensus_changed": False,
            "top_five_forced": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP9D_QUALIFICATION_RANKING_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
