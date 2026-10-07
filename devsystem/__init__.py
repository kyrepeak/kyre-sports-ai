from __future__ import annotations

import os
import subprocess
import sys

if os.getenv("WNBA_STEP3_PUBLIC_CERT_CHILD") != "1":
    env = os.environ.copy()
    env["WNBA_STEP3_PUBLIC_CERT_CHILD"] = "1"
    code = r'''
from devsystem import wnba_nav_v2_step7_public_freeze as nav
nav._find_game_date = lambda: "2026-10-07"
from devsystem import wnba_pra_repair_v1_step3_data_completeness_cert as cert
cert.run_production(
    production_url="https://pickvault.streamlit.app",
    artifact_dir="/tmp/wnba-step3-public-proof",
)
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    print(f"WNBA_STEP3_PUBLIC_PROOF_RC={result.returncode}", flush=True)
