"""WNBA PRA V3.3 — fingerprint-safe Monte Carlo summary persistence.

V3.2.1 persisted completed 5M/10M summaries by date/model schema and refreshed
only sportsbook fields on restore.  That was fast, but a same-day injury/minutes
change could leave a mathematically stale basketball distribution alive.  V3.3
uses a new schema and restores only when the current upstream basketball-state
fingerprint exactly matches the saved one.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import zlib

import pandas as pd
import streamlit as st

import wnba_pra_persist_v321 as old
import wnba_pra_integrity_v33 as integrity

SCHEMA = 2
MODEL_SCHEMA = "PRA-V3.3-AVAILABILITY-INTEGRITY"
CACHE_DIR = Path(".kyre_runtime_cache")
_LOCAL = getattr(old, "_LOCAL", None)


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_pra_v31_standard::{_day(day)}"


def final_key(day):
    return f"wnba_pra_v31_final::{_day(day)}"


def source_key(day):
    return f"wnba_pra_v33_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_pra_mc_v33::{_day(day)}"


def _component_key(day):
    return f"wnba_pra_v33_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_pra_mc_v33_{_day(day)}.json.gz"


def _records(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    try:
        return json.loads(frame.to_json(orient="records", date_format="iso"))
    except Exception:
        return []


def _snapshot(day, state):
    if not state or not state.get("safe"):
        return None
    std = st.session_state.get(std_key(day)) or {}
    rows = std.get("rows")
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return None
    fin = st.session_state.get(final_key(day)) or {}
    frows = fin.get("rows")
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema": SCHEMA,
        "model_schema": MODEL_SCHEMA,
        "day": _day(day),
        "basketball_fingerprint": str(state.get("fingerprint") or ""),
        "availability_state": str(state.get("availability_state") or "CHECK"),
        "saved_at": now,
        "standard_ran_at": str(std.get("ran_at") or now),
        "standard_rows": _records(rows),
        "final_ran_at": str(fin.get("ran_at") or ""),
        "final_rows": _records(frows),
    }


def _valid(snapshot, day, state):
    if not isinstance(snapshot, dict) or not state or not state.get("safe"):
        return False
    if int(snapshot.get("schema") or 0) != SCHEMA:
        return False
    if str(snapshot.get("model_schema") or "") != MODEL_SCHEMA:
        return False
    if str(snapshot.get("day") or "") != _day(day):
        return False
    if str(snapshot.get("basketball_fingerprint") or "") != str(state.get("fingerprint") or ""):
        return False
    rows = snapshot.get("standard_rows")
    if not isinstance(rows, list) or not rows:
        return False
    try:
        return any(int(float(r.get("sims") or 0)) >= 5_000_000 for r in rows if isinstance(r, dict))
    except Exception:
        return False


def _encode(snapshot):
    raw = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "z2:" + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode(value):
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.startswith("z2:"):
            return json.loads(zlib.decompress(base64.urlsafe_b64decode(text[3:].encode("ascii"))).decode("utf-8"))
        return json.loads(text)
    except Exception:
        return None


def _write_disk(snapshot):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _disk_path(snapshot.get("day"))
        tmp = path.with_suffix(path.suffix + ".tmp")
        raw = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        tmp.write_bytes(gzip.compress(raw, compresslevel=9))
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _read_disk(day):
    try:
        path = _disk_path(day)
        if not path.exists():
            return None
        return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except Exception:
        return None


def _regrade_and_gate(day, rows):
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return rows
    # Regrade exact sportsbook fields using the proven V3.2.1 helper, then apply
    # the current availability gate again as defense in depth.
    try:
        rows = old._regrade(day, rows)
    except Exception:
        rows = rows.copy()
    return integrity.apply_availability_gate_to_rows(day, rows, stage="RESTORE")


def _install(snapshot, day, state, source):
    if not _valid(snapshot, day, state):
        return False
    std_rows = pd.DataFrame(snapshot.get("standard_rows") or [])
    if std_rows.empty:
        return False
    std_rows = _regrade_and_gate(day, std_rows)
    st.session_state[std_key(day)] = {
        "rows": std_rows,
        "meta": {
            "restored": True,
            "source": source,
            "basketball_fingerprint": state.get("fingerprint"),
            "availability_state": state.get("availability_state"),
            "pra_v33_integrity": True,
        },
        "ran_at": snapshot.get("standard_ran_at") or snapshot.get("saved_at"),
    }
    frows = pd.DataFrame(snapshot.get("final_rows") or [])
    if not frows.empty:
        frows = _regrade_and_gate(day, frows)
        st.session_state[final_key(day)] = {
            "rows": frows,
            "meta": {
                "restored": True,
                "source": source,
                "basketball_fingerprint": state.get("fingerprint"),
                "availability_state": state.get("availability_state"),
                "pra_v33_integrity": True,
            },
            "ran_at": snapshot.get("final_ran_at") or snapshot.get("saved_at"),
        }
    st.session_state[source_key(day)] = source
    return True


def restore_if_missing(day, state):
    # Current-process rows also have to prove they belong to this exact upstream
    # basketball state. Legacy V3.2.1 rows without a fingerprint are discarded.
    current = st.session_state.get(std_key(day)) or {}
    rows = current.get("rows")
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        meta = current.get("meta") if isinstance(current.get("meta"), dict) else {}
        if (
            bool(state.get("safe"))
            and str(meta.get("basketball_fingerprint") or "") == str(state.get("fingerprint") or "")
        ):
            return False
        st.session_state.pop(std_key(day), None)
        st.session_state.pop(final_key(day), None)

    if not state or not state.get("safe"):
        return False

    disk = _read_disk(day)
    if _valid(disk, day, state) and _install(disk, day, state, "V3.3 server-disk snapshot"):
        return True

    if _LOCAL is not None:
        raw = None
        try:
            raw = _LOCAL.getItem(_browser_key(day), key=_component_key(day))
        except Exception:
            raw = st.session_state.get(_component_key(day))
        snap = _decode(raw)
        if _valid(snap, day, state) and _install(snap, day, state, "V3.3 browser persistent storage"):
            return True
    return False


def persist_if_ready(day, state):
    if not state or not state.get("safe"):
        return False
    integrity.attach_fingerprint(day, state)
    snap = _snapshot(day, state)
    if not snap:
        return False
    sig = f"{snap.get('basketball_fingerprint')}::{snap.get('standard_ran_at')}::{len(snap.get('standard_rows') or [])}::{len(snap.get('final_rows') or [])}"
    skey = f"wnba_pra_v33_saved::{_day(day)}"
    if st.session_state.get(skey) == sig:
        return True
    _write_disk(snap)
    if _LOCAL is not None:
        try:
            _LOCAL.setItem(_browser_key(day), _encode(snap))
        except Exception:
            pass
    st.session_state[skey] = sig
    st.session_state[source_key(day)] = "current V3.3 fingerprint-verified Monte Carlo pass"
    return True


def render_persistence_status(day, state):
    current = st.session_state.get(std_key(day)) or {}
    rows = current.get("rows")
    if not state or not state.get("safe"):
        st.warning("💾 Monte Carlo restore DISABLED while availability integrity is CHECK. No stale simulation will be revived.")
        return
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        st.caption("💾 V3.3 persistence armed • a new completed 5M pass will be saved only with this exact injury/minutes/role fingerprint.")
        return
    meta = current.get("meta") if isinstance(current.get("meta"), dict) else {}
    matched = str(meta.get("basketball_fingerprint") or "") == str(state.get("fingerprint") or "")
    src = st.session_state.get(source_key(day)) or "active V3.3 session"
    if matched:
        st.success(f"💾 Step-8 snapshot protected • basketball fingerprint MATCH • source: {src}.")
    else:
        st.error("💾 Snapshot fingerprint mismatch — Final Card is blocked until a new 5M pass is run.")


__all__ = ["restore_if_missing", "persist_if_ready", "render_persistence_status", "std_key", "final_key"]
