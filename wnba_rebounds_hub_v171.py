"""WNBA Rebounds V1.7.1 — persistent fast-start wrapper.

Performance-only patch over verified V1.7.

Goals:
- Preserve the verified Steps 1-8 model logic exactly as V1.7.
- Persist JSON-safe Rebounds session checkpoints to the Streamlit server disk.
- Rehydrate those checkpoints after a Streamlit process reboot when the snapshot
  is fresh and belongs to the current Eastern slate date.
- Never treat the snapshot as a new data source; it only restores already-
  verified session state so existing layer guards can avoid unnecessary work.
- Snapshot expires after 8 hours and is replaced atomically after successful
  renders. Redeploys may still replace the container filesystem; this patch is
  specifically aimed at ordinary app/process reboots.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v17 as base

MODEL_VERSION = "WNBA REBOUNDS V1.7.1 • PERSISTENT FAST START"
SNAPSHOT_MAX_AGE_SECONDS = 8 * 60 * 60
SNAPSHOT_DIR = Path(os.path.expanduser("~/.cache/kyre_sports_ai"))
SNAPSHOT_FILE = SNAPSHOT_DIR / "wnba_rebounds_fast_start_v171.json"


def _eastern_day() -> str:
    try:
        return str(pd.Timestamp.now(tz="America/New_York").date())
    except Exception:
        return str(pd.Timestamp.now().date())


def _json_safe(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        x = float(value)
        return x if np.isfinite(x) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return [_json_safe(x) for x in value.to_dict("records")]
    if isinstance(value, pd.Series):
        return {str(k): _json_safe(v) for k, v in value.to_dict().items()}
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            try:
                out[str(k)] = _json_safe(v)
            except Exception:
                continue
        return out
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    # Session state occasionally contains UI/runtime objects. Those are not
    # checkpoint data and should not be serialized.
    raise TypeError(f"unsupported snapshot value: {type(value).__name__}")


def _checkpoint_state() -> dict:
    data = {}
    for key in list(st.session_state.keys()):
        skey = str(key)
        if not skey.startswith("wnba_rebounds_"):
            continue
        # Do not persist transient button/action flags.
        if any(token in skey for token in ("force_", "button", "clicked", "refresh_requested")):
            continue
        try:
            data[skey] = _json_safe(st.session_state[key])
        except Exception:
            continue
    return data


def _write_snapshot() -> bool:
    state = _checkpoint_state()
    if not state:
        return False

    day = str(state.get("wnba_rebounds_step1_day") or _eastern_day())
    payload = {
        "version": MODEL_VERSION,
        "created_at": time.time(),
        "day": day,
        "state": state,
    }

    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SNAPSHOT_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, SNAPSHOT_FILE)
        return True
    except Exception as exc:
        st.session_state["wnba_rebounds_fast_start_write_error"] = f"{type(exc).__name__}: {exc}"
        return False


def _read_snapshot() -> tuple[dict, str]:
    if not SNAPSHOT_FILE.exists():
        return {}, "MISS"
    try:
        payload = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}, "CORRUPT"

    try:
        age = max(0.0, time.time() - float(payload.get("created_at") or 0.0))
    except Exception:
        return {}, "INVALID"

    if age > SNAPSHOT_MAX_AGE_SECONDS:
        return {}, "STALE"

    snapshot_day = str(payload.get("day") or "")
    session_day = str(st.session_state.get("wnba_rebounds_step1_day") or "")
    expected_day = session_day or _eastern_day()
    if snapshot_day != expected_day:
        return {}, "DATE_MISMATCH"

    state = payload.get("state")
    if not isinstance(state, dict):
        return {}, "INVALID"
    return state, "HIT"


def _hydrate_fast_start() -> str:
    # A live session already has its state; do not overwrite anything.
    if st.session_state.get("wnba_rebounds_fast_start_hydrated"):
        return str(st.session_state.get("wnba_rebounds_fast_start_status") or "SESSION")

    state, status = _read_snapshot()
    if status == "HIT":
        restored = 0
        for key, value in state.items():
            # Existing values always win so user actions/selections are preserved.
            if key not in st.session_state:
                st.session_state[key] = value
                restored += 1
        st.session_state["wnba_rebounds_fast_start_restored_keys"] = restored

    st.session_state["wnba_rebounds_fast_start_hydrated"] = True
    st.session_state["wnba_rebounds_fast_start_status"] = status
    return status


def render_wnba_rebounds_hub(*args, **kwargs):
    status = _hydrate_fast_start()

    out = base.render_wnba_rebounds_hub(*args, **kwargs)

    wrote = _write_snapshot()
    restored = int(st.session_state.get("wnba_rebounds_fast_start_restored_keys") or 0)

    if status == "HIT":
        st.success(
            f"⚡ FAST START RESTORED • {restored} verified Rebounds checkpoint values were rehydrated after restart."
        )
    elif status in {"STALE", "DATE_MISMATCH"}:
        st.caption(
            "⚡ Fast-start snapshot was intentionally ignored because it was stale or belonged to another slate date; a fresh snapshot is being built."
        )

    st.caption(
        "⚡ V1.7.1 persistent fast start • Steps 1–8 model logic unchanged from V1.7 • "
        f"snapshot {'saved' if wrote else 'not written'} • reboot restore target ≤8h • no sportsbook/Monte Carlo/projected rebound output."
    )
    return out


# Expose V1.7 helpers for compatibility/debugging without duplicating model code.
def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
