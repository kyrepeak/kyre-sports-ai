from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from . import cfb_game_total_page2_step8_finalizer as finalizer
from .workspace import CandidateWorkspace


def _next_phoenix_saturday() -> str:
    today = datetime.now(ZoneInfo("America/Phoenix")).date()
    delta = (5 - today.weekday()) % 7
    return (today + timedelta(days=delta)).isoformat()


def _run_live_cert_on_next_slate(app) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    slate_date = _next_phoenix_saturday()
    with CandidateWorkspace(repository_url, finalizer.MAIN_SHA, token=token) as workspace:
        artifact_dir = workspace.path / "artifacts" / "cfb-game-total-page2-step8"
        direct_route = finalizer.PRODUCTION_URL.rstrip("/") + "/?" + urlencode(
            (
                ("ks_sport", "College Football"),
                ("ks_cfb_market", "Game Total"),
                ("ks_cfb_game_total_date", slate_date),
            )
        )
        code = (
            "from devsystem import cfb_game_total_page2_step8_live_cert_v1 as cert; "
            f"cert.EXPECTED_MAIN_SHA={finalizer.MAIN_SHA!r}; "
            f"cert.route_handoff=lambda base_url={finalizer.PRODUCTION_URL!r}: {direct_route!r}; "
            f"cert.run(base_url={finalizer.PRODUCTION_URL!r}, artifact_dir={str(artifact_dir)!r})"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace.path,
            text=True,
            capture_output=True,
            timeout=540,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "")[-5000:]
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_FAILED:" + detail)
        evidence_path = artifact_dir / "cfb_game_total_page2_step8_live_cert.json"
        if not evidence_path.exists():
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_EVIDENCE_MISSING")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence.get("status") != "GREEN" or evidence.get("source_main_sha") != finalizer.MAIN_SHA:
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_IDENTITY_MISMATCH")
        evidence["certified_slate_date"] = slate_date
        return evidence


def install_startup(app):
    app.state.cfb_game_total_page2_step8_final = {"status": "NOT_RUN"}

    def _run():
        try:
            install = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                text=True,
                capture_output=True,
                timeout=420,
            )
            if install.returncode != 0:
                detail = (install.stderr or install.stdout or "")[-5000:]
                raise RuntimeError("PAGE2_STEP8_CHROMIUM_INSTALL_FAILED:" + detail)
            finalizer._run_live_cert = _run_live_cert_on_next_slate
            result = finalizer.execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        app.state.cfb_game_total_page2_step8_final = result
        print("CFB_GT_PAGE2_STEP8_FINAL=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start_background_finalizer():
        Thread(target=_run, name="cfb-gt-page2-step8-browser-finalizer", daemon=True).start()

    return app
