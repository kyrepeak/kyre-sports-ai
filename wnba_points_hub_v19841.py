"""WNBA Points V1.9.8.4.1 — browser-persistence compatibility + hydration fix.

No projection, SportsGameOdds, Monte Carlo, candidate, H2H, PRA or MLB math is
changed. V1.9.8.4.1 hardens ONLY the calibration-ledger persistence transport.

Fixes:
- reads browser storage through one getAll() component when available, with a
  getItem() compatibility fallback;
- hydrates browser storage from the merged server/session ledger even when no new
  pregame snapshot was created on this rerun;
- requires browser readback before calling the browser copy PROTECTED;
- keeps server primary + backup + session merge semantics from V1.9.8.4;
- reports DEVICE BLOCKED instead of pretending protection when the browser denies
  component storage.
"""
from __future__ import annotations

import json

import streamlit as st

import wnba_points_hub_v1984 as durable

MODEL_VERSION = "WNBA POINTS V1.9.8.4.1 • BROWSER HYDRATION FIX"
PRA_FROZEN_BRANCH = durable.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = durable.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = durable.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = durable.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = durable.POINTS_FROZEN_COMMIT


def _call_get_all():
    """Use the package's aggregate API first; tolerate version-signature drift."""
    if durable._LOCAL is None:
        return None
    try:
        return durable._LOCAL.getAll(key="wnba_calibration_browser_all_v19841")
    except TypeError:
        return durable._LOCAL.getAll()


def _call_get_item(item_key: str, component_key: str):
    if durable._LOCAL is None:
        return None
    try:
        return durable._LOCAL.getItem(item_key, key=component_key)
    except TypeError:
        return durable._LOCAL.getItem(item_key)


def _browser_read() -> tuple[dict | None, str]:
    if durable._LOCAL is None:
        return None, "UNAVAILABLE"

    aggregate_error = False
    try:
        all_items = _call_get_all()
        if isinstance(all_items, str):
            try:
                parsed = json.loads(all_items)
                all_items = parsed if isinstance(parsed, dict) else None
            except Exception:
                all_items = None
        if isinstance(all_items, dict):
            a = durable._unpack(all_items.get(durable._BROWSER_PRIMARY))
            b = durable._unpack(all_items.get(durable._BROWSER_BACKUP))
            if a is not None or b is not None:
                st.session_state[durable._BROWSER_ATTEMPTS] = durable._BROWSER_GRACE_RENDERS
                return durable._merge(a, b), "RESTORED"
            attempts = int(st.session_state.get(durable._BROWSER_ATTEMPTS, 0)) + 1
            st.session_state[durable._BROWSER_ATTEMPTS] = attempts
            return None, "SYNCING" if attempts < durable._BROWSER_GRACE_RENDERS else "EMPTY/READY"
        # Component hydration commonly returns None on its first renders.
        if all_items is None:
            attempts = int(st.session_state.get(durable._BROWSER_ATTEMPTS, 0)) + 1
            st.session_state[durable._BROWSER_ATTEMPTS] = attempts
            if attempts < durable._BROWSER_GRACE_RENDERS:
                return None, "SYNCING"
    except Exception:
        aggregate_error = True

    # Compatibility fallback for component builds where getAll is unavailable or
    # does not hydrate correctly.
    try:
        first = _call_get_item(
            durable._BROWSER_PRIMARY,
            "wnba_calibration_browser_primary_v19841",
        )
        second = _call_get_item(
            durable._BROWSER_BACKUP,
            "wnba_calibration_browser_backup_v19841",
        )
        a = durable._unpack(first)
        b = durable._unpack(second)
        if a is not None or b is not None:
            st.session_state[durable._BROWSER_ATTEMPTS] = durable._BROWSER_GRACE_RENDERS
            return durable._merge(a, b), "RESTORED"
        attempts = int(st.session_state.get(durable._BROWSER_ATTEMPTS, 0)) + 1
        st.session_state[durable._BROWSER_ATTEMPTS] = attempts
        return None, "SYNCING" if attempts < durable._BROWSER_GRACE_RENDERS else "EMPTY/READY"
    except Exception:
        # If both aggregate and direct component access fail, the device/browser
        # is denying the storage component. Do not report a false backup.
        return None, "DEVICE BLOCKED" if aggregate_error else "ERROR"


def _browser_write(payload: dict) -> bool:
    if durable._LOCAL is None:
        return False
    if int(st.session_state.get(durable._BROWSER_ATTEMPTS, 0)) < durable._BROWSER_GRACE_RENDERS:
        return False
    packed = durable._pack(payload)
    try:
        # Backup first, then primary. A later readback is required before the UI
        # calls this browser tier PROTECTED.
        durable._LOCAL.setItem(durable._BROWSER_BACKUP, packed)
        durable._LOCAL.setItem(durable._BROWSER_PRIMARY, packed)
        return True
    except Exception:
        return False


