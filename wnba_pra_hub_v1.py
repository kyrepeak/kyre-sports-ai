"""WNBA PRA V1 — mobile-first command center foundation.

This first WNBA module establishes the PRA workflow and visual hierarchy while
keeping the modeling honest: live WNBA data connectors are not claimed yet.
The Single Player lab can run an explicit manual/prototype correlated Monte
Carlo from user-entered component assumptions. P/R/A are modeled separately
and only combined into PRA at the simulation layer.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import streamlit as st

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "PRA V1"

PRA_CSS = r"""
<style>
.pra-hero{background:radial-gradient(circle at 12% 0%,rgba(255,77,145,.16),transparent 34%),radial-gradient(circle at 88% 5%,rgba(68,208,255,.10),transparent 31%),linear-gradient(145deg,#101226,#090e1a);border:1px solid #343a68;border-radius:22px;padding:20px 22px;margin:4px 0 16px;box-shadow:0 18px 40px rgba(0,0,0,.22)}
.pra-kicker{font-size:.66rem;font-weight:950;letter-spacing:.18em;text-transform:uppercase;color:#ff6ca8}.pra-title{font-size:2rem;line-height:1;font-weight:1000;color:#f8f7ff;margin-top:5px}.pra-sub{font-size:.86rem;color:#9ea8c6;margin-top:9px;line-height:1.5}.pra-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}.pra-pill{border:1px solid #343d63;background:#10182a;border-radius:999px;padding:6px 10px;color:#bdc7df;font-size:.67rem;font-weight:850}.pra-pill b{color:#fff}
.pra-panel{border:1px solid #30395c;background:linear-gradient(145deg,#10172a,#0a101d);border-radius:18px;padding:15px 16px;margin:10px 0}.pra-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.pra-head b{font-size:1.02rem;color:#f7f5ff}.pra-head span{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:#7987a8;font-weight:950}
.pra-source-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.pra-source{border:1px solid #2c3858;background:#0d1525;border-radius:13px;padding:10px}.pra-source b{display:block;color:#f6f4ff;font-size:.75rem}.pra-source span{display:block;color:#8090ae;font-size:.59rem;margin-top:4px}.pra-source.pending{border-color:#594b2c;background:#211c0d}.pra-source.pending b{color:#ffe39a}
.pra-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0}.pra-stat{border:1px solid #303c5e;background:#0d1626;border-radius:14px;padding:11px 12px}.pra-stat span{display:block;color:#7f8faa;font-size:.56rem;letter-spacing:.08em;text-transform:uppercase;font-weight:950}.pra-stat b{display:block;color:#fff;font-size:1.24rem;margin-top:5px}.pra-stat.cyan b{color:#5ddcff}.pra-stat.pink b{color:#ff82b6}.pra-stat.good b{color:#75efbc}.pra-stat.warn b{color:#ffe083}
.pra-result{background:radial-gradient(circle at 88% 12%,rgba(255,81,151,.13),transparent 31%),linear-gradient(145deg,#151a35,#0b1220);border:1px solid #4a5185;border-radius:20px;padding:17px 18px;margin-top:14px}.pra-result-top{display:flex;justify-content:space-between;align-items:flex-start;gap:15px}.pra-player{font-size:1.28rem;font-weight:1000;color:#fff}.pra-match{font-size:.7rem;color:#93a2be;margin-top:5px}.pra-big{font-size:3rem;line-height:.95;font-weight:1000;color:#fff;text-align:right}.pra-big-label{font-size:.62rem;color:#8797b3;text-align:right;margin-top:5px}.pra-badge{display:inline-flex;border-radius:999px;padding:4px 8px;font-size:.53rem;font-weight:950;margin-top:8px}.pra-badge.high{background:#0b382b;border:1px solid #1c6a4d;color:#78efba}.pra-badge.medium{background:#4a370c;border:1px solid #75571a;color:#ffe17b}.pra-badge.low{background:#3b1820;border:1px solid #71303a;color:#ff9cab}
.pra-result-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:14px}.pra-mini{border:1px solid #303c5c;background:#0b1423;border-radius:12px;padding:9px}.pra-mini span{display:block;color:#7e8eaa;font-size:.51rem;letter-spacing:.07em;text-transform:uppercase;font-weight:950}.pra-mini b{display:block;color:#fbfaff;font-size:.98rem;margin-top:4px}.pra-note{border-left:3px solid #ff5f9f;background:#191526;padding:10px 12px;border-radius:0 12px 12px 0;color:#b9bfd3;font-size:.7rem;line-height:1.55;margin:10px 0}.pra-empty{border:1px dashed #3b4665;background:#0c1422;border-radius:15px;padding:13px;color:#91a0ba;font-size:.72rem;line-height:1.55}
@media(max-width:1000px){.pra-source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.pra-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.pra-result-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){.pra-title{font-size:1.55rem}.pra-result-top{display:block}.pra-big{text-align:left;margin-top:12px;font-size:2.7rem}.pra-big-label{text-align:left}.pra-result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.pra-source-grid{grid-template-columns:1fr}}
</style>
"""


def _odds(prob):
    p = min(max(float(prob), 1e-6), 1 - 1e-6)
    if p >= 0.5:
        return f"{-100 * p / (1-p):.0f}"
    return f"+{100 * (1-p) / p:.0f}"


def _hero():
    now = datetime.now(ET)
    st.markdown(
        '<div class="pra-hero">'
        '<div class="pra-kicker">KYRE SPORTS AI • WNBA PLAYER PROP INTELLIGENCE</div>'
        '<div class="pra-title">🏀 WNBA PRA Command Center</div>'
        '<div class="pra-sub">Points, rebounds and assists are projected independently, then combined through a correlated uncertainty engine. Built for matchup context, role changes, lineup news and clean Over/Under probability.</div>'
        '<div class="pra-pills">'
        f'<div class="pra-pill">📅 <b>{now.strftime("%Y-%m-%d")}</b></div>'
        f'<div class="pra-pill">🧠 <b>{MODEL_VERSION}</b></div>'
        '<div class="pra-pill">🎲 <b>Correlated Monte Carlo</b></div>'
        '<div class="pra-pill">🎯 <b>P / R / A modeled separately</b></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _sources():
    sources = [
        ("WNBA.com", "official stats + game status"),
        ("Her Hoop Stats", "advanced player/team analytics"),
        ("RotoWire", "injury + lineup context"),
        ("LineStar", "matchup + position context"),
        ("StatMuse", "opponent history"),
        ("Across the Timeline", "historical WNBA database"),
        ("TeamRankings", "team situational context"),
    ]
    cards = ''.join(
        f'<div class="pra-source pending"><b>⏳ {name}</b><span>{desc}</span></div>'
        for name, desc in sources
    )
    st.markdown(
        '<div class="pra-panel"><div class="pra-head"><b>📡 Seven-Source Research Stack</b><span>connector phase next</span></div>'
        f'<div class="pra-source-grid">{cards}</div></div>',
        unsafe_allow_html=True,
    )


def _run_manual_mc(mu_p, mu_r, mu_a, sd_p, sd_r, sd_a, line, sims, corr_pr, corr_pa, corr_ra, seed):
    corr = np.array([
        [1.0, corr_pr, corr_pa],
        [corr_pr, 1.0, corr_ra],
        [corr_pa, corr_ra, 1.0],
    ], dtype=float)
    vals, vecs = np.linalg.eigh(corr)
    vals = np.clip(vals, 0.05, None)
    corr = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.diag(corr))
    corr = corr / np.outer(d, d)
    cov = np.diag([sd_p, sd_r, sd_a]) @ corr @ np.diag([sd_p, sd_r, sd_a])
    rng = np.random.default_rng(int(seed))
    draw = rng.multivariate_normal([mu_p, mu_r, mu_a], cov, size=int(sims))
    draw = np.rint(np.clip(draw, 0, None)).astype(np.int16)
    pra = draw.sum(axis=1)
    over = float(np.mean(pra > line))
    under = float(np.mean(pra < line))
    push = float(np.mean(pra == line)) if float(line).is_integer() else 0.0
    return {
        "over": over,
        "under": under,
        "push": push,
        "mean": float(np.mean(pra)),
        "median": float(np.median(pra)),
        "p_mean": float(np.mean(draw[:, 0])),
        "r_mean": float(np.mean(draw[:, 1])),
        "a_mean": float(np.mean(draw[:, 2])),
        "q10": float(np.percentile(pra, 10)),
        "q90": float(np.percentile(pra, 90)),
    }


def _manual_lab():
    st.markdown('<div class="pra-note"><b>Prototype mode:</b> this first PRA build does not pretend the live seven-source feed is connected yet. Enter the component assumptions you want tested; the next build will replace these manual inputs with verified WNBA data.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.35, 1])
    with c1:
        player = st.text_input("Player", placeholder="A'ja Wilson")
    with c2:
        line = st.number_input("Sportsbook PRA line", min_value=0.5, max_value=80.5, value=32.5, step=0.5)

    st.markdown("#### Component projections")
    p1, p2, p3 = st.columns(3)
    with p1:
        mu_p = st.number_input("Expected points", 0.0, 60.0, 20.0, 0.1)
        sd_p = st.number_input("Points SD", 1.0, 20.0, 6.0, 0.1)
    with p2:
        mu_r = st.number_input("Expected rebounds", 0.0, 25.0, 7.0, 0.1)
        sd_r = st.number_input("Rebounds SD", 0.5, 10.0, 3.0, 0.1)
    with p3:
        mu_a = st.number_input("Expected assists", 0.0, 20.0, 5.0, 0.1)
        sd_a = st.number_input("Assists SD", 0.5, 10.0, 2.5, 0.1)

    with st.expander("🧩 Correlation + simulation controls"):
        r1, r2, r3 = st.columns(3)
        with r1:
            corr_pr = st.slider("Points ↔ Rebounds", -0.50, 0.70, 0.10, 0.05)
        with r2:
            corr_pa = st.slider("Points ↔ Assists", -0.50, 0.70, 0.20, 0.05)
        with r3:
            corr_ra = st.slider("Rebounds ↔ Assists", -0.50, 0.70, 0.05, 0.05)
        s1, s2 = st.columns(2)
        with s1:
            depth = st.selectbox("Simulation size", ["Quick — 250K", "Standard — 1M", "Deep — 5M"], index=1)
        with s2:
            seed = st.number_input("Random seed", min_value=1, max_value=2_000_000_000, value=8172026, step=1)
    sims = {"Quick — 250K": 250_000, "Standard — 1M": 1_000_000, "Deep — 5M": 5_000_000}[depth]

    if st.button("🔥 RUN PRA PROJECTION", use_container_width=True, type="primary"):
        with st.spinner(f"Running {sims:,} correlated PRA simulations..."):
            sim = _run_manual_mc(mu_p, mu_r, mu_a, sd_p, sd_r, sd_a, line, sims, corr_pr, corr_pa, corr_ra, seed)
        st.session_state["wnba_pra_v1_result"] = {"player": player.strip() or "Selected player", "line": line, "sim": sim, "sims": sims, "seed": seed}

    result = st.session_state.get("wnba_pra_v1_result")
    if result:
        sim = result["sim"]
        p_over = sim["over"]
        grade = "high" if max(sim["over"], sim["under"]) >= .62 else "medium" if max(sim["over"], sim["under"]) >= .55 else "low"
        verdict = "OVER" if sim["over"] > sim["under"] else "UNDER"
        bestp = max(sim["over"], sim["under"])
        st.markdown(
            '<div class="pra-result"><div class="pra-result-top"><div>'
            f'<div class="pra-player">{result["player"]} • {verdict} {result["line"]:.1f}</div>'
            '<div class="pra-match">Manual/prototype PRA assumptions • live matchup feed not connected yet</div>'
            f'<span class="pra-badge {grade}">{grade.upper()} PROTOTYPE CONFIDENCE</span>'
            '</div><div>'
            f'<div class="pra-big">{bestp*100:.1f}%</div><div class="pra-big-label">projected {verdict.lower()} probability</div>'
            '</div></div>'
            '<div class="pra-result-grid">'
            f'<div class="pra-mini"><span>Expected PRA</span><b>{sim["mean"]:.1f}</b></div>'
            f'<div class="pra-mini"><span>Median PRA</span><b>{sim["median"]:.0f}</b></div>'
            f'<div class="pra-mini"><span>Over</span><b>{sim["over"]*100:.1f}%</b></div>'
            f'<div class="pra-mini"><span>Under</span><b>{sim["under"]*100:.1f}%</b></div>'
            f'<div class="pra-mini"><span>Push</span><b>{sim["push"]*100:.1f}%</b></div>'
            f'<div class="pra-mini"><span>Fair {verdict}</span><b>{_odds(bestp)}</b></div>'
            f'<div class="pra-mini"><span>Points</span><b>{sim["p_mean"]:.1f}</b></div>'
            f'<div class="pra-mini"><span>Rebounds</span><b>{sim["r_mean"]:.1f}</b></div>'
            f'<div class="pra-mini"><span>Assists</span><b>{sim["a_mean"]:.1f}</b></div>'
            f'<div class="pra-mini"><span>10th pct</span><b>{sim["q10"]:.0f}</b></div>'
            f'<div class="pra-mini"><span>90th pct</span><b>{sim["q90"]:.0f}</b></div>'
            f'<div class="pra-mini"><span>Simulations</span><b>{result["sims"]:,}</b></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(PRA_CSS, unsafe_allow_html=True)
    _hero()
    tabs = st.tabs(["🏆 PRA Slate", "🔎 Single Player", "📈 Backtest"])

    with tabs[0]:
        st.markdown('<div class="pra-panel"><div class="pra-head"><b>🏆 Daily PRA Scanner</b><span>foundation ready</span></div><div class="pra-empty"><b>Next build:</b> verified WNBA schedule + active rosters + confirmed starters + injury status + slate-wide PRA player pool, followed by independent P/R/A projections and ranked Over/Under probabilities. No fake slate is shown before those feeds are connected.</div></div>', unsafe_allow_html=True)
        _sources()

    with tabs[1]:
        st.markdown('<div class="pra-panel"><div class="pra-head"><b>🔎 Single-Player PRA Lab</b><span>manual prototype</span></div><div class="pra-summary"><div class="pra-stat pink"><span>Points model</span><b>Independent</b></div><div class="pra-stat cyan"><span>Rebound model</span><b>Independent</b></div><div class="pra-stat good"><span>Assist model</span><b>Independent</b></div><div class="pra-stat warn"><span>PRA layer</span><b>Correlated</b></div></div></div>', unsafe_allow_html=True)
        _manual_lab()

    with tabs[2]:
        st.markdown('<div class="pra-panel"><div class="pra-head"><b>📈 PRA Calibration</b><span>planned</span></div><div class="pra-empty">Pregame snapshots, official result grading, Brier score, log loss, calibration buckets and model-version tracking will be added after the verified data layer is wired. We will not backtest prototype/manual assumptions as if they were production predictions.</div></div>', unsafe_allow_html=True)
