"""WNBA PRA V2 — official schedule, rosters, season stats and recent-form foundation.

V2 connects the first official WNBA data layer and keeps unsupported inputs
explicitly marked pending. It does not pretend injury/confirmed-lineup or the
full seven-source matchup model is complete yet.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from wnba_data_v2 import (
    current_season,
    data_health,
    empirical_profile,
    game_for_team,
    logo_url,
    official_roster,
    player_form_table,
    player_game_log,
    schedule_for_date,
    slate_player_pool,
    team_player_pool,
)

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "PRA V2"

CSS = r"""
<style>
.w2-hero{background:radial-gradient(circle at 10% 0%,rgba(255,83,154,.18),transparent 34%),radial-gradient(circle at 92% 8%,rgba(57,210,255,.11),transparent 32%),linear-gradient(145deg,#12142b,#09101c);border:1px solid #3b4272;border-radius:22px;padding:20px 22px;margin:5px 0 16px;box-shadow:0 18px 42px rgba(0,0,0,.22)}
.w2-kicker{font-size:.66rem;font-weight:950;letter-spacing:.18em;text-transform:uppercase;color:#ff70aa}.w2-title{font-size:2rem;line-height:1;font-weight:1000;color:#fff;margin-top:6px}.w2-sub{font-size:.86rem;color:#9faac6;margin-top:10px;line-height:1.55}.w2-pills{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.w2-pill{border:1px solid #394362;background:#11192a;border-radius:999px;padding:6px 10px;color:#c0c9dd;font-size:.65rem;font-weight:850}.w2-pill b{color:#fff}
.w2-panel{border:1px solid #303b5d;background:linear-gradient(145deg,#10182a,#0a111e);border-radius:18px;padding:15px 16px;margin:11px 0}.w2-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:11px}.w2-head b{font-size:1.02rem;color:#f9f8ff}.w2-head span{font-size:.56rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase;color:#7787a6}
.w2-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.w2-metric{border:1px solid #303d5e;background:#0b1423;border-radius:14px;padding:11px 12px}.w2-metric span{display:block;color:#7d8daa;font-size:.55rem;letter-spacing:.08em;text-transform:uppercase;font-weight:950}.w2-metric b{display:block;color:#fff;font-size:1.2rem;margin-top:5px}.w2-metric.good b{color:#75efba}.w2-metric.pink b{color:#ff82b6}.w2-metric.cyan b{color:#57dcff}.w2-metric.warn b{color:#ffe083}
.w2-source{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.w2-source-card{border:1px solid #33405f;background:#0c1524;border-radius:13px;padding:10px}.w2-source-card b{display:block;color:#fff;font-size:.69rem}.w2-source-card span{display:block;color:#8493ac;font-size:.56rem;margin-top:4px}.w2-source-card.ok{border-color:#23634c;background:#0b2d24}.w2-source-card.ok b{color:#79efbd}.w2-source-card.wait{border-color:#635226;background:#27210d}.w2-source-card.wait b{color:#ffe38d}
.w2-game{border:1px solid #35446a;background:radial-gradient(circle at 50% 0%,rgba(76,105,173,.09),transparent 38%),linear-gradient(145deg,#101a2e,#0a1321);border-radius:20px;padding:15px 17px;margin:12px 0}.w2-game-top{display:flex;justify-content:space-between;gap:12px;color:#8797b2;font-size:.62rem;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.w2-match{display:grid;grid-template-columns:1fr 40px 1fr;gap:10px;align-items:center;text-align:center;margin-top:15px}.w2-team img{height:58px;max-width:72px}.w2-team b{display:block;color:#fff;font-size:1.02rem;margin-top:7px}.w2-team span{display:block;color:#8fa0b8;font-size:.62rem;margin-top:4px}.w2-at{color:#657894;font-size:1.2rem;font-weight:950}.w2-venue{text-align:center;color:#778ba4;font-size:.64rem;margin-top:12px}
.w2-player-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:13px}.w2-roster{border:1px solid #2d405e;background:#091523;border-radius:15px;padding:10px 11px}.w2-roster-head{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid #20324a;padding-bottom:7px;margin-bottom:4px}.w2-roster-head b{color:#f8f8ff;font-size:.75rem}.w2-roster-head span{color:#6f88a6;font-size:.53rem;text-transform:uppercase;font-weight:900}.w2-row{display:grid;grid-template-columns:1.5fr .55fr .55fr .55fr;gap:5px;padding:6px 0;border-bottom:1px solid #17283d;font-size:.61rem}.w2-row:last-child{border-bottom:0}.w2-row b{color:#f0f4fb}.w2-row span{color:#91a2b8;text-align:right}.w2-row.head b,.w2-row.head span{color:#637c9b;font-size:.49rem;text-transform:uppercase;letter-spacing:.05em}
.w2-note{border-left:3px solid #ff619f;background:#191525;border-radius:0 12px 12px 0;padding:10px 12px;color:#b9bfd2;font-size:.7rem;line-height:1.55;margin:9px 0}.w2-note.blue{border-left-color:#4dd5ff;background:#0b1b2b}.w2-note.warn{border-left-color:#efc84d;background:#25200e;color:#eadca1}.w2-empty{border:1px dashed #394a68;background:#0b1422;border-radius:14px;padding:13px;color:#8fa1b9;font-size:.7rem;line-height:1.55}
.w2-playerhero{display:flex;align-items:center;gap:14px;border:1px solid #374669;background:linear-gradient(145deg,#121b31,#0a1322);border-radius:18px;padding:15px 16px}.w2-playerhero img{height:58px;width:58px;object-fit:contain}.w2-pname{font-size:1.4rem;font-weight:1000;color:#fff}.w2-pmeta{font-size:.7rem;color:#8fa0b8;margin-top:4px}
.w2-result{background:radial-gradient(circle at 90% 10%,rgba(255,85,154,.12),transparent 30%),linear-gradient(145deg,#151a34,#0b1220);border:1px solid #4b5488;border-radius:20px;padding:17px 18px;margin-top:13px}.w2-result-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.w2-result-title{font-size:1.15rem;font-weight:1000;color:#fff}.w2-result-meta{font-size:.68rem;color:#8d9eb9;margin-top:5px}.w2-prob{font-size:3rem;line-height:.95;font-weight:1000;color:#fff;text-align:right}.w2-prob-label{text-align:right;color:#8090ad;font-size:.6rem;margin-top:5px}.w2-result-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:13px}.w2-mini{border:1px solid #303d5e;background:#0b1423;border-radius:12px;padding:9px}.w2-mini span{display:block;color:#7e8eaa;font-size:.49rem;text-transform:uppercase;letter-spacing:.06em;font-weight:950}.w2-mini b{display:block;color:#fff;font-size:.94rem;margin-top:4px}
@media(max-width:1000px){.w2-source{grid-template-columns:repeat(2,minmax(0,1fr))}.w2-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.w2-result-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){.w2-title{font-size:1.55rem}.w2-match{grid-template-columns:1fr 24px 1fr}.w2-team img{height:48px}.w2-player-grid{grid-template-columns:1fr}.w2-source{grid-template-columns:1fr}.w2-result-top{display:block}.w2-prob{text-align:left;margin-top:12px;font-size:2.6rem}.w2-prob-label{text-align:left}.w2-result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _e(value):
    return escape(str(value if value is not None else "—"))


def _f(value, digits=1, fallback="—"):
    try:
        if pd.isna(value):
            return fallback
        return f"{float(value):.{digits}f}"
    except Exception:
        return fallback


def _odds(prob):
    p = min(max(float(prob), 1e-6), 1 - 1e-6)
    if p >= .5:
        return f"{-100*p/(1-p):.0f}"
    return f"+{100*(1-p)/p:.0f}"


def _hero(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA OFFICIAL-DATA FOUNDATION</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2</div>'
        '<div class="w2-sub">Official WNBA schedule, current player pool, season P/R/A, Last 10, Last 5 and on-demand rosters. Single-player baselines use official game logs and empirical P/R/A correlation; matchup, injury and confirmed-lineup adjustments remain explicitly pending.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2</b></div>'
        '<div class="w2-pill">✅ <b>WNBA.com data layer</b></div>'
        '<div class="w2-pill">🎯 <b>P / R / A kept separate</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )


def _metrics(items):
    html = ''.join(
        f'<div class="w2-metric {cls}"><span>{_e(label)}</span><b>{_e(value)}</b></div>'
        for label, value, cls in items
    )
    st.markdown(f'<div class="w2-metrics">{html}</div>', unsafe_allow_html=True)


def _source_stack(schedule, stats):
    health = data_health(schedule, stats)
    cards = []
    for label, state in health.items():
        ok = state in ("CONNECTED", "ON DEMAND")
        cls = "ok" if ok else "wait"
        icon = "●" if ok else "⏳"
        cards.append(f'<div class="w2-source-card {cls}"><b>{icon} {_e(label)}</b><span>{_e(state)}</span></div>')
    st.markdown(
        '<div class="w2-panel"><div class="w2-head"><b>📡 WNBA V2 Data Health</b><span>unsupported layers stay labeled</span></div>'
        f'<div class="w2-source">{"".join(cards)}</div></div>', unsafe_allow_html=True,
    )
    sources = [
        ("WNBA.com", "official schedule + stats", True),
        ("Her Hoop Stats", "advanced player/team analytics", False),
        ("RotoWire", "injury + lineup context", False),
        ("LineStar", "matchup + position context", False),
        ("StatMuse", "opponent history", False),
        ("Across the Timeline", "historical WNBA database", False),
        ("TeamRankings", "team situational context", False),
    ]
    source_html = ''.join(
        f'<div class="w2-source-card {"ok" if ok else "wait"}"><b>{"✅" if ok else "⏳"} {_e(name)}</b><span>{_e(desc)}</span></div>'
        for name, desc, ok in sources
    )
    with st.expander("Seven-source research stack"):
        st.markdown(f'<div class="w2-source">{source_html}</div>', unsafe_allow_html=True)


def _player_rows(pool, limit=5):
    if pool is None or pool.empty:
        return '<div class="w2-empty">No official player rows available for this team yet.</div>'
    frame = pool.copy()
    if "MIN" in frame.columns:
        frame = frame.sort_values("MIN", ascending=False)
    rows = ['<div class="w2-row head"><b>Player</b><span>MIN</span><span>PRA</span><span>L10</span></div>']
    for _, p in frame.head(limit).iterrows():
        pra = sum(float(p.get(x) or 0) for x in ("PTS", "REB", "AST"))
        l10 = sum(float(p.get(f"L10_{x}") or 0) for x in ("PTS", "REB", "AST")) if all(f"L10_{x}" in frame.columns for x in ("PTS", "REB", "AST")) else np.nan
        rows.append(
            '<div class="w2-row">'
            f'<b>{_e(p.get("PLAYER_NAME", "Player"))}</b>'
            f'<span>{_f(p.get("MIN"))}</span><span>{pra:.1f}</span><span>{_f(l10)}</span></div>'
        )
    return ''.join(rows)


def _game_card(row, stats, roster_counts=None):
    away_id, home_id = int(row.away_team_id), int(row.home_team_id)
    away_pool, home_pool = team_player_pool(stats, away_id), team_player_pool(stats, home_id)
    away_count = roster_counts.get(away_id) if roster_counts else None
    home_count = roster_counts.get(home_id) if roster_counts else None
    away_meta = f"Official roster {away_count}" if away_count is not None else f"{len(away_pool)} players with season stats"
    home_meta = f"Official roster {home_count}" if home_count is not None else f"{len(home_pool)} players with season stats"
    status = row.status_text or row.status
    st.markdown(
        '<div class="w2-game">'
        f'<div class="w2-game-top"><span>{_e(row.status)}</span><span>{_e(row.first_tip_et)}</span></div>'
        '<div class="w2-match">'
        f'<div class="w2-team"><img src="{logo_url(away_id)}"><b>{_e(row.away_team)}</b><span>{_e(away_meta)}</span></div>'
        '<div class="w2-at">@</div>'
        f'<div class="w2-team"><img src="{logo_url(home_id)}"><b>{_e(row.home_team)}</b><span>{_e(home_meta)}</span></div>'
        '</div>'
        f'<div class="w2-venue">📍 {_e(row.venue)} • {_e(status)}</div>'
        '<div class="w2-player-grid">'
        f'<div class="w2-roster"><div class="w2-roster-head"><b>{_e(row.away_team)}</b><span>season / L10 snapshot</span></div>{_player_rows(away_pool)}</div>'
        f'<div class="w2-roster"><div class="w2-roster-head"><b>{_e(row.home_team)}</b><span>season / L10 snapshot</span></div>{_player_rows(home_pool)}</div>'
        '</div></div>', unsafe_allow_html=True,
    )


def _run_empirical_mc(profile, line, sims, seed):
    mu = np.array([
        .50*profile["pts"] + .30*profile["l10_pts"] + .20*profile["l5_pts"],
        .50*profile["reb"] + .30*profile["l10_reb"] + .20*profile["l5_reb"],
        .50*profile["ast"] + .30*profile["l10_ast"] + .20*profile["l5_ast"],
    ])
    sd = np.array([profile["sd_pts"], profile["sd_reb"], profile["sd_ast"]])
    corr = np.array([
        [1, profile["corr_pr"], profile["corr_pa"]],
        [profile["corr_pr"], 1, profile["corr_ra"]],
        [profile["corr_pa"], profile["corr_ra"], 1],
    ], dtype=float)
    vals, vecs = np.linalg.eigh(corr)
    vals = np.clip(vals, .05, None)
    corr = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.diag(corr)); corr = corr / np.outer(d, d)
    cov = np.diag(sd) @ corr @ np.diag(sd)
    rng = np.random.default_rng(int(seed))
    draw = rng.multivariate_normal(mu, cov, size=int(sims))
    draw = np.rint(np.clip(draw, 0, None)).astype(np.int16)
    pra = draw.sum(axis=1)
    over, under = float(np.mean(pra > line)), float(np.mean(pra < line))
    push = float(np.mean(pra == line)) if float(line).is_integer() else 0.0
    return {
        "mu_p": float(mu[0]), "mu_r": float(mu[1]), "mu_a": float(mu[2]),
        "mean": float(pra.mean()), "median": float(np.median(pra)),
        "over": over, "under": under, "push": push,
        "q10": float(np.percentile(pra, 10)), "q90": float(np.percentile(pra, 90)),
    }


def _slate_tab(day, schedule, stats):
    st.markdown('<div class="w2-note blue"><b>V2 foundation:</b> these slate tables are official descriptive data, not final PRA projections. V3 adds injuries, confirmed starters, opponent defense, usage/role changes and the full matchup-adjusted scanner.</div>', unsafe_allow_html=True)
    pool = slate_player_pool(schedule, stats)
    _metrics([
        ("Games", len(schedule), "cyan"),
        ("Teams", len(set(schedule.away_team_id.tolist()+schedule.home_team_id.tolist())) if not schedule.empty else 0, "pink"),
        ("Slate player pool", len(pool), "good"),
        ("Official source", "WNBA Stats", "warn"),
    ])

    if schedule.empty:
        st.markdown('<div class="w2-empty">No official WNBA games were returned for this date. Try another date or refresh after the WNBA schedule feed updates.</div>', unsafe_allow_html=True)
        return

    if not pool.empty:
        leaders = pool.copy()
        if "PRA" not in leaders.columns:
            leaders["PRA"] = leaders[[c for c in ("PTS", "REB", "AST") if c in leaders.columns]].sum(axis=1)
        if "MIN" in leaders.columns:
            leaders = leaders[leaders.MIN.fillna(0).ge(10)]
        leaders = leaders.sort_values("PRA", ascending=False).head(10)
        with st.expander("🏆 Official PRA baseline leaders on this slate", expanded=False):
            cols = [c for c in ("PLAYER_NAME", "TEAM_ABBREVIATION", "MIN", "PTS", "REB", "AST", "PRA", "L10_PRA", "L5_PRA") if c in leaders.columns]
            show = leaders[cols].rename(columns={"PLAYER_NAME":"Player","TEAM_ABBREVIATION":"Team","MIN":"MIN","PTS":"PTS","REB":"REB","AST":"AST","PRA":"Season PRA","L10_PRA":"L10 PRA","L5_PRA":"L5 PRA"})
            st.dataframe(show, use_container_width=True, hide_index=True)
            st.caption("Baseline leaderboard only — not an Over/Under recommendation or matchup-adjusted projection.")

    roster_counts = st.session_state.get("wnba_v2_roster_counts", {})
    if st.button("📋 LOAD OFFICIAL ROSTERS FOR THIS SLATE", use_container_width=True):
        counts = {}
        ids = sorted(set(schedule.away_team_id.astype(int).tolist()+schedule.home_team_id.astype(int).tolist()))
        bar = st.progress(0, text="Loading official WNBA rosters...")
        for i, team_id in enumerate(ids, 1):
            try:
                roster = official_roster(team_id, current_season())
                counts[int(team_id)] = int(len(roster))
            except Exception:
                counts[int(team_id)] = None
            bar.progress(i/max(len(ids),1), text=f"Official rosters {i}/{len(ids)}")
        bar.empty()
        st.session_state["wnba_v2_roster_counts"] = counts
        roster_counts = counts

    st.markdown("### 🗓️ Selected WNBA Slate")
    for _, row in schedule.iterrows():
        _game_card(row, stats, roster_counts)


def _single_player(day, schedule, stats):
    if stats is None or stats.empty or "PLAYER_NAME" not in stats.columns:
        st.warning("Official WNBA player stats are unavailable right now.")
        return
    names = stats.sort_values("PLAYER_NAME")["PLAYER_NAME"].dropna().astype(str).tolist()
    selected = st.selectbox("Player", names, index=0)
    row = stats[stats.PLAYER_NAME.astype(str).eq(selected)].iloc[0]
    team_id = int(row.get("TEAM_ID") or 0)
    matchup = game_for_team(schedule, team_id)
    st.markdown(
        '<div class="w2-playerhero">'
        f'<img src="{logo_url(team_id)}"><div><div class="w2-pname">{_e(selected)}</div>'
        f'<div class="w2-pmeta">{_e(row.get("TEAM_NAME") or row.get("TEAM_ABBREVIATION"))} • Selected slate {_e(day)} • {"vs "+_e(matchup.get("opponent")) if matchup else "No game on selected slate"}</div></div></div>',
        unsafe_allow_html=True,
    )
    season_pra = sum(float(row.get(x) or 0) for x in ("PTS","REB","AST"))
    l10_pra = sum(float(row.get(f"L10_{x}") or 0) for x in ("PTS","REB","AST")) if all(f"L10_{x}" in stats.columns for x in ("PTS","REB","AST")) else np.nan
    l5_pra = sum(float(row.get(f"L5_{x}") or 0) for x in ("PTS","REB","AST")) if all(f"L5_{x}" in stats.columns for x in ("PTS","REB","AST")) else np.nan
    _metrics([
        ("Season PTS", _f(row.get("PTS")), "pink"),
        ("Season REB", _f(row.get("REB")), "cyan"),
        ("Season AST", _f(row.get("AST")), "good"),
        ("Season PRA", f"{season_pra:.1f}", "warn"),
        ("Minutes", _f(row.get("MIN")), ""),
        ("L10 PRA", _f(l10_pra), ""),
        ("L5 PRA", _f(l5_pra), ""),
        ("Games", _f(row.get("GP"), 0), ""),
    ])

    if matchup:
        st.markdown(
            f'<div class="w2-note blue"><b>Matchup found:</b> {_e(matchup.get("opponent"))} • {_e(matchup.get("first_tip_et"))} • {_e(matchup.get("venue"))}. Confirmed starter/injury adjustments are not wired yet, so V2 will not pretend they are included.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="w2-note warn"><b>No selected-slate game:</b> a statistical baseline can still be inspected, but it is not a game-specific PRA projection.</div>', unsafe_allow_html=True)

    if st.button("📊 LOAD OFFICIAL GAME LOG + EMPIRICAL PROFILE", use_container_width=True):
        try:
            with st.spinner("Loading official WNBA game log..."):
                log = player_game_log(int(row.PLAYER_ID), current_season())
            st.session_state["wnba_v2_log"] = log
            st.session_state["wnba_v2_log_pid"] = int(row.PLAYER_ID)
        except Exception as exc:
            st.error(f"WNBA game-log request failed: {exc}")

    log = st.session_state.get("wnba_v2_log") if st.session_state.get("wnba_v2_log_pid") == int(row.PLAYER_ID) else None
    if log is None or log.empty:
        st.markdown('<div class="w2-empty">Load the official game log to unlock empirical variance, P/R/A correlation, recent form and the V2 baseline simulator.</div>', unsafe_allow_html=True)
        return

    profile = empirical_profile(log)
    if not profile:
        st.warning("Not enough official game-log data to build an empirical PRA profile.")
        return
    _metrics([
        ("Game-log PRA", f"{profile['pra']:.1f}", "warn"),
        ("Last 10 PRA", f"{profile['l10_pra']:.1f}", "cyan"),
        ("Last 5 PRA", f"{profile['l5_pra']:.1f}", "pink"),
        ("Games sampled", profile["games"], "good"),
    ])
    with st.expander("🧩 Empirical P/R/A variance + correlation"):
        st.write({
            "PTS SD": round(profile["sd_pts"],2), "REB SD": round(profile["sd_reb"],2), "AST SD": round(profile["sd_ast"],2),
            "PTS↔REB": round(profile["corr_pr"],3), "PTS↔AST": round(profile["corr_pa"],3), "REB↔AST": round(profile["corr_ra"],3),
        })
    with st.expander("🗂️ Recent official game log"):
        cols = [c for c in ("GAME_DATE","MATCHUP","MIN","PTS","REB","AST") if c in log.columns]
        st.dataframe(log[cols].head(10), use_container_width=True, hide_index=True)

    st.markdown("### 🎲 V2 Empirical PRA Baseline")
    st.markdown('<div class="w2-note"><b>Important:</b> this is an automatic statistical baseline from official season/L10/L5 production, historical variance and empirical P/R/A correlation. It is not yet the final V3 matchup-adjusted projection.</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        line = st.number_input("PRA line", 0.5, 80.5, float(round(profile["pra"]*2)/2), .5)
    with c2:
        depth = st.selectbox("Simulation depth", ["Quick — 250K","Standard — 1M","Deep — 5M"], index=1)
    with c3:
        seed = st.number_input("Seed", 1, 2_000_000_000, 8172026, 1)
    sims = {"Quick — 250K":250_000,"Standard — 1M":1_000_000,"Deep — 5M":5_000_000}[depth]
    if st.button("🔥 RUN V2 EMPIRICAL PRA BASELINE", use_container_width=True, type="primary"):
        with st.spinner(f"Running {sims:,} correlated simulations..."):
            sim = _run_empirical_mc(profile, line, sims, seed)
        st.session_state["wnba_v2_sim"] = (int(row.PLAYER_ID), float(line), sim, sims)
    saved = st.session_state.get("wnba_v2_sim")
    if saved and saved[0] == int(row.PLAYER_ID):
        _, saved_line, sim, sims = saved
        verdict = "OVER" if sim["over"] >= sim["under"] else "UNDER"
        prob = max(sim["over"], sim["under"])
        st.markdown(
            '<div class="w2-result"><div class="w2-result-top"><div>'
            f'<div class="w2-result-title">{_e(selected)} • {verdict} {saved_line:.1f}</div>'
            f'<div class="w2-result-meta">V2 empirical official-data baseline • {sims:,} correlated simulations • matchup/injury adjustment pending</div>'
            '</div><div>'
            f'<div class="w2-prob">{prob*100:.1f}%</div><div class="w2-prob-label">baseline {verdict.lower()} probability</div>'
            '</div></div><div class="w2-result-grid">'
            f'<div class="w2-mini"><span>Expected PRA</span><b>{sim["mean"]:.1f}</b></div>'
            f'<div class="w2-mini"><span>Median PRA</span><b>{sim["median"]:.0f}</b></div>'
            f'<div class="w2-mini"><span>Expected PTS</span><b>{sim["mu_p"]:.1f}</b></div>'
            f'<div class="w2-mini"><span>Expected REB</span><b>{sim["mu_r"]:.1f}</b></div>'
            f'<div class="w2-mini"><span>Expected AST</span><b>{sim["mu_a"]:.1f}</b></div>'
            f'<div class="w2-mini"><span>Fair {verdict}</span><b>{_odds(prob)}</b></div>'
            f'<div class="w2-mini"><span>Over</span><b>{sim["over"]*100:.1f}%</b></div>'
            f'<div class="w2-mini"><span>Under</span><b>{sim["under"]*100:.1f}%</b></div>'
            f'<div class="w2-mini"><span>Push</span><b>{sim["push"]*100:.1f}%</b></div>'
            f'<div class="w2-mini"><span>10% floor</span><b>{sim["q10"]:.0f}</b></div>'
            f'<div class="w2-mini"><span>90% ceiling</span><b>{sim["q90"]:.0f}</b></div>'
            f'<div class="w2-mini"><span>Data source</span><b>WNBA</b></div>'
            '</div></div>', unsafe_allow_html=True,
        )


def _backtest_tab():
    st.markdown('<div class="w2-panel"><div class="w2-head"><b>📈 PRA Calibration Workspace</b><span>V3 prediction history next</span></div><div class="w2-empty">V2 does not save empirical baselines as final betting-model predictions. Once V3 adds matchup, injury, lineup, usage and opponent-defense layers, clean pregame PRA projections will be stored here and graded after games finish.</div></div>', unsafe_allow_html=True)


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(CSS, unsafe_allow_html=True)
    today = datetime.now(ET).date()
    min_day, max_day = today - timedelta(days=21), today + timedelta(days=45)
    day = st.date_input("WNBA slate date", value=today, min_value=min_day, max_value=max_day, key="wnba_pra_v2_date")
    day_str = day.strftime("%Y-%m-%d")
    _hero(day_str)

    schedule, stats = pd.DataFrame(), pd.DataFrame()
    schedule_error = stats_error = None
    try:
        schedule = schedule_for_date(day)
    except Exception as exc:
        schedule_error = str(exc)
    try:
        stats = player_form_table(day.year)
    except Exception as exc:
        stats_error = str(exc)

    if schedule_error or stats_error:
        messages = []
        if schedule_error: messages.append(f"schedule: {schedule_error}")
        if stats_error: messages.append(f"player stats: {stats_error}")
        st.warning("Official WNBA feed needs a refresh/check • " + " | ".join(messages))

    _source_stack(schedule, stats)
    tabs = st.tabs(["🏆 PRA Slate", "🔎 Single Player", "📈 Backtest"])
    with tabs[0]:
        _slate_tab(day_str, schedule, stats)
    with tabs[1]:
        _single_player(day_str, schedule, stats)
    with tabs[2]:
        _backtest_tab()

    st.caption("WNBA PRA V2 • Official WNBA schedule/player statistics • empirical baseline simulator only until V3 matchup/injury/lineup layers are connected.")
