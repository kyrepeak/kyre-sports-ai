from __future__ import annotations

from . import cfb_step8_route_pointer_lock_postmerge_closeout_r1 as closeout

terminal = closeout.terminal
PRODUCT_MAIN_SHA = closeout.PRODUCT_MAIN_SHA
HANDOFF_CERT_DAY = closeout.HANDOFF_CERT_DAY
VIEWPORTS = {
    "mobile390": {"width": 390, "height": 844},
    "mobile430": {"width": 430, "height": 932},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1440, "height": 1200},
}


class ParallelViewportCertFailure(RuntimeError):
    pass


def _viewport_script() -> str:
    return f'''
import json
import sys
from urllib.parse import urlencode
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

name = sys.argv[1]
viewport = json.loads(sys.argv[2])
cert.SOURCE_MAIN_SHA = "{PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{HANDOFF_CERT_DAY}"
cert.VIEWPORTS = {{name: viewport}}


def _jump_route_for_day(base_url, selected_day):
    query = urlencode({{
        "ks_jump_sport": "CFB",
        "ks_jump_market": "Game Total",
        "ks_cfb_game_total_date": str(selected_day),
    }})
    return base_url.rstrip("/") + "/?" + query


cert._route_for_day = _jump_route_for_day
_original_page1 = cert._page1_result


def _guarded_page1(page, viewport_name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(
        page, viewport_name, artifact_dir, base_url
    )
    frame, _ = cert._find_cfb_frame(
        page,
        required_markers=cert.PAGE1_FRAME_MARKERS,
        required_testids=(cert.PHOENIX_DAY_TESTID, cert.PAGE1_TESTID),
        timeout_seconds=30.0,
    )
    wrapper_event = cert._event_from_url(page.url)
    frame_event = cert._event_from_url(str(getattr(frame, "url", "") or ""))
    if wrapper_event or frame_event:
        raise cert.Step8MobileProductionFailure(
            f"PAGE1_AUTO_EVENT_VISIBLE:{{viewport_name}}:{{wrapper_event}}:{{frame_event}}"
        )
    row["auto_event_visible"] = False
    return row, selected_url, event_id


cert._page1_result = _guarded_page1
payload = cert.run_public(
    base_url="{terminal.PRODUCTION_URL}",
    artifact_dir=f"artifacts/cfb-game-total-step8-r6-{{name}}",
)
print("CFB_STEP8_R6_VIEWPORT=" + json.dumps({{"name": name, "payload": payload}}, sort_keys=True), flush=True)
'''


def _validator_script() -> str:
    return f'''
import json
import sys
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{HANDOFF_CERT_DAY}"
payload = json.load(open(sys.argv[1], "r", encoding="utf-8"))
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("R6_AGGREGATE_TERMINAL_GREEN_REJECTED")
print("R6_AGGREGATE_TERMINAL_GREEN", flush=True)
'''


def _parallel_public_once(client):
    token = client.auth.installation_token()
    with terminal.CandidateWorkspace(
        terminal._repo_url(client), PRODUCT_MAIN_SHA, token=token
    ) as workspace:
        root = terminal.Path(workspace.path)
        viewport_script = root / ".cfb_step8_r6_viewport.py"
        validator_script = root / ".cfb_step8_r6_validate.py"
        aggregate_path = root / ".cfb_step8_r6_aggregate.json"
        viewport_script.write_text(_viewport_script(), encoding="utf-8")
        validator_script.write_text(_validator_script(), encoding="utf-8")

        processes = {}
        for name, viewport in VIEWPORTS.items():
            processes[name] = terminal.subprocess.Popen(
                [
                    terminal.sys.executable,
                    str(viewport_script),
                    name,
                    terminal.json.dumps(viewport, sort_keys=True),
                ],
                cwd=str(root),
                text=True,
                stdout=terminal.subprocess.PIPE,
                stderr=terminal.subprocess.PIPE,
            )

        rows = {}
        payloads = {}
        failures = []
        try:
            for name, process in processes.items():
                try:
                    stdout, stderr = process.communicate(timeout=900)
                except terminal.subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    failures.append({
                        "viewport": name,
                        "error": "TIMEOUT",
                        "detail": ((stdout or "") + "\n" + (stderr or ""))[-12000:],
                    })
                    continue
                combined = (stdout or "") + "\n" + (stderr or "")
                if process.returncode:
                    failures.append({
                        "viewport": name,
                        "error": "PUBLIC_CERT_FAILED",
                        "detail": combined[-16000:],
                    })
                    continue
                prefix = "CFB_STEP8_R6_VIEWPORT="
                lines = [line for line in (stdout or "").splitlines() if line.startswith(prefix)]
                if len(lines) != 1:
                    failures.append({
                        "viewport": name,
                        "error": "VIEWPORT_PAYLOAD_MISSING",
                        "detail": combined[-12000:],
                    })
                    continue
                envelope = terminal.json.loads(lines[0][len(prefix):])
                payload = envelope.get("payload") or {}
                row = (payload.get("viewports") or {}).get(name)
                if not isinstance(row, dict):
                    failures.append({
                        "viewport": name,
                        "error": "VIEWPORT_ROW_MISSING",
                        "detail": str(payload)[-12000:],
                    })
                    continue
                if (row.get("page1") or {}).get("auto_event_visible") is not False:
                    failures.append({
                        "viewport": name,
                        "error": "PAGE1_AUTO_EVENT_NOT_PROVEN",
                        "detail": str(row)[-12000:],
                    })
                    continue
                payloads[name] = payload
                rows[name] = row
        finally:
            for process in processes.values():
                if process.poll() is None:
                    process.kill()
                    process.communicate()

        if failures:
            raise ParallelViewportCertFailure(
                "R6_PARALLEL_PUBLIC_FAILED:" + terminal.json.dumps(failures, sort_keys=True)
            )
        if set(rows) != set(VIEWPORTS):
            raise ParallelViewportCertFailure("R6_VIEWPORT_SET_DRIFT")

        first = payloads["mobile390"]
        for name, payload in payloads.items():
            if (
                payload.get("status") != "GREEN"
                or payload.get("source_main_sha") != PRODUCT_MAIN_SHA
                or payload.get("handoff_cert_day") != HANDOFF_CERT_DAY
                or payload.get("phoenix_timezone") != first.get("phoenix_timezone")
                or payload.get("render_identity") != first.get("render_identity")
                or int(payload.get("github_actions_fallback", -1)) != 0
            ):
                raise ParallelViewportCertFailure("R6_VIEWPORT_IDENTITY_DRIFT:" + name)

        aggregate = dict(first)
        aggregate["viewports"] = rows
        aggregate_path.write_text(
            terminal.json.dumps(aggregate, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        validated = terminal.subprocess.run(
            [terminal.sys.executable, str(validator_script), str(aggregate_path)],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=60,
        )
        if validated.returncode:
            raise ParallelViewportCertFailure(
                "R6_AGGREGATE_VALIDATION_FAILED:"
                + ((validated.stdout or "") + "\n" + (validated.stderr or ""))[-12000:]
            )
        return aggregate


def _parallel_public(client):
    payload = _parallel_public_once(client)
    return {
        "status": "GREEN",
        "attempt": 1,
        "product_main_sha": PRODUCT_MAIN_SHA,
        "handoff_cert_day": HANDOFF_CERT_DAY,
        "required_widths": [390, 430, 768, 1440],
        "evidence": payload,
    }


terminal._public_once = _parallel_public_once
terminal._public = _parallel_public
install_startup = closeout.install_startup
