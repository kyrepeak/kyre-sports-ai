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


def run_public_cert(**kwargs):
    original = prior._set_slate_date_exact
    prior._set_slate_date_exact = _hydration_safe_date
    try:
        return prior.run_public_cert(**kwargs)
    finally:
        prior._set_slate_date_exact = original


if __name__ == "__main__":
    args = base._parse_args()
    run_public_cert(
        production_url=args.production_url,
        api_url=args.api_url,
        artifact_dir=args.artifact_dir,
    )
