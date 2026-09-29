from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import wnba_pra_navigation_v2_step1 as nav
import wnba_pra_responsive_v2_step6 as responsive

raw=str(st.query_params.get("proof_page") or "slate").strip().lower()
if raw=="game":
    state=nav.NavigationState(page=nav.PAGE_GAME,game_id="1022600001")
elif raw=="player":
    state=nav.NavigationState(page=nav.PAGE_PLAYER,game_id="1022600001",player_id="1642291")
else:
    raw="slate"; state=nav.NavigationState()

responsive.render_responsive_shell(state)
st.html(f'<main data-wnba-step6-proof-page="{raw}"></main>')

if raw=="slate":
    st.html("""
<div class="wn2-hero"><div class="wn2-title">WNBA Slate Responsive Proof</div></div>
<div class="wn2-health"><span>CONNECTED</span><span>Very long health metadata that must wrap safely</span></div>
<div class="wn2-card">
 <div class="wn2-team"><div class="wn2-name">Extremely Long Away Team Name For Overflow Certification</div><div class="wn2-code">AWAY</div></div>
 <div class="wn2-mid"><div>10:30 PM ET</div><div class="wn2-venue">Very Long Arena Venue Name For Responsive Certification</div></div>
 <div class="wn2-team home"><div class="wn2-name">Extremely Long Home Team Name For Overflow Certification</div><div class="wn2-code">HOME</div></div>
</div>
""")
    st.button("Open Game Center →",key="proof-slate")
elif raw=="game":
    st.html("""
<div class="wn3-hero"><div class="wn3-title">Game Center Responsive Proof</div></div>
<div class="wn3-health"><span>GAME CENTER READY</span><span>Selected game only</span></div>
<div class="wn3-teamhead"><div class="wn3-teamname">Very Long WNBA Team Name</div></div>
<div class="wn3-player">
 <div class="wn3-headshot"></div>
 <div><div class="wn3-name">Very Long Player Name For Responsive Certification</div><div class="wn3-role">CONFIRMED STARTER</div><div class="wn3-detail">Current roster • availability context</div></div>
 <div class="wn3-metrics"><div>34.2 MIN</div><div>18.4 PTS</div><div>7.2 REB</div><div>5.1 AST</div><div>30.7 PRA</div></div>
</div>
""")
    st.button("← Back to WNBA Slate",key="proof-game-back")
    st.button("Open Player PRA →",key="proof-game-open")
else:
    st.html("""
<div class="wn4-hero"><div class="wn4-headshot"></div><div><div class="wn4-title">Very Long Player Name For Responsive Certification</div><div class="wn4-sub">TEAM • Away Team @ Home Team • Confirmed Starter</div></div></div>
<div class="wn4-chips"><span>PLAYER SELECTED</span><span>STARTER</span><span>READ-ONLY INTELLIGENCE</span></div>
<div class="wn4-strip"><div class="wn4-metric">34.2 MIN</div><div class="wn4-metric">18.4 PTS</div><div class="wn4-metric">7.2 REB</div><div class="wn4-metric">5.1 AST</div><div class="wn4-metric">30.7 PRA</div></div>
<div class="wn4-decision"><div class="wn4-pick">OVER 29.5 — QUALIFIED PRA DECISION</div><div class="wn4-grid"><div class="wn4-metric">LINE 29.5</div><div class="wn4-metric">MODEL 61.2%</div><div class="wn4-metric">NO-VIG 52.1%</div><div class="wn4-metric">EDGE 9.1 pp</div></div></div>
<div class="wn4-panel"><div class="wn4-row"><span>Exact pace adjustment</span><b>N/A — not exposed by read-only payload</b></div><div class="wn4-row"><span>Projected minutes</span><b>34.2</b></div></div>
<div class="wn4-games"><div class="wn4-game">31 PRA vs Opponent</div><div class="wn4-game">28 PRA vs Opponent</div><div class="wn4-game">35 PRA vs Opponent</div></div>
""")
    st.button("← Back to Game Center",key="proof-player-back")
