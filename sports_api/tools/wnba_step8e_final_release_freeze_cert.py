"""Final OFF-only FastAPI/release-freeze certification for WNBA Step 8."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api import wnba_step8_release_freeze as freeze
from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

REPORT_PATH = Path("step8e-final-release-freeze-cert.json")
_STATS = ("points", "rebounds", "assists")
_PRA = "points_rebounds_assists"
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)
_REQUIRED_STEP_FLAGS = (
    "WNBA_STEP7G_FIRST_PARTY_ENABLED",
    "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
    "WNBA_STEP8_CORE_PROJECTION_ENABLED",
    "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED",
    "WNBA_STEP8_MONTE_CARLO_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [name for name in _OFF_ENV_KEYS if _truthy(os.getenv(name))]
    if bad:
        raise RuntimeError(
            "Final Step 8 freeze cert refuses production switches: " + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_STEP_FLAGS if not _truthy(os.getenv(name))]
    if missing:
        raise RuntimeError(
            "Final Step 8 freeze cert requires isolated Step flags: " + ", ".join(missing)
        )


def _num(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Step 8E cert expected numeric {label}.")
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"Step 8E cert expected finite {label}.")
    return result


def _assert_distribution(body: dict[str, Any], stat: str) -> dict[str, Any]:
    distributions = body.get("distributions")
    distribution = distributions.get(stat) if isinstance(distributions, dict) else None
    if not isinstance(distribution, dict):
        raise RuntimeError(f"Step 8E endpoint is missing {stat} distribution.")
    if abs(_num(distribution.get("probability_mass_sum"), f"{stat} mass sum") - 1.0) > 1e-10:
        raise RuntimeError(f"Step 8E {stat} probability mass does not sum to 1.")
    if not isinstance(distribution.get("probability_mass"), list) or not distribution["probability_mass"]:
        raise RuntimeError(f"Step 8E {stat} probability mass table is empty.")
    for key in ("expected", "variance", "stddev"):
        _num(distribution.get(key), f"{stat} {key}")
    if not isinstance(distribution.get("median"), int) or not isinstance(distribution.get("mode"), int):
        raise RuntimeError(f"Step 8E {stat} median/mode must be discrete integers.")
    return {
        "expected": distribution.get("expected"),
        "stddev": distribution.get("stddev"),
        "median": distribution.get("median"),
        "mode": distribution.get("mode"),
        "quantiles": distribution.get("quantiles"),
    }


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    if freeze.DEFAULT_ENABLED is not False or freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise RuntimeError("Frozen Step 8 release does not preserve default-OFF safety.")
    if freeze.CERTIFIED_STEP8D_SHA != "932e1baf05bf762cfb149de1f58be4f72bb7a526":
        raise RuntimeError("Frozen Step 8 release lost the live-certified Step 8D anchor.")
    if freeze.DEFAULT_SIMULATIONS != 5_000_000 or freeze.DEFAULT_BATCH_SIZE != 250_000:
        raise RuntimeError("Frozen Step 8 simulation defaults changed unexpectedly.")
    for key, expected in freeze.SAFETY_CONTRACT.items():
        if expected is not False:
            raise RuntimeError(f"Step 8 freeze safety contract {key!r} unexpectedly permits activation.")

    from sports_api.main import app

    endpoint_template = freeze.ENDPOINT_PATH_TEMPLATE
    openapi_paths = app.openapi().get("paths") or {}
    if endpoint_template not in openapi_paths:
        raise RuntimeError("Final Step 8 projection-probability route is missing from FastAPI OpenAPI.")
    operations = openapi_paths[endpoint_template]
    if "get" not in operations:
        raise RuntimeError("Final Step 8 projection-probability route does not expose GET.")

    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])
    endpoint = endpoint_template.format(game_id=game_id, player_id=player_id)
    requested_lines = {
        "points_line": 20.5,
        "rebounds_line": 15.5,
        "assists_line": 4.5,
        "pra_line": 40.5,
    }

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(endpoint, params=requested_lines)
    if response.status_code != 200:
        raise RuntimeError(
            f"Final Step 8 FastAPI certification returned HTTP {response.status_code}: {response.text[:500]}"
        )
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("Final Step 8 FastAPI endpoint returned non-object JSON.")
    if body.get("data_type") != "joint_player_stat_probability_distribution":
        raise RuntimeError("Final Step 8 endpoint returned the wrong data type.")
    if body.get("model_version") != freeze.MODEL_VERSIONS["step8d"]:
        raise RuntimeError("Final Step 8 endpoint returned the wrong Monte Carlo model version.")
    if body.get("game_id") != game_id or body.get("player_id") != player_id:
        raise RuntimeError("Final Step 8 endpoint returned the wrong requested identity.")

    simulation = body.get("simulation") or {}
    if simulation.get("simulations") != freeze.DEFAULT_SIMULATIONS:
        raise RuntimeError("Final Step 8 FastAPI call did not execute exactly 5,000,000 simulations.")
    if simulation.get("batch_size") != freeze.DEFAULT_BATCH_SIZE or simulation.get("batch_count") != 20:
        raise RuntimeError("Final Step 8 FastAPI call did not use the frozen 20 x 250,000 batching.")
    if not isinstance(simulation.get("random_seed"), int):
        raise RuntimeError("Final Step 8 FastAPI call did not expose its deterministic random seed.")

    distribution_summary = {
        stat: _assert_distribution(body, stat) for stat in (*_STATS, _PRA)
    }
    component_expected = sum(
        _num(distribution_summary[stat]["expected"], f"{stat} expected") for stat in _STATS
    )
    pra_expected = _num(distribution_summary[_PRA]["expected"], "PRA expected")
    if abs(component_expected - pra_expected) > 2e-6:
        raise RuntimeError("Final Step 8 endpoint PRA is not recomposed from the same P/R/A draws.")

    target = body.get("step8c_target") or {}
    if not isinstance(target, dict):
        raise RuntimeError("Final Step 8 endpoint is missing Step 8C target provenance.")
    for stat in (*_STATS, _PRA):
        _num(target.get(stat), f"Step 8C target {stat}")
    if body.get("model_specification", {}).get("family") != "regularized_gaussian_copula_discrete_counts":
        raise RuntimeError("Final Step 8 endpoint did not preserve the frozen joint model family.")

    line_probabilities = body.get("requested_line_probabilities") or {}
    expected_line_keys = {"points", "rebounds", "assists", _PRA}
    if set(line_probabilities) != expected_line_keys:
        raise RuntimeError("Final Step 8 endpoint did not return all requested line probabilities.")
    compact_lines: dict[str, Any] = {}
    for stat in (*_STATS, _PRA):
        row = line_probabilities.get(stat)
        if not isinstance(row, dict):
            raise RuntimeError(f"Final Step 8 endpoint line probability is missing for {stat}.")
        under = _num(row.get("under_probability"), f"{stat} under")
        push = _num(row.get("push_probability"), f"{stat} push")
        over = _num(row.get("over_probability"), f"{stat} over")
        if abs(under + push + over - 1.0) > 2e-8:
            raise RuntimeError(f"Final Step 8 {stat} line probabilities do not sum to 1.")
        if push != 0.0:
            raise RuntimeError(f"Final Step 8 half-point line unexpectedly has push probability for {stat}.")
        compact_lines[stat] = {
            "line": row.get("line"),
            "under_probability": under,
            "push_probability": push,
            "over_probability": over,
        }

    convergence = body.get("convergence") or {}
    if convergence.get("converged") is not True:
        raise RuntimeError("Final Step 8 FastAPI 5M run did not satisfy convergence certification.")
    if _num(convergence.get("max_probe_batch_probability_range"), "max batch range") > 0.01:
        raise RuntimeError("Final Step 8 batch stability exceeded the frozen limit.")
    if _num(convergence.get("max_mean_target_absolute_error"), "max mean target error") > 0.05:
        raise RuntimeError("Final Step 8 mean calibration exceeded the frozen limit.")
    if _num(convergence.get("max_probe_monte_carlo_standard_error"), "max MC SE") > 0.0005:
        raise RuntimeError("Final Step 8 Monte Carlo error exceeded the frozen limit.")

    guardrails = body.get("guardrails") or {}
    for key in (
        "official_integer_box_counts_only_for_dispersion_and_dependence",
        "small_sample_variance_regularized_toward_poisson",
        "small_sample_correlation_regularized_toward_independence",
        "p_r_a_not_simulated_independently",
        "pra_recomposed_from_same_joint_p_r_a_draws",
    ):
        if guardrails.get(key) is not True:
            raise RuntimeError(f"Final Step 8 guardrail {key!r} is not true.")
    for key in (
        "sportsbook_data_used",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_enabled",
        "production_activation_allowed",
    ):
        if guardrails.get(key) is not False:
            raise RuntimeError(f"Final Step 8 safety flag {key!r} is not false.")

    report = {
        "data_type": "wnba_step8e_final_release_freeze_cert_v1",
        "certification_result": "STEP8_FASTAPI_PROJECTION_PROBABILITY_RELEASE_FROZEN_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "release": {
            "release_id": freeze.RELEASE_ID,
            "integration_version": freeze.INTEGRATION_VERSION,
            "certified_step8d_sha": freeze.CERTIFIED_STEP8D_SHA,
            "certified_branch": freeze.CERTIFIED_BRANCH,
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "season": freeze.SEASON,
            "season_type": freeze.SEASON_TYPE,
            "model_versions": freeze.MODEL_VERSIONS,
            "certified_scope": freeze.CERTIFIED_SCOPE,
        },
        "selected_game": game,
        "selected_player": player,
        "fastapi": {
            "endpoint_template": endpoint_template,
            "endpoint": endpoint,
            "http_status": response.status_code,
            "openapi_get_registered": True,
            "requested_lines": requested_lines,
            "line_probabilities": compact_lines,
        },
        "step8c_target": target,
        "simulation": simulation,
        "distribution_summary": distribution_summary,
        "convergence": convergence,
        "result_content_sha256": body.get("result_content_sha256"),
        "safety": {
            "default_enabled": False,
            "production_activation_allowed": False,
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "step8_enabled_for_isolated_ci_only": True,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8_FASTAPI_PROJECTION_PROBABILITY_RELEASE_FROZEN_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
