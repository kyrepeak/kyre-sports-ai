"""WNBA Spread V1.2 — clock-safe pregame eligibility guard.

Preserves the verified V1.0/V1.1 foundation and fixes the remaining pregame
boundary bug: a provider can briefly keep a game labeled UPCOMING after the
scheduled tip. Pregame eligibility therefore cannot rely on provider status
alone.

V1.2 requires BOTH:
- a non-live/non-final/non-delayed provider state; and
- a verified scheduled tip that is still in the future in America/New_York.

If the scheduled tip has passed, the game is excluded even when a cached provider
row still says UPCOMING. If the tip cannot be parsed, the game fails closed.

No sportsbook spread, projected margin, cover probability, or Monte Carlo math is
introduced here.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import wnba_spread_hub_v10 as base

MODEL_VERSION = "WNBA SPREAD V1.2 • CLOCK-SAFE PREGAME ELIGIBILITY"
ET = base.ET

_BLOCKED_TEXT = (
    "FINAL", "LIVE", "IN PROGRESS", "IN_PROGRESS", "HALFTIME", "END OF",
    "POSTPONED", "POSTPONE", "CANCEL", "SUSPENDED", "DELAYED",
)


def _combined_status(row) -> str:
    return " | ".join(
        str(row.get(c) or "").upper().strip()
        for c in ("status", "status_text")
        if str(row.get(c) or "").strip()
    )


def _scheduled_tip_et(row):
    """Return an aware Eastern timestamp for the verified schedule tip."""
    day = str(row.get("game_date") or "").strip()
    tip = str(row.get("first_tip_et") or "").strip()
    if not day or not tip or tip.upper() in {"TBD", "TBA", "—", "NONE", "NAN"}:
        return pd.NaT

    # first_tip_et is normally like "10:00 PM ET". Remove only the display
    # suffix; the schedule's game_date is already the reconciled Eastern date.
    clean = re.sub(r"\s+ET$", "", tip, flags=re.IGNORECASE).strip()
    raw = clean if re.search(r"\d{4}-\d{2}-\d{2}", clean) else f"{day} {clean}"
    ts = pd.to_datetime(raw, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    try:
        if ts.tzinfo is None:
            ts = ts.tz_localize(ET)
        else:
            ts = ts.tz_convert(ET)
    except Exception:
        return pd.NaT
    return ts


def _eligibility_frame(schedule: pd.DataFrame, now_et=None) -> pd.DataFrame:
    if schedule is None or schedule.empty:
        cols = list(getattr(schedule, "columns", [])) + ["eligibility", "exclusion_reason", "scheduled_tip_guard_et"]
        return pd.DataFrame(columns=list(dict.fromkeys(cols)))

    now_et = now_et or pd.Timestamp.now(tz=ET)
    if getattr(now_et, "tzinfo", None) is None:
        now_et = now_et.tz_localize(ET)
    else:
        now_et = now_et.tz_convert(ET)

    rows = []
    for _, row in schedule.iterrows():
        obj = row.to_dict()
        status = _combined_status(row)
        tip = _scheduled_tip_et(row)
        reason = ""

        if any(token in status for token in _BLOCKED_TEXT) or re.search(r"(^|\|\s*)(Q[1-4]|OT|[1-4](ST|ND|RD|TH))\b", status):
            reason = "provider state is not pregame"
        elif pd.isna(tip):
            reason = "scheduled tip is unverified"
        elif now_et >= tip:
            reason = "scheduled tip has passed"

        obj["eligibility"] = "EXCLUDED" if reason else "PREGAME"
        obj["exclusion_reason"] = reason
        obj["scheduled_tip_guard_et"] = "—" if pd.isna(tip) else tip.strftime("%Y-%m-%d %I:%M %p ET")
        rows.append(obj)

    return pd.DataFrame(rows)


def _pregame_schedule(schedule: pd.DataFrame, now_et=None) -> pd.DataFrame:
    checked = _eligibility_frame(schedule, now_et=now_et)
    if checked.empty:
        return checked
    return checked.loc[checked["eligibility"].eq("PREGAME")].copy().reset_index(drop=True)


def _excluded_schedule(schedule: pd.DataFrame, now_et=None) -> pd.DataFrame:
    checked = _eligibility_frame(schedule, now_et=now_et)
    if checked.empty:
        return checked
    return checked.loc[checked["eligibility"].eq("EXCLUDED")].copy().reset_index(drop=True)


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.2 foundation • verified slate → provider-state + scheduled-tip clock guard → team context → current availability. "
        "A stale UPCOMING label cannot keep a game pregame-eligible after tip."
    )

    default_day = st.session_state.get("wnba_spread_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Spread slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_spread_v1_date_picker",
    )
    st.session_state["wnba_spread_v1_date"] = selected
    day_str = base._day(selected)
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA spread slate + clock-safe pregame eligibility…"):
        schedule = base._schedule(day_str)
        pregame = _pregame_schedule(schedule, now_et=now_et)
        excluded = _excluded_schedule(schedule, now_et=now_et)

    teams = 0
    if not schedule.empty:
        team_ids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                team_ids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(team_ids)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "FOUNDATION")

    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ PREGAME ELIGIBILITY PASSED • {len(pregame)} game(s) are still before scheduled tip and provider-safe.")
    else:
        st.info("ℹ️ No games on this slate remain pregame-eligible. Passed-tip/live/final/uncertain-tip games are locked out.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from pregame production", expanded=True):
            cols = [c for c in [
                "away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et",
                "status", "status_text", "exclusion_reason",
            ] if c in excluded.columns]
            show = excluded[cols].copy() if cols else excluded.copy()
            st.dataframe(show, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = base.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified',0) or 0)}/{int(cdiag.get('teams',teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))

    if state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

    with st.spinner("🩺 Verifying current team availability for pregame-eligible games…"):
        av = base._availability_snapshot(day_str, pregame)
    av_map = {str(r.get("game_id") or ""): r.to_dict() for _, r in av.iterrows()} if not av.empty else {}

    covered = int(pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    expected_coverage = int(2 * len(pregame))
    unverified = int(pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Availability coverage", f"{covered}/{expected_coverage}" if expected_coverage else "0/0")
    a2.metric("Hard OUT", int(pd.to_numeric(av.get("hard_out", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a3.metric("Status uncertain", int(pd.to_numeric(av.get("uncertain", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a4.metric("Unverified players", unverified)

    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    if availability_ready:
        st.success("✅ STEP 3 PASSED • current availability coverage is complete for every pregame-eligible game.")
    elif expected_coverage == 0:
        st.info("ℹ️ STEP 3 NOT APPLICABLE • there are no remaining pregame-eligible games on this slate.")
    else:
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future spread production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Game Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            base._render_game_context(game, contexts, av_map)

    st.markdown("### 🔒 Spread Production Locks")
    foundation_ready = bool(len(pregame) and state == "VERIFIED" and availability_ready)
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook spread line", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "Projected game margin", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "Cover probability / fair spread", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.2 still makes no spread pick. Provider status and the scheduled Eastern tip clock must BOTH say the game is pregame-safe."
    )


__all__ = [
    "MODEL_VERSION", "_scheduled_tip_et", "_eligibility_frame",
    "_pregame_schedule", "_excluded_schedule", "render_wnba_spread_hub",
]
