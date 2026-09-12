"""Public-production Step 4 certification for NFL Passing Yards V26.

Certification-only wrapper over the existing hydration-safe public browser cert.
It adds assertions for the exact Tampa Bay @ Cincinnati Step 4 pressure cards
that were repaired by Pressure V5 / Hub V26. Runtime/model code is untouched.
"""
from __future__ import annotations

import json
import re
from typing import Any

import nfl_passing_yards_public_prod_cert_v1 as base
import nfl_passing_yards_public_prod_cert_v4 as prior


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _card_segment(body: str, player: str, next_marker: str) -> str:
    start = f"{player} • Protection vs Pressure"
    if start not in body:
        raise base.PublicProductionCertFailure(f"public Step 4 card missing for {player}")
    segment = body.split(start, 1)[1]
    if next_marker and next_marker in segment:
        segment = segment.split(next_marker, 1)[0]
    return _norm(segment)


def _require_patterns(segment: str, player: str, patterns: list[str]) -> None:
    for pattern in patterns:
        if re.search(pattern, segment, flags=re.IGNORECASE) is None:
            raise base.PublicProductionCertFailure(
                f"public Step 4 {player} card missing expected pattern {pattern!r}; segment={segment[:2500]!r}"
            )


def _assert_public_step4_pressure(frame) -> dict[str, Any]:
    body = base._body(frame)
    lower = body.casefold()
    if "step 4 pressure green" not in lower:
        raise base.PublicProductionCertFailure("public page did not render STEP 4 PRESSURE GREEN")
    if "step 4 pressure check" in lower:
        raise base.PublicProductionCertFailure("public page still renders STEP 4 PRESSURE CHECK")

    baker = _card_segment(body, "Baker Mayfield", "Joe Burrow • Protection vs Pressure")
    burrow = _card_segment(body, "Joe Burrow", "Step 5 — Weapons + Injuries")

    _require_patterns(
        baker,
        "Baker Mayfield",
        [
            r"MODERATE",
            r"mean sack-rate context 6\.2%.*early-season fallback",
            r"2\.24\s+Sacks Allowed/G",
            r"6\.4%\s+Offense Sack Rate",
            r"38\s+Sacks Allowed",
            r"255\s+Sack Yds Lost",
            r"2\.00\s+Defense Sacks/G",
            r"6\.0%\s+Defense Sack Rate",
            r"34\s+Defense Sacks",
            r"534\s+Opp Pass Attempts",
            r"Recent 3 protection:\s+2\.33\s+sacks allowed/game.*7\.3%\s+sack rate",
            r"Recent 3 rush:\s+3\.33\s+sacks/game.*10\.4%\s+sack rate",
        ],
    )
    _require_patterns(
        burrow,
        "Joe Burrow",
        [
            r"MODERATE",
            r"mean sack-rate context 5\.7%.*early-season fallback",
            r"2\.12\s+Sacks Allowed/G",
            r"5\.3%\s+Offense Sack Rate",
            r"36\s+Sacks Allowed",
            r"239\s+Sack Yds Lost",
            r"2\.18\s+Defense Sacks/G",
            r"6\.1%\s+Defense Sack Rate",
            r"37\s+Defense Sacks",
            r"568\s+Opp Pass Attempts",
            r"Recent 3 protection:\s+2\.33\s+sacks allowed/game.*6\.1%\s+sack rate",
            r"Recent 3 rush:\s+1\.33\s+sacks/game.*4\.7%\s+sack rate",
        ],
    )

    return {
        "step4_status": "GREEN",
        "baker": {
            "sacks_allowed_per_game": 2.24,
            "offense_sack_rate": "6.4%",
            "defense_sacks_per_game": 2.00,
            "defense_sack_rate": "6.0%",
            "opponent_pass_attempts": 534,
            "pressure_label": "MODERATE",
        },
        "burrow": {
            "sacks_allowed_per_game": 2.12,
            "offense_sack_rate": "5.3%",
            "defense_sacks_per_game": 2.18,
            "defense_sack_rate": "6.1%",
            "opponent_pass_attempts": 568,
            "pressure_label": "MODERATE",
        },
    }


def run_public_cert(**kwargs):
    original_market_assert = base._assert_market_triplets
    step4_evidence: dict[str, Any] = {}

    def assert_step4_then_market(frame, api_payload):
        nonlocal step4_evidence
        step4_evidence = _assert_public_step4_pressure(frame)
        return original_market_assert(frame, api_payload)

    base._assert_market_triplets = assert_step4_then_market
    try:
        result = prior.run_public_cert(**kwargs)
    finally:
        base._assert_market_triplets = original_market_assert

    print("NFL_PASSING_YARDS_STEP4_PUBLIC_PRODUCTION_CERT_GREEN")
    print(json.dumps(step4_evidence, indent=2, sort_keys=True))
    if isinstance(result, dict):
        result["step4_pressure"] = step4_evidence
    return result


if __name__ == "__main__":
    args = base._parse_args()
    run_public_cert(
        production_url=args.production_url,
        api_url=args.api_url,
        artifact_dir=args.artifact_dir,
    )
