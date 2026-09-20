"""Hydration-safe wrapper for the NFL Passing Yards public production cert.

V4 is certification-only. The public Passing Yards route can show its bridge
banner before the slate/date/matchup widgets finish their Streamlit rerun. V4
waits for that hydration to settle before V3 applies its exact-date logic.
Production code and model/market behavior are untouched.
"""
from __future__ import annotations

from datetime import datetime
import json
import time

import nfl_passing_yards_public_prod_cert_v1 as base
import nfl_passing_yards_public_prod_cert_v3 as prior


def _hydration_safe_date(page, frame, day: str) -> None:
    target = datetime.fromisoformat(day).date().isoformat()
    deadline = time.monotonic() + 45.0
    last_body = ""

    while time.monotonic() < deadline:
        if prior._rendered_slate_is_exact(frame, target):
            print(
                "PUBLIC_CERT_DATE_GREEN "
                + json.dumps({"mode": "public-auto-slate-after-hydration", "target": target}, sort_keys=True)
            )
            return
        try:
            last_body = base._body(frame)
        except Exception:
            last_body = ""

        # If the actual date widget has hydrated, V3 can safely perform its exact
        # setter/verification path. Until then, do not fail just because the route
        # is still on the first lightweight render after changing NFL Market.
        if prior._date_input(frame) is not None:
            return prior._set_slate_date_exact(page, frame, day)

        # Verified matchup is rendered only after the slate loader completed. If
        # it appears before the compact ET SLATE text is readable, give the page a
        # short final paint window instead of immediately declaring a DOM failure.
        try:
            if frame.get_by_role("combobox", name="Verified matchup", exact=True).count() > 0:
                page.wait_for_timeout(800)
                if prior._rendered_slate_is_exact(frame, target):
                    print(
                        "PUBLIC_CERT_DATE_GREEN "
                        + json.dumps({"mode": "verified-matchup-hydrated", "target": target}, sort_keys=True)
                    )
                    return
        except Exception:
            pass
        page.wait_for_timeout(500)

    raise base.PublicProductionCertFailure(
        "public Passing Yards route did not hydrate exact ESPN slate within 45s; "
        + json.dumps({"target": target, "body_start": last_body[:2000]}, sort_keys=True)
    )


def _assert_reference_why_visual(frame) -> dict[str, int]:
    panel = frame.locator('section[data-reference-why-projection="true"]')
    if panel.count() != 1:
        raise base.PublicProductionCertFailure(
            f"reference Why This Projection panel count expected 1, saw {panel.count()}"
        )
    root = panel.first
    if not root.is_visible():
        raise base.PublicProductionCertFailure("reference Why This Projection panel is not visible")

    cards = root.locator("section.kpy16-whycard")
    reasons = root.locator(".kpy16-reason")
    logos = root.locator("img.kpy16-teamlogo")
    proj_icons = root.locator(".kpy16-projicon")
    grades = root.locator(".kpy16-grade")
    foot = root.locator(".kpy16-foot")
    brain = root.locator(".kpy16-brain")

    counts = {
        "cards": cards.count(),
        "reasons": reasons.count(),
        "logos": logos.count(),
        "projection_icons": proj_icons.count(),
        "grades": grades.count(),
        "foot": foot.count(),
        "brain": brain.count(),
    }
    expected = {
        "cards": 2,
        "reasons": 12,
        "logos": 2,
        "projection_icons": 2,
        "grades": 2,
        "foot": 1,
        "brain": 1,
    }
    if counts != expected:
        raise base.PublicProductionCertFailure(
            "reference Why This Projection visual structure mismatch; "
            + json.dumps({"expected": expected, "observed": counts}, sort_keys=True)
        )

    visible = root.inner_text(timeout=10000)
    for token in (
        "Why This Projection",
        "RESULT → REASONS",
        "Volume",
        "Efficiency",
        "Pressure Adj",
        "Personnel",
        "Weather",
        "Recent SD",
        "Projection:",
        "CONFIDENCE",
    ):
        if token.casefold() not in visible.casefold():
            raise base.PublicProductionCertFailure(
                f"reference Why This Projection panel missing visible token {token!r}"
            )

    duplicate_counts = {
        "v36_dashboard": frame.locator("section.kpass36-dashboard").count(),
        "v36_five_step_marker": frame.locator('[data-five-step-visual-complete="true"]').count(),
        "v36_qb_identity": frame.locator('[data-qb-identity-card="true"]').count(),
        "v36_why_intro": frame.locator(".kpass36-whyintro").count(),
    }
    if any(duplicate_counts.values()):
        raise base.PublicProductionCertFailure(
            "duplicate V36 dashboard still visible; "
            + json.dumps(duplicate_counts, sort_keys=True)
        )

    print(
        "NFL_PASSING_WHY_REFERENCE_PRODUCTION_VISUAL_GREEN "
        + json.dumps(counts, sort_keys=True)
    )
    return counts


def run_public_cert(**kwargs):
    original_date = prior._set_slate_date_exact
    original_market_triplets = base._assert_market_triplets

    def assert_market_and_reference_visual(frame, api_payload):
        observed = original_market_triplets(frame, api_payload)
        _assert_reference_why_visual(frame)
        return observed

    prior._set_slate_date_exact = _hydration_safe_date
    base._assert_market_triplets = assert_market_and_reference_visual
    try:
        return prior.run_public_cert(**kwargs)
    finally:
        base._assert_market_triplets = original_market_triplets
        prior._set_slate_date_exact = original_date


if __name__ == "__main__":
    args = base._parse_args()
    run_public_cert(
        production_url=args.production_url,
        api_url=args.api_url,
        artifact_dir=args.artifact_dir,
    )