def _load_ledger() -> dict:
    primary, backup = durable._server_paths()
    server_primary = durable._read_server(primary)
    server_backup = durable._read_server(backup)
    session_copy = durable._normalise(st.session_state.get(durable._SESSION_LEDGER))
    browser_copy, browser_state = _browser_read()

    merged = durable._merge(server_primary, server_backup, session_copy, browser_copy)
    st.session_state[durable._SESSION_LEDGER] = merged

    # Critical V1.9.8.4.1 fix: after a deploy/reload the ledger may be unchanged,
    # so the calibration lab would never call save(). Hydrate the browser anyway
    # once its initial async recovery window has passed.
    browser_write = False
    if (
        browser_copy is None
        and browser_state in {"EMPTY/READY", "ERROR"}
        and int(st.session_state.get(durable._BROWSER_ATTEMPTS, 0)) >= durable._BROWSER_GRACE_RENDERS
        and durable._counts(merged)[0] > 0
    ):
        browser_write = _browser_write(merged)
        if browser_write:
            browser_state = "VERIFYING"

    st.session_state[durable._SESSION_HEALTH] = {
        "browser_state": browser_state,
        "server_primary": durable._counts(server_primary),
        "server_backup": durable._counts(server_backup),
        "browser": durable._counts(browser_copy),
        "browser_write": browser_write,
        "merged": durable._counts(merged),
        "loaded_at_utc": durable._utcnow(),
    }
    return merged


def _save_ledger(payload: dict) -> None:
    merged = durable._merge(st.session_state.get(durable._SESSION_LEDGER), payload)
    st.session_state[durable._SESSION_LEDGER] = merged
    primary_ok, backup_ok = durable._save_server(merged)
    browser_ok = _browser_write(merged)
    health = dict(st.session_state.get(durable._SESSION_HEALTH, {}))
    health.update({
        "server_primary_write": primary_ok,
        "server_backup_write": backup_ok,
        "browser_write": browser_ok,
        "merged": durable._counts(merged),
        "saved_at_utc": durable._utcnow(),
    })
    # A write request alone is not proof. The next successful readback upgrades
    # browser_state to RESTORED/PROTECTED.
    if browser_ok and health.get("browser_state") not in {"RESTORED"}:
        health["browser_state"] = "VERIFYING"
    st.session_state[durable._SESSION_HEALTH] = health


def _render_persistence_health() -> None:
    health = st.session_state.get(durable._SESSION_HEALTH, {})
    snaps, results = health.get("merged", (0, 0))
    browser_state = str(health.get("browser_state") or "UNKNOWN")
    server_ok = bool(health.get("server_primary_write") and health.get("server_backup_write"))
    # Existing healthy files also count when this rerun performed no new save.
    if not server_ok:
        sp = health.get("server_primary", (0, 0))
        sb = health.get("server_backup", (0, 0))
        server_ok = bool(sp and sb and int(sp[0]) >= int(snaps) and int(sb[0]) >= int(snaps))

    with st.expander("🛡️ Calibration persistence health", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Merged snapshots", int(snaps))
        c2.metric("Resolved results", int(results))
        c3.metric("Server copies", "2/2" if server_ok else "CHECK")

        if browser_state == "RESTORED":
            browser_label = "PROTECTED"
        elif browser_state in {"SYNCING", "EMPTY/READY", "VERIFYING"}:
            browser_label = "VERIFYING" if browser_state == "VERIFYING" else browser_state
        elif browser_state == "DEVICE BLOCKED":
            browser_label = "DEVICE BLOCKED"
        else:
            browser_label = browser_state
        c4.metric("Browser backup", browser_label)

        st.caption(
            "Recovery order: server primary + server backup + session copy + checksummed browser primary/backup are merged by key. "
            "Browser protection is marked PROTECTED only after a successful readback."
        )
        if browser_state == "SYNCING":
            st.info("Browser storage is hydrating. Reload once after the component finishes its initial sync window.")
        elif browser_state == "VERIFYING":
            st.info("Browser backup write was sent. One normal rerun/readback is required before it is marked PROTECTED.")
        elif browser_state == "DEVICE BLOCKED":
            st.warning(
                "This browser/device is blocking the local-storage component. The two server copies and session copy are healthy, "
                "but cross-redeploy durability should use a shared cloud store rather than pretending the browser tier is protected."
            )
        st.caption("For a second device/browser, use the calibration-ledger export until a shared cloud database is added.")


def _install() -> None:
    durable._browser_read = _browser_read
    durable._browser_write = _browser_write
    durable._load_ledger = _load_ledger
    durable._save_ledger = _save_ledger
    durable._render_persistence_health = _render_persistence_health


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    return durable.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
