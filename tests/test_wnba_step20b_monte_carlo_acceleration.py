from __future__ import annotations

import time

import numpy as np
import pytest

from sports_api import wnba_step8_joint_monte_carlo as step8d
from sports_api import wnba_step20b_monte_carlo_acceleration as accel
from sports_api import wnba_step20b_monte_carlo_cdf_compat as cdf_compat


SAFE_ENV = {
    "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    "WNBA_BOARD_SCHEDULER_ENABLED": "false",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
    "WNBA_STEP6J_CANARY_ENABLED": "false",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
    "WNBA_STEP8_CORE_PROJECTION_ENABLED": "true",
    "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED": "true",
    "WNBA_STEP8_MONTE_CARLO_ENABLED": "true",
}


def _fixture() -> tuple[dict, dict]:
    rows = [
        (11, 26, 3),
        (31, 14, 2),
        (20, 10, 8),
        (21, 10, 4),
        (15, 14, 6),
    ]
    games = [
        {
            "game_id": str(index),
            "points": p,
            "rebounds": r,
            "assists": a,
            "points_rebounds_assists": p + r + a,
        }
        for index, (p, r, a) in enumerate(rows, 1)
    ]
    adjusted = {
        "data_type": "context_adjusted_deterministic_player_projection",
        "schema_version": step8d.STEP8C_SCHEMA_VERSION,
        "model_version": step8d.STEP8C_MODEL_VERSION,
        "game_id": "target-game",
        "player_id": 1642291,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "projection_id": "fixture-projection",
        "projection_content_sha256": "a" * 64,
        "projection": {
            "points": 20.446228,
            "rebounds": 15.438988,
            "assists": 4.798605,
            "points_rebounds_assists": 40.683821,
        },
    }
    baseline = {
        "data_type": "official_recent_player_box_stat_baseline",
        "requested_game_id": "target-game",
        "player_id": 1642291,
        "baseline_content_sha256": "b" * 64,
        "selected_game_ids": [str(i) for i in range(1, 6)],
        "games": games,
    }
    return adjusted, baseline


def _mapping_fixture():
    adjusted, baseline = _fixture()
    _game_id, _player_id, target, history = step8d._validate_inputs(adjusted, baseline)
    spec = step8d._build_model_spec(target, history)
    cholesky = np.linalg.cholesky(spec["regularized_latent_correlation"])
    cdfs = [step8d._cdf_table(spec["marginals"][stat]) for stat in step8d._STATS]
    thresholds = [accel._latent_threshold_table(cdf) for cdf in cdfs]
    return cholesky, cdfs, thresholds


def test_latent_threshold_mapping_matches_frozen_mapping_for_large_fixed_sample():
    cholesky, cdfs, thresholds = _mapping_fixture()
    rng = np.random.default_rng(8675309)
    normals = rng.standard_normal((500_000, 3)) @ cholesky.T

    uniforms = step8d._standard_normal_cdf(normals)
    frozen = np.empty((normals.shape[0], 3), dtype=np.int16)
    for index, cdf in enumerate(cdfs):
        frozen[:, index] = np.searchsorted(
            cdf, uniforms[:, index], side="left"
        ).astype(np.int16)

    accelerated = accel._counts_from_latent(normals, thresholds)
    assert np.array_equal(accelerated, frozen)


def test_threshold_tables_are_monotone_and_cover_all_finite_latent_draws():
    _cholesky, cdfs, thresholds = _mapping_fixture()
    for cdf, threshold in zip(cdfs, thresholds):
        assert cdf[-1] == 1.0
        assert np.isposinf(threshold[-1])
        assert np.all(np.diff(threshold) >= 0.0)


def test_accelerated_simulator_has_identical_content_hash_to_frozen_simulator():
    adjusted, baseline = _fixture()
    kwargs = {
        "simulations": 120_000,
        "batch_size": 20_000,
        "seed": 123456,
        "env": SAFE_ENV,
    }
    frozen = accel._ORIGINAL_SIMULATE(adjusted, baseline, **kwargs)
    accelerated = accel.simulate_step8_joint_distribution_accelerated(
        adjusted, baseline, **kwargs
    )

    assert accelerated["result_content_sha256"] == frozen["result_content_sha256"]
    frozen_surface = dict(frozen)
    accelerated_surface = dict(accelerated)
    frozen_surface.pop("generated_at_utc")
    accelerated_surface.pop("generated_at_utc")
    assert accelerated_surface == frozen_surface


