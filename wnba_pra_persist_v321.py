"""WNBA PRA V3.2.1 — reload-safe Monte Carlo summary persistence.

WNBA-only. MLB V2.1.7 remains frozen.

Persists completed Step-8 5M/10M summary rows (never raw Monte Carlo draws) to
browser localStorage plus a compressed server-disk fallback. On reload/redeploy,
the saved simulation summary is restored into the existing V3.1 session-state
contract so Step 8 and Step 9 can resume without rerunning millions of draws.

Restored rows are regraded against the current exact PRA sportsbook snapshot when
available. Sportsbook prices never alter the saved simulation distribution.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import zlib

import numpy as np
import pandas as pd
import streamlit as st

try:
    from streamlit_local_storage import LocalStorage
except Exception:
    LocalStorage = None

import wnba_pra_market_v29 as market

SCHEMA = 1
MODEL_SCHEMA = "PRA-V3.1.1-EMPIRICAL-CORRELATED"
CACHE_DIR = Path(".kyre_runtime_cache")
_LOCAL = LocalStorage() if LocalStorage is not None else None


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_pra_v31_standard::{_day(day)}"


def final_key(day):
    return f"wnba_pra_v31_final::{_day(day)}"


def migration_key(day):
    return f"wnba_pra_v311_empirical_migrated::{_day(day)}"


def source_key(day):
    return f"wnba_pra_v321_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_pra_mc_v321::{_day(day)}"


def _component_key(day):
    return f"wnba_pra_v321_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_pra_mc_{_day(day)}.json.gz"


def _records(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    try:
        return json.loads(frame.to_json(orient="records", date_format="iso"))
    except Exception:
        return []


def _snapshot(day):
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
        "saved_at": now,
        "standard_ran_at": str(std.get("ran_at") or now),
        "standard_rows": _records(rows),
        "final_ran_at": str(fin.get("ran_at") or ""),
        "final_rows": _records(frows),
    }


def _valid(snapshot, day):
    if not isinstance(snapshot, dict):
        return False
    if int(snapshot.get("schema") or 0) != SCHEMA:
        return False
    if str(snapshot.get("model_schema") or "") != MODEL_SCHEMA:
        return False
    if str(snapshot.get("day") or "") != _day(day):
        return False
    rows = snapshot.get("standard_rows")
    if not isinstance(rows, list) or not rows:
        return False
    # A saved standard pass must actually represent completed 5M rows.
    try:
        return any(int(float(r.get("sims") or 0)) >= 5_000_000 for r in rows if isinstance(r, dict))
    except Exception:
        return False


def _encode(snapshot):
    raw = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "z1:" + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode(value):
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.startswith("z1:"):
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


def _current_pairs(day):
    try:
        pairs, _snap = market._paired_pra_markets(day)
        return pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _regrade(day, rows):
    """Refresh price/no-vig/freshness fields without rerunning basketball sims."""
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return rows
    pairs = _current_pairs(day)
    if pairs.empty:
        out = rows.copy()
        out["freshness"] = "STALE"
        out["fresh_score"] = 0.25
        out["model_qualified"] = False
        out["final_ready"] = False
        out["status"] = "AVOID"
        return out

    lookup = {}
    for _, p in pairs.iterrows():
        key = (
            str(p.get("game_id") or ""),
            str(p.get("player_key") or ""),
            round(float(p.get("line")), 3),
            str(p.get("book") or "").lower(),
        )
        lookup[key] = p

    out = rows.copy()
    updated = []
    for _, r in out.iterrows():
        obj = r.to_dict()
        try:
            key = (
                str(obj.get("game_id") or ""),
                str(obj.get("player_key") or ""),
                round(float(obj.get("line")), 3),
                str(obj.get("book") or "").lower(),
            )
        except Exception:
            updated.append(obj)
            continue
        p = lookup.get(key)
        if p is None:
            obj["freshness"] = "STALE"
            obj["fresh_score"] = 0.25
            obj["model_qualified"] = False
            obj["final_ready"] = False
            obj["status"] = "AVOID"
            updated.append(obj)
            continue

        nv_over, _nv_under = market._no_vig(p.get("over_odds"), p.get("under_odds"))
        fresh_label, fresh_score = market._freshness(p.get("market_age"))
        model_over = float(obj.get("model_over") or 0.0)
        push = float(obj.get("push") or 0.0)
        edge = model_over - nv_over if pd.notna(nv_over) else np.nan
        profit = market._profit_per_dollar(p.get("over_odds"))
        raw_over = model_over * max(0.0, 1.0 - push)
        raw_under = max(0.0, 1.0 - push - raw_over)
        ev100 = (raw_over * profit - raw_under) * 100.0 if pd.notna(profit) else np.nan

        obj.update({
            "over_odds": p.get("over_odds"),
            "under_odds": p.get("under_odds"),
            "no_vig_over": nv_over,
            "edge": edge,
            "ev100": ev100,
            "market_age": p.get("market_age"),
            "freshness": fresh_label,
            "fresh_score": fresh_score,
        })
        proj_min = float(obj.get("proj_min") or 0.0)
        context_q = float(obj.get("context_quality") or 0.0)
        role_label = str(obj.get("role_label") or "ACTIVE").upper()
        converged = bool(obj.get("converged"))
        qualified = (
            pd.notna(nv_over)
            and pd.notna(edge)
            and model_over >= 0.55
            and edge >= 0.030
            and proj_min >= 10.0
            and fresh_label != "STALE"
            and context_q >= 0.60
            and role_label != "OUT"
            and converged
        )
        obj["model_qualified"] = bool(qualified)
        obj["final_ready"] = bool(qualified and bool(obj.get("lineup_ready")))
        if fresh_label == "STALE" or role_label == "OUT":
            obj["status"] = "AVOID"
        elif obj["final_ready"]:
            obj["status"] = "FINAL READY"
        elif qualified:
            obj["status"] = "MONITOR LINEUP"
        else:
            obj["status"] = "NO EDGE"
        updated.append(obj)
    return pd.DataFrame(updated)


def _install(snapshot, day, source):
    if not _valid(snapshot, day):
        return False
    std_rows = pd.DataFrame(snapshot.get("standard_rows") or [])
    if std_rows.empty:
        return False
    std_rows = _regrade(day, std_rows)
    st.session_state[std_key(day)] = {
        "rows": std_rows,
        "meta": {"restored": True, "source": source},
        "ran_at": snapshot.get("standard_ran_at") or snapshot.get("saved_at"),
    }
    frows = pd.DataFrame(snapshot.get("final_rows") or [])
    if not frows.empty:
        frows = _regrade(day, frows)
        st.session_state[final_key(day)] = {
            "rows": frows,
            "meta": {"restored": True, "source": source},
            "ran_at": snapshot.get("final_ran_at") or snapshot.get("saved_at"),
        }
    st.session_state[migration_key(day)] = True
    st.session_state[source_key(day)] = source
    return True


def restore_if_missing(day):
    current = st.session_state.get(std_key(day)) or {}
    if isinstance(current.get("rows"), pd.DataFrame) and not current.get("rows").empty:
        return False

    disk = _read_disk(day)
    if _valid(disk, day) and _install(disk, day, "server-disk snapshot"):
        return True

    if _LOCAL is not None:
        raw = None
        try:
            raw = _LOCAL.getItem(_browser_key(day), key=_component_key(day))
        except Exception:
            raw = st.session_state.get(_component_key(day))
        snap = _decode(raw)
        if _valid(snap, day) and _install(snap, day, "browser persistent storage"):
            return True
    return False


def persist_if_ready(day):
    snap = _snapshot(day)
    if not snap:
        return False
    sig = f"{snap.get('standard_ran_at')}::{len(snap.get('standard_rows') or [])}::{len(snap.get('final_rows') or [])}"
    skey = f"wnba_pra_v321_saved::{_day(day)}"
    if st.session_state.get(skey) == sig:
        return True
    _write_disk(snap)
    if _LOCAL is not None:
        try:
            _LOCAL.setItem(_browser_key(day), _encode(snap))
        except Exception:
            pass
    st.session_state[skey] = sig
    st.session_state[source_key(day)] = "current completed Monte Carlo pass"
    return True


def render_persistence_status(day):
    current = st.session_state.get(std_key(day)) or {}
    rows = current.get("rows")
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        st.caption("💾 Monte Carlo persistence armed • the next completed 5M pass will be saved for reload/redeploy recovery.")
        return
    src = st.session_state.get(source_key(day)) or "active session"
    uniq = rows[["game_id", "player_key", "line"]].drop_duplicates().shape[0] if {"game_id","player_key","line"}.issubset(rows.columns) else len(rows)
    st.success(f"💾 Step-8 snapshot protected • {uniq} unique distributions • source: {src} • future reloads can restore without rerunning 5M sims.")


__all__ = ["restore_if_missing", "persist_if_ready", "render_persistence_status", "std_key", "final_key"]
