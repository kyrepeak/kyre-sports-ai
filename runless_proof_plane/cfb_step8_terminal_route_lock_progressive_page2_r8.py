from __future__ import annotations

from . import cfb_step8_terminal_route_lock_oom_recovery_r7 as r7

fast = r7.fast
terminal = r7.terminal
_original_script = fast._fast_cert_script

_PROGRESSIVE_PAGE2_PATCH = r'''


def _progressive_page2(page, name, selected_url, event_id, artifact_dir):
    page.goto(selected_url, wait_until="domcontentloaded", timeout=120000)
    frame, scans = cert._find_cfb_frame(
        page,
        required_testids=("gtp2s8-final",),
        timeout_seconds=25.0,
    )
    for testid in cert.PAGE2_REQUIRED_TESTIDS:
        _original_visible(frame, testid, timeout_ms=45000)

    body = frame.locator("body").inner_text(timeout=30000)
    forbidden = cert._forbidden(body, cert.PAGE2_FORBIDDEN_VISIBLE_TEXT)
    runtime_error = cert._runtime_error(body)
    overflow = cert._horizontal_overflow(frame)
    wrapper_event = cert._event_from_url(page.url)
    frame_event = cert._event_from_url(str(getattr(frame, "url", "") or ""))
    observed_events = {value for value in (wrapper_event, frame_event) if value}

    if observed_events != {event_id}:
        raise cert.Step8MobileProductionFailure(
            f"PAGE2_EVENT_ID_DRIFT:{name}:expected={event_id}:"
            f"observed={sorted(observed_events)}"
        )
    if forbidden:
        raise cert.Step8MobileProductionFailure(
            f"PAGE2_FORBIDDEN_COPY:{name}:{forbidden}"
        )
    if runtime_error:
        raise cert.Step8MobileProductionFailure(
            f"PAGE2_RUNTIME_ERROR:{name}:{runtime_error}"
        )
    if overflow:
        raise cert.Step8MobileProductionFailure(
            f"PAGE2_HORIZONTAL_OVERFLOW:{name}"
        )

    return {
        "all_required_visible": True,
        "required_testids_visible": list(cert.PAGE2_REQUIRED_TESTIDS),
        "exact_event_id": event_id,
        "wrapper_event_id": wrapper_event,
        "frame_event_id": frame_event,
        "observed_event_ids": sorted(observed_events),
        "horizontal_overflow": False,
        "forbidden_visible_text": [],
        "runtime_error": "",
        "frame_scan": scans,
        "screenshot": "",
    }


cert._page2_result = _progressive_page2
'''


def _progressive_cert_script():
    script = _original_script()
    marker = "payload = cert.run_public("
    if script.count(marker) != 1:
        raise terminal.TerminalFreezeFailure("R8_CERT_SCRIPT_MARKER_DRIFT")
    return script.replace(marker, _PROGRESSIVE_PAGE2_PATCH + "\n" + marker, 1)


fast._fast_cert_script = _progressive_cert_script
fast.r5._jump_route_cert_script = _progressive_cert_script
terminal._cert_script = _progressive_cert_script
install_startup = r7.install_startup
