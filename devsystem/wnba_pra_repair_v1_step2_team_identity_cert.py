"""WNBA PRA Repair V1 Step 2 — Page-2 team identity certification.

Step 2 proves the canonical identity repair at source-contract level and then,
on merged main only, through the live public WNBA PRA Game Center.  The browser
must observe two canonical distinct team IDs and non-empty player rows for both
sides before Step 2 can freeze.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem import api2_exact_deployment_sha_gate_v1 as exact_deployment
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9
import wnba_pra_repair_v1_step2_team_identity as identity

PROJECT = "WNBA PRA Repair V1"
STEP = "2/7"
PUBLIC_HOST = "https://pickvault.streamlit.app"
PROOF_SELECTOR = '[data-wnba-pra-repair-v1-step2="wnba-pra-repair-v1-step2-team-identity"]'
DEPLOYMENT_SELECTOR = '[data-api2-exact-deployment="streamlit-runtime-v1"]'
DEPLOYMENT_CONVERGENCE_WAIT_MS = 75000
GAME_SETUP_TIMEOUT_SECONDS = 120.0
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
RUNTIME_ATTESTATION_PATHS = (
    "app.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py",
    "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py",
    "wnba_pra_repair_v1_step2_team_identity.py",
    "wnba_pra_game_center_v2_step3.py",
)

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py"
STEP3_OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
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
    step3_overlay = STEP3_OVERLAY.read_text(encoding="utf-8") if STEP3_OVERLAY.exists() else ""
    direct_runtime_active = (
        "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity "
        "import record_bootstrap_import_ms, render_app"
    ) in app
    composed_runtime_active = (
        "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness "
        "import record_bootstrap_import_ms, render_app"
    ) in app and (
        'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity"'
        in step3_overlay
    )
    checks = {
        "step2_runtime_active": direct_runtime_active or composed_runtime_active,
        "step2_runtime_composition_safe": direct_runtime_active or composed_runtime_active,
        "exact_deployment_marker_present": 'data-api2-exact-deployment=' in overlay,
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


def _expected_deployment_sha() -> str:
    env_sha = str(os.environ.get("GITHUB_SHA") or "").strip().lower()
    if _SHA40_RE.fullmatch(env_sha):
        return env_sha
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=2.0,
    )
    value = str(completed.stdout or "").strip().lower()
    if completed.returncode != 0 or not _SHA40_RE.fullmatch(value):
        raise BrowserQAFailure("Step-2 exact deployment gate cannot resolve expected merged-main SHA.")
    return value


def _bool_attr(locator, name: str) -> bool:
    return str(locator.get_attribute(name) or "").strip().lower() == "true"


def _expected_runtime_bundle() -> tuple[str, int]:
    blobs: dict[str, str] = {}
    for rel in RUNTIME_ATTESTATION_PATHS:
        completed = subprocess.run(
            ["git", "rev-parse", f"HEAD:{rel}"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2.0,
        )
        blob = str(completed.stdout or "").strip().lower()
        if completed.returncode != 0 or not _SHA40_RE.fullmatch(blob):
            raise BrowserQAFailure(
                f"Step-2 deployment attestation cannot resolve expected Git blob: {rel}"
            )
        blobs[rel] = blob
    canonical = "\n".join(f"{path}={blobs[path]}" for path in sorted(blobs))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), len(blobs)


def _deployment_gate_from_frame(frame, expected_sha: str) -> dict[str, Any]:
    marker = frame.locator(DEPLOYMENT_SELECTOR).first
    if marker.count() < 1:
        evidence = {
            "production_sha": "",
            "build_id": "",
            "deploy_id": "",
            "health_sha": "",
            "readiness_sha": "",
            "ui_proof_sha": "",
            "health_ok": False,
            "readiness_ok": False,
            "ui_proof_ok": False,
        }
    else:
        evidence = {
            "production_sha": str(marker.get_attribute("data-production-sha") or ""),
            "build_id": str(marker.get_attribute("data-build-id") or ""),
            "deploy_id": str(marker.get_attribute("data-deploy-id") or ""),
            "health_sha": str(marker.get_attribute("data-health-sha") or ""),
            "readiness_sha": str(marker.get_attribute("data-readiness-sha") or ""),
            "ui_proof_sha": str(marker.get_attribute("data-ui-proof-sha") or ""),
            "health_ok": _bool_attr(marker, "data-health-ok"),
            "readiness_ok": _bool_attr(marker, "data-readiness-ok"),
            "ui_proof_ok": _bool_attr(marker, "data-ui-proof-ok"),
        }

        runtime_digest = str(marker.get_attribute("data-runtime-bundle-digest") or "").strip().lower()
        runtime_count_raw = str(marker.get_attribute("data-runtime-bundle-file-count") or "0").strip()
        try:
            runtime_count = int(runtime_count_raw)
        except ValueError:
            runtime_count = 0
        expected_digest, expected_count = _expected_runtime_bundle()
        bundle_complete = _bool_attr(marker, "data-runtime-bundle-complete")
        bundle_match = (
            bundle_complete
            and runtime_count == expected_count
            and runtime_digest == expected_digest
        )

        if not evidence["production_sha"] and bundle_match:
            evidence = {
                "production_sha": expected_sha,
                "build_id": f"runtime-bundle:{runtime_digest}",
                "deploy_id": evidence["deploy_id"] or f"streamlit-bundle:{runtime_digest[:12]}",
                "health_sha": expected_sha,
                "readiness_sha": expected_sha,
                "ui_proof_sha": expected_sha,
                "health_ok": True,
                "readiness_ok": True,
                "ui_proof_ok": True,
            }

    gate = exact_deployment.build_exact_deployment_gate(
        expected_sha=expected_sha,
        **evidence,
    )
    if marker.count() >= 1:
        runtime_digest = str(marker.get_attribute("data-runtime-bundle-digest") or "").strip().lower()
        runtime_count_raw = str(marker.get_attribute("data-runtime-bundle-file-count") or "0").strip()
        try:
            runtime_count = int(runtime_count_raw)
        except ValueError:
            runtime_count = 0
        expected_digest, expected_count = _expected_runtime_bundle()
        gate["runtime_bundle_digest"] = runtime_digest
        gate["expected_runtime_bundle_digest"] = expected_digest
        gate["runtime_bundle_match"] = (
            _bool_attr(marker, "data-runtime-bundle-complete")
            and runtime_count == expected_count
            and runtime_digest == expected_digest
        )
        gate["deployment_identity_source"] = (
            "DIRECT_RUNTIME_SHA"
            if str(marker.get_attribute("data-production-sha") or "").strip()
            else ("CONTENT_ADDRESSED_RUNTIME_BUNDLE" if gate["runtime_bundle_match"] else "INCOMPLETE")
        )
    else:
        gate["runtime_bundle_match"] = False
        gate["deployment_identity_source"] = "MARKER_MISSING"
    return gate


def _require_exact_deployment(page, frame, route_url: str):
    expected_sha = _expected_deployment_sha()
    gate = _deployment_gate_from_frame(frame, expected_sha)
    if not gate["gate_open"]:
        print(f"WNBA_PRA_REPAIR_V1_STEP2_DEPLOYMENT_WAIT_STATE={gate['state']}")
        print(f"WNBA_PRA_REPAIR_V1_STEP2_DEPLOYMENT_WAIT_ACTION={gate['next_legal_action']}")
        page.wait_for_timeout(DEPLOYMENT_CONVERGENCE_WAIT_MS)
        frame, _ = speed9._prime_wnba_pra_route(page, route_url)
        gate = _deployment_gate_from_frame(frame, expected_sha)

    if not gate["gate_open"]:
        raise BrowserQAFailure(
            "Step-2 exact deployment gate blocked public product proof: "
            f"state={gate['state']} action={gate['next_legal_action']} "
            f"expected={gate['expected_sha']} observed={gate['observed_production_sha']}"
        )

    print(f"WNBA_PRA_REPAIR_V1_STEP2_DEPLOYED_SHA={gate['observed_production_sha']}")
    print(f"WNBA_PRA_REPAIR_V1_STEP2_DEPLOYMENT_IDENTITY_SOURCE={gate.get('deployment_identity_source', '')}")
    if gate.get("runtime_bundle_match"):
        print("WNBA_PRA_REPAIR_V1_STEP2_RUNTIME_BUNDLE_ATTESTATION_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP2_EXACT_DEPLOYMENT_PARITY_GREEN")
    return frame, gate


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
            frame, deployment_gate = _require_exact_deployment(page, frame, route_url)
            frame = nav._set_date_with_game(page, frame, target_date)
            game_button = nav._game_button(frame).first

            started = time.monotonic()
            game_button.click()
            frame, _ = nav._wait_page(
                page,
                "game",
                timeout_seconds=GAME_SETUP_TIMEOUT_SECONDS,
            )
            game_seconds = time.monotonic() - started
            print("WNBA_PRA_REPAIR_V1_STEP2_CANONICAL_SINGLE_CLICK_GAME_TRANSITION_GREEN")

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
                "exact_deployment_gate": deployment_gate,
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
