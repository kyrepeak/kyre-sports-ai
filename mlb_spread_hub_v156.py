"""MLB Spread / Run Line V15.6.1 — Step-1 logo transport repair.

This module preserves the exact V15.6 Step-1 presentation from commit
8f44cf7da6e678be1371452f7db2de985c27c656 and changes only how MLB team logos
are supplied to that renderer.

Why this exists
---------------
V15.6 correctly carried selected/opponent MLB team IDs into the Top-5 cards, but
its renderer delegated logo HTML to the old frozen app ``team_logo`` callback.
On the current Spread Scanner path that callback can return an empty/unsupported
fragment, leaving the reserved logo slots blank even though team identity is
correct.

Repair
------
Use MLB's ID-addressable static team-logo CDN directly for the Step-1 card. This
is presentation-only and does not touch V15.2 probability/history math, ranking,
simulation, projected scores, fair odds, confidence, V15.3 backtest, V15.4 live
board or V15.5 verified-slate intake.
"""
from __future__ import annotations

import subprocess
import sys
import types
import urllib.request

import streamlit as st


_BASE_COMMIT = "8f44cf7da6e678be1371452f7db2de985c27c656"
_BASE_PATH = "mlb_spread_hub_v156.py"
_BASE_MODULE_NAME = "_kyre_mlb_spread_v156_frozen_step1"
MODEL_VERSION = "V15.6.1 • TOP-5 CARD STEP 1 • LOGO REPAIR"


def _load_frozen_v156():
    cached = sys.modules.get(_BASE_MODULE_NAME)
    if cached is not None:
        return cached

    try:
        source = subprocess.check_output(
            ["git", "show", f"{_BASE_COMMIT}:{_BASE_PATH}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        url = (
            "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
            f"{_BASE_COMMIT}/{_BASE_PATH}"
        )
        with urllib.request.urlopen(url, timeout=15) as response:
            source = response.read().decode("utf-8")

    module = types.ModuleType(_BASE_MODULE_NAME)
    module.__file__ = f"<{_BASE_MODULE_NAME}>"
    module.__package__ = ""
    sys.modules[_BASE_MODULE_NAME] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


base = _load_frozen_v156()

# Preserve public helpers that downstream debugging/checkpoint code may inspect.
prior = base.prior
v154 = base.v154
v153 = base.v153
v152 = base.v152


def _mlb_logo_html(team_id) -> str:
    """Return browser-renderable MLB logo HTML from the canonical numeric team ID."""
    try:
        tid = int(float(team_id))
    except Exception:
        return ""
    if tid <= 0:
        return ""

    # MLB static logos are keyed directly by official MLB team ID. Keep sizing in
    # the V15.6 CSS so desktop/mobile behavior stays exactly where it was designed.
    url = f"https://www.mlbstatic.com/team-logos/{tid}.svg"
    return (
        f'<img src="{url}" alt="MLB team {tid} logo" '
        'loading="lazy" decoding="async" referrerpolicy="no-referrer">'
    )


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    """Render frozen V15.6 with only the team-logo transport replaced."""

    def robust_team_logo(team_id):
        direct = _mlb_logo_html(team_id)
        if direct:
            return direct
        try:
            return team_logo(team_id) or ""
        except Exception:
            return ""

    st.caption(
        "🛠️ MLB Spread V15.6.1 • Step-1 logo transport repaired with official MLB team-ID assets • probability/ranking math unchanged."
    )
    return base.render_spread_hub(
        games_df,
        section_header,
        status_info,
        robust_team_logo,
        h,
    )


__all__ = ["MODEL_VERSION", "render_spread_hub", "prior", "v154", "v153", "v152"]
