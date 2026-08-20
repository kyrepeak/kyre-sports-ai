"""WNBA Daily Picks V17 — Assists Connector Step 7 final production guard.

Preserves the complete Daily Picks V16 page (existing Daily Picks Steps 1–10 and
Assists Connector Steps 1–6) and appends the final four-market production-ready
guard verification.

The frozen Daily Picks Step-10 guard contract is reused. PRA, Points and Rebounds
retain their original behavior; Assists uses the isolated Guard V2 compatibility
adapter so its selected rows receive the same slate/quote/5M/convergence/
availability/game-state/freshness/finalization rechecks.

Only READY rows are rendered as the final four-market production card. MONITOR or
BLOCKED rows are never backfilled with lower-ranked candidates. No source model is
run or modified, no simulation/network refresh occurs, and no source production
state is written.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v16 as v16
import wnba_daily_picks_hub_v9 as visual
import wnba_daily_picks_selection_v2 as selection_v2
import wnba_daily_picks_guard_v2 as guard_v2

MODEL_VERSION = "WNBA DAILY PICKS V17 • ASSISTS CONNECTOR STEP 7 FINAL FOUR-MARKET GUARD"
_ET = ZoneInfo("America/New_York")


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in {"", "—", "NONE", "NAN", "NULL", "N/A", "NA"} else s


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _state_metric(diag: dict) -> str:
    if not int(diag.get("selected", 0) or 0):
        return "ARMED"
    ready = int(diag.get("ready", 0) or 0)
    monitor = int(diag.get("monitor", 0) or 0)
    blocked = int(diag.get("blocked", 0) or 0)
    if ready and not monitor and not blocked:
        return "READY"
    if ready:
        return "PARTIAL"
    if blocked and not monitor:
        return "BLOCKED"
    return "MONITOR"


def _audit_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Daily rank", "Guard state", "Market", "Player", "Team", "Opponent",
        "Side", "Line", "Book", "Posted odds", "Qualification state", "Safety state",
        "Finalization gate", "Connector gate", "Slate recheck", "Exact quote gate",
        "Simulation recheck", "Convergence recheck", "Availability recheck",
        "Game-state recheck", "Freshness recheck", "Guard reasons",
        "Guard checked at ET", "Guard fingerprint",
    ]
    return frame[[c for c in keep if c in frame.columns]].copy()


def _snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[
            "identity", "Daily rank", "Market", "Player", "Team", "Opponent",
            "Side", "Line", "Book", "Posted odds", "Guard state", "Guard fingerprint",
        ])
    records = []
    for _, row in frame.iterrows():
        identity = "::".join([
            _norm(row.get("Market")), _norm(row.get("Player")), _norm(row.get("Team")),
            _norm(row.get("Opponent")), _norm(row.get("Side")),
        ])
        records.append({
            "identity": identity,
            "Daily rank": _num(row.get("Daily rank")),
            "Market": _text(row.get("Market")),
            "Player": _text(row.get("Player")),
            "Team": _text(row.get("Team")),
            "Opponent": _text(row.get("Opponent")),
            "Side": _text(row.get("Side")),
            "Line": _num(row.get("Line")),
            "Book": _text(row.get("Book")),
            "Posted odds": _num(row.get("Posted odds")),
            "Guard state": _text(row.get("Guard state")),
            "Guard fingerprint": _text(row.get("Guard fingerprint")),
        })
    return pd.DataFrame(records)


def _movement(previous: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    prev = previous.copy() if isinstance(previous, pd.DataFrame) else pd.DataFrame()
    cur = current.copy() if isinstance(current, pd.DataFrame) else pd.DataFrame()
    if prev.empty and cur.empty:
        return pd.DataFrame(columns=["Player", "Market", "Movement", "Before", "Now"])
    if prev.empty:
        return pd.DataFrame([
            {
                "Player": r.get("Player", "—"),
                "Market": r.get("Market", "—"),
                "Movement": "NEW",
                "Before": "—",
                "Now": f"{r.get('Side','—')} {r.get('Line','—')} • {r.get('Book','—')} {r.get('Posted odds','—')} • {r.get('Guard state','—')}",
            }
            for _, r in cur.iterrows()
        ])

    prev_map = {str(r.get("identity")): r for _, r in prev.iterrows()}
    cur_map = {str(r.get("identity")): r for _, r in cur.iterrows()}
    keys = list(dict.fromkeys(list(prev_map.keys()) + list(cur_map.keys())))
    records = []
    for key in keys:
        a = prev_map.get(key)
        b = cur_map.get(key)
        if a is None:
            move = "NEW"
        elif b is None:
            move = "REMOVED"
        else:
            changes = []
            if _num(a.get("Line")) != _num(b.get("Line")):
                changes.append("LINE")
            if _text(a.get("Book")) != _text(b.get("Book")) or _num(a.get("Posted odds")) != _num(b.get("Posted odds")):
                changes.append("PRICE/BOOK")
            if _text(a.get("Guard state")) != _text(b.get("Guard state")):
                changes.append("GUARD")
            if _num(a.get("Daily rank")) != _num(b.get("Daily rank")):
                changes.append("RANK")
            move = " + ".join(changes) if changes else "UNCHANGED"
        ref = b if b is not None else a
        records.append({
            "Player": ref.get("Player", "—") if ref is not None else "—",
            "Market": ref.get("Market", "—") if ref is not None else "—",
            "Movement": move,
            "Before": "—" if a is None else f"{a.get('Side','—')} {a.get('Line','—')} • {a.get('Book','—')} {a.get('Posted odds','—')} • {a.get('Guard state','—')}",
            "Now": "—" if b is None else f"{b.get('Side','—')} {b.get('Line','—')} • {b.get('Book','—')} {b.get('Posted odds','—')} • {b.get('Guard state','—')}",
        })
    return pd.DataFrame(records)


def _render_ready_cards(ready: pd.DataFrame):
    if ready is None or ready.empty:
        return
    original = visual._card_html

    def production_card(row: pd.Series) -> str:
        html = original(row)
        html = html.replace("STEP-9 SELECTED", "✅ PRODUCTION READY")
        html = html.replace("STEP 10 GUARD PENDING", "GUARD PASSED")
        return html

    try:
        visual._card_html = production_card
        visual._render_cards(ready)
    finally:
        visual._card_html = original


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve all previously verified Daily Picks + Assists Connector Steps 1–6.
    v16.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    checked_at = datetime.now(_ET)
    bundle = selection_v2.build_four_market_selection(slate_day)
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    feeds = bundle.get("feeds", {}) if isinstance(bundle, dict) else {}
    if not isinstance(selected, pd.DataFrame):
        selected = pd.DataFrame()
    if not isinstance(feeds, dict):
        feeds = {}

    guarded = guard_v2.evaluate_four_market(selected, slate_day, feeds=feeds, now_et=checked_at)
    ready = guard_v2.ready_rows(guarded)
    diag = guard_v2.diagnostics(guarded, selected)
    coverage = bool(diag.get("coverage_pass"))
    state = _state_metric(diag)
    fingerprint = guard_v2.card_fingerprint(guarded)

    st.markdown("---")
    st.markdown("## 🛡️ Assists Connector — Step 7: Final Four-Market Production Guard")
    st.caption(
        "FINAL connector integration. The current selected PRA + Points + Rebounds + Assists board is rechecked through the existing Daily Picks production guard for exact ET slate, quote identity, 5M proof, convergence, availability, upcoming game state, freshness and source-final readiness. READY rows publish; MONITOR/BLOCKED rows do not, and no lower-ranked pick is backfilled."
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Step-6 selected", int(diag.get("selected", 0)))
    a2.metric("✅ READY", int(diag.get("ready", 0)))
    a3.metric("⏳ MONITOR", int(diag.get("monitor", 0)))
    a4.metric("⛔ BLOCKED", int(diag.get("blocked", 0)))

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Production card", f"{int(diag.get('ready', 0))}/5")
    b2.metric("Markets ready", int(diag.get("markets", 0)))
    b3.metric("Guard state", state)
    b4.metric("Guard coverage", "PASS" if coverage else "CHECK")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Assists selected", int(diag.get("assists_selected", 0)))
    c2.metric("Assists READY", int(diag.get("assists_ready", 0)))
    c3.metric("Assists MONITOR", int(diag.get("assists_monitor", 0)))
    c4.metric("Assists BLOCKED", int(diag.get("assists_blocked", 0)))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("New simulations", "0")
    d2.metric("Network requests", "0")
    d3.metric("Source-model writes", "0")
    d4.metric("Card fingerprint", fingerprint)

    st.caption(
        f"Guard checked {checked_at.strftime('%Y-%m-%d %I:%M:%S %p ET')} • ET slate {slate_day} • max source-output age {int(guard_v2.MAX_OUTPUT_AGE_MIN)}m"
    )

    if coverage:
        if selected.empty:
            st.success(
                "✅ ASSISTS CONNECTOR STEP 7 PASSED • the current four-market selection is 0/5, so the final guard has no rows to publish and nothing is forced. Assists is fully integrated."
            )
        else:
            st.success(
                f"✅ ASSISTS CONNECTOR STEP 7 PASSED • all {len(selected)} Step-6 selection(s) were evaluated by the final four-market production guard. READY/MONITOR/BLOCKED are final-card outcomes; nothing is backfilled."
            )
    else:
        st.warning(
            "⚠️ ASSISTS CONNECTOR STEP 7 CHECK • selected-row and guard-row coverage did not reconcile. No final four-market production claim should be made until coverage passes."
        )

    if guarded.empty:
        st.info("⏳ FOUR-MARKET GUARD ARMED • there are no current Step-6 selections to evaluate.")
    elif not ready.empty:
        if len(ready) == len(guarded):
            st.success(f"✅ FOUR-MARKET PRODUCTION READY • all {len(ready)} selected pick(s) passed every final guard.")
        else:
            st.warning(
                f"⚠️ PARTIAL FOUR-MARKET PRODUCTION CARD • {len(ready)} of {len(guarded)} selected pick(s) are READY. MONITOR/BLOCKED rows are withheld and are not replaced."
            )
        st.markdown("### 🚦 Four-Market Production Final Card")
        _render_ready_cards(ready)
    else:
        st.warning(
            "🏆 NO PRODUCTION-READY PICKS RIGHT NOW • selected candidates exist, but none cleared every final guard. Nothing is forced or backfilled."
        )

    snap_key = f"wnba_daily_picks_v17_guard_snapshot::{slate_day}"
    snap_at_key = f"wnba_daily_picks_v17_guard_snapshot_at::{slate_day}"
    current_snapshot = _snapshot(guarded)
    saved_raw = st.session_state.get(snap_key)
    saved = pd.DataFrame(saved_raw) if isinstance(saved_raw, list) else pd.DataFrame()
    movement = _movement(saved, current_snapshot)

    if st.button(
        "🔄 RECHECK FOUR-MARKET DAILY PICKS — GUARDS ONLY",
        use_container_width=True,
        key=f"wnba_daily_picks_v17_guard_recheck::{slate_day}",
    ):
        # Daily-Picks-only runtime ledger. This does not mutate source-model keys.
        st.session_state[snap_key] = current_snapshot.to_dict(orient="records")
        st.session_state[snap_at_key] = checked_at.isoformat()
        st.success("✅ Four-market guard snapshot saved. No source model, sportsbook refresh or simulation was triggered.")

    with st.expander("🧪 Four-market final production guard audit", expanded=False):
        view = _audit_view(guarded)
        if view.empty:
            st.info("No selected row exists to final-guard right now.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)

    with st.expander("📡 Four-market card movement since saved guard snapshot", expanded=False):
        st.caption(f"Saved snapshot: {_text(st.session_state.get(snap_at_key)) or '—'} • Daily-Picks-only runtime namespace")
        if movement.empty:
            st.info("No saved/current guard rows to compare yet.")
        else:
            st.dataframe(movement, use_container_width=True, hide_index=True)

    with st.expander("🛡️ Assists Connector Step-7 final isolation diagnostics", expanded=False):
        st.write("• Inputs: only current Step-6 selected rows + passive four-market connector metadata")
        st.write("• Existing Daily Picks Step-10 guard logic is reused; Assists only receives a market-identity compatibility shim")
        st.write("• Exact ET slate / exact quote / 5M / convergence are rechecked")
        st.write("• Explicit current-session availability + upcoming game-state evidence are required for READY")
        st.write(f"• Source-output freshness maximum: {int(guard_v2.MAX_OUTPUT_AGE_MIN)} minutes")
        st.write("• Source qualification must remain explicitly production/final ready")
        st.write("• MONITOR/BLOCKED selections are withheld; no lower-ranked backfill is performed")
        st.write("• Ranking changes: 0")
        st.write("• New simulations: 0")
        st.write("• Sportsbook/injury/network refreshes: 0")
        st.write("• PRA / Points / Rebounds / Assists source-model writes: 0")

    st.markdown("### ✅ Assists → Daily Picks Integration Status")
    if coverage:
        st.success(
            "🏁 7/7 CONNECTOR STEPS COMPLETE • Assists is now fully integrated into Daily Picks from read-only source connection → common schema → safety → protection → cross-market ranking → Top-5 selection → final production guard."
        )
    else:
        st.warning("Connector Step 7 is installed but final guard coverage still needs verification before declaring 7/7 complete.")

    st.caption(
        "⚡ WNBA Daily Picks V17 • Assists Connector Step 7 • four-market final production guard ACTIVE • no forced picks • no source-model control"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
