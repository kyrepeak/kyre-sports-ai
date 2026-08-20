"""WNBA Assists V2 — Step 2 verified daily WNBA slate.

Steps 1–2 only. Step 2 may read schedule feeds, but it deliberately does not
load rosters, injuries, assist stats, sportsbook lines, projections or Monte
Carlo state. Existing PRA/Points/Rebounds/Daily Picks pages remain isolated.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from wnba_assists_schedule_v1 import load_verified_wnba_slate

MODEL_VERSION = "WNBA ASSISTS V2 • STEP 2 VERIFIED DAILY SLATE"
_ET = ZoneInfo("America/New_York")


def _layer_card(step: int, label: str, state: str, note: str = "") -> str:
    if "LIVE" in state:
        tone, border = "#6ee7b7", "rgba(52,211,153,.34)"
    elif "NEXT" in state:
        tone, border = "#67e8f9", "rgba(56,189,248,.30)"
    else:
        tone, border = "#94a3b8", "rgba(148,163,184,.22)"
    return f"""
    <div style="min-height:118px;padding:15px 16px;border:1px solid {border};border-radius:16px;
      background:linear-gradient(180deg,rgba(10,31,47,.98),rgba(7,24,38,.98));box-shadow:0 8px 24px rgba(0,0,0,.12);">
      <div style="color:#7f91aa;font-size:.65rem;font-weight:900;letter-spacing:.10em;text-transform:uppercase;">STEP {step}</div>
      <div style="margin-top:7px;color:#f8fafc;font-size:.90rem;font-weight:900;line-height:1.25;">{label}</div>
      <div style="margin-top:8px;color:{tone};font-size:.78rem;font-weight:950;">{state}</div>
      <div style="margin-top:6px;color:#7f91aa;font-size:.64rem;font-weight:700;line-height:1.35;">{note}</div>
    </div>"""


def _source_box(name: str, meta: dict, selected: int, role: str) -> str:
    ok = bool(meta.get("ok"))
    status = meta.get("status") or "—"
    tone = "#6ee7b7" if ok else "#fbbf24"
    border = "rgba(52,211,153,.34)" if ok else "rgba(251,191,36,.35)"
    state = "PASS" if ok else "CHECK"
    return f"""
    <div style="padding:12px 14px;border:1px solid {border};border-radius:14px;background:rgba(7,24,38,.94);min-height:104px;">
      <div style="color:{tone};font-weight:950;font-size:.78rem;">{name} • {state}</div>
      <div style="margin-top:6px;color:#dbeafe;font-weight:850;font-size:.75rem;">{selected} same-day game(s)</div>
      <div style="margin-top:6px;color:#7f91aa;font-size:.66rem;font-weight:700;">HTTP {status} • {role}</div>
    </div>"""


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = load_verified_wnba_slate(slate_day)

    st.markdown(
        """
        <style>
        .ks-ast-hero{padding:25px 27px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;
          background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);}
        .ks-ast-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;}
        .ks-ast-title{margin-top:9px;color:#f8fafc;font-size:2.05rem;line-height:1.08;font-weight:950;}
        .ks-ast-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.62;font-weight:650;}
        .ks-ast-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);
          border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="ks-ast-hero">
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 2</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Step 2 adds only the verified same-day WNBA schedule. Games are selected by Eastern calendar date so UTC rollover cannot pull yesterday or tomorrow into the slate. No roster, injury, assists, sportsbook, projection or simulation layer exists yet.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">🧱 Steps 1–2 only</span>
          <span class="ks-ast-chip">📡 schedule requests only</span>
          <span class="ks-ast-chip">🚫 zero simulations</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("### 📅 Step 2 — Verified Daily WNBA Slate")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected date", slate_day)
    c2.metric("Verification", slate.get("verification", "CHECK"))
    c3.metric("Games found", int(slate.get("games_found", 0)))
    c4.metric("WNBA teams validated", int(slate.get("teams_validated", 0)))

    s1, s2 = st.columns(2)
    with s1:
        st.markdown(_source_box("WNBA official CDN", slate.get("wnba_meta", {}), int(slate.get("wnba_games", 0)), "authoritative schedule"), unsafe_allow_html=True)
    with s2:
        st.markdown(_source_box("ESPN WNBA daily", slate.get("espn_meta", {}), int(slate.get("espn_games", 0)), "independent confirmation / fallback"), unsafe_allow_html=True)

    verification = slate.get("verification")
    if verification == "VERIFIED":
        st.success(f"✅ STEP 2 PASSED • {slate.get('games_found', 0)} WNBA game(s) belong to the {slate_day} ET slate. Official WNBA schedule is authoritative; ESPN confirms {slate.get('espn_confirmed', 0)} pairing(s).")
    elif verification == "FALLBACK":
        st.warning(f"⚠️ STEP 2 FALLBACK • Official WNBA schedule transport is unavailable, so {slate.get('games_found', 0)} ESPN same-day game(s) are displayed. Step 3 should remain locked until the official source returns.")
    elif verification == "NO GAMES":
        st.info(f"ℹ️ STEP 2 VERIFIED EMPTY • No WNBA games were returned for {slate_day} ET.")
    else:
        st.error("⛔ STEP 2 CHECK • The same-day slate could not be verified. No downstream Assists modeling should unlock.")

    games = slate.get("games", [])
    if games:
        st.markdown("#### 🏀 Verified WNBA games")
        table_rows = []
        for g in games:
            table_rows.append({
                "Away": g.get("away"),
                "Home": g.get("home"),
                "Tip (ET)": g.get("tip_et"),
                "Venue": g.get("venue"),
                "Status": g.get("status"),
                "Verified Source": g.get("source"),
                "ESPN Confirmed": "YES" if g.get("espn_confirmed") else "—",
            })
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

    if st.button("🔄 RECHECK ASSISTS WNBA SCHEDULE", use_container_width=True, key="assists_step2_schedule_recheck"):
        load_verified_wnba_slate.clear()
        st.rerun()

    st.caption(f"Checked: {slate.get('checked_at_et', '—')} • Step 2 source: {slate.get('source', 'NONE')} • exact ET-date filtering active")

    st.markdown("### 🧱 Assists Build Order — Current")
    layers = [
        (1, "Isolated Assists page", "✅ LIVE", "Display shell preserved"),
        (2, "Verified daily WNBA slate", "✅ LIVE" if verification in {"VERIFIED", "NO GAMES"} else "⚠️ CHECK", "Exact ET date + games"),
        (3, "Current rosters + injuries/status", "➡️ NEXT" if verification in {"VERIFIED", "NO GAMES"} else "🔒 LOCKED", "No unavailable player may enter modeling"),
        (4, "Projected minutes + rotation", "🔒 LOCKED", "Assist opportunity starts with court time"),
        (5, "Assist role + ball-handling / usage", "🔒 LOCKED", "Primary/secondary creation responsibility"),
        (6, "Recent + season assist form", "🔒 LOCKED", "Minute-normalized, regression protected"),
        (7, "Potential assists / passes / creation chances", "🔒 LOCKED", "Opportunity layer before conversion"),
        (8, "Teammate shot-making + lineup conversion", "🔒 LOCKED", "Who finishes the created chances"),
        (9, "Opponent assist environment", "🔒 LOCKED", "Opponent scheme + assists allowed"),
        (10, "Position matchup — Guard / Wing / Big", "🔒 LOCKED", "Role-sensitive matchup context"),
        (11, "Pace + expected possession volume", "🔒 LOCKED", "Possession opportunity adjustment"),
        (12, "Player vs opponent assist history", "🔒 LOCKED", "Descriptive H2H context"),
        (13, "Exact SportsGameOdds assist lines", "🔒 LOCKED", "Exact book / line / side only"),
        (14, "Same-book no-vig", "🔒 LOCKED", "Market math stays separate from projection"),
        (15, "Market-independent assist projection", "🔒 LOCKED", "Expected assists before market grading"),
        (16, "Uncertainty + distribution calibration", "🔒 LOCKED", "Discrete assist count distribution"),
        (17, "5M Monte Carlo + convergence / sensitivity", "🔒 LOCKED", "Actual simulations only"),
        (18, "Line-specific O/U probability + fair odds", "🔒 LOCKED", "Threshold probabilities from model distribution"),
        (19, "Model-vs-market edge + EV", "🔒 LOCKED", "Exact posted price grading"),
        (20, "Risk-adjusted qualification + Top 5", "🔒 LOCKED", "Never force five"),
    ]
    for start in range(0, len(layers), 4):
        cols = st.columns(4, gap="small")
        for col, item in zip(cols, layers[start:start + 4]):
            with col:
                st.markdown(_layer_card(*item), unsafe_allow_html=True)

    with st.expander("🛡️ Step-2 methodology / diagnostics", expanded=False):
        st.write("• ET slate date is derived from America/New_York, not server UTC.")
        st.write("• Official WNBA CDN is authoritative when available.")
        st.write("• ESPN is confirmation/fallback only; it cannot create extra games when WNBA official rows exist.")
        st.write("• Adjacent UTC dates are filtered out after each game time is converted to Eastern Time.")
        st.write("• Current roster / injury requests: 0")
        st.write("• Assist-stat requests: 0")
        st.write("• Sportsbook requests: 0")
        st.write("• Monte Carlo runs: 0")
        st.write("• PRA / Points / Rebounds / Daily Picks production imports: 0")
        st.write(f"• Invalid team rows: {slate.get('invalid_team_rows', 0)}")

    st.caption("⚡ WNBA Assists V2 Step 2 • verified same-day schedule only • Steps 1–2 preserved • no roster/injury/projection/market/Monte Carlo yet")


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
