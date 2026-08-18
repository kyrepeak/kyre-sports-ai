"""WNBA Rebounds V1.0 — Step 1 verified daily slate.

This is the first isolated production layer for the WNBA Rebounds page.
It intentionally does ONE thing only: establish the correct Eastern-date WNBA
slate before roster, minutes, rebound-role, matchup, sportsbook or Monte Carlo
work is allowed to begin.

The schedule engine is shared read-only infrastructure from wnba_schedule_v25:
- WNBA official CDN is the preferred row source.
- ESPN WNBA daily and ESPN WNBA season independently cross-check the slate.
- Matchups reconcile by WNBA team identity.
- The selected calendar date is America/New_York.
- Provider failure is never disguised as a zero-game off day.

Frozen WNBA Points/PRA and MLB production math is not imported or modified.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_schedule_v25 as schedule

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA REBOUNDS V1.0 • STEP 1 VERIFIED SLATE"


def _today_et():
    return datetime.now(ET).date()


def _safe_day(value) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(ET).strftime("%Y-%m-%d")


def _int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _logo(team_id) -> str:
    try:
        return str(schedule.logo_url(_int(team_id)) or "")
    except Exception:
        return ""


def _game_card(row) -> str:
    away = escape(str(row.get("away_team") or "Away"))
    home = escape(str(row.get("home_team") or "Home"))
    venue = escape(str(row.get("venue") or "Venue TBD"))
    tip = escape(str(row.get("first_tip_et") or "TBD"))
    status = escape(str(row.get("status") or "UPCOMING"))
    away_logo = escape(_logo(row.get("away_team_id")), quote=True)
    home_logo = escape(_logo(row.get("home_team_id")), quote=True)

    away_img = f'<img src="{away_logo}" alt="{away}" />' if away_logo else '<div class="rb-logo-fallback">🏀</div>'
    home_img = f'<img src="{home_logo}" alt="{home}" />' if home_logo else '<div class="rb-logo-fallback">🏀</div>'

    return f"""
    <div class="rb-game-card">
      <div class="rb-card-top"><span>🏀 {status}</span><span>{tip}</span></div>
      <div class="rb-matchup">
        <div class="rb-team">{away_img}<div>{away}</div></div>
        <div class="rb-at">@</div>
        <div class="rb-team">{home_img}<div>{home}</div></div>
      </div>
      <div class="rb-venue">📍 {venue}</div>
    </div>
    """


def _render_game_cards(frame: pd.DataFrame):
    st.markdown(
        """
        <style>
        .rb-game-card{background:#071b2c;border:1px solid #24597a;border-radius:22px;padding:18px 18px 15px;margin:5px 0 12px;min-height:245px}
        .rb-card-top{display:flex;justify-content:space-between;color:#9eb2c6;font-size:.82rem;font-weight:800;letter-spacing:.08em}
        .rb-matchup{display:grid;grid-template-columns:1fr 34px 1fr;gap:8px;align-items:center;margin-top:18px}
        .rb-team{text-align:center;color:#f6f8fb;font-weight:800;font-size:1rem;line-height:1.2}
        .rb-team img{width:78px;height:78px;object-fit:contain;display:block;margin:0 auto 10px}
        .rb-logo-fallback{height:78px;display:flex;align-items:center;justify-content:center;font-size:42px;margin-bottom:10px}
        .rb-at{text-align:center;color:#7f96aa;font-size:1.3rem;font-weight:900}
        .rb-venue{border-top:1px solid #173c56;margin-top:18px;padding-top:12px;text-align:center;color:#92a8bb;font-size:.9rem}
        @media(max-width:700px){.rb-game-card{min-height:220px}.rb-team img{width:64px;height:64px}.rb-team{font-size:.92rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    rows = [row for _, row in frame.iterrows()]
    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(rows):
                continue
            with col:
                st.markdown(_game_card(rows[idx]), unsafe_allow_html=True)


def _source_diagnostics(diag: dict) -> pd.DataFrame:
    records = []
    for meta in (diag or {}).get("attempts", []) or []:
        records.append({
            "Source": str(meta.get("provider") or "Unknown"),
            "HTTP": meta.get("http"),
            "JSON": "YES" if bool(meta.get("json")) else "NO",
            "Selected games": _int(meta.get("selected_games")),
            "Valid season rows": _int(meta.get("valid_games")),
            "Rejected": _int(meta.get("rejected_games")),
            "Latency ms": meta.get("elapsed_ms"),
            "Status": "PASS" if bool(meta.get("request_ok")) and bool(meta.get("parse_ok", True)) else "CHECK",
        })
    return pd.DataFrame(records)


def render_wnba_rebounds_hub(section_header=None, status_info=None, _unused=None, h=None):
    st.caption("🏀 WNBA Rebounds V1.0 • isolated build • Step 1 schedule verification only • Points/PRA/MLB frozen")

    selected = st.date_input(
        "WNBA Rebounds slate date",
        value=_today_et(),
        key="wnba_rebounds_date",
    )
    day = _safe_day(selected)

    st.markdown(
        """
        <div style="border:1px solid #27658a;border-radius:24px;padding:20px 22px;background:#071b2c;margin:10px 0 16px">
          <div style="font-size:.72rem;letter-spacing:.15em;font-weight:800;color:#5dd6ff">KYRE SPORTS AI • WNBA REBOUNDS • ISOLATED PRODUCTION PAGE</div>
          <div style="font-size:2rem;font-weight:900;color:#f7f9fc;margin-top:8px">🏀 WNBA Rebounds Command Center — V1.0</div>
          <div style="color:#9fb1c1;margin-top:8px">Step 1 establishes the verified Eastern-date WNBA slate. No rebound projection, sportsbook line, matchup factor or simulation is allowed to run until the slate is trustworthy.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        frame = schedule.schedule_for_date(day)
        diag = schedule.schedule_diagnostics(day)
    except Exception as exc:
        frame = pd.DataFrame(columns=schedule.SCHEDULE_COLUMNS)
        diag = {"state": "PROVIDER_FAILURE", "games": 0, "teams": 0, "attempts": [], "error": str(exc)}

    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(columns=schedule.SCHEDULE_COLUMNS)

    state = str((diag or {}).get("state") or "PROVIDER_FAILURE")
    games = len(frame)
    teams = set()
    if not frame.empty:
        teams.update(pd.to_numeric(frame.get("away_team_id"), errors="coerce").dropna().astype(int).tolist())
        teams.update(pd.to_numeric(frame.get("home_team_id"), errors="coerce").dropna().astype(int).tolist())
    statuses = frame.get("status", pd.Series(dtype=str)).astype(str).str.upper() if not frame.empty else pd.Series(dtype=str)
    upcoming = int(statuses.eq("UPCOMING").sum())
    live = int(statuses.eq("LIVE").sum())
    final = int(statuses.eq("FINAL").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Verification", "VERIFIED" if state.startswith("VERIFIED") else "CHECK")
    c2.metric("Slate games", games)
    c3.metric("WNBA teams", len(teams))
    c4.metric("Upcoming", upcoming)

    if state == "PROVIDER_FAILURE":
        st.error("❌ STEP 1 BLOCKED • WNBA schedule providers did not produce a trustworthy slate. Rebounds modeling remains locked; a feed failure is not treated as a zero-game day.")
    elif state == "VERIFIED_OFF_DAY":
        st.success(f"✅ VERIFIED WNBA OFF-DAY • {day} • multiple season-level feeds loaded successfully and no WNBA games belong to this Eastern-date slate.")
    elif state == "VERIFIED_SINGLE_SOURCE":
        st.warning(f"⚠️ STEP 1 PARTIAL VERIFICATION • {games} game(s) found for {day}, but only one schedule path currently confirms the slate. Keep later Rebounds steps locked until another source confirms it.")
    else:
        confirming = len((diag or {}).get("confirming_sources", []) or [])
        st.success(f"✅ STEP 1 PASSED • {games} WNBA game(s) verified for {day} Eastern Time • {len(teams)} teams • confirmed by {confirming} schedule path(s).")

    if games:
        st.markdown("## 🗓️ Today’s Verified WNBA Rebound Slate")
        st.caption("Every verified game stays visible. FINAL games will remain part of slate history but later projection/simulation stages will exclude them from pregame grading.")
        _render_game_cards(frame)

        table = frame.copy()
        table["Matchup"] = table["away_team"].astype(str) + " @ " + table["home_team"].astype(str)
        table["Tip (ET)"] = table["first_tip_et"].astype(str)
        table["Venue"] = table["venue"].astype(str)
        table["Status"] = table["status"].astype(str)
        table["Verified source"] = table["source"].astype(str)
        st.dataframe(
            table[["Matchup", "Tip (ET)", "Venue", "Status", "Verified source"]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("🧭 Step-1 verification details", expanded=False):
        st.write({
            "selected_date": day,
            "timezone_rule": (diag or {}).get("timezone_rule", "America/New_York slate date"),
            "state": state,
            "chosen_source": (diag or {}).get("chosen_source", "none"),
            "confirming_sources": (diag or {}).get("confirming_sources", []),
            "source_selected_counts": (diag or {}).get("source_selected_counts", {}),
            "live_games": live,
            "final_games": final,
        })
        source_df = _source_diagnostics(diag or {})
        if not source_df.empty:
            st.dataframe(source_df, hide_index=True, use_container_width=True)
        if (diag or {}).get("error"):
            st.error(str(diag.get("error")))

    if st.button("🔄 RECHECK WNBA REBOUNDS SCHEDULE FEEDS", use_container_width=True, key="wnba_rebounds_recheck"):
        schedule.clear_schedule_cache()
        st.rerun()

    st.markdown("## 🧱 Rebounds Build Order")
    labels = [
        ("1", "Verified daily WNBA slate", state.startswith("VERIFIED")),
        ("2", "Current rosters + injuries/status", False),
        ("3", "Projected minutes + rotation", False),
        ("4", "Offensive/defensive rebound role", False),
        ("5", "Recent + season rebound form", False),
        ("6", "Rebound chances/opportunities", False),
        ("7", "Opponent missed-shot environment", False),
        ("8", "Opponent rebounding allowed", False),
        ("9", "Position matchup — Guard/Wing/Big", False),
        ("10", "Pace + expected shot volume", False),
        ("11", "Lineup effects / rebound competition", False),
        ("12", "Player vs opponent rebound history", False),
        ("13", "Exact SportsGameOdds rebound lines", False),
        ("14", "Same-book no-vig", False),
        ("15", "Empirical rebound variance", False),
        ("16", "Real 5M Monte Carlo", False),
        ("17", "Selective 10M finalist pass", False),
        ("18", "BEST / STRONG / MONITOR / AVOID", False),
        ("19", "Top Rebound Candidates", False),
        ("20", "Rich cards + Why this pick?", False),
        ("21", "Out-of-sample calibration ledger", False),
        ("22", "WNBA Daily Master Card handoff", False),
    ]
    tracker = pd.DataFrame([
        {"Step": n, "Layer": label, "Status": "✅ LIVE" if ok else ("➡️ NEXT" if n == "2" and state.startswith("VERIFIED") else "🔒 LOCKED")}
        for n, label, ok in labels
    ])
    st.dataframe(tracker, hide_index=True, use_container_width=True)

    st.info("Step 1 only is active. No Rebounds player projection, injury adjustment, sportsbook grading or Monte Carlo has been created yet. That isolation is intentional so we can validate each layer before the next one is allowed to influence the model.")

    st.session_state["wnba_rebounds_step1_state"] = state
    st.session_state["wnba_rebounds_step1_day"] = day
    st.session_state["wnba_rebounds_step1_games"] = games
