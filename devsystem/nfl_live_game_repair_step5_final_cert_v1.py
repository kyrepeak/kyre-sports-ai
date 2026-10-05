"""NFL Rushing + Receiving live-game repair — Step 5/5 final certification.

Proof-only closeout for the frozen Rushing V16 / Receiving V17 runtime.
The certification pins the protected runtime blobs, proves the full
pregame -> LIVE -> final lifecycle, requires one current live event for both
pages, and checks the two production routes at 390/768/1440 with a fresh
Chromium browser for every route/viewport proof.

Production URL ownership belongs to devsystem/production_targets_v1.json.
Step 5 deliberately does not carry a second hard-coded Streamlit hostname so a
retired deployment target cannot create a false product RED.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

MISSION_STEP = "5/5"
MODEL_VERSION = "NFL LIVE GAME REPAIR STEP 5 • FINAL CERT V1"
MAY_MODIFY_PRODUCT_RUNTIME = False
MAY_MODIFY_ROUTER = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SPORTSBOOK = False
API2_USED = False

RUSHING_OWNER = "nfl_rushing_yards_hub_v16.py"
RECEIVING_OWNER = "nfl_receiving_yards_hub_v17.py"
SHARED_GATE = "nfl_prop_app_eligibility_v1.py"
ROUTER_OWNER = "streamlit_memory_lazy_router_v187.py"
PRODUCTION_TARGETS_PATH = Path("devsystem/production_targets_v1.json")
LEGACY_STREAMLIT_HOST = "https://kyre-sports-ai.streamlit.app"

_EXPECTED_RUSHING_BLOB = "2a81e3130882b579a8d1e52bca0ef1f4e94c988c"
_EXPECTED_RECEIVING_BLOB = "d69990d75666db414839470db20f68958c284b9e"
_EXPECTED_SHARED_GATE_BLOB = "01d8b0039e270b03d5f96fa4ac17f542f360a610"
_EXPECTED_ROUTER_BLOB = "449a6a0712ab0f6be70cebe5a3822e59f279e3b6"

RESPONSIVE_VIEWPORTS = ((390, 844), (768, 1024), (1440, 1000))
FRESH_BROWSER_PER_VIEWPORT = True
PUBLIC_ROUTES = (("NFL", "Rushing Yards"), ("NFL", "Receiving Yards"))


def production_base_url() -> str:
    """Return the single canonical Streamlit production target, fail closed."""
    try:
        payload = json.loads(PRODUCTION_TARGETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError("NFL_LIVE_GAME_STEP5_PRODUCTION_TARGET_UNREADABLE") from exc
    streamlit = payload.get("streamlit") if isinstance(payload, dict) else None
    url = str((streamlit or {}).get("url") or "").strip().rstrip("/")
    if not url.startswith("https://") or ".streamlit.app" not in url:
        raise AssertionError("NFL_LIVE_GAME_STEP5_PRODUCTION_TARGET_INVALID")
    if url == LEGACY_STREAMLIT_HOST:
        raise AssertionError("NFL_LIVE_GAME_STEP5_STALE_STREAMLIT_TARGET")
    return url


def _blob(path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"NFL_LIVE_GAME_STEP5_BLOB_UNRESOLVED:{path}")
    return completed.stdout.strip().lower()


def verify_repository_contract() -> dict[str, Any]:
    router = Path(ROUTER_OWNER).read_text(encoding="utf-8")
    target = production_base_url()
    checks = {
        "rushing_frozen_exact": _blob(RUSHING_OWNER) == _EXPECTED_RUSHING_BLOB,
        "receiving_frozen_exact": _blob(RECEIVING_OWNER) == _EXPECTED_RECEIVING_BLOB,
        "shared_gate_frozen_exact": _blob(SHARED_GATE) == _EXPECTED_SHARED_GATE_BLOB,
        "router_frozen_exact": _blob(ROUTER_OWNER) == _EXPECTED_ROUTER_BLOB,
        "router_owners_exact": (
            '"Rushing Yards": "nfl_rushing_yards_hub_v16"' in router
            and '"Receiving Yards": "nfl_receiving_yards_hub_v17"' in router
        ),
        "production_target_canonical": target != LEGACY_STREAMLIT_HOST,
    }
    failed = [name for name, value in checks.items() if value is not True]
    if failed:
        raise AssertionError("NFL_LIVE_GAME_STEP5_REPOSITORY_DRIFT:" + ",".join(failed))
    return {
        "status": "GREEN",
        **checks,
        "production_base_url": target,
        "product_runtime_mutation": False,
        "router_mutation": False,
        "api2_used": False,
    }


def _pregame_snapshot(state: str) -> dict[str, Any]:
    state = state.upper()
    if state not in {"PENDING", "CONFIRMED"}:
        raise ValueError(state)
    return {
        "ready": True,
        "state": state,
        "prop_gate_open": state == "CONFIRMED",
        "reason": "" if state == "CONFIRMED" else "final game-day inactive confirmation is not verified",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }


def _normalize_pregame(result: dict[str, Any], expected_state: str) -> dict[str, Any]:
    players = [
        player
        for team in (result.get("teams") or [])
        if isinstance(team, dict)
        for player in (team.get("players") or [])
        if isinstance(player, dict)
    ]
    assert result.get("ready") is True, result.get("reason")
    assert result.get("data_available") is True, result.get("reason")
    assert result.get("step7_app_identity_verified") is True
    assert result.get("step7_app_identity_state") == expected_state
    assert len(result.get("teams") or []) == 2
    assert len(players) >= 1
    return {
        "status": "GREEN",
        "ready": True,
        "identity_state": expected_state,
        "player_count": len(players),
    }


def certify_synthetic_lifecycle() -> dict[str, Any]:
    from devsystem import nfl_live_game_repair_step3_rushing_live_v1 as rushing_cert
    from devsystem import nfl_live_game_repair_step4_receiving_live_v1 as receiving_cert

    rushing_pending = _normalize_pregame(
        rushing_cert._run_wrapper(_pregame_snapshot("PENDING")), "PENDING"
    )
    rushing_confirmed = _normalize_pregame(
        rushing_cert._run_wrapper(_pregame_snapshot("CONFIRMED")), "CONFIRMED"
    )
    receiving_pending = _normalize_pregame(
        receiving_cert._run_wrapper(_pregame_snapshot("PENDING")), "PENDING"
    )
    receiving_confirmed = _normalize_pregame(
        receiving_cert._run_wrapper(_pregame_snapshot("CONFIRMED")), "CONFIRMED"
    )

    rushing_live = rushing_cert.certify_synthetic_live_rushing()
    receiving_live = receiving_cert.certify_synthetic_live_receiving()
    rushing_final_raw = rushing_cert.certify_synthetic_final_rushing()
    receiving_final_raw = receiving_cert.certify_synthetic_final_receiving()

    rushing_final = {
        **rushing_final_raw,
        "fail_closed": rushing_final_raw.get("ready") is False,
    }
    receiving_final = {
        **receiving_final_raw,
        "fail_closed": receiving_final_raw.get("ready") is False,
    }
    assert rushing_final["fail_closed"] is True
    assert receiving_final["fail_closed"] is True

    return {
        "status": "GREEN",
        "rushing": {
            "pregame_pending": rushing_pending,
            "pregame_confirmed": rushing_confirmed,
            "live": rushing_live,
            "final": rushing_final,
        },
        "receiving": {
            "pregame_pending": receiving_pending,
            "pregame_confirmed": receiving_confirmed,
            "live": receiving_live,
            "final": receiving_final,
        },
    }


def _current_live_page(
    *, event_id: str, market: str, attempts: int = 3
) -> dict[str, Any]:
    if market == "Rushing Yards":
        import nfl_rushing_yards_hub_v16 as page
        loader = page._load_rushing_context_step7
        filtered_key = "step3_live_roster_filtered_count"
    elif market == "Receiving Yards":
        import nfl_receiving_yards_hub_v17 as page
        loader = page._load_receiving_context_step7
        filtered_key = "step4_live_roster_filtered_count"
    else:
        raise ValueError(market)

    result: dict[str, Any] = {}
    for attempt in range(1, max(1, attempts) + 1):
        result = loader(event_id)
        if (
            result.get("ready") is True
            and result.get("data_available") is True
            and result.get("step7_app_identity_state") == "LIVE"
            and result.get("step7_app_live_identity_verified") is True
        ):
            break
        if attempt < attempts:
            time.sleep(5)

    teams = result.get("teams") or []
    players = [
        player
        for team in teams
        if isinstance(team, dict)
        for player in (team.get("players") or [])
        if isinstance(player, dict)
    ]
    assert result.get("ready") is True, f"{market}:{result.get('reason')}"
    assert result.get("data_available") is True, f"{market}:{result.get('reason')}"
    assert result.get("step7_app_identity_verified") is True
    assert result.get("step7_app_identity_state") == "LIVE"
    assert result.get("step7_app_live_identity_verified") is True
    assert result.get("step7_app_final_inactives_verified") is False
    assert result.get("market_enabled") is False
    assert float(result.get("sportsbook_influence") or 0.0) == 0.0
    assert len(teams) == 2
    assert len(players) >= 1
    assert all(player.get("step7_app_identity_verified") is True for player in players)
    return {
        "status": "GREEN",
        "ready": True,
        "event_id": event_id,
        "identity_state": "LIVE",
        "live_identity_verified": True,
        "prop_market_open": False,
        "team_count": len(teams),
        "player_count": len(players),
        "filtered_count": int(result.get(filtered_key) or 0),
        "sportsbook_projection_influence": 0.0,
        "api2_used": False,
    }


def certify_current_live_dual_page() -> dict[str, Any]:
    from devsystem import nfl_live_game_repair_step3_rushing_live_v1 as rushing_cert

    live = rushing_cert.discover_current_live_nfl_event()
    if not live:
        raise AssertionError("NFL_LIVE_GAME_STEP5_NO_ACTIVE_NFL_EVENT")
    event_id = str(live["event_id"])
    rushing = _current_live_page(event_id=event_id, market="Rushing Yards")
    receiving = _current_live_page(event_id=event_id, market="Receiving Yards")
    assert rushing["event_id"] == receiving["event_id"] == event_id
    return {
        "status": "GREEN",
        "event_id": event_id,
        "event": live.get("name"),
        "event_state": "in",
        "same_authoritative_event": True,
        "rushing": rushing,
        "receiving": receiving,
    }


def certify_public_responsive(
    *,
    base_url: str | None = None,
    artifact_dir: str | Path = "artifacts/nfl-live-game-repair-step5-final-cert",
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright
    from devsystem.sitewide_page_load_health_v1 import (
        _fatal_marker,
        _root_overflow,
        _route_url,
        _wait_for_meaningful_route,
    )

    target = (base_url or production_base_url()).strip().rstrip("/")
    if not target.startswith("http://") and not target.startswith("https://"):
        raise AssertionError("NFL_LIVE_GAME_STEP5_BROWSER_TARGET_INVALID")

    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    proofs: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        for sport_code, market in PUBLIC_ROUTES:
            for width, height in RESPONSIVE_VIEWPORTS:
                browser = playwright.chromium.launch(headless=True)
                try:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    page = context.new_page()
                    url = _route_url(target, sport_code, market)
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    text, render_seconds = _wait_for_meaningful_route(
                        page,
                        sport_code=sport_code,
                        sport_label="NFL",
                        market=market,
                        timeout=60.0,
                        require_idle=True,
                    )
                    fatal = _fatal_marker(text)
                    overflow, overflow_detail = _root_overflow(page)
                    assert fatal is None, f"{market}:{width}:fatal:{fatal}"
                    assert overflow is False, f"{market}:{width}:overflow:{overflow_detail}"
                    screenshot = artifacts / f"public-{market.lower().replace(' ', '-')}-{width}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    proofs.append(
                        {
                            "status": "GREEN",
                            "market": market,
                            "width": width,
                            "height": height,
                            "fresh_browser": True,
                            "first_render_seconds": round(render_seconds, 3),
                            "fatal": None,
                            "root_overflow": False,
                            "screenshot": str(screenshot),
                        }
                    )
                    context.close()
                finally:
                    browser.close()

    expected = len(PUBLIC_ROUTES) * len(RESPONSIVE_VIEWPORTS)
    assert len(proofs) == expected
    assert all(row["status"] == "GREEN" for row in proofs)
    return {
        "status": "GREEN",
        "base_url": target,
        "proof_count": len(proofs),
        "proofs": proofs,
    }


def run(
    *,
    require_live: bool = False,
    require_public: bool = False,
    production_url: str | None = None,
    artifact_dir: str | Path = "artifacts/nfl-live-game-repair-step5-final-cert",
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "model_version": MODEL_VERSION,
        "repository": verify_repository_contract(),
        "synthetic_lifecycle": certify_synthetic_lifecycle(),
        "product_runtime_mutation": False,
        "router_mutation": False,
        "api2_used": False,
    }
    if require_live:
        payload["current_live_dual_page"] = certify_current_live_dual_page()
    if require_public:
        payload["public_responsive"] = certify_public_responsive(
            base_url=production_url,
            artifact_dir=artifacts,
        )

    (artifacts / "step5_final_cert.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("NFL_LIVE_GAME_REPAIR_STEP5_FINAL_CERT_GREEN")
    if require_live:
        print("NFL_LIVE_GAME_REPAIR_STEP5_CURRENT_LIVE_DUAL_PAGE_GREEN")
    if require_public:
        print("NFL_LIVE_GAME_REPAIR_STEP5_PUBLIC_RESPONSIVE_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--require-public", action="store_true")
    parser.add_argument("--production-url", default=None)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/nfl-live-game-repair-step5-final-cert",
    )
    args = parser.parse_args()
    run(
        require_live=args.require_live,
        require_public=args.require_public,
        production_url=args.production_url,
        artifact_dir=args.artifact_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
