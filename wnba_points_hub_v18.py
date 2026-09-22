"""WNBA Points V1.8 hub — rotation-aware minutes + existing strict gates."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import streamlit as st

import wnba_points_v18 as points


def _load_v171():
    path = Path(__file__).with_name("wnba_points_hub_v171.py")
    spec = importlib.util.spec_from_file_location("_kyre_wnba_points_v171_base_for_v18", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load WNBA Points V1.7.1 base.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v171 = _load_v171()
MODEL_VERSION = "WNBA POINTS V1.8 • ROTATION-AWARE MINUTES"
PRA_FROZEN_BRANCH = v171.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = v171.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = v171.MLB_FROZEN_BRANCH

# Redirect every V1.7/V1.7.1 page helper to the new Points-only execution layer.
v171.points = points
v171.base.points = points
v171.base.ui.points = points
v171.ui.points = points

_orig_handoff = v171.base._render_data_handoff


def _rotation_integrity(day):
    try:
        projections, _, _, pmeta, _ = points._prepare(day)
    except Exception as exc:
        st.error(f"Rotation-minute integrity could not complete: {type(exc).__name__}: {exc}")
        return
    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    if projections.empty:
        st.warning("⚠️ Rotation-minute integrity has no projection rows yet.")
        return

    frame = projections.copy()
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame["PROJ_MIN_ROLE"] = pd.to_numeric(frame.get("PROJ_MIN_ROLE"), errors="coerce").fillna(frame["PROJ_MIN"])
    grouped = frame.groupby(["game_id", "TEAM_ID", "team_name"], dropna=False).agg(
        Players=("PLAYER_NAME", "count"),
        New_MIN=("PROJ_MIN", "sum"),
        Old_role_MIN=("PROJ_MIN_ROLE", "sum"),
    ).reset_index()
    grouped["New_MIN"] = grouped["New_MIN"].round(1)
    grouped["Old_role_MIN"] = grouped["Old_role_MIN"].round(1)
    checks = int(grouped["New_MIN"].between(199.5, 200.5).sum())
    teams = len(grouped)

    with st.expander("⏱️ Rotation-minute integrity", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Team-minute checks", f"{checks}/{teams}")
        c2.metric("Minutes model", "L3/L5")
        c3.metric("Team target", "200")
        c4.metric("Sportsbook input", "NONE")
        if teams and checks == teams:
            st.success("✅ ROTATION MINUTES VERIFIED • every modeled team reconciles to 200 minutes using actual recent team rotations plus a small role stabilizer.")
        else:
            st.error("⛔ ROTATION MINUTES NOT READY • do not run 5M until every modeled team reconciles to 200 minutes.")
        st.dataframe(
            grouped[["team_name", "Players", "New_MIN", "Old_role_MIN"]].rename(columns={
                "team_name": "Team", "New_MIN": "Rotation MIN", "Old_role_MIN": "Old role MIN"
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Recent team minutes come from verified completed WNBA box scores. DNPs count as zero for current-roster players; OUT/INACTIVE/DOUBTFUL stay at zero. Sportsbook lines never move projected minutes.")


def _handoff_with_rotation(day):
    result = _orig_handoff(day)
    _rotation_integrity(day)
    return result


v171.base._render_data_handoff = _handoff_with_rotation


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🏀 WNBA Points V1.8 • rotation-aware minutes • empirical history + sanity gates • PRA V3.2.1 frozen • MLB V2.1.7 frozen")
    return v171.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
