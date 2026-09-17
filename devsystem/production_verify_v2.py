"""DevSystem production verification V2 — CFB Clean Page V39 activation.

Additive over frozen production_verify_v1. V2 preserves V1's Render API,
identity, observability, safety, and HTTP checks, but delegates the CFB
Over/Under browser proof to the already-certified V39 browser driver. That
single readiness contract waits for the final Steps 11–12 marker before
judging the rendered page, eliminating duplicate timing logic between PR and
production certification.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from devsystem import browser_qa_v1 as certified_browser
    from devsystem import production_verify_v1 as frozen
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v2.py`
    import browser_qa_v1 as certified_browser
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


def _browser_verify_v39(
    streamlit_url: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    result = dict(
        certified_browser.run_browser_qa(
            base_url=streamlit_url,
            artifact_dir=artifact_dir,
        )
    )
    # V1 owns the top-level production status. Keep browser evidence additive.
    result.pop("status", None)
    return result


def run(*, artifact_dir: str = "artifacts/production-verification"):
    original_browser = frozen._browser_verify
    frozen._browser_verify = _browser_verify_v39
    try:
        return frozen.run(artifact_dir=artifact_dir)
    finally:
        frozen._browser_verify = original_browser


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
