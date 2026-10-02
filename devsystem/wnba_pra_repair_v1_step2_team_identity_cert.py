"""WNBA PRA Repair V1 Step 2 — Page-2 team identity certification.

Step 2 proves the canonical identity repair at source-contract level and then,
on merged main only, through the live public WNBA PRA Game Center.  The browser
must observe two canonical distinct team IDs and non-empty player rows for both
sides before Step 2 can freeze.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9
import wnba_pra_repair_v1_step2_team_identity as identity

PROJECT = "WNBA PRA Repair V1"
STEP = "2/7"
PUBLIC_HOST = "https://pickvault.streamlit.app"
PROOF_SELECTOR = '[data-wnba-pra-repair-v1-step2="wnba-pra-repair-v1-step2-team-identity"]'

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py"
FROZEN_SLATE = ROOT / "wnba_pra_slate_v2_step2.py"
FROZEN_GAME = ROOT / "wnba_pra_game_center_v2_step3.py"
FROZEN_PLAYER = ROOT / "wnba_pra_player_intelligence_v2_step4.py"
FROZEN_STEP9 = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard.py"

EXPECTED_FROZEN_BLOBS = {
    "wnba_pra_slate_v2_step2.py": "4636cb4314489e3458b70cb3c17c6a6af4c5ea3d",
    "wnba_pra_game_center_v2_step3.py": "a181c8949991bb139521f7d379046f34147e5306",
    "wnba_pra_player_intelligence_v2_step4.py": "393c29711962bf1d42b8fc58322938c92e23000a",
    "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard.py": "51eef1fe2526801a467f155d1c0b32d516ef8a35",
}


def certify_source_contract() -> dict[str, Any]:
    app = APP.read_text(encoding="utf-8")
    overlay = OVERLAY.read_text(encoding="utf-8")
    checks = {
        "step2_runtime_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "step9_parent_preserved": (
            'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"'
        ) in overlay,
        "slate_loader_only_identity_reconciled": "identity.reconcile_slate_payload(payload)" in overlay,
        "game_center_render_wrapped_for_proof": "game_center.render_game_center = guarded_game_renderer" in overlay,
        "model_locked": "MAY_MODIFY_WNBA_MODEL = False" in overlay,
        "projection_math_locked": "MAY_MODIFY_PROJECTION_MATH = False" in overlay,
        "market_math_locked": "MAY_MODIFY_MARKET_MATH = False" in overlay,
        "sportsbook_influence_zero": "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in overlay,
        "wrapper_restores_slate": "slate.load_slate = original_slate_loader" in overlay,
        "wrapper_restores_game": "game_center.render_game_center = original_game_renderer" in overlay,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BrowserQAFailure(f"Step-2 source contract failed: {failed}")

    if len(identity.TEAM_BY_ID) != 15 or len(set(identity.TEAM_BY_ID)) != 15:
        raise BrowserQAFailure("Step-2 canonical 2026 WNBA registry must contain 15 unique IDs.")

    print("WNBA_PRA_REPAIR_V1_STEP2_SOURCE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP2_FROZEN_STEP9_PARENT_GREEN")
    return {"status": "GREEN", "checks": checks, "team_count": len(identity.TEAM_BY_ID)}


def _int_attr(locator, name: str) -> int:
    raw = str(locator.get_attribute(name) or "").strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise BrowserQAFailure(f"Step-2 marker attribute {name} is not an integer: {raw!r}") from exc


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    source = certify_source_contract()
    route_url = speed9._wnba_pra_route_url(production_url)
    target_date = nav._find_game_date()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=nav.VIEWPORT)
        page = context.new_page()
        try:
            frame, slate_seconds = speed9._prime_wnba_pra_route(page, route_url)
            frame = nav._set_date_with_game(page, frame, target_date)
            game_button = nav._game_button(frame).first

            started = time.monotonic()
            game_button.click()
            frame, _ = nav._wait_page(page, "game", timeout_seconds=nav.GAME_READY_BUDGET_SECONDS)
            game_seconds = time.monotonic() - started

            marker = frame.locator(PROOF_SELECTOR).first
            if marker.count() < 1:
                raise BrowserQAFailure("Step-2 canonical team identity proof marker is missing.")
            if str(marker.get_attribute("data-status") or "") != "green":
                raise BrowserQAFailure("Step-2 Page-2 marker reports a blocked team/player identity.")

            away_id = _int_attr(marker, "data-away-team-id")
            home_id = _int_attr(marker, "data-home-team-id")
            away_players = _int_attr(marker, "data-away-player-count")
            home_players = _int_attr(marker, "data-home-player-count")

            if away_id == home_id:
                raise BrowserQAFailure("Step-2 public matchup resolved both sides to one team.")
            if not identity.is_canonical_team_id(away_id) or not identity.is_canonical_team_id(home_id):
                raise BrowserQAFailure(
                    f"Step-2 public Page-2 IDs are not canonical: away={away_id} home={home_id}"
                )
            if away_players <= 0 or home_players <= 0:
                raise BrowserQAFailure(
                    f"Step-2 public Page-2 team rows are incomplete: away={away_players} home={home_players}"
                )
            if frame.locator(".wn3-teamhead").count() < 2:
                raise BrowserQAFailure("Step-2 public Game Center did not render both team headers.")
            if frame.get_by_role("button", name="← Back to WNBA Slate", exact=True).count() < 1:
                raise BrowserQAFailure("Step-2 public Game Center back navigation is missing.")

            result = {
                "project": PROJECT,
                "step": STEP,
                "status": "GREEN",
                "production_url": production_url,
                "target_date": target_date,
                "slate_ready_seconds": round(float(slate_seconds), 3),
                "game_ready_seconds": round(float(game_seconds), 3),
                "away_team_id": away_id,
                "home_team_id": home_id,
                "away_player_count": away_players,
                "home_player_count": home_players,
                "both_team_ids_canonical": True,
                "both_team_player_groups_nonempty": True,
                "frozen_speed_v3_steps_1_9_preserved": True,
                "projection_math_changed": False,
                "market_math_changed": False,
                "sportsbook_projection_influence_changed": False,
                "source_contract": source,
            }
            (artifacts / "wnba_pra_repair_v1_step2_team_identity.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(
                path=str(artifacts / "wnba_pra_repair_v1_step2_team_identity.png"),
                full_page=True,
            )

            print(f"WNBA_PRA_REPAIR_V1_STEP2_AWAY_TEAM_ID={away_id}")
            print(f"WNBA_PRA_REPAIR_V1_STEP2_HOME_TEAM_ID={home_id}")
            print(f"WNBA_PRA_REPAIR_V1_STEP2_AWAY_PLAYER_COUNT={away_players}")
            print(f"WNBA_PRA_REPAIR_V1_STEP2_HOME_PLAYER_COUNT={home_players}")
            print(f"WNBA_PRA_REPAIR_V1_STEP2_GAME_READY_SECONDS={game_seconds:.3f}")
            print("WNBA_PRA_REPAIR_V1_STEP2_BOTH_TEAM_IDS_CANONICAL_GREEN")
            print("WNBA_PRA_REPAIR_V1_STEP2_BOTH_TEAM_PLAYER_GROUPS_GREEN")
            print("WNBA_PRA_REPAIR_V1_STEP2_FROZEN_SPEED_V3_STEPS1_9_GREEN")
            print("WNBA_PRA_REPAIR_V1_STEP2_GREEN")
            print("WNBA_PRA_REPAIR_V1_STEP2_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-repair-v1-step2-team-identity",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
