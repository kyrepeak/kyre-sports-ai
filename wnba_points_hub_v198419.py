"""WNBA Points V1.9.8.4.19 — Step 8 usage handoff + lineup-source clarity.

Presentation/context-only wrapper over V1.9.8.4.18. The protected V1.9.8.4.5
Points projection, sportsbook transport, Monte Carlo, calibration, candidate
hierarchy, persistence, readiness gates and Top-5 ordering remain unchanged.

Repairs two Step-8 audit issues only:
1) when the Top-5 presentation row does not carry USG_PCT/L10_USG_PCT/
   L5_USG_PCT, reuse the same hardened WNBA role/usage table that the protected
   role engine already depends on; never invent an unlabeled usage value;
2) make boolean lineup-source text explicit (for example
   STARTER_CONFIRMED = FALSE) so a NOT CONFIRMED result cannot visually look
   like a confirmation merely because the source field is named
   STARTER_CONFIRMED.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198418 as prior
import wnba_role_v282 as role

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.19 • STEP 8 USAGE HANDOFF + LINEUP LABEL REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Preserve the genuine V1.9.8.4.18 functions once so repeated Streamlit reruns
# never wrap an already wrapped presentation function.
_BASE_STEP8_BLOCK = getattr(prior, "_kyre_v198419_base_step8", prior._step8_block)
_BASE_LINEUP_STATE = getattr(prior, "_kyre_v198419_base_lineup_state", prior._lineup_state)
setattr(prior, "_kyre_v198419_base_step8", _BASE_STEP8_BLOCK)
setattr(prior, "_kyre_v198419_base_lineup_state", _BASE_LINEUP_STATE)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _id_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _valid_usage(value) -> bool:
    x = _num(value, np.nan)
    return bool(pd.notna(x) and x > 0)


def _usage_source_label(source: str) -> str:
    text = str(source or "").strip()
    upper = text.upper()
    if not text:
        return "NOT EXPOSED"
    if "PRODUCTION-ROLE PROXY" in upper:
        return "PROTECTED ROLE-ENGINE PROXY • ESTIMATED, NOT OFFICIAL USG%"
    if "ESPN" in upper:
        return "ESPN WNBA BOX-SCORE ESTIMATED USG%"
    return text


def _usage_handoff(day: str, data: dict) -> tuple[dict, str]:
    """Fill missing Step-8 usage fields from the protected role engine source.

    Existing row values always win. This function is presentation-only: it does
    not write the hydrated values back into the Points projection or simulation.
    """
    out = dict(data or {})
    keys = ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT")
    existing = {k: _valid_usage(out.get(k)) for k in keys}
    if all(existing.values()):
        return out, "PROTECTED POINTS PROJECTION ROW"

    try:
        season = int(pd.to_datetime(day).year)
        table, source = role.advanced_usage_table(season)
    except Exception:
        table, source = pd.DataFrame(), ""

    if table is None or table.empty:
        return out, "NOT EXPOSED BY PROTECTED ROLE/USAGE RUNTIME"

    pid = _id_int(out.get("PLAYER_ID"))
    tid = _id_int(out.get("TEAM_ID"))
    matched = table.copy()

    if pid and "PLAYER_ID" in matched.columns:
        ids = pd.to_numeric(matched["PLAYER_ID"], errors="coerce").fillna(-1).astype(int)
        matched = matched.loc[ids.eq(pid)]
    if tid and not matched.empty and "TEAM_ID" in matched.columns:
        tids = pd.to_numeric(matched["TEAM_ID"], errors="coerce").fillna(-1).astype(int)
        team_match = matched.loc[tids.eq(tid)]
        if not team_match.empty:
            matched = team_match

    if matched.empty:
        return out, "PLAYER NOT FOUND IN PROTECTED ROLE/USAGE TABLE"

    row = matched.iloc[0]
    filled = 0
    for key in keys:
        if not _valid_usage(out.get(key)) and key in row.index and _valid_usage(row.get(key)):
            out[key] = row.get(key)
            filled += 1

    if filled <= 0:
        return out, "USAGE VALUES NOT PUBLISHED FOR THIS PLAYER"
    return out, _usage_source_label(source)


def _lineup_state_clear(data: dict) -> tuple[str, str]:
    # Keep the exact V1.9.8.4.18 decision rule; change only source wording.
    for key in ("LINEUP_CONFIRMED", "STARTER_CONFIRMED", "CONFIRMED_STARTER"):
        if key in data:
            value = prior._boolish(data.get(key))
            if value is True:
                return "CONFIRMED", f"protected runtime • {key} = TRUE"
            if value is False:
                return "NOT CONFIRMED", f"protected runtime • {key} = FALSE"

    for key in ("LINEUP_STATUS", "STARTER_STATUS", "STARTING_STATUS"):
        raw = prior._text(data, [key], "")
        if raw:
            return raw.upper(), f"protected runtime • {key} = {raw.upper()}"

    for key in ("IS_STARTER", "STARTER"):
        if key in data:
            value = prior._boolish(data.get(key))
            if value is True:
                return "STARTER ROLE", f"protected runtime • {key} = TRUE • role only"
            if value is False:
                return "BENCH ROLE", f"protected runtime • {key} = FALSE • role only"

    return "NOT EXPOSED", "no explicit lineup-confirmation field in protected runtime"


def _step8_block(day: str, data: dict) -> str:
    hydrated, usage_source = _usage_handoff(day, data)
    html = _BASE_STEP8_BLOCK(day, hydrated)

    # Add provenance beside the usage metrics without changing any scoring or
    # opportunity grade. The existing redistribution firewall remains intact.
    usage_note = escape(str(usage_source or "NOT EXPOSED"))
    marker = "<b>Usage redistribution</b> •"
    replacement = f"<b>Usage source</b> • {usage_note}<br><b>Usage redistribution</b> •"
    if marker in html:
        html = html.replace(marker, replacement, 1)
    return html


def _install() -> None:
    # V1.9.8.4.18 resolves both helpers from its module globals at render time.
    # Reassign on every rerun; do not touch projection/simulation objects.
    prior._lineup_state = _lineup_state_clear
    prior._step8_block = _step8_block


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🩺 Points V1.9.8.4.19 • Step 8 usage handoff + lineup-source clarity ACTIVE • "
        "existing protected usage preferred • source labeled • model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
