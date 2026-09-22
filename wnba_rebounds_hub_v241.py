"""WNBA Rebounds V2.4.1 — Step 15 source-reconciliation repair.

Root cause fixed:
V2.4 correctly asked Step 15 for atomic Step-9/10 basketball factors, but the
Step-11 player frame intentionally rebuilt a compact row and did not carry all
of those upstream columns forward. Step 12 inherited that compact Step-11 row.
As a result, V2.4 could see verified Steps 9/10 on-screen while Step 15 received
NaN for Step10 expected miss-volume index, Step8 allowed index, and the Step9
same-position competition index.

Repair rules:
- Keep Steps 1-14 model logic untouched.
- Keep V2.4 projection math/weights/caps untouched.
- Reconcile Step-15 atomic inputs directly from their verified source frames:
  * Step 10 -> expected miss-volume index
  * Step 9  -> Step8 allowed index + same-position competition index
  * Step 12 -> capture baseline, lineup competition, H2H history
- Join only by unique normalized Player + Team identity; never guess.
- Sportsbook/no-vig data remains completely excluded from projection math.
- Add zero network requests.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v24 as base

MODEL_VERSION = "WNBA REBOUNDS V2.4.1 • STEP 15 SOURCE RECONCILIATION REPAIR"

_ORIGINAL_BUILD_STEP15 = base._build_step15


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _lookup(frame: pd.DataFrame):
    """Unique Player+Team lookup; duplicates are deliberately rejected."""
    if frame is None or frame.empty:
        return {}
    buckets = {}
    for idx, row in frame.iterrows():
        key = (_norm(row.get("Player")), _norm(row.get("Team")))
        if key[0] and key[1]:
            buckets.setdefault(key, []).append(idx)
    out = {}
    for key, idxs in buckets.items():
        if len(idxs) == 1:
            out[key] = frame.loc[idxs[0]]
    return out


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _build_step15_reconciled():
    players12 = pd.DataFrame(st.session_state.get("wnba_rebounds_step12_players") or [])
    players10 = pd.DataFrame(st.session_state.get("wnba_rebounds_step10_players") or [])
    players9 = pd.DataFrame(st.session_state.get("wnba_rebounds_step9_players") or [])
    step14_ready = bool(st.session_state.get("wnba_rebounds_step14_ready"))

    if players12.empty:
        return pd.DataFrame(), {
            "ready": False,
            "players": 0,
            "covered": 0,
            "market_isolation": True,
            "reason": "no verified Step-12 player frame",
            "step9_reconciled": 0,
            "step10_reconciled": 0,
        }

    lookup10 = _lookup(players10)
    lookup9 = _lookup(players9)

    rows = []
    step9_reconciled = 0
    step10_reconciled = 0
    missing_step9 = 0
    missing_step10 = 0

    for _, p in players12.iterrows():
        key = (_norm(p.get("Player")), _norm(p.get("Team")))
        s10 = lookup10.get(key)
        s9 = lookup9.get(key)

        merged = p.copy()

        step10_ok = False
        if s10 is not None and str(s10.get("Step10 state") or "") == "VERIFIED":
            miss_idx = _num(s10.get("Step10 expected miss-volume index"))
            if np.isfinite(miss_idx) and miss_idx > 0:
                merged["Step10 expected miss-volume index"] = miss_idx
                step10_ok = True
                step10_reconciled += 1
        if not step10_ok:
            missing_step10 += 1

        step9_ok = False
        if s9 is not None and str(s9.get("State") or "") == "VERIFIED":
            allowed_idx = _num(s9.get("Step8 allowed index"))
            position_idx = _num(s9.get("Same-position competition index"))
            if (
                np.isfinite(allowed_idx) and allowed_idx > 0
                and np.isfinite(position_idx) and position_idx >= 0
            ):
                merged["Step8 allowed index"] = allowed_idx
                merged["Same-position competition index"] = position_idx
                step9_ok = True
                step9_reconciled += 1
        if not step9_ok:
            missing_step9 += 1

        comp = base._projection_components(merged)
        step12_ok = str(p.get("Step12 state") or "") == "VERIFIED"
        verified = bool(step12_ok and step9_ok and step10_ok and comp.get("ok"))

        out = p.to_dict()
        out.update({
            "Projection baseline REB": comp.get("baseline"),
            "Projection miss factor": comp.get("miss"),
            "Projection allowed factor": comp.get("allowed"),
            "Projection opponent-position factor": comp.get("opp_pos"),
            "Projection lineup factor": comp.get("lineup"),
            "Projection H2H factor": comp.get("h2h"),
            "Projection H2H weight": comp.get("h2h_weight"),
            "Projection H2H sample": comp.get("h2h_label"),
            "Projection context factor": comp.get("factor"),
            "Expected REB": comp.get("projection"),
            "Projection market input": False,
            "Projection Step9 source": "VERIFIED" if step9_ok else "CHECK",
            "Projection Step10 source": "VERIFIED" if step10_ok else "CHECK",
            "Step15 state": "VERIFIED" if verified else "CHECK",
        })
        rows.append(out)

    frame = pd.DataFrame(rows)
    covered = int(frame["Step15 state"].eq("VERIFIED").sum()) if not frame.empty else 0
    ready = bool(
        step14_ready
        and not frame.empty
        and covered == len(frame)
        and frame["Projection market input"].eq(False).all()
    )

    expected = pd.to_numeric(frame.get("Expected REB"), errors="coerce") if not frame.empty else pd.Series(dtype=float)
    context = pd.to_numeric(frame.get("Projection context factor"), errors="coerce") if not frame.empty else pd.Series(dtype=float)

    return frame, {
        "ready": ready,
        "players": int(len(frame)),
        "covered": covered,
        "market_isolation": True,
        "mean_projection": float(expected.mean()) if expected.notna().any() else np.nan,
        "min_context": float(context.min()) if context.notna().any() else np.nan,
        "max_context": float(context.max()) if context.notna().any() else np.nan,
        "method": "V2.4 bounded log-space synthesis with direct verified Step9/10 atomic-source reconciliation",
        "step9_reconciled": step9_reconciled,
        "step10_reconciled": step10_reconciled,
        "missing_step9": missing_step9,
        "missing_step10": missing_step10,
    }


def render_wnba_rebounds_hub(*args, **kwargs):
    old_builder = base._build_step15
    base._build_step15 = _build_step15_reconciled
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
        step15 = pd.DataFrame(st.session_state.get("wnba_rebounds_step15_players") or [])
        if not step15.empty:
            s9 = int(step15.get("Projection Step9 source", pd.Series(dtype=str)).eq("VERIFIED").sum())
            s10 = int(step15.get("Projection Step10 source", pd.Series(dtype=str)).eq("VERIFIED").sum())
            total = int(len(step15))
            st.caption(
                f"⚡ V2.4.1 Step-15 source repair • direct verified atomic joins: Step 9 {s9}/{total} • "
                f"Step 10 {s10}/{total} • V2.4 projection math unchanged • zero new network requests • "
                "sportsbook/no-vig remains excluded from projection."
            )
        return out
    finally:
        base._build_step15 = old_builder


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
