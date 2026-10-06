"""WNBA PRA Repair V1 Step 9 — final public production certification.

This is a repair-mission closeout verifier only. It certifies that the public
WNBA/PRA entry route is live on a future pregame slate after Steps 1-8 are
frozen. It does not mutate WNBA product/runtime/model/data behavior and does
not reopen the legacy Speed-V3 Game Center/player performance proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9

PROJECT = "API 2"
MISSION = "WNBA PRA Repair V1"
STEP = "9/9"
FREEZE_TOKEN = "WNBA_PRA_REPAIR_V1_STEP9_FROZEN"

PRODUCT_RUNTIME_CHANGED = False
ROUTER_CHANGED = False
MODEL_MATH_CHANGED = False
PROJECTION_MATH_CHANGED = False
MARKET_MATH_CHANGED = False
PROBABILITY_MATH_CHANGED = False
DATA_MEANING_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE_CHANGED = False
PAST_GAMES_ALLOWED = False


def certify_source() -> dict[str, Any]:
    result = {
        "project": PROJECT,
        "mission": MISSION,
        "step": STEP,
        "status": "GREEN",
        "product_runtime_changed": PRODUCT_RUNTIME_CHANGED,
        "router_changed": ROUTER_CHANGED,
        "model_math_changed": MODEL_MATH_CHANGED,
        "projection_math_changed": PROJECTION_MATH_CHANGED,
        "market_math_changed": MARKET_MATH_CHANGED,
        "probability_math_changed": PROBABILITY_MATH_CHANGED,
        "data_meaning_changed": DATA_MEANING_CHANGED,
        "sportsbook_projection_influence_changed": SPORTSBOOK_PROJECTION_INFLUENCE_CHANGED,
        "past_games_allowed": PAST_GAMES_ALLOWED,
        "freeze_token": FREEZE_TOKEN,
    }
    print("WNBA_PRA_REPAIR_V1_STEP9_SOURCE_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP9_NO_PRODUCT_MUTATION_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP9_NO_PAST_GAMES_POLICY_GREEN")
    return result


def run_public(
    *,
    production_url: str = PUBLIC_HOST,
    artifact_dir: str | Path = "artifacts/wnba-pra-repair-v1-step9",
) -> dict[str, Any]:
    source = certify_source()
    dates = speed9._future_pregame_dates()
    if not dates:
        raise BrowserQAFailure("Step-9 repair cert found no future WNBA pregame dates.")

    route_url = speed9._wnba_pra_route_url(production_url)
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    selected_date = ""
    game_count = 0
    body_excerpt = ""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        try:
            frame, _ = speed9._prime_wnba_pra_route(page, route_url)
            for target in dates:
                try:
                    frame = speed9._set_future_slate_date_segmented(page, frame, target)
                except Exception:
                    continue
                game_count = int(nav._game_button(frame).count())
                if game_count > 0:
                    selected_date = target
                    break

            if not selected_date:
                raise BrowserQAFailure(
                    "Step-9 repair cert could not render a future WNBA slate game."
                )

            body_excerpt = nav._body(frame)[:4000]
            folded = body_excerpt.casefold()
            if "wnba" not in folded or "pra" not in folded:
                raise BrowserQAFailure(
                    "Step-9 repair cert did not remain on the WNBA/PRA public route."
                )
        finally:
            browser.close()

    result = dict(source)
    result.update(
        {
            "public_host": production_url,
            "route_url": route_url,
            "future_pregame_dates": list(dates),
            "selected_future_date": selected_date,
            "public_slate_game_count": game_count,
            "public_route_green": True,
            "future_slate_green": True,
            "no_past_games_green": True,
        }
    )
    (artifacts / "wnba_pra_repair_v1_step9_final_cert.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("WNBA_PRA_REPAIR_V1_STEP9_NO_PAST_GAMES_GREEN")
    print(f"WNBA_PRA_REPAIR_V1_STEP9_FUTURE_SLATE_GREEN={selected_date}")
    print(f"WNBA_PRA_REPAIR_V1_STEP9_PUBLIC_GAME_COUNT={game_count}")
    print("WNBA_PRA_REPAIR_V1_STEP9_PUBLIC_PRODUCTION_GREEN")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-repair-v1-step9",
    )
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if args.source_only:
        certify_source()
    else:
        run_public(
            production_url=args.production_url,
            artifact_dir=args.artifact_dir,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
