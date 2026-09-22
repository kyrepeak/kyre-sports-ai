"""Kyre Sports AI — NFL Moneyline V1 foundation.

Step 1 only. Reuses the verified NFL V1 slate and adds a strict pregame clock
boundary, season-phase awareness and a dedicated Moneyline workspace. No
sportsbook price, win probability, fair odds, edge, Monte Carlo, qualification,
ranking or recommendation is produced.

This module is NFL-only and does not import MLB or WNBA production code.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation

ET = foundation.ET
MODEL_VERSION = "NFL MONEYLINE V1 • STEP 1 VERIFIED PREGAME FOUNDATION"


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _scheduled_tip(day_str: str, tip_et: str):
    """Parse the already-verified NFL slate clock. Missing/TBD fails closed."""
    text = _safe(tip_et)
    if not text or text.upper() == "TBD":
        return pd.NaT
    clean = text.replace(" ET", "").replace(" EDT", "").replace(" EST", "").strip()
    try:
        ts = pd.to_datetime(f"{day_str} {clean}")
        if ts.tzinfo is None:
            return ts.tz_localize(ET)
        return ts.tz_convert(ET)
    except Exception:
        return pd.NaT


def _pregame_partition(games: pd.DataFrame, day_str: str, now_et=None):
    """Fail-closed pregame guard: provider state must be pre and tip must be future."""
    if games is None or games.empty:
        return pd.DataFrame(), pd.DataFrame()

    now_et = now_et if now_et is not None else pd.Timestamp.now(tz=ET)
    eligible = []
    locked = []

    for _, src in games.iterrows():
        row = src.to_dict()
        state = _safe(row.get("state"), "unknown").lower()
        tip = _scheduled_tip(day_str, row.get("tip_et"))
        reason = ""

        if state != "pre":
            reason = f"provider state = {state}"
        elif pd.isna(tip):
            reason = "scheduled tip unavailable"
        elif tip <= now_et:
            reason = "scheduled tip has passed"

        row["scheduled_tip_guard_et"] = "—" if pd.isna(tip) else tip.strftime("%Y-%m-%d %I:%M %p ET")
        row["exclusion_reason"] = reason
        if reason:
            locked.append(row)
        else:
            eligible.append(row)

    return pd.DataFrame(eligible), pd.DataFrame(locked)


def _record_value(value) -> str:
    return _safe(value, "—")


def _team_identity(row, side: str) -> str:
    team = _safe(row.get(f"{side}_team"), side.title())
    abbr = _safe(row.get(f"{side}_abbr"), "TEAM")
    logo = _safe(row.get(f"{side}_logo"))
    record = _record_value(row.get(f"{side}_record"))
    logo_html = foundation._team_logo(logo, abbr, team)
    return (
        '<div class="knfl-ml-team">'
        f'{logo_html}'
        '<div class="knfl-ml-teamcopy">'
        f'<b>{escape(team)}</b><span>{escape(record)}</span>'
        '</div></div>'
    )


def _game_foundation_card(row) -> str:
    away = _safe(row.get("away_team"), "Away")
    home = _safe(row.get("home_team"), "Home")
    phase = _safe(row.get("season_type"), "NFL")
    tip = _safe(row.get("tip_et"), "TBD")
    venue = _safe(row.get("venue"), "Venue TBD")
    broadcast = _safe(row.get("broadcast"), "—")
    return f'''
    <article class="knfl-ml-game">
      <div class="knfl-ml-top"><span>{escape(phase)}</span><span>✅ PREGAME ELIGIBLE</span></div>
      {_team_identity(row, 'away')}
      <div class="knfl-ml-at">AT</div>
      {_team_identity(row, 'home')}
      <div class="knfl-ml-meta">
        <span>🕒 {escape(tip)}</span>
        <span>🏟️ {escape(venue)}</span>
        <span>📺 {escape(broadcast)}</span>
      </div>
      <div class="knfl-ml-lock">MODEL WIN PROBABILITY: OFF • SPORTSBOOK PRICE: OFF • MONTE CARLO: OFF</div>
    </article>
    '''


_CSS = r'''
<style>
.knfl-ml-shell{border:1px solid #2c5575;border-radius:20px;background:linear-gradient(180deg,#0c1725,#08111d);padding:17px 18px;margin:7px 0 16px}
.knfl-ml-title{font-size:1.45rem;font-weight:950;color:#f8fafc}.knfl-ml-title span{color:#7ff2c2}.knfl-ml-sub{color:#8ea4ba;font-size:.76rem;line-height:1.5;margin-top:5px}
.knfl-ml-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.knfl-ml-chip{border:1px solid #2b516f;border-radius:999px;background:#091a29;color:#9bd9f5;padding:5px 8px;font-size:.58rem;font-weight:900}
.knfl-ml-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin-top:11px}.knfl-ml-game{border:1px solid #284a66;border-radius:15px;background:#081522;padding:12px}.knfl-ml-top{display:flex;justify-content:space-between;gap:8px;color:#7ff2c2;font-size:.54rem;font-weight:950}.knfl-ml-team{display:flex;align-items:center;gap:9px;margin-top:10px}.knfl-ml-teamcopy{display:flex;flex-direction:column;min-width:0}.knfl-ml-teamcopy b{color:#f4f8ff;font-size:.82rem}.knfl-ml-teamcopy span{color:#7890a8;font-size:.56rem;margin-top:2px}.knfl-ml-at{color:#60798f;font-size:.46rem;font-weight:950;margin-left:54px}.knfl-ml-meta{display:grid;gap:3px;border-top:1px solid #193149;margin-top:9px;padding-top:7px;color:#768ea5;font-size:.54rem}.knfl-ml-lock{margin-top:8px;border:1px dashed #334c63;border-radius:8px;padding:6px;color:#71879b;font-size:.48rem;font-weight:850}.knfl-ml-empty{border:1px dashed #36536f;border-radius:12px;padding:15px;color:#8ea4ba;background:#091522}
@media(max-width:700px){.knfl-ml-grid{grid-template-columns:1fr}.knfl-ml-shell{padding:14px}}
</style>
'''


def render_nfl_moneyline_hub():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="knfl-ml-shell">'
        '<div class="knfl-ml-title">💰 NFL Moneyline <span>Command Center</span></div>'
        '<div class="knfl-ml-sub">Step 1 foundation • verified NFL slate → strict pregame clock guard → season-phase awareness → team identity/record. No probability or sportsbook math is enabled yet.</div>'
        '<div class="knfl-ml-chips">'
        '<span class="knfl-ml-chip">STEP 1</span><span class="knfl-ml-chip">PREGAME ONLY</span>'
        '<span class="knfl-ml-chip">FAIL CLOSED</span><span class="knfl-ml-chip">MODEL OFF</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(ET).date()

    selected = st.date_input(
        "📅 Moneyline slate date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_moneyline_v1_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("💰 Verifying NFL Moneyline pregame foundation…"):
        schedule, diag = foundation.load_nfl_slate(day_str)
        pregame, excluded = _pregame_partition(schedule, day_str, now_et=now_et)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "FOUNDATION")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule verification failed. Moneyline production remains locked and no games are fabricated. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        return

    if schedule.empty:
        st.info("No verified NFL games were returned for this ET date. Moneyline remains locked.")
        return

    st.success(f"✅ STEP 1A PASSED • verified NFL slate loaded for {day_str}.")

    phases = sorted({_safe(x) for x in schedule.get("season_type", pd.Series(dtype=str)).tolist() if _safe(x)})
    if len(phases) == 1 and phases[0] == "Preseason":
        st.warning(
            "⚠️ PRESEASON SLATE • future Moneyline projection will require quarterback rotation, starter-rest and depth-chart context before any win probability can be enabled."
        )
    elif phases:
        st.caption("Season phase: " + " / ".join(phases))

    if len(pregame):
        st.success(f"✅ STEP 1B PASSED • {len(pregame)} game(s) are provider-safe and still before scheduled kickoff.")
    else:
        st.info("ℹ️ No games remain pregame-eligible. Live/final/passed-tip/unknown-tip games stay locked out.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from pregame Moneyline", expanded=False):
            cols = [c for c in ["away_team", "home_team", "tip_et", "state", "status", "exclusion_reason"] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    st.markdown("### 🧩 Pregame Moneyline Foundation")
    if pregame.empty:
        st.markdown('<div class="knfl-ml-empty">No pregame-eligible NFL game is available for this date.</div>', unsafe_allow_html=True)
    else:
        cards = "".join(_game_foundation_card(row) for _, row in pregame.iterrows())
        st.markdown(f'<div class="knfl-ml-grid">{cards}</div>', unsafe_allow_html=True)

    st.markdown("### 🔒 Moneyline production locks")
    locks = pd.DataFrame([
        {"Layer": "Verified NFL slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Season-phase guard", "State": "READY" if phases else "CHECK"},
        {"Layer": "QB / depth-chart verification", "State": "LOCKED — NEXT"},
        {"Layer": "Current injuries / availability", "State": "LOCKED — NEXT"},
        {"Layer": "Sportsbook Moneyline prices", "State": "LOCKED"},
        {"Layer": "Team-strength win model", "State": "LOCKED"},
        {"Layer": "Monte Carlo", "State": "LOCKED"},
        {"Layer": "No-vig edge / EV / final grading", "State": "LOCKED"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)

    st.session_state["nfl_moneyline_v1_day"] = day_str
    st.session_state["nfl_moneyline_v1_schedule"] = schedule.to_dict("records")
    st.session_state["nfl_moneyline_v1_pregame"] = pregame.to_dict("records") if not pregame.empty else []
    st.session_state["nfl_moneyline_v1_foundation_ready"] = bool(len(schedule) and len(pregame))

    st.caption(
        "Step 1 performs zero sportsbook requests, zero projection math and zero simulations. "
        "Next layer: quarterback/depth-chart + injury availability verification."
    )


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
