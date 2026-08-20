"""WNBA Daily Picks V10 — Step 10 final production guard + recheck.

Steps 1-9 remain frozen. This wrapper renders the existing V9 page, recomputes the
same read-only pipeline from current Streamlit session payloads, then applies the
strict Step-10 production-readiness guard. It launches no simulations, performs no
sportsbook/model/network refresh, and writes no PRA/Points/Rebounds production
state.

The optional RECHECK button stores only a namespaced Daily-Picks runtime snapshot
for movement comparison; it never mutates any source-model key.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v9 as v9
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_standardizer_v1 as standardizer
import wnba_daily_picks_safety_v1 as safety
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking
import wnba_daily_picks_selection_v1 as selection
import wnba_daily_picks_guard_v1 as guard

MODEL_VERSION = "WNBA DAILY PICKS V10 • STEP 10 PRODUCTION GUARD"
_ET = ZoneInfo("America/New_York")
_SNAPSHOT_KEY = "wnba_daily_picks_v10_guard_snapshot"
_SNAPSHOT_AT_KEY = "wnba_daily_picks_v10_guard_snapshot_at"


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


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _state_metric(diag: dict) -> str:
    if not diag.get("selected"):
        return "ARMED"
    if diag.get("ready") and not diag.get("monitor") and not diag.get("blocked"):
        return "READY"
    if diag.get("ready"):
        return "PARTIAL"
    if diag.get("blocked") and not diag.get("monitor"):
        return "BLOCKED"
    return "MONITOR"


def _audit_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Daily rank", "Guard state", "Market", "Player", "Team", "Opponent", "Side",
        "Line", "Book", "Posted odds", "Qualification state", "Safety state",
        "Finalization gate", "Connector gate", "Slate recheck", "Exact quote gate",
        "Simulation recheck", "Convergence recheck", "Availability recheck",
        "Game-state recheck", "Freshness recheck", "Guard reasons",
        "Guard checked at ET", "Guard fingerprint",
    ]
    return frame[[c for c in keep if c in frame.columns]].copy()


def _snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[
            "identity", "Daily rank", "Market", "Player", "Team", "Opponent", "Side",
            "Line", "Book", "Posted odds", "Guard state", "Guard fingerprint",
        ])
    rows = []
    for _, row in frame.iterrows():
        identity = "::".join([
            _norm(row.get("Market")), _norm(row.get("Player")), _norm(row.get("Team")),
            _norm(row.get("Opponent")), _norm(row.get("Side")),
        ])
        rows.append({
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
    return pd.DataFrame(rows)


def _movement(previous: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    prev = previous.copy() if isinstance(previous, pd.DataFrame) else pd.DataFrame()
    cur = current.copy() if isinstance(current, pd.DataFrame) else pd.DataFrame()
    if prev.empty and cur.empty:
        return pd.DataFrame(columns=["Player", "Market", "Movement", "Before", "Now"])
    if prev.empty:
        return pd.DataFrame([
            {
                "Player": r.get("Player", "—"), "Market": r.get("Market", "—"),
                "Movement": "NEW", "Before": "—",
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
            movement = "NEW"
        elif b is None:
            movement = "REMOVED"
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
            movement = " + ".join(changes) if changes else "UNCHANGED"
        ref = b if b is not None else a
        before = "—" if a is None else f"{a.get('Side','—')} {a.get('Line','—')} • {a.get('Book','—')} {a.get('Posted odds','—')} • {a.get('Guard state','—')}"
        now = "—" if b is None else f"{b.get('Side','—')} {b.get('Line','—')} • {b.get('Book','—')} {b.get('Posted odds','—')} • {b.get('Guard state','—')}"
        records.append({
            "Player": ref.get("Player", "—") if ref is not None else "—",
            "Market": ref.get("Market", "—") if ref is not None else "—",
            "Movement": movement,
            "Before": before,
            "Now": now,
        })
    return pd.DataFrame(records)


def _render_ready_cards(ready: pd.DataFrame):
    """Reuse the frozen Step-9 card design but change presentation labels only."""
    if ready is None or ready.empty:
        return
    original = v9._card_html

    def production_card(row: pd.Series) -> str:
        html = original(row)
        html = html.replace("STEP-9 SELECTED", "✅ PRODUCTION READY")
        html = html.replace("STEP 10 GUARD PENDING", "GUARD PASSED")
        return html

    try:
        v9._card_html = production_card
        v9._render_cards(ready)
    finally:
        v9._card_html = original


def _build_pipeline(slate_day: str):
    pra = pra_feed.status(slate_day)
    points = points_feed.status(slate_day)
    rebounds = rebounds_feed.status(slate_day)
    feeds = {"PRA": pra, "POINTS": points, "REBOUNDS": rebounds}
    common = standardizer.normalize_all(slate_day)
    audit = safety.evaluate(common, slate_day, feeds=feeds)
    protected = protection.annotate(audit)
    ranked = ranking.rank_candidates(protected)
    selected, skipped = selection.select_top5(ranked)
    guarded = guard.evaluate(selected, slate_day, feeds=feeds)
    ready = guard.ready_rows(guarded)
    return feeds, selected, guarded, ready, skipped


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Render Steps 1-9 exactly as frozen in V9 first.
    v9.render_wnba_daily_picks_hub(section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    checked_at = datetime.now(_ET)
    feeds, selected, guarded, ready, skipped = _build_pipeline(slate_day)
    gdiag = guard.diagnostics(guarded)
    fingerprint = guard.card_fingerprint(guarded)
    state = _state_metric(gdiag)

    st.markdown("---")
    st.markdown("## 🛡️ Step 10 — Final Production-Ready Guard")
    st.caption(
        "Final card guard only. Step 10 rechecks the current ET slate, exact quote, 5M simulation proof, "
        "convergence, availability, upcoming game state, freshness and source-final readiness. It never "
        "reruns or modifies PRA, Points or Rebounds and it never backfills a held pick."
    )

    row1 = st.columns(4, gap="small")
    row1[0].metric("Step-9 selected", int(gdiag.get("selected", 0)))
    row1[1].metric("✅ READY", int(gdiag.get("ready", 0)))
    row1[2].metric("⏳ MONITOR", int(gdiag.get("monitor", 0)))
    row1[3].metric("⛔ BLOCKED", int(gdiag.get("blocked", 0)))
    row2 = st.columns(4, gap="small")
    row2[0].metric("Production card", f"{int(gdiag.get('ready', 0))}/5")
    row2[1].metric("Markets ready", int(gdiag.get("markets", 0)))
    row2[2].metric("Guard state", state)
    row2[3].metric("Max output age", f"{int(guard.MAX_OUTPUT_AGE_MIN)}m")
    row3 = st.columns(4, gap="small")
    row3[0].metric("New simulations", 0)
    row3[1].metric("Python network", 0)
    row3[2].metric("Source-model writes", 0)
    row3[3].metric("Card fingerprint", fingerprint)

    st.caption(f"Guard checked: {checked_at.strftime('%Y-%m-%d %I:%M:%S %p ET')} • ET slate {slate_day}")

    if guarded.empty:
        st.info(
            "⏳ PRODUCTION GUARD ARMED • no Step-9 selections exist yet. Run source models only from their own "
            "pages; Daily Picks will re-evaluate automatically when same-day outputs exist."
        )
    elif not ready.empty:
        if len(ready) == len(guarded):
            st.success(f"✅ PRODUCTION READY • {len(ready)} selection(s) passed every Step-10 final guard.")
        else:
            st.warning(
                f"⚠️ PARTIAL PRODUCTION CARD • {len(ready)} of {len(guarded)} Step-9 selection(s) are READY. "
                "MONITOR/BLOCKED rows are not published as final picks."
            )
        st.markdown("### 🚦 Production Final Card")
        _render_ready_cards(ready)
    else:
        st.warning(
            "🏆 NO PRODUCTION-READY PICKS RIGHT NOW • Step-9 candidates exist, but none cleared every final "
            "freshness / availability / upcoming-game / source-finalization guard. Nothing is forced."
        )

    current_snapshot = _snapshot(guarded)
    saved_raw = st.session_state.get(_SNAPSHOT_KEY)
    saved = pd.DataFrame(saved_raw) if isinstance(saved_raw, list) else pd.DataFrame()
    movement = _movement(saved, current_snapshot)

    if st.button("🔄 RECHECK DAILY PICKS — GUARDS ONLY", use_container_width=True, key="wnba_daily_picks_v10_recheck"):
        # Namespaced Daily-Picks-only runtime ledger. No production model key is touched.
        st.session_state[_SNAPSHOT_KEY] = current_snapshot.to_dict(orient="records")
        st.session_state[_SNAPSHOT_AT_KEY] = checked_at.isoformat()
        st.success("✅ Guard snapshot saved. No source model, simulation or sportsbook refresh was triggered.")

    with st.expander("🧪 Step-10 production guard audit", expanded=False):
        audit_view = _audit_display(guarded)
        if audit_view.empty:
            st.caption("No Step-9 selections exist to audit yet.")
        else:
            st.dataframe(audit_view, use_container_width=True, hide_index=True)

    with st.expander("📡 Card movement since saved Daily Picks guard snapshot", expanded=False):
        saved_at = _text(st.session_state.get(_SNAPSHOT_AT_KEY)) or "—"
        st.caption(f"Saved guard snapshot: {saved_at} • runtime-only Daily Picks namespace")
        if movement.empty:
            st.caption("No saved/current card rows to compare yet.")
        else:
            st.dataframe(movement, use_container_width=True, hide_index=True)

    with st.expander("🛡️ Step-10 methodology / isolation diagnostics", expanded=False):
        st.write("• Step 10 consumes only the current Step-9 selected rows + passive feed metadata")
        st.write("• No lower-ranked candidate is backfilled when a selected row is MONITOR/BLOCKED")
        st.write("• Exact ET slate, quote/projection identity, 5M proof and convergence are rechecked")
        st.write("• Explicit current-session availability and UPCOMING game-state evidence are required for READY")
        st.write(f"• Actual source-output age is capped at {int(guard.MAX_OUTPUT_AGE_MIN)} minutes when timestamp proof exists")
        st.write("• Source qualification must be explicitly final-ready / production-ready (or a production-guard/final-card source)")
        st.write("• RECHECK writes only a namespaced Daily Picks runtime snapshot for movement comparison")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Python sportsbook/model network requests launched by Daily Picks: 0")
        st.write("• PRA / Points / Rebounds production-model writes by Daily Picks: 0")

    st.caption(
        "⚡ WNBA Daily Picks V10 Step 10 • Steps 1–9 preserved • final production guard ACTIVE • "
        "recheck is guard-only • no forced picks"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