def test_accelerated_mapping_is_faster_than_frozen_mapping_on_same_draws():
    cholesky, cdfs, thresholds = _mapping_fixture()
    rng = np.random.default_rng(20260830)
    normals = rng.standard_normal((350_000, 3)) @ cholesky.T

    frozen_best = float("inf")
    accelerated_best = float("inf")
    frozen_counts = None
    accelerated_counts = None
    for _ in range(3):
        started = time.perf_counter()
        uniforms = step8d._standard_normal_cdf(normals)
        candidate = np.empty((normals.shape[0], 3), dtype=np.int16)
        for index, cdf in enumerate(cdfs):
            candidate[:, index] = np.searchsorted(
                cdf, uniforms[:, index], side="left"
            ).astype(np.int16)
        frozen_best = min(frozen_best, time.perf_counter() - started)
        frozen_counts = candidate

        started = time.perf_counter()
        candidate = accel._counts_from_latent(normals, thresholds)
        accelerated_best = min(accelerated_best, time.perf_counter() - started)
        accelerated_counts = candidate

    assert np.array_equal(accelerated_counts, frozen_counts)
    assert accelerated_best < frozen_best


def test_installer_only_rebinds_step8d_simulator(monkeypatch):
    monkeypatch.setattr(step8d, "simulate_step8_joint_distribution", accel._ORIGINAL_SIMULATE)
    monkeypatch.setattr(accel, "_INSTALLED", False)

    status = accel.install_step20b_monte_carlo_acceleration()

    assert step8d.simulate_step8_joint_distribution is accel.simulate_step8_joint_distribution_accelerated
    assert status["installed"] is True
    assert status["binding_active"] is True
    guards = status["guardrails"]
    assert guards["same_pcg64_random_stream"] is True
    assert guards["same_latent_gaussian_draws"] is True
    assert guards["same_marginal_cdf_tables"] is True
    assert guards["same_discrete_count_mapping_required"] is True
    assert guards["simulations_modified"] is False
    assert guards["batch_size_modified"] is False
    assert guards["projection_math_modified"] is False
    assert guards["readiness_relaxed"] is False


def test_frozen_cdf_tail_roundoff_is_capped_without_changing_searchsorted_mapping():
    raw = np.asarray(
        [0.05, 0.40, 0.90, 1.0 + np.finfo(np.float64).eps, 1.0],
        dtype=np.float64,
    )
    canonical, changed = cdf_compat._canonicalize_frozen_cdf(raw)

    assert changed is True
    assert canonical[-2] == 1.0
    assert canonical[-1] == 1.0
    assert np.all(np.diff(canonical) >= 0.0)

    uniforms = np.linspace(0.0, 1.0, 200_001, dtype=np.float64)
    frozen = np.searchsorted(raw, uniforms, side="left")
    repaired = np.searchsorted(canonical, uniforms, side="left")
    assert np.array_equal(repaired, frozen)

    thresholds = cdf_compat._latent_threshold_table_compatible(raw)
    normals = np.linspace(-8.0, 8.0, 250_001, dtype=np.float64)
    frozen_from_normals = np.searchsorted(
        raw, step8d._standard_normal_cdf(normals), side="left"
    )
    accelerated_from_normals = np.searchsorted(thresholds, normals, side="left")
    assert np.array_equal(accelerated_from_normals, frozen_from_normals)


def test_cdf_compat_still_rejects_genuine_in_domain_decrease():
    raw = np.asarray([0.10, 0.80, 0.79, 1.0], dtype=np.float64)
    with pytest.raises(step8d.WNBAStep8MonteCarloUpstreamError):
        cdf_compat._canonicalize_frozen_cdf(raw)


def test_cdf_compat_still_rejects_out_of_tolerance_overshoot():
    raw = np.asarray(
        [0.10, 0.80, 1.0 + 10.0 * cdf_compat.CDF_ROUNDOFF_TOLERANCE, 1.0],
        dtype=np.float64,
    )
    with pytest.raises(step8d.WNBAStep8MonteCarloUpstreamError):
        cdf_compat._canonicalize_frozen_cdf(raw)


def test_cdf_compat_installer_only_rebinds_accelerator_threshold_helper(monkeypatch):
    monkeypatch.setattr(accel, "_latent_threshold_table", cdf_compat._ORIGINAL_LATENT_THRESHOLD_TABLE)
    monkeypatch.setattr(cdf_compat, "_INSTALLED", False)
    simulator_before = step8d.simulate_step8_joint_distribution

    status = cdf_compat.install_step20b_monte_carlo_cdf_compat()

    assert accel._latent_threshold_table is cdf_compat._latent_threshold_table_compatible
    assert step8d.simulate_step8_joint_distribution is simulator_before
    assert status["installed"] is True
    assert status["binding_active"] is True
    guards = status["guardrails"]
    assert guards["only_values_above_one_within_roundoff_tolerance_capped"] is True
    assert guards["genuine_in_domain_decreases_accepted"] is False
    assert guards["frozen_searchsorted_mapping_verified"] is True
    assert guards["simulations_modified"] is False
    assert guards["batch_size_modified"] is False
    assert guards["projection_math_modified"] is False
    assert guards["readiness_relaxed"] is False
