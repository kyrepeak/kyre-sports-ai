"""WNBA Rebounds V1.8.3 — Step 9 zero-competition stabilization.

Narrow repair over V1.8.2.

Why this exists:
- V1.8.2 repaired opponent identity by using the exact Step-1 V2.5 slate.
- A remaining Step-9 CHECK can occur when an opponent has a verified structural
  zero capture share for a Guard/Wing/Big bucket. That is valid data, not missing
  data, but the diagnostic formula previously divided by the zero competition
  index and produced NaN.

Rules:
- Preserve the raw same-position competition index, including a real 0.000.
- For the diagnostic position-context arithmetic only, apply a small numerical
  floor of 0.05 when the verified competition index is exactly zero.
- This floor is NOT a player projection factor and is not sportsbook/Monte Carlo
  input. It only prevents a divide-by-zero from being mislabeled as missing data.
- Unknown/missing positions still remain CHECK and are never guessed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v18 as _impl
import wnba_rebounds_hub_v182 as base

MODEL_VERSION = "WNBA REBOUNDS V1.8.3 • STEP 9 STRUCTURAL-ZERO STABILIZATION"
ZERO_COMPETITION_FLOOR = 0.05


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _build_step9_stabilized():
    frame, board, info = base._build_step9_repaired()
    if frame is None or frame.empty:
        return frame, board, info

    out = frame.copy()
    if "Competition floor applied" not in out.columns:
        out["Competition floor applied"] = False

    repaired = 0
    for idx, row in out.iterrows():
        if str(row.get("State") or "") == "VERIFIED":
            continue

        bucket = str(row.get("Position bucket") or "")
        opp = str(row.get("Opponent") or "")
        share = _num(row.get("Opp positional capture share"))
        comp = _num(row.get("Same-position competition index"))
        miss_idx = _num(row.get("Step7 miss index"))
        allowed_idx = _num(row.get("Step8 allowed index"))

        # Only repair a mathematically singular, provider-verified structural
        # zero. Missing position/opponent/share/environment remains CHECK.
        structural_zero = bool(
            bucket in {"Guard", "Wing", "Big"}
            and opp and opp != "—"
            and np.isfinite(share) and share == 0.0
            and np.isfinite(comp) and comp == 0.0
            and np.isfinite(miss_idx) and miss_idx > 0
            and np.isfinite(allowed_idx) and allowed_idx > 0
        )
        if not structural_zero:
            continue

        env = miss_idx * allowed_idx
        stabilized_context = env / ZERO_COMPETITION_FLOOR
        if not np.isfinite(stabilized_context):
            continue

        # Raw competition index stays 0.000. Only the downstream diagnostic
        # division uses the floor so zero is not mistaken for unavailable data.
        out.at[idx, "Position context index"] = float(stabilized_context)
        out.at[idx, "Competition floor applied"] = True
        out.at[idx, "State"] = "VERIFIED"
        repaired += 1

    covered = int(out["State"].eq("VERIFIED").sum())
    total = int(len(out))
    new_info = dict(info or {})
    new_info["covered"] = covered
    new_info["players"] = total
    new_info["ready"] = bool(total > 0 and covered == total)
    new_info["zero_competition_rows_stabilized"] = repaired
    new_info["zero_competition_floor"] = ZERO_COMPETITION_FLOOR
    new_info["method"] = (
        "verified V2.5 full-slate opponent join + cached Step-7/8 context + "
        "structural-zero numerical stabilization"
    )
    return out, board, new_info


def render_wnba_rebounds_hub(*args, **kwargs):
    # V1.8.2 ultimately renders Step 9 through the V1.8 function. Swap only the
    # Step-9 builder for this call, then restore it immediately.
    old_repaired = base._build_step9_repaired
    base._build_step9_repaired = _build_step9_stabilized
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        base._build_step9_repaired = old_repaired

    st.caption(
        "⚡ V1.8.3 Step-9 stabilization • raw verified zero competition remains 0.000 • "
        "0.05 floor used only for diagnostic divide-by-zero protection • unknown positions still never guessed • "
        "no final rebound projection."
    )
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
