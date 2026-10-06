from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "proof_shims" / "step9"


def _run(*, enabled: bool) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SHIM)
    env["PORT"] = "0"
    if enabled:
        env["WNBA_STEP9_RENDER_PORT_GUARD"] = "1"
    else:
        env.pop("WNBA_STEP9_RENDER_PORT_GUARD", None)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import argparse; assert argparse.ArgumentParser; "
            "print('WNBA_STEP9_CERT_PROCESS_STARTED', flush=True)",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def test_render_port_guard_opens_before_cert_process() -> None:
    result = _run(enabled=True)
    assert result.returncode == 0, result.stderr
    guard = "WNBA_STEP9_RENDER_PORT_GUARD_LISTENING="
    cert = "WNBA_STEP9_CERT_PROCESS_STARTED"
    assert guard in result.stdout
    assert result.stdout.index(guard) < result.stdout.index(cert)


def test_render_port_guard_is_strictly_opt_in() -> None:
    result = _run(enabled=False)
    assert result.returncode == 0, result.stderr
    assert "WNBA_STEP9_RENDER_PORT_GUARD_LISTENING=" not in result.stdout
    assert "WNBA_STEP9_CERT_PROCESS_STARTED" in result.stdout
