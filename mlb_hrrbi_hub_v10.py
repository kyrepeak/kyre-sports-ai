"""MLB Hits + Runs + RBIs Monster V1.0 — isolated full-slate joint-event model.

H+R+RBI ONLY. Does not modify 1+ Hit, Home Run, Moneyline, Spread, Totals,
Live Game, Pitcher Strikeouts, or WNBA.

Model principles:
- verified MLB slate through mlb_schedule_v32
- confirmed batting order, otherwise last official order clearly PROJECTED
- season H/R/RBI rates with empirical shrinkage
- Last 10 / Last 5 recent-form blend
- platoon quality vs probable starter hand
- opposing starter quality + park/weather environment
- batting-order opportunity / projected PA
- home runs are simulated as a JOINT event: every HR contributes at least
  1 Hit + 1 Run + 1 RBI to the same simulated outcome
- shared game-environment latent factor correlates non-HR hits, runs and RBIs
- sportsbook price is never a model input

Primary scanner ranks by 2+ combined probability, with selectable 3+/4+/5+ views.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math

import numpy as np
import pandas as pd
import requests
import streamlit as st

import mlb_schedule_v32 as schedule
from mlb_hit_hub_v133 import _candidate_pool
from engine import (
    MLB_API,
    ab_for_spot,
    clamp,
    env_adj,
    environment,
    hand_split,
    odds,
    pitcher_stats,
    season,
    sf,
)

MODEL_VERSION = "H+R+RBI V1.0"
LEAGUE_HIT_PA = 0.225
LEAGUE_RUN_PA = 0.115
LEAGUE_RBI_PA = 0.110
PRIOR_PA = 120.0

CSS = r"""
<style>
.hrr-hero{background:radial-gradient(circle at 8% 0%,rgba(74,222,128,.13),transparent 36%),linear-gradient(145deg,#101b2a,#07131f);border:1px solid #28506a;border-radius:22px;padding:20px 22px;margin:5px 0 16px}.hrr-kicker{color:#5eead4;font-size:.67rem;font-weight:950;letter-spacing:.17em;text-transform:uppercase}.hrr-title{color:#fff;font-size:2rem;font-weight:1000;line-height:1.05;margin-top:5px}.hrr-sub{color:#9cadc0;font-size:.83rem;line-height:1.55;margin-top:8px}.hrr-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.hrr-pill{border:1px solid #28506a;background:#091a28;border-radius:999px;padding:6px 9px;color:#c6d8e7;font-size:.62rem;font-weight:850}
.hrr-panel{border:1px solid #293f59;background:linear-gradient(150deg,#0d1929,#08131f);border-radius:18px;padding:15px 16px;margin:11px 0}.hrr-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.hrr-head b{color:#f7fafc;font-size:1.05rem}.hrr-head span{color:#7c91aa;font-size:.58rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase}
.hrr-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.hrr-card{border:1px solid #27445e;background:linear-gradient(145deg,#0c1a2c,#08131f);border-radius:18px;padding:15px;min-width:0}.hrr-card.one{border-color:#c99f19;box-shadow:inset 4px 0 #d6ab18}.hrr-rank{color:#50d8ff;font-size:.58rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.hrr-name{color:#fff;font-size:1.1rem;font-weight:1000;margin-top:7px}.hrr-meta{color:#8da1b8;font-size:.66rem;line-height:1.55;margin-top:4px}.hrr-prob{font-size:2.45rem;color:#fff;font-weight:1000;line-height:1;margin-top:13px}.hrr-prob-label{color:#8298ae;font-size:.58rem;text-transform:uppercase;font-weight:900;margin-top:3px}.hrr-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:12px}.hrr-stat{border:1px solid #203b55;background:#081522;border-radius:11px;padding:8px}.hrr-stat span{display:block;color:#718ba3;font-size:.48rem;text-transform:uppercase;font-weight:900}.hrr-stat b{display:block;color:#f6f9fd;font-size:.82rem;margin-top:3px}.hrr-conf{display:inline-flex;border:1px solid #1d654b;background:#0a3326;color:#7beeb8;border-radius:999px;padding:4px 7px;font-size:.52rem;font-weight:950;margin-top:9px}.hrr-conf.med{border-color:#715917;background:#3b300d;color:#ffe07a}.hrr-note{border-left:3px solid #50d8ff;background:#071c2c;color:#b8c3d0;padding:9px 11px;font-size:.68rem;line-height:1.55;margin-top:10px}
@media(max-width:780px){.hrr-grid{grid-template-columns:1fr}.hrr-title{font-size:1.55rem}.hrr-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _e(v):
    return escape(str(v if v is not None else "—"))


def _int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def _rate(n, d):
    n = sf(n, 0) or 0
    d = sf(d, 0) or 0
    return n / d if d > 0 else None


@st.cache_data(ttl=600, show_spinner=False)
def _player_profile(pid):
    """Season counting profile from official MLB stats."""
    pid = int(pid)
    r = requests.get(
        f"{MLB_API}/people/{pid}/stats",
        params={"stats": "season", "group": "hitting", "season": season()},
        timeout=15,
    )
    r.raise_for_status()
    groups = r.json().get("stats") or []
    s = groups[0]["splits"][0].get("stat", {}) if groups and groups[0].get("splits") else {}
    pa = sf(s.get("plateAppearances"), 0) or 0
    ab = sf(s.get("atBats"), 0) or 0
    if pa <= 0 and ab > 0:
        pa = ab * 1.08
    return {
        "pa": pa,
        "ab": ab,
        "hits": sf(s.get("hits"), 0) or 0,
        "runs": sf(s.get("runs"), 0) or 0,
        "rbi": sf(s.get("rbi"), 0) or 0,
        "hr": sf(s.get("homeRuns"), 0) or 0,
        "bb": sf(s.get("baseOnBalls"), 0) or 0,
        "avg": sf(s.get("avg")),
        "obp": sf(s.get("obp")),
        "slg": sf(s.get("slg")),
        "ops": sf(s.get("ops")),
    }


@st.cache_data(ttl=600, show_spinner=False)
def _game_log(pid, n=20):
    """Recent official game logs with joint H/R/RBI/HR outcomes."""
    pid = int(pid)
    r = requests.get(
        f"{MLB_API}/people/{pid}/stats",
        params={"stats": "gameLog", "group": "hitting", "season": season()},
        timeout=15,
    )
    r.raise_for_status()
    groups = r.json().get("stats") or []
    splits = groups[0].get("splits", []) if groups else []
    rows = []
    for sp in splits[-int(n):]:
        s = sp.get("stat") or {}
        ab = sf(s.get("atBats"), 0) or 0
        bb = sf(s.get("baseOnBalls"), 0) or 0
        pa = max(ab + bb, 1.0)
        rows.append({
            "pa": pa,
            "h": sf(s.get("hits"), 0) or 0,
            "r": sf(s.get("runs"), 0) or 0,
            "rbi": sf(s.get("rbi"), 0) or 0,
            "hr": sf(s.get("homeRuns"), 0) or 0,
        })
    return rows


def _recent_rates(logs, n):
    rows = list(logs or [])[-int(n):]
    pa = sum(float(x.get("pa", 0) or 0) for x in rows)
    if pa <= 0:
        return None
    return {
        "games": len(rows),
        "pa": pa,
        "h": sum(float(x.get("h", 0) or 0) for x in rows) / pa,
        "r": sum(float(x.get("r", 0) or 0) for x in rows) / pa,
        "rbi": sum(float(x.get("rbi", 0) or 0) for x in rows) / pa,
        "hr": sum(float(x.get("hr", 0) or 0) for x in rows) / pa,
        "combined_pg": (sum(float(x.get("h", 0) or 0) + float(x.get("r", 0) or 0) + float(x.get("rbi", 0) or 0) for x in rows) / len(rows)) if rows else 0.0,
    }


def _projected_pa(c, p):
    ab = float(ab_for_spot(c.get("position") or 4))
    pa = float(p.get("pa", 0) or 0)
    sab = float(p.get("ab", 0) or 0)
    ratio = clamp(pa / sab, 1.0, 1.20) if sab else 1.07
    return clamp(ab * ratio, 3.2, 5.35)


def _lineup_component_factors(spot):
    spot = int(spot or 4)
    run = {1:1.10,2:1.08,3:1.05,4:1.00,5:.97,6:.94,7:.91,8:.88,9:.86}.get(spot,1.0)
    rbi = {1:.88,2:.94,3:1.05,4:1.12,5:1.10,6:1.04,7:.98,8:.92,9:.88}.get(spot,1.0)
    return run, rbi


def _profile_candidate(c):
    pid = int(c["player_id"])
    p = _player_profile(pid)
    pa = float(p.get("pa", 0) or 0)
    if pa <= 0:
        return None

    logs = _game_log(pid, 20)
    l10 = _recent_rates(logs, 10)
    l5 = _recent_rates(logs, 5)

    # Empirical-Bayes anchors prevent tiny samples from dominating.
    hit_rate = (p["hits"] + LEAGUE_HIT_PA * PRIOR_PA) / (pa + PRIOR_PA)
    run_rate = (p["runs"] + LEAGUE_RUN_PA * PRIOR_PA) / (pa + PRIOR_PA)
    rbi_rate = (p["rbi"] + LEAGUE_RBI_PA * PRIOR_PA) / (pa + PRIOR_PA)
    hr_rate = (p["hr"] + 0.0315 * 180.0) / (pa + 180.0)

    # Recent form: useful, but tightly capped.
    for recent, weight in ((l10, .10), (l5, .05)):
        if recent and recent.get("pa", 0) >= 12:
            rel = recent["pa"] / (recent["pa"] + 55.0)
            w = weight * rel
            hit_rate = hit_rate * (1-w) + recent["h"] * w
            run_rate = run_rate * (1-w) + recent["r"] * w
            rbi_rate = rbi_rate * (1-w) + recent["rbi"] * w
            hr_rate = hr_rate * (1-w*.6) + recent["hr"] * (w*.6)

    pitcher = None
    try:
        pitcher = pitcher_stats(c.get("starter_id")) if c.get("starter_id") else None
    except Exception:
        pitcher = None
    hand = str((pitcher or {}).get("hand") or "").upper()

    # Platoon layer mainly changes hit/contact quality; run/RBI follow only mildly.
    split = None
    if hand in {"R","L"}:
        try:
            split = hand_split(pid, hand)
        except Exception:
            split = None
    if split:
        sab = sf(split.get("at_bats"), 0) or 0
        savg = sf(split.get("avg"))
        sops = sf(split.get("ops"))
        if sab >= 20 and savg is not None and p.get("avg"):
            rel = sab / (sab + 160.0)
            contact_mult = 1.0 + clamp((savg / max(float(p["avg"]), .120) - 1.0) * .22 * rel, -.10, .10)
            hit_rate *= contact_mult
        if sab >= 20 and sops is not None and p.get("ops"):
            rel = sab / (sab + 180.0)
            quality_mult = 1.0 + clamp((sops / max(float(p["ops"]), .350) - 1.0) * .10 * rel, -.06, .06)
            run_rate *= quality_mult
            rbi_rate *= quality_mult
            hr_rate *= 1.0 + clamp((quality_mult - 1.0) * .65, -.04, .04)

    # Starter quality, regressed by workload.
    era = sf((pitcher or {}).get("era"))
    whip = sf((pitcher or {}).get("whip"))
    ip = sf((pitcher or {}).get("true_innings"), 0) or 0
    starter_mult = 1.0
    if era is not None or whip is not None:
        rel = ip / (ip + 100.0) if ip else .20
        era_dev = ((era - 4.20) / 4.20) if era is not None else 0.0
        whip_dev = ((whip - 1.28) / 1.28) if whip is not None else 0.0
        starter_mult = 1.0 + clamp((.10*era_dev + .08*whip_dev) * rel, -.10, .12)
        hit_rate *= 1.0 + (starter_mult - 1.0) * .70
        run_rate *= starter_mult
        rbi_rate *= starter_mult
        hr_rate *= 1.0 + (starter_mult - 1.0) * .65

    # Park/weather environment stays conservative.
    env = None
    try:
        env = environment(int(c["game_pk"]))
    except Exception:
        env = None
    em = env_adj(env, c.get("venue_name") or "Unknown")
    raw_env = sf((em or {}).get("total_adjustment"), 0) or 0
    park_mult = 1.0 + clamp(raw_env * 1.8, -.08, .08)
    hit_rate *= 1.0 + (park_mult - 1.0) * .55
    run_rate *= park_mult
    rbi_rate *= park_mult
    hr_rate *= 1.0 + (park_mult - 1.0) * .85

    run_spot, rbi_spot = _lineup_component_factors(c.get("position"))
    run_rate *= run_spot
    rbi_rate *= rbi_spot

    # Guardrails on component rates.
    hit_rate = clamp(hit_rate, .075, .360)
    run_rate = clamp(run_rate, .025, .260)
    rbi_rate = clamp(rbi_rate, .020, .275)
    hr_rate = clamp(hr_rate, .002, min(hit_rate*.55, .090))
    exp_pa = _projected_pa(c, p)

    expected_h = hit_rate * exp_pa
    expected_r = run_rate * exp_pa
    expected_rbi = rbi_rate * exp_pa
    expected_total = expected_h + expected_r + expected_rbi

    score = 0
    score += int(pa >= 100)
    score += int(pa >= 250)
    score += int(bool(l10 and l10.get("games",0) >= 8))
    score += int(bool(split and (sf(split.get("at_bats"),0) or 0) >= 40))
    score += int(bool(pitcher and ip >= 25))
    score += int(bool(env))
    score += int(bool(c.get("lineup_confirmed")))
    if score >= 6 and c.get("lineup_confirmed"):
        confidence = "HIGH"
    elif score >= 5:
        confidence = "MEDIUM-HIGH"
    elif score >= 4:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        **c,
        "profile": p,
        "logs": logs,
        "l10": l10,
        "l5": l5,
        "pitcher": pitcher,
        "environment_model": em,
        "projected_pa": exp_pa,
        "hit_rate": hit_rate,
        "run_rate": run_rate,
        "rbi_rate": rbi_rate,
        "hr_rate": hr_rate,
        "expected_h": expected_h,
        "expected_r": expected_r,
        "expected_rbi": expected_rbi,
        "expected_total": expected_total,
        "confidence": confidence,
        "data_score": score,
    }


def _simulate(r, n):
    """Joint H/R/RBI simulator with HR triple-count consistency."""
    n = int(n)
    seed = int((int(r["player_id"]) * 2029 + int(r["game_pk"]) * 43 + 210) % (2**32 - 1))
    rng = np.random.default_rng(seed)
    target_pa = float(r["projected_pa"])
    h_rate = float(r["hit_rate"])
    run_rate = float(r["run_rate"])
    rbi_rate = float(r["rbi_rate"])
    hr_rate = min(float(r["hr_rate"]), h_rate)

    done = 0
    batch = 250_000
    counts = np.zeros(9, dtype=np.int64)  # exact combined 0..7 and 8+
    sum_h = sum_r = sum_rbi = sum_total = 0.0
    p2_batches = []

    while done < n:
        k = min(batch, n-done)
        pas = np.clip(np.rint(rng.normal(target_pa, .38, k)).astype(np.int16), 2, 7)

        # Shared latent game environment introduces realistic positive covariance.
        latent = rng.gamma(shape=8.0, scale=1/8.0, size=k)
        hrp = np.clip(hr_rate * (0.88 + .12*latent), .0005, .18)
        hrs = rng.binomial(pas, hrp)

        remaining_pa = np.maximum(pas - hrs, 0)
        nonhr_hit_p = np.clip((h_rate-hr_rate) / max(1.0-hr_rate, .01) * (0.90 + .10*latent), .01, .48)
        nonhr_hits = rng.binomial(remaining_pa, nonhr_hit_p)
        hits = hrs + nonhr_hits

        # Every HR already contributes one run and one RBI. Simulate only residual pieces.
        residual_run_rate = max(run_rate-hr_rate, .005)
        residual_rbi_rate = max(rbi_rate-hr_rate, .005)
        hit_signal = np.clip((hits / np.maximum(pas,1)) / max(h_rate,.05), .55, 1.75)
        lam_r = residual_run_rate * pas * latent * (0.82 + .18*hit_signal)
        lam_rbi = residual_rbi_rate * pas * latent * (0.78 + .22*hit_signal)
        extra_r = rng.poisson(np.clip(lam_r, 0, 3.5))
        extra_rbi = rng.poisson(np.clip(lam_rbi, 0, 3.8))
        runs = hrs + extra_r
        rbis = hrs + extra_rbi

        # Practical per-game caps keep the tail realistic without suppressing true ceiling games.
        hits = np.minimum(hits, 6)
        runs = np.minimum(runs, 5)
        rbis = np.minimum(rbis, 7)
        total = hits + runs + rbis

        sum_h += float(hits.sum())
        sum_r += float(runs.sum())
        sum_rbi += float(rbis.sum())
        sum_total += float(total.sum())
        clipped = np.minimum(total, 8)
        counts += np.bincount(clipped, minlength=9)[:9]
        p2_batches.append(float(np.mean(total >= 2)))
        done += k

    probs_ge = {x: float(counts[x:].sum()/done) for x in range(1,9)}
    cdf = np.cumsum(counts) / done
    median = int(np.searchsorted(cdf, .5))
    mode = int(np.argmax(counts))
    spread = max(p2_batches)-min(p2_batches) if p2_batches else 0.0
    p2 = probs_ge[2]
    return {
        "n": done,
        "seed": seed,
        "expected_h": sum_h/done,
        "expected_r": sum_r/done,
        "expected_rbi": sum_rbi/done,
        "expected_total": sum_total/done,
        "median": median,
        "mode": mode,
        "p1": probs_ge[1],
        "p2": probs_ge[2],
        "p3": probs_ge[3],
        "p4": probs_ge[4],
        "p5": probs_ge[5],
        "p6": probs_ge[6],
        "p7": probs_ge[7],
        "p8": probs_ge[8],
        "mc_se_p2": math.sqrt(max(p2*(1-p2),0)/done),
        "batch_range_p2": spread,
        "converged": spread <= .006,
        "distribution": counts.tolist(),
    }


def _bulk_profiles(candidates):
    out = []
    def work(c):
        try:
            return _profile_candidate(c)
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        fs = [pool.submit(work,c) for c in candidates]
        total = len(fs)
        bar = st.progress(0, text="Building H+R+RBI player profiles...")
        for i, fut in enumerate(as_completed(fs),1):
            r = fut.result()
            if r:
                out.append(r)
            bar.progress(i/max(total,1), text=f"Building profiles {i}/{total}")
        bar.empty()
    return out


def _threshold_prob(sim, threshold):
    return float(sim.get(f"p{int(threshold)}", 0) or 0)


def _card(r, rank, threshold):
    sim = r["sim"]
    p = _threshold_prob(sim, threshold)
    medal = "🥇" if rank==1 else "🥈" if rank==2 else "🥉" if rank==3 else "•"
    source = "✅ CONFIRMED" if r.get("lineup_confirmed") else "🕒 PROJECTED"
    cls = "hrr-card one" if rank==1 else "hrr-card"
    conf_cls = "" if r.get("confidence")=="HIGH" else " med"
    l10 = (r.get("l10") or {}).get("combined_pg")
    l5 = (r.get("l5") or {}).get("combined_pg")
    return f'''<div class="{cls}">
      <div class="hrr-rank">{medal} Rank {rank} • {source}</div>
      <div class="hrr-name">{_e(r.get('player_name'))}</div>
      <div class="hrr-meta">{_e(r.get('team'))} vs {_e(r.get('opponent'))}<br>vs {_e(r.get('starter_name'))} • Bat #{_e(r.get('position'))} • {_e(r.get('first_pitch'))}</div>
      <div class="hrr-prob">{p*100:.1f}%</div><div class="hrr-prob-label">{threshold}+ H+R+RBI probability • Fair {odds(p)}</div>
      <div class="hrr-stats">
        <div class="hrr-stat"><span>xH</span><b>{sim['expected_h']:.2f}</b></div>
        <div class="hrr-stat"><span>xR</span><b>{sim['expected_r']:.2f}</b></div>
        <div class="hrr-stat"><span>xRBI</span><b>{sim['expected_rbi']:.2f}</b></div>
        <div class="hrr-stat"><span>xCombined</span><b>{sim['expected_total']:.2f}</b></div>
        <div class="hrr-stat"><span>3+</span><b>{sim['p3']*100:.1f}%</b></div>
        <div class="hrr-stat"><span>4+</span><b>{sim['p4']*100:.1f}%</b></div>
        <div class="hrr-stat"><span>L10</span><b>{l10:.1f}</b></div>
        <div class="hrr-stat"><span>L5</span><b>{l5:.1f}</b></div>
      </div>
      <div class="hrr-conf{conf_cls}">{_e(r.get('confidence'))}</div>
    </div>'''


def _render_results(results, threshold):
    if not results:
        return
    results = sorted(results, key=lambda r: _threshold_prob(r["sim"], threshold), reverse=True)
    top = results[:5]
    st.markdown(f'<div class="hrr-head"><b>🔥 Strongest {threshold}+ H+R+RBI Probabilities</b><span>joint-event pure probability ranking</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="hrr-grid">'+''.join(_card(r,i,threshold) for i,r in enumerate(top,1))+'</div>', unsafe_allow_html=True)
    a = top[0]
    sim = a["sim"]
    p = _threshold_prob(sim, threshold)
    st.markdown(
        f'<div class="hrr-note"><b>Current #{1}:</b> {_e(a.get("player_name"))} • {p*100:.1f}% for {threshold}+ • '
        f'Fair {odds(p)} • xH {sim["expected_h"]:.2f} • xR {sim["expected_r"]:.2f} • xRBI {sim["expected_rbi"]:.2f} • '
        f'xCombined {sim["expected_total"]:.2f} • Median {sim["median"]} • Mode {sim["mode"]} • {sim["n"]:,} sims • '
        f'MC SE(2+) {sim["mc_se_p2"]*100:.3f} pts • {"converged" if sim["converged"] else "watch convergence"}.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("📋 Full H+R+RBI rankings"):
        rows=[]
        for i,r in enumerate(results,1):
            s=r["sim"]
            rows.append({
                "Rank":i,"Player":r.get("player_name"),"Team":r.get("team"),"Opponent":r.get("opponent"),
                "Lineup":"CONFIRMED" if r.get("lineup_confirmed") else "PROJECTED","Bat":r.get("position"),
                "2+":f"{s['p2']*100:.1f}%","3+":f"{s['p3']*100:.1f}%","4+":f"{s['p4']*100:.1f}%","5+":f"{s['p5']*100:.1f}%",
                "xH":round(s['expected_h'],2),"xR":round(s['expected_r'],2),"xRBI":round(s['expected_rbi'],2),"xCombined":round(s['expected_total'],2),
                "Median":s['median'],"Mode":s['mode'],"Confidence":r.get("confidence")
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(CSS, unsafe_allow_html=True)
    day=schedule.current_selected_date()
    try:
        fresh,diag=schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh=pd.DataFrame();diag={"source":"none","attempts":[{"error":str(exc)}]}
    games=fresh if fresh is not None and not fresh.empty else games_df
    count=int(len(games)) if games is not None else 0
    source=str((diag or {}).get("source") or "verified MLB slate")
    if not count:
        st.error(f"H+R+RBI could not load a verified MLB slate for {day}.")
        return
    st.success(f"🧮 H+R+RBI slate verified • {day} • {count} game(s) • {source}")

    st.markdown(
        '<div class="hrr-hero"><div class="hrr-kicker">KYRE SPORTS AI • MLB HITS + RUNS + RBIS</div>'
        '<div class="hrr-title">🧮 H+R+RBI Command Center — V1.0</div>'
        '<div class="hrr-sub">Joint-event projection engine for Hits + Runs + RBIs. Home runs are modeled correctly as one hit, at least one run and at least one RBI in the same simulated event. Season production, recent form, platoon, starter quality, park/weather and batting-order opportunity are modeled independently from sportsbook price.</div>'
        '<div class="hrr-pills"><div class="hrr-pill">🎯 2+ primary</div><div class="hrr-pill">🔗 Joint-event simulation</div><div class="hrr-pill">📡 Full verified slate</div><div class="hrr-pill">🔒 Other modules frozen</div></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hrr-panel"><div class="hrr-head"><b>🏆 Daily H+R+RBI Scanner</b><span>full slate → joint-event finalists</span></div>', unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,1,1.5])
    with c1:
        include_live=st.checkbox("Include live games",value=False,key="hrr10_live")
    with c2:
        threshold=st.selectbox("Ranking threshold",[2,3,4,5],index=0,format_func=lambda x:f"{x}+",key="hrr10_threshold")
    with c3:
        depth=st.selectbox("Simulation depth",["Quick — 250K/finalist","Standard — 500K/finalist","Deep — 1M/finalist","Final — 5M/finalist"],index=1,key="hrr10_depth")
    sims={"Quick — 250K/finalist":250_000,"Standard — 500K/finalist":500_000,"Deep — 1M/finalist":1_000_000,"Final — 5M/finalist":5_000_000}[depth]

    if st.button("🔥 SCAN FULL H+R+RBI SLATE",use_container_width=True,type="primary",key="hrr10_scan"):
        with st.spinner("Building confirmed + projected batting orders..."):
            candidates,meta=_candidate_pool(games,include_live)
        if not candidates:
            st.warning(f"No eligible hitters were found across {meta.get('checked',0)} actionable games.")
        else:
            st.info(f"{len(candidates)} hitters • {meta['usable_games']}/{meta['checked']} actionable games covered • {meta['confirmed_hitters']} confirmed • {meta['projected_hitters']} projected")
            profiles=_bulk_profiles(candidates)
            profiles.sort(key=lambda x:x.get("expected_total",0),reverse=True)
            finalists=profiles[:min(20,len(profiles))]
            deep=[]
            bar=st.progress(0,text="Running joint H+R+RBI simulations...")
            for i,r in enumerate(finalists,1):
                try:
                    rr=dict(r);rr["sim"]=_simulate(rr,sims);deep.append(rr)
                except Exception:
                    pass
                bar.progress(i/max(len(finalists),1),text=f"Simulating finalist {i}/{len(finalists)}")
            bar.empty()
            deep.sort(key=lambda x:_threshold_prob(x["sim"],threshold),reverse=True)
            st.session_state["hrr10_results"]=deep
            st.session_state["hrr10_meta"]=meta
    st.markdown('</div>',unsafe_allow_html=True)

    meta=st.session_state.get("hrr10_meta")
    if meta:
        st.caption(f"Coverage: {meta.get('usable_games',0)}/{meta.get('checked',0)} actionable games • confirmed hitters {meta.get('confirmed_hitters',0)} • projected hitters {meta.get('projected_hitters',0)}. Projected lineups reduce confidence.")
    _render_results(st.session_state.get("hrr10_results") or [],threshold)
