"""Deterministic opt-in import shim for the WNBA Step-9 Render proof harness.

Only active when this directory is explicitly prepended to PYTHONPATH.
It opens Render's HTTP port before delegating to the real stdlib argparse.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import os
import sysconfig
import threading


_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        body = b"wnba-step9-proof\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _start_guard() -> None:
    global _SERVER, _THREAD

    if os.environ.get("WNBA_STEP9_RENDER_PORT_GUARD") != "1":
        return

    raw_port = os.environ.get("PORT", "").strip()
    if not raw_port:
        return

    try:
        port = int(raw_port)
    except ValueError:
        print("WNBA_STEP9_RENDER_PORT_GUARD_INVALID_PORT", flush=True)
        return

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    except OSError as exc:
        print(
            "WNBA_STEP9_RENDER_PORT_GUARD_BIND_FAILED=" + type(exc).__name__,
            flush=True,
        )
        return

    thread = threading.Thread(
        target=server.serve_forever,
        name="wnba-step9-render-port-guard",
        daemon=True,
    )
    thread.start()
    _SERVER = server
    _THREAD = thread
    print(
        "WNBA_STEP9_RENDER_PORT_GUARD_LISTENING="
        + str(server.server_address[1]),
        flush=True,
    )


_start_guard()

_stdlib_argparse = os.path.join(sysconfig.get_path("stdlib"), "argparse.py")
_spec = importlib.util.spec_from_file_location(
    "_wnba_step9_stdlib_argparse",
    _stdlib_argparse,
)
if _spec is None or _spec.loader is None:
    raise ImportError("WNBA_STEP9_ARGPARSE_DELEGATE_UNAVAILABLE")
_real = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real)

for _name, _value in vars(_real).items():
    if _name not in {"__name__", "__loader__", "__package__", "__spec__", "__file__"}:
        globals()[_name] = _value
