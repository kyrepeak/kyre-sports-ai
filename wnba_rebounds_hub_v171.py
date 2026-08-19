"""WNBA Rebounds V1.7.1.2 — crash-safe persistent fast-start wrapper.

Performance-only patch over verified V1.7.

Fix in V1.7.1.2:
- Persist only verified Rebounds data/checkpoint keys, never Streamlit widget keys.
- Never write fast-start bookkeeping flags into st.session_state.
- Ignore any legacy snapshot that may contain button/widget state.
- Preserve Steps 1-8 model logic exactly as V1.7.
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

MODEL_VERSION = "WNBA REBOUNDS V1.7.1.2 • CRASH-SAFE PERSISTENT FAST START"
SNAPSHOT_MAX_AGE_SECONDS = 8 * 60 * 60
SNAPSHOT_DIR = Path(os.path.expanduser("~/.cache/kyre_sports_ai"))
SNAPSHOT_FILE = SNAPSHOT_DIR / "wnba_rebounds_fast_start_v1712.json"

_SAFE_PREFIXES = tuple(f"wnba_rebounds_step{i}_" for i in range(1, 10))
_UNSAFE_TOKENS = (
    "button", "clicked", "recheck", "refresh", "force_", "widget",
    "select", "radio", "toggle", "checkbox", "date_input", "number_input",
    "slider", "multiselect", "text_input", "submit", "rerun",
)


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
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
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
    raise TypeError(f"unsupported snapshot value: {type(value).__name__}")


def _safe_checkpoint_key(key) -> bool:
    skey = str(key)
    if not skey.startswith(_SAFE_PREFIXES):
        return False
    low = skey.lower()
    return not any(token in low for token in _UNSAFE_TOKENS)


def _checkpoint_state() -> dict:
    data = {}
    for key in list(st.session_state.keys()):
        if not _safe_checkpoint_key(key):
            continue
        try:
            data[str(key)] = _json_safe(st.session_state[key])
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
    except Exception:
        # Persistence is only an optimization. Never let a snapshot failure
        # touch Streamlit widget/session state or break the page.
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
    state = {str(k): v for k, v in state.items() if _safe_checkpoint_key(k)}
    return state, "HIT"


def _hydrate_fast_start() -> tuple[str, int]:
    """Restore only safe data keys; never create bookkeeping session keys."""
    state, status = _read_snapshot()
    restored = 0
    if status == "HIT":
        for key, value in state.items():
            if key in st.session_state:
                continue
            try:
                st.session_state[key] = value
                restored += 1
            except Exception:
                # If Streamlit considers a key widget-owned or otherwise unsafe,
                # skip it. Fast start must never prevent normal rendering.
                continue
    return status, restored


def render_wnba_rebounds_hub(*args, **kwargs):
    status, restored = _hydrate_fast_start()
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    wrote = _write_snapshot()

    if status == "HIT" and restored:
        st.success(
            f"⚡ SAFE FAST START RESTORED • {restored} verified Rebounds checkpoint values were rehydrated after restart."
        )
    elif status in {"STALE", "DATE_MISMATCH"}:
        st.caption(
            "⚡ Fast-start snapshot was ignored because it was stale or belonged to another slate date; a fresh safe snapshot is being built."
        )

    st.caption(
        "⚡ V1.7.1.2 crash-safe persistent fast start • no fast-start bookkeeping is written to Streamlit session state • "
        f"snapshot {'saved' if wrote else 'not written'} • reboot restore target ≤8h • Steps 1–8 logic unchanged."
    )
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
