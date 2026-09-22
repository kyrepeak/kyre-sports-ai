"""WNBA Points V1.9.8.4 — durable calibration-ledger persistence.

Presentation/model math remains frozen at WNBA Points V1.9.8.2 and the
out-of-sample tracker remains V1.9.8.3. This wrapper changes persistence only.

Durability layers:
1. Streamlit session-state working copy.
2. Atomic server primary + backup files.
3. Compressed, checksummed browser localStorage primary + backup copies.
4. Merge-on-load semantics so a stale/partial copy cannot erase newer snapshots
   or resolved outcomes from another healthy copy.

Browser storage is deliberately not overwritten on the first couple of renders
when the Streamlit component has not returned a value yet. That protects an
existing browser copy during a fresh server/redeploy boot.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import zlib

import streamlit as st

import wnba_points_hub_v1983 as lab

try:
    from streamlit_local_storage import LocalStorage
except Exception:  # pragma: no cover - dependency exists in production requirements
    LocalStorage = None

MODEL_VERSION = "WNBA POINTS V1.9.8.4 • DURABLE CALIBRATION LEDGER"
PRA_FROZEN_BRANCH = lab.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = lab.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = lab.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = lab.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = lab.POINTS_FROZEN_COMMIT

_SESSION_LEDGER = "_wnba_points_calibration_ledger_v1984"
_SESSION_HEALTH = "_wnba_points_calibration_persistence_health_v1984"
_BROWSER_ATTEMPTS = "_wnba_points_calibration_browser_attempts_v1984"
_BROWSER_PRIMARY = "kyre_wnba_points_calibration_ledger_v1984"
_BROWSER_BACKUP = "kyre_wnba_points_calibration_ledger_v1984_backup"
_BROWSER_GRACE_RENDERS = 3
_PACK_FORMAT = "kyre-zlib-b64-v1"

_ORIGINAL_RENDER_LAB = lab._render_calibration_lab

# One component manager per Python process. Method calls are still Streamlit
# components, but keeping the manager stable avoids needless component churn.
_LOCAL = LocalStorage() if LocalStorage is not None else None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise(payload) -> dict | None:
    if not isinstance(payload, dict):
        return None
    snapshots = payload.get("snapshots")
    results = payload.get("results")
    if not isinstance(snapshots, dict) or not isinstance(results, dict):
        return None
    out = dict(payload)
    out["schema"] = payload.get("schema", lab.LEDGER_SCHEMA)
    out["snapshots"] = dict(snapshots)
    out["results"] = dict(results)
    return out


def _timestamp(row: dict, field: str) -> str:
    value = row.get(field) if isinstance(row, dict) else None
    return str(value or "")


def _merge(*payloads) -> dict:
    """Union healthy copies; newest timestamp wins only on key collisions."""
    out = lab._empty_ledger()
    for payload in payloads:
        item = _normalise(payload)
        if item is None:
            continue
        for key, row in item.get("snapshots", {}).items():
            if not isinstance(row, dict):
                continue
            old = out["snapshots"].get(key)
            if old is None or _timestamp(row, "captured_at_utc") >= _timestamp(old, "captured_at_utc"):
                out["snapshots"][key] = dict(row)
        for key, row in item.get("results", {}).items():
            if not isinstance(row, dict):
                continue
            old = out["results"].get(key)
            if old is None or _timestamp(row, "resolved_at_utc") >= _timestamp(old, "resolved_at_utc"):
                out["results"][key] = dict(row)
            # A resolved result also contains the archived pregame fields. Keep a
            # snapshot copy if another tier lost the corresponding snapshot.
            if key not in out["snapshots"]:
                snap = {k: v for k, v in row.items() if k not in {"actual_pts", "over_result", "resolved_at_utc"}}
                out["snapshots"][key] = snap
    out["persistence"] = {
        "version": MODEL_VERSION,
        "merged_at_utc": _utcnow(),
    }
    return out


def _raw_json(payload: dict) -> str:
    clean = _normalise(payload) or lab._empty_ledger()
    # Persistence metadata is retained, but deterministic ordering makes the
    # checksum and change detection stable.
    if isinstance(payload, dict) and isinstance(payload.get("persistence"), dict):
        clean["persistence"] = dict(payload["persistence"])
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _pack(payload: dict) -> str:
    raw = _raw_json(payload).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    compressed = zlib.compress(raw, level=9)
    return json.dumps({
        "format": _PACK_FORMAT,
        "sha256": digest,
        "payload": base64.b64encode(compressed).decode("ascii"),
    }, separators=(",", ":"))


def _unpack(value) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        # The component may deserialize JSON for us, or this may be a raw ledger.
        if "snapshots" in value and "results" in value:
            return _normalise(value)
        envelope = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            envelope = json.loads(text)
        except Exception:
            return None
        if isinstance(envelope, dict) and "snapshots" in envelope and "results" in envelope:
            return _normalise(envelope)
    if not isinstance(envelope, dict) or envelope.get("format") != _PACK_FORMAT:
        return None
    try:
        compressed = base64.b64decode(str(envelope["payload"]).encode("ascii"), validate=True)
        raw = zlib.decompress(compressed)
        if hashlib.sha256(raw).hexdigest() != str(envelope.get("sha256") or ""):
            return None
        return _normalise(json.loads(raw.decode("utf-8")))
    except Exception:
        return None


def _server_paths() -> tuple[Path, Path]:
    primary = lab._ledger_path()
    backup = primary.with_name(primary.stem + ".backup" + primary.suffix)
    return primary, backup


def _read_server(path: Path) -> dict | None:
    try:
        return _normalise(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _save_server(payload: dict) -> tuple[bool, bool]:
    primary, backup = _server_paths()
    text = _raw_json(payload)
    backup_ok = primary_ok = False
    try:
        _atomic_write(backup, text)
        backup_ok = _read_server(backup) is not None
    except Exception:
        backup_ok = False
    try:
        _atomic_write(primary, text)
        primary_ok = _read_server(primary) is not None
    except Exception:
        primary_ok = False
    return primary_ok, backup_ok


def _browser_read() -> tuple[dict | None, str]:
    if _LOCAL is None:
        return None, "UNAVAILABLE"
    try:
        first = _LOCAL.getItem(_BROWSER_PRIMARY, key="wnba_calibration_browser_primary_v1984")
        second = _LOCAL.getItem(_BROWSER_BACKUP, key="wnba_calibration_browser_backup_v1984")
        a = _unpack(first)
        b = _unpack(second)
        if a is not None or b is not None:
            st.session_state[_BROWSER_ATTEMPTS] = _BROWSER_GRACE_RENDERS
            return _merge(a, b), "RESTORED"
        attempts = int(st.session_state.get(_BROWSER_ATTEMPTS, 0)) + 1
        st.session_state[_BROWSER_ATTEMPTS] = attempts
        return None, "SYNCING" if attempts < _BROWSER_GRACE_RENDERS else "EMPTY/READY"
    except Exception:
        return None, "ERROR"


def _browser_write(payload: dict) -> bool:
    if _LOCAL is None:
        return False
    # Do not overwrite an existing browser copy during the component's initial
    # asynchronous hydration window on a fresh Streamlit process.
    if int(st.session_state.get(_BROWSER_ATTEMPTS, 0)) < _BROWSER_GRACE_RENDERS:
        return False
    packed = _pack(payload)
    try:
        _LOCAL.setItem(_BROWSER_BACKUP, packed)
        _LOCAL.setItem(_BROWSER_PRIMARY, packed)
        return True
    except Exception:
        return False


def _counts(payload: dict | None) -> tuple[int, int]:
    item = _normalise(payload)
    if item is None:
        return 0, 0
    return len(item.get("snapshots", {})), len(item.get("results", {}))


def _load_ledger() -> dict:
    primary, backup = _server_paths()
    server_primary = _read_server(primary)
    server_backup = _read_server(backup)
    session_copy = _normalise(st.session_state.get(_SESSION_LEDGER))
    browser_copy, browser_state = _browser_read()

    merged = _merge(server_primary, server_backup, session_copy, browser_copy)
    st.session_state[_SESSION_LEDGER] = merged

    sp = _counts(server_primary)
    sb = _counts(server_backup)
    br = _counts(browser_copy)
    st.session_state[_SESSION_HEALTH] = {
        "browser_state": browser_state,
        "server_primary": sp,
        "server_backup": sb,
        "browser": br,
        "merged": _counts(merged),
        "loaded_at_utc": _utcnow(),
    }
    return merged


def _save_ledger(payload: dict) -> None:
    # Merge again with the in-session copy so an older caller can never shrink
    # the ledger by omission.
    merged = _merge(st.session_state.get(_SESSION_LEDGER), payload)
    st.session_state[_SESSION_LEDGER] = merged
    primary_ok, backup_ok = _save_server(merged)
    browser_ok = _browser_write(merged)
    health = dict(st.session_state.get(_SESSION_HEALTH, {}))
    health.update({
        "server_primary_write": primary_ok,
        "server_backup_write": backup_ok,
        "browser_write": browser_ok,
        "merged": _counts(merged),
        "saved_at_utc": _utcnow(),
    })
    st.session_state[_SESSION_HEALTH] = health


def _render_persistence_health() -> None:
    health = st.session_state.get(_SESSION_HEALTH, {})
    snaps, results = health.get("merged", (0, 0))
    browser_state = str(health.get("browser_state") or "UNKNOWN")
    with st.expander("🛡️ Calibration persistence health", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Merged snapshots", int(snaps))
        c2.metric("Resolved results", int(results))
        c3.metric("Server copies", "2/2" if health.get("server_primary_write") and health.get("server_backup_write") else "CHECK")
        if browser_state == "RESTORED" or health.get("browser_write"):
            browser_label = "PROTECTED"
        elif browser_state == "SYNCING":
            browser_label = "SYNCING"
        elif browser_state == "EMPTY/READY":
            browser_label = "READY"
        else:
            browser_label = browser_state
        c4.metric("Browser backup", browser_label)
        st.caption(
            "Recovery order: server primary + server backup + session copy + checksummed browser primary/backup are merged by key. "
            "A healthy copy can restore missing snapshots/results after a Streamlit reload or redeploy on this browser."
        )
        if browser_state == "SYNCING":
            st.info("Browser backup is hydrating. It is intentionally not overwritten during the initial recovery window.")
        st.caption("For a second device/browser, use the calibration-ledger export until a shared cloud database is added.")


def _render_calibration_lab(day: str, ledger: dict) -> None:
    _ORIGINAL_RENDER_LAB(day, ledger)
    _render_persistence_health()


def _install() -> None:
    lab._load_ledger = _load_ledger
    lab._save_ledger = _save_ledger
    lab._render_calibration_lab = _render_calibration_lab


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    return lab.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
