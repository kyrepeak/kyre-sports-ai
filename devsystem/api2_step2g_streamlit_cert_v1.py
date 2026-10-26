"""API2 Step 2G public Streamlit render certificate.

Read-only browser proof. It never mutates product/model/provider state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_TARGETS_PATH = ROOT / "devsystem" / "production_targets_v1.json"
VERSION = "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1"
DEFAULT_MARKERS = (VERSION,)
FORBIDDEN_MARKERS = (
    "Traceback",
    "SyntaxError",
    "ModuleNotFoundError",
    "KeyError",
    "TypeError:",
    "Sign in",
    "Log in",
    "This app is private",
)


class Step2GStreamlitCertificationFailure(RuntimeError):
    pass


def production_base_url() -> str:
    try:
        payload = json.loads(PRODUCTION_TARGETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Step2GStreamlitCertificationFailure("STEP2G_PRODUCTION_TARGET_UNREADABLE") from exc
    streamlit = payload.get("streamlit") if isinstance(payload, dict) else None
    url = str((streamlit or {}).get("url") or "").strip().rstrip("/")
    if not url.startswith("https://") or ".streamlit.app" not in url:
        raise Step2GStreamlitCertificationFailure("STEP2G_PRODUCTION_TARGET_INVALID")
    return url


def evaluate_rendered_body(body: str, *, required_markers: list[str] | tuple[str, ...]) -> dict[str, object]:
    text = str(body or "")
    required = [str(marker) for marker in required_markers if str(marker)]
    if not required:
        raise Step2GStreamlitCertificationFailure("STEP2G_REQUIRED_MARKERS_EMPTY")
    observed = [marker for marker in required if marker in text]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise Step2GStreamlitCertificationFailure(
            "STEP2G_REQUIRED_MARKER_MISSING:" + ",".join(missing)
        )
    forbidden = [marker for marker in FORBIDDEN_MARKERS if marker in text]
    if forbidden:
        raise Step2GStreamlitCertificationFailure(
            "STEP2G_FORBIDDEN_MARKER:" + ",".join(forbidden)
        )
    return {
        "live_render_verified": True,
        "required_markers": required,
        "observed_markers": observed,
        "forbidden_markers_present": [],
        "body_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def certify(*, required_markers: list[str], artifact_dir: str | Path) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    base = production_base_url()
    query = urlencode({"ks_jump_sport": "NFL", "ks_jump_market": "Game Total"})
    target = base + "/?" + query

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            page.goto(target, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)
            bodies: list[str] = []
            for frame in page.frames:
                try:
                    bodies.append(frame.locator("body").inner_text(timeout=5000))
                except Exception:
                    continue
            body = "\n".join(bodies)
            evaluated = evaluate_rendered_body(body, required_markers=required_markers)
            screenshot = artifacts / "api2_step2g_streamlit_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
        finally:
            browser.close()

    result = {
        "version": VERSION,
        "url": base,
        "source_branch": "main",
        **evaluated,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "route": "NFL -> Game Total",
        "screenshot": str(screenshot),
    }
    path = artifacts / "api2_step2g_streamlit_cert.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("API2_STEP2G_STREAMLIT_CERT_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="artifacts/api2-step2g-streamlit")
    parser.add_argument("--required-marker", action="append", default=[])
    return parser.parse_args()


if __name__ == "__main__":
    args = _args()
    markers = args.required_marker or list(DEFAULT_MARKERS)
    certify(required_markers=markers, artifact_dir=args.artifact_dir)
