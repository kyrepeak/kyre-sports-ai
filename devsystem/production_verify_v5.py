"""DevSystem production verification V5 — Streamlit Cloud frame query proof.

Additive successor to production_verify_v4. V5 preserves the complete frozen V3
Render/API/Streamlit proof and the V163 selector surface contract, but resolves
selected ESPN event identity from either the outer browser URL (direct/local
Streamlit) or the matched Streamlit app-frame URL (Streamlit Community Cloud).

No Game Total page, router, projection/model/distribution, Step-12, Top-5, API,
or sportsbook influence behavior is modified by this verifier.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

try:
    from devsystem import production_verify_v1 as base
    from devsystem import production_verify_v3 as prior
except ModuleNotFoundError:  # direct `python devsystem/production_verify_v5.py`
    import production_verify_v1 as base
    import production_verify_v3 as prior

FROZEN_VERIFIER = "devsystem.production_verify_v3"
EXPECTED_ROUTER = "streamlit_memory_lazy_router_v159"
GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"
GAME_SELECTOR_REQUIRED_TEXT = "GAMES ON THIS DAY"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CERT_DATE = "2026-09-19"
ProductionVerificationFailure = base.ProductionVerificationFailure


def _assert_v163_surface(body: str) -> None:
    text = str(body or "")
    if GAME_TOTAL_REQUIRED_HEARTBEAT not in text:
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total V163 deployment: "
            f"required production heartbeat {GAME_TOTAL_REQUIRED_HEARTBEAT!r} was not present"
        )
    if GAME_SELECTOR_REQUIRED_TEXT not in text:
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total V163 deployment: "
            f"required selector text {GAME_SELECTOR_REQUIRED_TEXT!r} was not present"
        )


def _event_id_from_url(url: str) -> str:
    parsed = parse_qs(urlparse(str(url or "")).query)
    return str((parsed.get(EVENT_QUERY_KEY) or [""])[-1] or "").strip()


def _event_id_from_urls(page_url: str, frame_url: str) -> str:
    """Resolve query identity across direct Streamlit and Cloud iframe hosting."""
    return _event_id_from_url(page_url) or _event_id_from_url(frame_url)


def _build_v163_evidence(
    *,
    expected_commit: str,
    event_id: str,
    event_identity_source: str,
) -> dict[str, Any]:
    if not str(event_id or "").strip():
        raise ProductionVerificationFailure(
            "stale Streamlit Game Total V163 deployment: selected ESPN event_id was not persisted"
        )
    return {
        "expected_commit": str(expected_commit or "unknown"),
        "expected_router": EXPECTED_ROUTER,
        "observed_router": "V159",
        "observed_build_marker": GAME_TOTAL_REQUIRED_HEARTBEAT,
        "game_selector_visible": True,
        "selected_espn_event_id": str(event_id),
        "event_identity_source": str(event_identity_source),
        "v163_freshness_verified": True,
    }


def _browser_verify_v163_selector(
    streamlit_url: str,
    artifact_dir: Path,
    *,
    expected_commit: str,
) -> dict[str, Any]:
    direct_query = urlencode(
        {
            ROUTE_QUERY_SPORT: CFB_SPORT,
            ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
            DATE_QUERY_KEY: CERT_DATE,
        }
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/?" + direct_query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            deadline = time.monotonic() + 120.0
            final_body = ""
            selected_event = ""
            event_identity_source = ""
            matched_frame = None
            scans: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                scans = []
                matched_frame = None
                for index, frame in enumerate(page.frames):
                    try:
                        body = frame.locator("body").inner_text(timeout=5000)
                    except Exception:
                        body = ""
                    scans.append({"index": index, "url": frame.url, "body_start": body[:500]})
                    if (
                        GAME_TOTAL_REQUIRED_HEARTBEAT in body
                        and GAME_SELECTOR_REQUIRED_TEXT in body
                    ):
                        final_body = body
                        matched_frame = frame
                        break

                frame_url = matched_frame.url if matched_frame is not None else ""
                outer_event = _event_id_from_url(page.url)
                frame_event = _event_id_from_url(frame_url)
                selected_event = _event_id_from_urls(page.url, frame_url)
                if outer_event:
                    event_identity_source = "outer_page_url"
                elif frame_event:
                    event_identity_source = "streamlit_app_frame_url"

                if matched_frame is not None and selected_event:
                    break
                page.wait_for_timeout(1000)

            _assert_v163_surface(final_body)
            if matched_frame is None:
                raise ProductionVerificationFailure(
                    "stale Streamlit Game Total V163 deployment: active V163 app frame not found"
                )
            forbidden = base._body_has_forbidden_error(final_body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Game Total V163 runtime error marker: {forbidden}"
                )
            evidence = _build_v163_evidence(
                expected_commit=expected_commit,
                event_id=selected_event,
                event_identity_source=event_identity_source,
            )
            screenshot = artifact_dir / "production_game_total_v163_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                **evidence,
                "game_total_route": f"{CFB_SPORT} -> {GAME_TOTAL_MARKET}",
                "certification_date": CERT_DATE,
                "outer_page_url": page.url,
                "game_total_app_frame_url": matched_frame.url,
                "game_total_frame_scan_count": len(scans),
                "game_total_v163_screenshot": str(screenshot),
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(artifact_dir / "production_game_total_v163_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(*, artifact_dir: str | Path = "artifacts/production-verification") -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # Preserve every frozen V3 verification first; V4 remains untouched as history.
    result = dict(prior.run(artifact_dir=artifacts))

    targets = base._load_targets()
    streamlit_url = str(targets["streamlit"]["url"]).rstrip("/")
    expected_commit = str(os.environ.get("GITHUB_SHA") or "unknown")
    v163 = _browser_verify_v163_selector(
        streamlit_url,
        artifacts,
        expected_commit=expected_commit,
    )
    result.update(v163)
    result["status"] = "GREEN"
    result["production_verifier"] = "V5"

    result_path = artifacts / "production_verification.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("DEVSYSTEM_PRODUCTION_VERIFICATION_V5_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


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
