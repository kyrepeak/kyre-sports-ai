"""Final isolated certification for the frozen WNBA Step-9 FastAPI market board."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api import wnba_step9_release_freeze as release
from sports_api import wnba_step9_threshold_pricing as pricing
from sports_api.main import app
from sports_api.wnba_step8_joint_monte_carlo import (
    MODEL_VERSION as STEP8D_MODEL_VERSION,
    SCHEMA_VERSION as STEP8D_SCHEMA_VERSION,
)

REPORT_PATH = Path("step9e-final-release-freeze-cert.json")
MARKER = "STEP9_FASTAPI_MARKET_BOARD_RELEASE_FROZEN_CERTIFIED"


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_environment() -> None:
    required_true = (
        "WNBA_STEP9_FASTAPI_ENABLED",
        "WNBA_STEP9_THRESHOLD_PRICING_ENABLED",
        "WNBA_STEP9B_MARKET_COMPARISON_ENABLED",
        "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED",
        "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED",
    )
    required_false = (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    )
    missing = [name for name in required_true if not _truthy(os.getenv(name))]
    unsafe = [name for name in required_false if _truthy(os.getenv(name))]
    if missing:
        raise RuntimeError("Step 9E cert missing isolated gates: " + ", ".join(missing))
    if unsafe:
        raise RuntimeError("Step 9E cert refuses production switches: " + ", ".join(unsafe))


def _distribution(*, player_id: int, stat: str, over_probability: float) -> dict[str, Any]:
    under = round(1.0 - over_probability, 10)
    pmfs = {
        "points": [{"value": 20, "probability": 0.4}, {"value": 21, "probability": 0.6}],
        "rebounds": [{"value": 10, "probability": 0.4}, {"value": 11, "probability": 0.6}],
        "assists": [{"value": 4, "probability": 0.4}, {"value": 5, "probability": 0.6}],
        "points_rebounds_assists": [
            {"value": 39, "probability": 0.4},
            {"value": 40, "probability": 0.6},
        ],
    }
    key = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "pra": "points_rebounds_assists",
    }[stat]
    low_value = pmfs[key][0]["value"]
    high_value = pmfs[key][1]["value"]
    pmfs[key] = [
        {"value": low_value, "probability": under},
        {"value": high_value, "probability": over_probability},
    ]
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": STEP8D_SCHEMA_VERSION,
        "model_version": STEP8D_MODEL_VERSION,
        "generated_at_utc": "2026-08-28T04:32:31+00:00",
        "game_id": "1022600291",
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "simulation": {"simulations": 5_000_000, "batch_size": 250_000},
        "convergence": {
            "converged": True,
            "max_probe_batch_probability_range": 0.005,
            "max_mean_target_absolute_error": 0.002,
            "max_probe_monte_carlo_standard_error": 0.000224,
        },
        "distributions": {
            name: {"probability_mass": rows} for name, rows in pmfs.items()
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = pricing._canonical_hash(surface)
    return result


def _prop(
    *,
    player_id: int,
    stat: str,
    line: float,
    model_over_probability: float,
    captured_at: datetime,
) -> dict[str, Any]:
    return {
        "step8_distribution": _distribution(
            player_id=player_id,
            stat=stat,
            over_probability=model_over_probability,
        ),
        "stat": stat,
        "offers": [
            {
                "sportsbook": "Certification Book A",
                "line": line,
                "over_odds": -110,
                "under_odds": -110,
                "market_captured_at_utc": captured_at.isoformat(),
            },
            {
                "sportsbook": "Certification Book B",
                "line": line,
                "over_odds": -105,
                "under_odds": -115,
                "market_captured_at_utc": (captured_at + timedelta(seconds=5)).isoformat(),
            },
        ],
    }


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    _assert_environment()
    started = datetime.now(timezone.utc)
    captured = started - timedelta(seconds=20)

    if release.DEFAULT_ENABLED is not False or release.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise RuntimeError("Step 9 release safety contract drifted.")
    if release.ENDPOINT_METHOD != "POST" or release.ENDPOINT_PATH != "/api/v1/wnba/props/market-board":
        raise RuntimeError("Step 9 frozen FastAPI endpoint contract drifted.")

    schema = app.openapi()
    path = schema.get("paths", {}).get(release.ENDPOINT_PATH)
    if not isinstance(path, dict) or set(path) != {"post"}:
        raise RuntimeError("Step 9 market-board POST route is not registered exactly once.")

    payload = {
        "props": [
            _prop(
                player_id=1642301,
                stat="points",
                line=20.5,
                model_over_probability=0.64,
                captured_at=captured,
            ),
            _prop(
                player_id=1642302,
                stat="rebounds",
                line=10.5,
                model_over_probability=0.61,
                captured_at=captured + timedelta(seconds=10),
            ),
            _prop(
                player_id=1642303,
                stat="assists",
                line=4.5,
                model_over_probability=0.58,
                captured_at=captured + timedelta(seconds=20),
            ),
            _prop(
                player_id=1642304,
                stat="pra",
                line=39.5,
                model_over_probability=0.60,
                captured_at=captured + timedelta(seconds=30),
            ),
        ],
        "policy": {"top_n": 5},
    }

    response = TestClient(app).post(release.ENDPOINT_PATH, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Step 9E FastAPI cert returned HTTP {response.status_code}: {response.text}")
    body = response.json()
    board = body.get("board") or {}
    summary = board.get("qualification_summary") or {}
    ranking = (board.get("rankings") or {}).get("pure_probability") or []
    top_card_envelope = board.get("top_cards") or {}
    top_cards = top_card_envelope.get("primary") or []

    if body.get("data_type") != "wnba_step9_market_board_api_response_v1":
        raise RuntimeError("Step 9E response data type drifted.")
    if (body.get("release") or {}).get("release_id") != release.RELEASE_ID:
        raise RuntimeError("Step 9E response release identity drifted.")
    if (body.get("pipeline") or {}).get("order") != ["step9a", "step9b", "step9c", "step9d"]:
        raise RuntimeError("Step 9E A→B→C→D pipeline order drifted.")
    if summary.get("qualified_prop_count") != 4:
        raise RuntimeError("Step 9E expected all four certification props to qualify.")
    if summary.get("top_card_count") != 4 or summary.get("requested_top_card_count") != 5:
        raise RuntimeError("Step 9E must expose four cards while five were requested.")
    if summary.get("full_requested_board_available") is not False:
        raise RuntimeError("Step 9E must never force a fifth card.")
    if top_card_envelope.get("not_forced") is not True:
        raise RuntimeError("Step 9E frozen Step-9D top-card envelope lost not_forced=true.")

    expected_probability_order = [1642301, 1642302, 1642304, 1642303]
    observed_probability_order = [int(item["player_id"]) for item in ranking]
    if observed_probability_order != expected_probability_order:
        raise RuntimeError(
            f"Step 9E pure-probability ranking drifted: {observed_probability_order}"
        )
    if [int(item["player_id"]) for item in top_cards] != expected_probability_order:
        raise RuntimeError("Step 9E primary cards must follow qualified probability ranking.")

    for item in top_cards:
        if item.get("qualified") is not True:
            raise RuntimeError("Step 9E emitted an unqualified primary card.")
        if float(item.get("model_probability")) < 0.55:
            raise RuntimeError("Step 9E emitted a card below the model-probability floor.")
        if float(item.get("ev_per_unit")) < 0.05:
            raise RuntimeError("Step 9E emitted a card below the EV floor.")
        if float(item.get("same_line_consensus_edge_probability")) < 0.03:
            raise RuntimeError("Step 9E emitted a card below the consensus-edge floor.")

    guards = body.get("guardrails") or {}
    for key in (
        "sportsbook_network_fetch_performed",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        if guards.get(key) is not False:
            raise RuntimeError(f"Step 9E guardrail {key!r} is not false.")

    report = {
        "data_type": "wnba_step9e_final_release_freeze_cert_v1",
        "certification_result": MARKER,
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step9e": {
            "release_id": release.RELEASE_ID,
            "integration_version": release.INTEGRATION_VERSION,
            "branch": os.getenv("GITHUB_REF_NAME"),
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "endpoint_method": release.ENDPOINT_METHOD,
            "endpoint_path": release.ENDPOINT_PATH,
            "openapi_post_registered": True,
        },
        "frozen_lineage": {
            "step8": release.STEP8_FROZEN_SHA,
            "step9a": release.STEP9A_FROZEN_SHA,
            "step9b": release.STEP9B_FROZEN_SHA,
            "step9c": release.STEP9C_FROZEN_SHA,
            "step9d": release.STEP9D_FROZEN_SHA,
        },
        "api_certification": {
            "http_status": response.status_code,
            "input_prop_count": len(payload["props"]),
            "qualified_prop_count": summary["qualified_prop_count"],
            "requested_top_card_count": summary["requested_top_card_count"],
            "top_card_count": summary["top_card_count"],
            "full_requested_board_available": summary["full_requested_board_available"],
            "pure_probability_player_order": observed_probability_order,
            "ranking_content_sha256": board.get("ranking_content_sha256"),
            "response_evidence_sha256": _sha256_json(
                {
                    "release": body.get("release"),
                    "pipeline": body.get("pipeline"),
                    "ranking_content_sha256": board.get("ranking_content_sha256"),
                    "top_cards": top_cards,
                    "guardrails": guards,
                }
            ),
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_network_fetch_performed": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_activation_allowed": False,
            "top_five_forced": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(MARKER)
    _assert_environment()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
