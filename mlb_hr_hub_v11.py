"""MLB Home Run Monster V1.1 — calibrated pure-probability HR model.

HOME RUN ONLY. This module does not modify 1+ Hit, Moneyline, Spread, Totals,
Live Game, WNBA, H+R+RBI, or pitcher strikeouts.

V1.1 calibration changes:
- empirical-Bayes shrinkage of season HR/PA toward a league prior
- platoon and recent HR rates are shrunk and tightly capped in influence
- Statcast power is sample-size weighted (small BBE/PA cannot dominate)
- starter HR/9 is regressed toward league average by innings reliability
- park/weather is capped to a conservative HR-specific multiplier
- dynamic per-PA HR ceiling grows only with meaningful season sample/power
- confidence grades use sample quality, not mere source availability
- Monte Carlo uncertainty is centered on the calibrated per-PA HR rate

Sportsbook price is never an input to the ranking.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math

import numpy as np
import pandas as pd
import streamlit as st

import mlb_hr_hub_v10 as core
import mlb_hr_hub_v101 as _ui_patch  # installs null-safe base card before we replace it
import mlb_schedule_v32 as schedule
from engine import (
    ab_for_spot,
    clamp,
    env_adj,
    environment,
    hand_split,
    hitter_stats,
    odds,
    recent_form,
    sf,
    statcast,
)

MODEL_VERSION = "HR V1.1"
LEAGUE_HR_PA = 0.0315
SEASON_PRIOR_PA = 180.0
STARTER_HR9_PRIOR = 1.15


def _e(v):
    return escape(str(v if v is not None else "—"))


def _rate(num, den):
    n = sf(num, 0) or 0
    d = sf(den, 0) or 0
    return n / d if d > 0 else None


def _statcast_power(sc):
    """Small-sample-safe Statcast multiplier."""
    if not sc:
        return 1.0, 0.0, "Unavailable", 0.0
    sample = max(sf(sc.get("bbe"), 0) or 0, (sf(sc.get("pa"), 0) or 0) * 0.65)
    rel = sample / (sample + 300.0) if sample else 0.0
    comps = []
    br = sf(sc.get("barrel_rate"))
    xs = sf(sc.get("xslg"))
    ev = sf(sc.get("avg_ev"))
    la = sf(sc.get("launch_angle"))
    if br is not None:
        comps.append(0.45 * clamp((br - 0.075) / 0.075, -1.25, 1.55))
    if xs is not None:
        comps.append(0.25 * clamp((xs - 0.420) / 0.190, -1.25, 1.55))
    if ev is not None:
        comps.append(0.20 * clamp((ev - 88.5) / 5.5, -1.25, 1.55))
    if la is not None:
        shape = 1.0 - abs(la - 18.0) / 18.0
        comps.append(0.10 * clamp(shape, -1.0, 1.0))
    raw = sum(comps) if comps else 0.0
    adj = clamp(0.16 * raw * rel, -0.10, 0.14)
    grade = "Elite Power" if adj >= 0.09 else "Power Boost" if adj >= 0.035 else "Power Suppression" if adj <= -0.05 else "Near Neutral"
    return 1.0 + adj, rel, grade, sample


def _projected_pa(candidate, stats):
    ab = float(ab_for_spot(candidate.get("position") or 4))
    pa = sf((stats or {}).get("plate_appearances"), 0) or 0
    sab = sf((stats or {}).get("at_bats"), 0) or 0
    ratio = clamp(pa / sab, 1.0, 1.20) if sab else 1.07
    return clamp(ab * ratio, 3.2, 5.35)


def _simulate(r, n):
    n = int(n)
    seed = int((int(r["player_id"]) * 1013 + int(r["game_pk"]) * 37 + 111) % (2**32 - 1))
    rng = np.random.default_rng(seed)
    base = float(r["hr_rate_pa"])
    pa_sample = max(float(r.get("season_pa", 0) or 0), 20.0)
    power_sample = float(r.get("statcast_sample", 0) or 0)
    effective_sample = 0.80 * pa_sample + 0.20 * power_sample
    kappa = float(clamp(70.0 + 0.45 * effective_sample, 80.0, 320.0))
    a = max(base * kappa, 0.50)
    b = max((1.0 - base) * kappa, 0.50)
    done = 0
    batch = 250_000
    one = two = total_hr = 0
    probs = []
    while done < n:
        k = min(batch, n - done)
        rates = rng.beta(a, b, k)
        pas = np.clip(np.rint(rng.normal(float(r["projected_pa"]), 0.36, k)).astype(np.int8), 2, 7)
        hrs = rng.binomial(pas.astype(np.int16), rates)
        one += int(np.count_nonzero(hrs >= 1))
        two += int(np.count_nonzero(hrs >= 2))
        total_hr += int(hrs.sum())
        probs.append(float(np.mean(hrs >= 1)))
        done += k
    p1 = one / done
    p2 = two / done
    spread = (max(probs) - min(probs)) if probs else 0.0
    return {
        "n": done,
        "seed": seed,
        "p_hr": p1,
        "p_2hr": p2,
        "expected_hr": total_hr / done,
        "mc_se": math.sqrt(max(p1 * (1 - p1), 0) / done),
        "batch_range": spread,
        "converged": spread <= 0.006,
    }


def _model_candidate(c, deep=False, sims=500_000):
    pid = int(c["player_id"])
    stats = hitter_stats(pid) or {}
    pa = sf(stats.get("plate_appearances"), 0) or 0
    ab = sf(stats.get("at_bats"), 0) or 0
    hr = sf(stats.get("home_runs"), 0) or 0
    if pa <= 0 and ab > 0:
        pa = ab * 1.08
    if pa <= 0:
        return None

    raw_season = hr / pa
    # Strong season anchor: small samples are explicitly regressed toward league HR/PA.
    rate = (hr + LEAGUE_HR_PA * SEASON_PRIOR_PA) / (pa + SEASON_PRIOR_PA)
    season_rel = pa / (pa + SEASON_PRIOR_PA)

    pitcher = core._pitcher_hr_profile(c.get("starter_id"))
    hand = str((pitcher or {}).get("hand") or "").upper()

    split = None
    if hand in {"R", "L"}:
        try:
            split = hand_split(pid, hand)
        except Exception:
            split = None
    split_ab = sf((split or {}).get("at_bats"), 0) or 0
    split_hr = sf((split or {}).get("home_runs"), 0) or 0
    split_pa = split_ab * 1.08
    split_raw = split_hr / split_pa if split_pa > 0 else None
    if split_pa > 0:
        split_shrunk = (split_hr + rate * 140.0) / (split_pa + 140.0)
        w = 0.18 * split_pa / (split_pa + 250.0)
        rate = rate * (1.0 - w) + split_shrunk * w

    try:
        recent = recent_form(pid, 10)
    except Exception:
        recent = None
    recent_ab = sf((recent or {}).get("at_bats"), 0) or 0
    recent_hr = sf((recent or {}).get("home_runs"), 0) or 0
    recent_pa = recent_ab * 1.08
    recent_raw = recent_hr / recent_pa if recent_pa > 0 else None
    if recent_pa > 0:
        recent_shrunk = (recent_hr + rate * 90.0) / (recent_pa + 90.0)
        w = 0.055 * recent_pa / (recent_pa + 50.0)
        rate = rate * (1.0 - w) + recent_shrunk * w

    try:
        sc = statcast(pid)
    except Exception:
        sc = None
    power_mult, sc_rel, power_grade, sc_sample = _statcast_power(sc)
    rate *= power_mult

    hr9 = sf((pitcher or {}).get("hr9"))
    pitcher_ip = sf((pitcher or {}).get("true_innings"), 0) or 0
    pitcher_mult = 1.0
    shrunk_hr9 = None
    if hr9 is not None:
        p_rel = pitcher_ip / (pitcher_ip + 120.0) if pitcher_ip else 0.0
        shrunk_hr9 = STARTER_HR9_PRIOR * (1.0 - p_rel) + hr9 * p_rel
        dev = (shrunk_hr9 - STARTER_HR9_PRIOR) / STARTER_HR9_PRIOR
        pitcher_mult = 1.0 + clamp(0.14 * dev, -0.10, 0.12)
        rate *= pitcher_mult

    try:
        env = environment(int(c["game_pk"]))
    except Exception:
        env = None
    env_model = env_adj(env, c.get("venue_name") or "Unknown")
    env_raw = sf((env_model or {}).get("total_adjustment"), 0) or 0
    park_mult = 1.0 + clamp(env_raw * 2.2, -0.10, 0.10)
    rate *= park_mult

    # Dynamic ceiling: rookies/tiny samples cannot jump to elite per-PA HR rates on a hot week.
    sample_term = 0.020 * (pa / (pa + 250.0))
    production_term = 0.010 * clamp(hr / 30.0, 0.0, 1.0)
    statcast_term = 0.004 * sc_rel
    rate_cap = clamp(0.058 + sample_term + production_term + statcast_term, 0.060, 0.090)
    rate = clamp(rate, 0.0030, rate_cap)

    exp_pa = _projected_pa(c, stats)
    p1 = 1.0 - (1.0 - rate) ** exp_pa
    p2 = 1.0 - ((1.0 - rate) ** exp_pa + exp_pa * rate * ((1.0 - rate) ** max(exp_pa - 1.0, 0.0)))
    p2 = clamp(p2, 0.0, p1)

    quality = {
        "season": pa >= 100,
        "split": split_pa >= 60,
        "recent": recent_ab >= 20,
        "statcast": sc_sample >= 60,
        "pitcher": hr9 is not None and pitcher_ip >= 30,
        "environment": bool(env),
        "lineup": bool(c.get("lineup_confirmed")),
    }
    score = sum(bool(v) for v in quality.values())
    if score >= 6 and pa >= 250 and c.get("lineup_confirmed"):
        conf = "HIGH"
    elif score >= 5 and pa >= 120:
        conf = "MEDIUM-HIGH"
    elif score >= 4:
        conf = "MEDIUM"
    else:
        conf = "LOW"

    result = {
        **c,
        "season_hr": int(hr),
        "season_pa": int(pa),
        "raw_season_hr_rate": raw_season,
        "season_hr_rate": rate,
        "season_reliability": season_rel,
        "split_hr_rate": split_raw,
        "split_pa": split_pa,
        "recent_hr": int(recent_hr),
        "recent_ab": int(recent_ab),
        "recent_hr_rate": recent_raw,
        "statcast": sc,
        "statcast_reliability": sc_rel,
        "statcast_sample": sc_sample,
        "power_grade": power_grade,
        "pitcher": pitcher,
        "pitcher_hr9": hr9,
        "pitcher_hr9_shrunk": shrunk_hr9,
        "pitcher_multiplier": pitcher_mult,
        "environment_model": env_model,
        "park_multiplier": park_mult,
        "projected_pa": exp_pa,
        "hr_rate_pa": rate,
        "rate_cap": rate_cap,
        "p_hr": p1,
        "p_2hr": p2,
        "expected_hr": rate * exp_pa,
        "confidence": conf,
        "data_score": score,
        "sources": quality,
    }
    if deep:
        sim = _simulate(result, sims)
        result["sim"] = sim
        result["p_hr"] = sim["p_hr"]
        result["p_2hr"] = sim["p_2hr"]
        result["expected_hr"] = sim["expected_hr"]
    return result


def _bulk_prescreen(candidates):
    out = []
    def work(c):
        try:
            return _model_candidate(c, deep=False)
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(work, c) for c in candidates]
        total = len(futures)
        bar = st.progress(0, text="Building calibrated HR power profiles...")
        done = 0
        for fut in as_completed(futures):
            done += 1
            r = fut.result()
            if r:
                out.append(r)
            bar.progress(done / max(total, 1), text=f"Calibrating HR profiles {done}/{total}")
        bar.empty()
    return out


def _card(r, rank):
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    confirmed = "✅ CONFIRMED" if r.get("lineup_confirmed") else "🕒 PROJECTED"
    cls = "hr-card one" if rank == 1 else "hr-card"
    sc = r.get("statcast") or {}
    barrel = sf(sc.get("barrel_rate"))
    xslg = sf(sc.get("xslg"))
    hr9 = sf(r.get("pitcher_hr9"))
    barrel_text = f"{barrel*100:.1f}%" if barrel is not None else "—"
    xslg_text = f"{xslg:.3f}" if xslg is not None else "—"
    hr9_text = f"{hr9:.2f}" if hr9 is not None else "—"
    power_rel = float(r.get("statcast_reliability", 0) or 0)
    conf_cls = "" if r.get("confidence") == "HIGH" else " med"
    return f'''<div class="{cls}">
      <div class="hr-rank">{medal} Rank {rank} • {confirmed}</div>
      <div class="hr-name">{_e(r.get('player_name'))}</div>
      <div class="hr-meta">{_e(r.get('team'))} vs {_e(r.get('opponent'))}<br>vs {_e(r.get('starter_name'))} • Bat #{_e(r.get('position'))} • {_e(r.get('first_pitch'))}</div>
      <div class="hr-prob">{r['p_hr']*100:.1f}%</div><div class="hr-prob-label">1+ HR probability • Fair {odds(r['p_hr'])} • calibrated</div>
      <div class="hr-stats">
        <div class="hr-stat"><span>Season HR</span><b>{r.get('season_hr',0)}</b></div>
        <div class="hr-stat"><span>2+ HR</span><b>{r.get('p_2hr',0)*100:.1f}%</b></div>
        <div class="hr-stat"><span>Barrel%</span><b>{barrel_text}</b></div>
        <div class="hr-stat"><span>Starter HR/9</span><b>{hr9_text}</b></div>
        <div class="hr-stat"><span>xSLG</span><b>{xslg_text}</b></div>
        <div class="hr-stat"><span>Recent HR</span><b>{r.get('recent_hr',0)} / L10</b></div>
        <div class="hr-stat"><span>Proj PA</span><b>{r.get('projected_pa',0):.1f}</b></div>
        <div class="hr-stat"><span>Power sample</span><b>{power_rel*100:.0f}% rel</b></div>
      </div>
      <div class="hr-conf{conf_cls}">{_e(r.get('confidence'))}</div>
    </div>'''


def _render_results(results):
    if not results:
        return
    st.markdown('<div class="hr-panel-head"><b>💣 Strongest Calibrated Home Run Probabilities</b><span>pure probability • sample-size protected</span></div>', unsafe_allow_html=True)
    top = results[:5]
    st.markdown('<div class="hr-grid">' + ''.join(_card(r, i) for i, r in enumerate(top, 1)) + '</div>', unsafe_allow_html=True)
    if top:
        a = top[0]
        sim = a.get("sim") or {}
        st.markdown(
            f'<div class="hr-note"><b>Current HR #1:</b> {_e(a.get("player_name"))} • {a["p_hr"]*100:.1f}% 1+ HR • '
            f'Fair {odds(a["p_hr"])} • xHR {a.get("expected_hr",0):.3f} • calibrated HR/PA {a.get("hr_rate_pa",0)*100:.2f}% • '
            f'{int(sim.get("n",0)):,} simulations • MC SE {float(sim.get("mc_se",0))*100:.3f} pts • '
            f'{"converged" if sim.get("converged") else "watch convergence"}.</div>',
            unsafe_allow_html=True,
        )
    with st.expander("📋 Full calibrated HR rankings"):
        rows = []
        for i, r in enumerate(results, 1):
            sc = r.get("statcast") or {}
            rows.append({
                "Rank": i,
                "Player": r.get("player_name"),
                "Team": r.get("team"),
                "Opponent": r.get("opponent"),
                "Lineup": "CONFIRMED" if r.get("lineup_confirmed") else "PROJECTED",
                "Bat": r.get("position"),
                "1+ HR": f"{r['p_hr']*100:.1f}%",
                "2+ HR": f"{r.get('p_2hr',0)*100:.1f}%",
                "Fair": odds(r["p_hr"]),
                "Season HR": r.get("season_hr"),
                "Season PA": r.get("season_pa"),
                "Raw HR/PA": f"{r.get('raw_season_hr_rate',0)*100:.2f}%",
                "Model HR/PA": f"{r.get('hr_rate_pa',0)*100:.2f}%",
                "Barrel%": f"{(sf(sc.get('barrel_rate'),0) or 0)*100:.1f}%" if sc else "—",
                "Power rel": f"{float(r.get('statcast_reliability',0) or 0)*100:.0f}%",
                "Starter HR/9": f"{sf(r.get('pitcher_hr9')):.2f}" if sf(r.get('pitcher_hr9')) is not None else "—",
                "Confidence": r.get("confidence"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_home_run_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(core.CSS, unsafe_allow_html=True)
    day = schedule.current_selected_date()
    try:
        fresh, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh = pd.DataFrame()
        diag = {"date": str(day), "source": "none", "attempts": [{"provider": MODEL_VERSION, "error": str(exc)}]}
    games = fresh if fresh is not None and not fresh.empty else games_df
    count = int(len(games)) if games is not None else 0
    source = str((diag or {}).get("source") or "verified MLB slate")
    if count:
        st.success(f"💣 Home Run slate verified • {day} • {count} game(s) • {source}")
    else:
        st.error(f"Home Run could not load a verified MLB slate for {day}.")
        return

    st.markdown(
        '<div class="hr-hero"><div class="hr-kicker">KYRE SPORTS AI • MLB HOME RUN MONSTER</div>'
        '<div class="hr-title">💣 Home Run Command Center — V1.1</div>'
        '<div class="hr-sub">Calibrated pure HR probability. Season HR/PA is empirically shrunk first; platoon, recent form, Statcast power, starter HR/9 and park/weather then apply conservative sample-size-weighted adjustments. Tiny samples cannot dominate the board.</div>'
        '<div class="hr-pills"><div class="hr-pill">🎯 Pure probability</div><div class="hr-pill">🧪 Sample-size protected</div><div class="hr-pill">📡 Full verified slate</div><div class="hr-pill">🔒 Other modules frozen</div></div></div>',
        unsafe_allow_html=True,
    )

    st.info("🧪 V1.1 calibration guard: extreme Barrel%, xSLG, recent HR streaks and starter HR/9 are regressed by their actual sample size before they can move the final HR probability.")

    st.markdown('<div class="hr-panel"><div class="hr-panel-head"><b>🏆 Daily Home Run Scanner</b><span>full slate → calibrated finalists</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.5])
    with c1:
        include_live = st.checkbox("Include live games", value=False, key="hr11_live")
    with c2:
        depth = st.selectbox(
            "Simulation depth",
            ["Quick — 250K/finalist", "Standard — 500K/finalist", "Deep — 1M/finalist", "Final — 5M/finalist"],
            index=1,
            key="hr11_depth",
        )
    sims = {
        "Quick — 250K/finalist": 250_000,
        "Standard — 500K/finalist": 500_000,
        "Deep — 1M/finalist": 1_000_000,
        "Final — 5M/finalist": 5_000_000,
    }[depth]

    if st.button("🔥 SCAN CALIBRATED HOME RUN SLATE", use_container_width=True, type="primary", key="hr11_scan"):
        with st.spinner("Building confirmed + projected lineups..."):
            candidates, meta = core._candidate_pool(games, include_live)
        if not candidates:
            st.warning(f"No eligible hitters were found across {meta.get('checked',0)} actionable games.")
        else:
            st.info(
                f"{len(candidates)} hitters • {meta['usable_games']}/{meta['checked']} actionable games covered • "
                f"{meta['confirmed_hitters']} confirmed • {meta['projected_hitters']} projected"
            )
            screened = _bulk_prescreen(candidates)
            screened.sort(key=lambda x: x.get("p_hr", 0), reverse=True)
            finalists = screened[: min(12, len(screened))]
            deep = []
            bar = st.progress(0, text="Running calibrated HR finalist simulations...")
            for i, r in enumerate(finalists, 1):
                try:
                    deep_r = _model_candidate(r, deep=True, sims=sims)
                    if deep_r:
                        deep.append(deep_r)
                except Exception:
                    pass
                bar.progress(i / max(len(finalists), 1), text=f"Simulating HR finalist {i}/{len(finalists)}")
            bar.empty()
            deep.sort(key=lambda x: x.get("p_hr", 0), reverse=True)
            st.session_state["hr11_results"] = deep
            st.session_state["hr11_meta"] = meta
    st.markdown('</div>', unsafe_allow_html=True)

    meta = st.session_state.get("hr11_meta")
    if meta:
        st.caption(
            f"Coverage: {meta.get('usable_games',0)}/{meta.get('checked',0)} actionable games • "
            f"confirmed hitters {meta.get('confirmed_hitters',0)} • projected hitters {meta.get('projected_hitters',0)}. "
            "Projected batting orders reduce confidence; calibration history should prefer confirmed-lineup snapshots."
        )
    _render_results(st.session_state.get("hr11_results") or [])
