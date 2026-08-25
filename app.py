"""Kyre Sports AI — WNBA Live Games Step-6.3 replay-fidelity routing wrapper.

Preserves the frozen Step-1 application checkpoint exactly and changes only the
isolated WNBA Live Games implementation target:

    Live Games -> wnba_live_hub_v63

The verified production Steps 1-6, Step-6.1 replay harness, and Step-6.2 rejected
calibration audit remain intact. V6.3 appends a checkpoint-only ESPN play-by-play
fidelity audit so historical replay can better match the partial data available
to a real live Step-6 state before any further calibration is attempted.

All pre-existing WNBA, MLB and NFL routes remain owned by the preserved app.
"""
from __future__ import annotations

import subprocess
import urllib.request


FROZEN_LIVE_STEP1_COMMIT = "e091e92c7a1f03ba07c403506ef347c75f69d7de"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{FROZEN_LIVE_STEP1_COMMIT}/app.py"
)


def _load_step1_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{FROZEN_LIVE_STEP1_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_step1_app()
anchor = "    import wnba_live_hub_v1 as wnba_live_v1"
replacement = "    import wnba_live_hub_v63 as wnba_live_v1"
if anchor not in source:
    raise RuntimeError("Frozen WNBA Live Step-1 route import not found.")
source = source.replace(anchor, replacement, 1)

compile(source, "<kyre_wnba_live_step63_replay_fidelity_preflight>", "exec")
exec(
    compile(source, "kyre_wnba_live_games_v63_replay_fidelity.py", "exec"),
    globals(),
    globals(),
)
