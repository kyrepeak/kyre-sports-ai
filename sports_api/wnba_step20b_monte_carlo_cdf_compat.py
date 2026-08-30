"""Step20B compatibility for frozen Step8D marginal-CDF tail roundoff.

Frozen Step8D normalizes each nonnegative PMF, builds a cumulative CDF and then
forces only the final entry to exactly ``1.0``. IEEE-754 summation can leave one
or more immediately preceding cumulative entries a few ulps above one (for
example ``1.0000000000000002``). The frozen simulator still consumes those CDFs
with uniforms clipped to ``[0, 1]``.

The Step20B latent-threshold accelerator originally required the raw CDF array to
be globally nondecreasing, so the harmless final ``...1.0000000000000002, 1.0``
roundoff shape was rejected before any draws were made.

This compatibility layer is deliberately narrow. It caps only values above one
that are within 1e-12 of one, verifies the resulting boundaries are monotone,
and verifies the frozen ``np.searchsorted`` mapping is unchanged at every
relevant boundary in the uniform domain. Genuine negative, non-finite,
out-of-tolerance, or in-domain decreasing CDFs still fail closed through the
existing Step8D upstream error.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

import numpy as np

from sports_api import wnba_step8_joint_monte_carlo as step8d
from sports_api import wnba_step20b_monte_carlo_acceleration as accel

SOURCE = "Kyre Sports API WNBA Step20B frozen-CDF tail-roundoff compatibility"
MODEL_VERSION = "wnba_step20b_frozen_cdf_tail_roundoff_compat_v1"
CDF_ROUNDOFF_TOLERANCE = 1e-12

_ORIGINAL_LATENT_THRESHOLD_TABLE: Callable[[np.ndarray], np.ndarray] = accel._latent_threshold_table
_LOCK = threading.RLock()
_INSTALLED = False
_CANONICALIZED_TABLE_COUNT = 0


def _invalid() -> step8d.WNBAStep8MonteCarloUpstreamError:
    return step8d.WNBAStep8MonteCarloUpstreamError(
        "Step20B latent-threshold acceleration received an invalid marginal CDF."
    )


def _canonicalize_frozen_cdf(cdf: np.ndarray) -> tuple[np.ndarray, bool]:
    """Cap only harmless >1 floating roundoff while preserving frozen mapping."""
    raw = np.asarray(cdf, dtype=np.float64)
    if raw.ndim != 1 or raw.size == 0:
        raise _invalid()
    if np.any(~np.isfinite(raw)) or np.any(raw < 0.0):
        raise _invalid()
    if float(raw[-1]) != 1.0:
        raise _invalid()
    if np.any(raw > 1.0 + CDF_ROUNDOFF_TOLERANCE):
        raise _invalid()

    canonical = np.minimum(raw, 1.0)
    if np.any(np.diff(canonical) < 0.0):
        # This still catches every genuine in-domain decrease. The only shape
        # repaired here is cumulative roundoff above 1 followed by frozen 1.0.
        raise _invalid()

    changed = bool(np.any(raw != canonical))
    if changed:
        # searchsorted outcomes can change only at CDF boundaries. Probe each
        # boundary and its adjacent representable floats, plus 0 and 1, to prove
        # the frozen uniform-domain mapping is identical before using thresholds.
        boundaries = canonical[(canonical >= 0.0) & (canonical <= 1.0)]
        probes = [np.asarray([0.0, 1.0, np.nextafter(1.0, 0.0)], dtype=np.float64)]
        if boundaries.size:
            probes.extend(
                [
                    boundaries,
                    np.maximum(np.nextafter(boundaries, -np.inf), 0.0),
                    np.minimum(np.nextafter(boundaries, np.inf), 1.0),
                ]
            )
        uniforms = np.unique(np.concatenate(probes))
        frozen_counts = np.searchsorted(raw, uniforms, side="left")
        canonical_counts = np.searchsorted(canonical, uniforms, side="left")
        if not np.array_equal(frozen_counts, canonical_counts):
            raise _invalid()

    return canonical, changed


def _latent_threshold_table_compatible(cdf: np.ndarray) -> np.ndarray:
    global _CANONICALIZED_TABLE_COUNT
    canonical, changed = _canonicalize_frozen_cdf(cdf)
    thresholds = _ORIGINAL_LATENT_THRESHOLD_TABLE(canonical)
    if changed:
        with _LOCK:
            _CANONICALIZED_TABLE_COUNT += 1
    return thresholds


def install_step20b_monte_carlo_cdf_compat() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        current = accel._latent_threshold_table
        if current is _latent_threshold_table_compatible:
            _INSTALLED = True
        elif current is _ORIGINAL_LATENT_THRESHOLD_TABLE:
            accel._latent_threshold_table = _latent_threshold_table_compatible
            _INSTALLED = True
        else:
            raise RuntimeError(
                "Step20B CDF compatibility refuses an unknown latent-threshold override."
            )
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        installed = bool(_INSTALLED)
        canonicalized = int(_CANONICALIZED_TABLE_COUNT)
    return {
        "data_type": "wnba_step20b_monte_carlo_cdf_compat_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "installed": installed,
        "binding_active": bool(installed and accel._latent_threshold_table is _latent_threshold_table_compatible),
        "canonicalized_table_count": canonicalized,
        "roundoff_tolerance": CDF_ROUNDOFF_TOLERANCE,
        "guardrails": {
            "only_values_above_one_within_roundoff_tolerance_capped": True,
            "negative_cdf_values_accepted": False,
            "nonfinite_cdf_values_accepted": False,
            "genuine_in_domain_decreases_accepted": False,
            "frozen_searchsorted_mapping_verified": True,
            "simulations_modified": False,
            "batch_size_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "sportsbook_transport_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "CDF_ROUNDOFF_TOLERANCE",
    "MODEL_VERSION",
    "SOURCE",
    "install_step20b_monte_carlo_cdf_compat",
    "installation_status",
]
