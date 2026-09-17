"""DevSystem production verification V2 — CFB Clean Page V39 activation.

Additive over frozen production_verify_v1. V2 replaces only the CFB Over/Under
browser presentation markers with the certified Clean Page V39 marker contract.
Every Render API, identity, observability, safety, and Streamlit verification
flow remains owned and executed by V1 unchanged.
"""
from __future__ import annotations

import argparse

try:
    from devsystem import production_verify_v1 as frozen
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v2.py`
    import production_verify_v1 as frozen

FROZEN_VERIFIER = "devsystem.production_verify_v1"
CFB_REQUIRED_MARKERS = (
    "CFB O/U • CLEAN PAGE V39 ACTIVE",
    "COMPACT EVIDENCE RENDERER",
    "VERIFIED IDENTITY ≠ MISSING STEP METRIC",
    "0.0% SPORTSBOOK PROJECTION INFLUENCE",
    "Matchup Foundation",
    "Steps 1–4 • compact verified evidence",
    "Frozen O/U math • Mutation OFF • Sportsbook 0.0%",
    "Step 5 • Explosive Plays",
    "Step 10 • Historical Matchup",
    "Steps 11–12 • current form + certification",
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
