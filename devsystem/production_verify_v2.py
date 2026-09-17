"""DevSystem production verification V2 — CFB Clean Page V39 activation.

Additive over frozen production_verify_v1. V2 preserves V1's Render API,
identity, observability, safety, HTTP checks, and production-specific browser
selector flow. It changes only the CFB Over/Under marker readiness contract so
V1 waits for the last-rendered Steps 11–12 marker before judging the full V39
page, preventing early snapshots of a partially rendered Streamlit rerun.
"""
from __future__ import annotations

import argparse

try:
    from devsystem import production_verify_v1 as frozen
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v2.py`
    import production_verify_v1 as frozen

FROZEN_VERIFIER = "devsystem.production_verify_v1"
CFB_REQUIRED_MARKERS = (
    "Steps 11–12 • current form + certification",
    "CFB O/U • CLEAN PAGE V39 ACTIVE",
    "COMPACT EVIDENCE RENDERER",
    "VERIFIED IDENTITY ≠ MISSING STEP METRIC",
    "0.0% SPORTSBOOK PROJECTION INFLUENCE",
    "Matchup Foundation",
    "Steps 1–4 • compact verified evidence",
    "Frozen O/U math • Mutation OFF • Sportsbook 0.0%",
    "Step 5 • Explosive Plays",
    "Step 10 • Historical Matchup",
)


def run(*, artifact_dir: str = "artifacts/production-verification"):
    original_markers = frozen.CFB_REQUIRED_MARKERS
    frozen.CFB_REQUIRED_MARKERS = CFB_REQUIRED_MARKERS
    try:
        return frozen.run(artifact_dir=artifact_dir)
    finally:
        frozen.CFB_REQUIRED_MARKERS = original_markers


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-verification",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(artifact_dir=args.artifact_dir)
