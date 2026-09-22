"""MLB Home Run Monster V1.0 — isolated full-slate HR probability engine.

HOME RUN ONLY. Does not modify 1+ Hit, Moneyline, Spread, Totals, Live Game,
WNBA, H+R+RBI or pitcher strikeouts.

Inputs:
- verified MLB slate from mlb_schedule_v32
- confirmed lineup, else last official lineup clearly labeled PROJECTED
- season HR/PA
- platoon HR rate vs probable starter hand
- recent HR form
- Baseball Savant Statcast power indicators (barrel rate, xSLG, EV, launch angle)
- opposing starter HR/9
- park/weather environment
- batting-order plate-appearance expectation

Sportsbook price is not an input. Ranking is pure modeled 1+ HR probability.
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
    hitter_stats,
    odds,
    pitcher_stats,
    recent_form,
    season,
    sf,
    statcast,
)

MODEL_VERSION = "HR V1.0"

CSS = r"""
<style>
.hr-hero{background:radial-gradient(circle at 8% 0%,rgba(255,91,55,.18),transparent 34%),linear-gradient(145deg,#1a1321,#081522);border:1px solid #5b334e;border-radius:22px;padding:20px 22px;margin:5px 0 16px}.hr-kicker{color:#ff7b70;font-size:.67rem;font-weight:950;letter-spacing:.17em;text-transform:uppercase}.hr-title{color:#fff;font-size:2rem;font-weight:1000;line-height:1.05;margin-top:5px}.hr-sub{color:#9cabc0;font-size:.83rem;line-height:1.55;margin-top:8px}.hr-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.hr-pill{border:1px solid #4b3850;background:#171422;border-radius:999px;padding:6px 9px;color:#d7c9d8;font-size:.62rem;font-weight:850}
.hr-panel{border:1px solid #293c55;background:linear-gradient(150deg,#0d1929,#08131f);border-radius:18px;padding:15px 16px;margin:11px 0}.hr-panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.hr-panel-head b{color:#f6f8fb;font-size:1.05rem}.hr-panel-head span{color:#7c91aa;font-size:.58rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase}
.hr-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.hr-card{border:1px solid #27445e;background:linear-gradient(145deg,#0c1a2c,#08131f);border-radius:18px;padding:15px;min-width:0}.hr-card.one{border-color:#c99f19;box-shadow:inset 4px 0 #d6ab18}.hr-rank{color:#4bd6ff;font-size:.58rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.hr-name{color:#fff;font-size:1.1rem;font-weight:1000;margin-top:7px}.hr-meta{color:#8da1b8;font-size:.66rem;line-height:1.55;margin-top:4px}.hr-prob{font-size:2.45rem;color:#fff;font-weight:1000;line-height:1;margin-top:13px}.hr-prob-label{color:#8298ae;font-size:.58rem;text-transform:uppercase;font-weight:900;margin-top:3px}.hr-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:12px}.hr-stat{border:1px solid #203b55;background:#081522;border-radius:11px;padding:8px}.hr-stat span{display:block;color:#718ba3;font-size:.48rem;text-transform:uppercase;font-weight:900}.hr-stat b{display:block;color:#f6f9fd;font-size:.82rem;margin-top:3px}.hr-conf{display:inline-flex;border:1px solid #1d654b;background:#0a3326;color:#7beeb8;border-radius:999px;padding:4px 7px;font-size:.52rem;font-weight:950;margin-top:9px}.hr-conf.med{border-color:#715917;background:#3b300d;color:#ffe07a}.hr-note{border-left:3px solid #ff765d;background:#171724;color:#b8c3d0;padding:9px 11px;font-size:.68rem;line-height:1.55;margin-top:10px}
@media(max-width:780px){.hr-grid{grid-template-columns:1fr}.hr-title{font-size:1.55rem}.hr-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _e(v):
    return escape(str(v if v is not None else "—"))


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _rate(num, den):
    n = sf(num, 0) or 0
    d = sf(den, 0) or 0
    return (n / d) if d > 0 else None


@st.cache_data(ttl=600, show_spinner=False)
def _pitcher_hr_profile(pid):
    """Starter season HR prevention layer using official MLB pitching stats."""
    if pid is None:
        return None
    try:
        pid = int(pid)
        base = pitcher_stats(pid) or {}
        r = requests.get(
            f"{MLB_API}/people/{pid}/stats",
            params={"stats": "season", "group": "pitching", "season": season()},
            timeout=15,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []
        s = groups[0]["splits"][0].get("stat", {}) if groups and groups[0].get("splits") else {}
        ip = sf(base.get("true_innings"), 0) or 0
        hr = sf(s.get("homeRuns"), 0) or 0
        return {
            **base,
            "home_runs_allowed": int(hr),
            "hr9": (hr * 9 / ip) if ip else None,
            "reliability": ip / (ip + 60.0) if ip else 0.0,
        }
    except Exception:
        return None


def _power_adjustment(sc):
    """Convert Statcast power indicators to a conservative HR-rate multiplier."""
    if not sc:
        return 1.0, 0.0, "Unavailable"
    rel = max(sf(sc.get("bbe"), 0) or 0, (sf(sc.get("pa"), 0) or 0) * .65)
    rel = rel / (rel + 100.0) if rel else 0.0
    comps = []
    br = sf(sc.get("barrel_rate"))
    xs = sf(sc.get("xslg"))
    ev = sf(sc.get("avg_ev"))
    la = sf(sc.get("launch_angle"))
    if br is not None:
        comps.append(.42 * clamp((br - .08) / .08, -1.4, 1.8))
    if xs is not None:
        comps.append(.27 * clamp((xs - .420) / .190, -1.4, 1.8))
    if ev is not None:
        comps.append(.19 * clamp((ev - 88.5) / 5.0, -1.4, 1.8))
    if la is not None:
        # HR-friendly average launch-angle window is rewarded; extreme shapes are penalized.
        shape = 1.0 - abs(la - 18.0) / 18.0
        comps.append(.12 * clamp(shape, -1.0, 1.0))
    raw = sum(comps) if comps else 0.0
    adj = clamp(.32 * raw * rel, -.28, .38)
    mult = 1.0 + adj
    grade = "Elite Power" if adj >= .20 else "Power Boost" if adj >= .07 else "Power Suppression" if adj <= -.10 else "Near Neutral"
    return mult, rel, grade


def _projected_pa(candidate, stats):
    # Existing batting-order AB expectation plus the hitter's season PA/AB walk/HBP allowance.
    ab = float(ab_for_spot(candidate.get("position") or 4))
    pa = sf((stats or {}).get("plate_appearances"), 0) or 0
    sab = sf((stats or {}).get("at_bats"), 0) or 0
    ratio = clamp(pa / sab, 1.0, 1.22) if sab else 1.08
    return clamp(ab * ratio, 3.2, 5.4)


def _model_candidate(c, deep=False, sims=500_000):
    pid = int(c["player_id"])
    stats = hitter_stats(pid) or {}
    pa = sf(stats.get("plate_appearances"), 0) or 0
    hr = sf(stats.get("home_runs"), 0) or 0
    season_rate = _rate(hr, pa)
    if season_rate is None:
        return None

    pitcher = _pitcher_hr_profile(c.get("starter_id"))
    hand = (pitcher or {}).get("hand")
    split = None
    if hand in {"R", "L"}:
        try:
            split = hand_split(pid, hand)
        except Exception:
            split = None
    recent = None
    try:
        recent = recent_form(pid, 10)
    except Exception:
        recent = None

    rate = season_rate
    split_rate = None
    split_n = 0
    if split:
        split_n = sf(split.get("at_bats"), 0) or 0
        split_rate = _rate(split.get("home_runs"), split_n)
        if split_rate is not None and split_n:
            w = .28 * split_n / (split_n + 140.0)
            rate = rate * (1 - w) + split_rate * w

    recent_rate = None
    recent_n = 0
    if recent:
        recent_n = sf(recent.get("at_bats"), 0) or 0
        recent_rate = _rate(recent.get("home_runs"), recent_n)
        if recent_rate is not None and recent_n:
            w = .16 * recent_n / (recent_n + 40.0)
            rate = rate * (1 - w) + recent_rate * w

    sc = None
    try:
        sc = statcast(pid)
    except Exception:
        sc = None
    power_mult, sc_rel, power_grade = _power_adjustment(sc)
    rate *= power_mult

    pitcher_mult = 1.0
    hr9 = sf((pitcher or {}).get("hr9"))
    if hr9 is not None:
        rel = sf((pitcher or {}).get("reliability"), 0) or 0
        pitcher_mult = 1.0 + clamp(.26 * ((hr9 - 1.15) / 1.15) * rel, -.24, .28)
        rate *= pitcher_mult

    env = None
    try:
        env = environment(int(c["game_pk"]))
    except Exception:
        env = None
    env_model = env_adj(env, c.get("venue_name") or "Unknown")
    park_mult = 1.0 + clamp((sf(env_model.get("total_adjustment"), 0) or 0) * 4.5, -.22, .24)
    rate *= park_mult

    rate = clamp(rate, .0015, .125)
    exp_pa = _projected_pa(c, stats)
    p1 = 1.0 - (1.0 - rate) ** exp_pa
    p2 = 1.0 - ((1.0 - rate) ** exp_pa + exp_pa * rate * ((1.0 - rate) ** max(exp_pa - 1.0, 0.0)))
    p2 = clamp(p2, 0.0, p1)

    sources = {
        "season": bool(pa and pa >= 25),
        "split": bool(split_rate is not None),
        "recent": bool(recent_n),
        "statcast": bool(sc),
        "pitcher": bool(pitcher),
        "environment": bool(env),
        "lineup": bool(c.get("lineup_confirmed")),
    }
    score = sum(bool(v) for v in sources.values())
    if score >= 6 and c.get("lineup_confirmed"):
        conf = "HIGH"
    elif score >= 5:
        conf = "MEDIUM-HIGH"
    elif score >= 4:
        conf = "MEDIUM"
    else:
        conf = "LOW"

    result = {
        **c,
        "season_hr": int(hr),
        "season_pa": int(pa),
        "season_hr_rate": season_rate,
        "split_hr_rate": split_rate,
        "recent_hr": int(sf((recent or {}).get("home_runs"), 0) or 0),
        "recent_ab": int(recent_n),
        "statcast": sc,
        "power_grade": power_grade,
        "pitcher": pitcher,
        "pitcher_hr9": hr9,
        "environment_model": env_model,
        "projected_pa": exp_pa,
        "hr_rate_pa": rate,
        "p_hr": p1,
        "p_2hr": p2,
        "expected_hr": rate * exp_pa,
        "confidence": conf,
        "data_score": score,
        "sources": sources,
    }

    if deep:
        result["sim"] = _simulate_hr(result, sims)
        # Rank by computed simulation once available.
        result["p_hr"] = result["sim"]["p_hr"]
        result["p_2hr"] = result["sim"]["p_2hr"]
        result["expected_hr"] = result["sim"]["expected_hr"]
    return result


def _simulate_hr(r, n):
    n = int(n)
    seed = int((int(r["player_id"]) * 1009 + int(r["game_pk"]) * 31 + 101) % (2**32 - 1))
    rng = np.random.default_rng(seed)
    base = float(r["hr_rate_pa"])
    sample = max(int(r.get("season_pa", 0) or 0), 30)
    # Beta uncertainty around modeled per-PA HR rate; cap concentration so old samples do not become falsely certain.
    kappa = float(clamp(sample, 45, 420))
    a = max(base * kappa, .25)
    b = max((1.0 - base) * kappa, .25)
    done = 0
    batch = 250_000
    one = two = total_hr = 0
    probs = []
    while done < n:
        k = min(batch, n - done)
        rates = rng.beta(a, b, k)
        pas = np.clip(np.rint(rng.normal(float(r["projected_pa"]), .42, k)).astype(np.int8), 2, 7)
        hrs = rng.binomial(pas.astype(np.int16), rates)
        one += int(np.count_nonzero(hrs >= 1))
        two += int(np.count_nonzero(hrs >= 2))
        total_hr += int(hrs.sum())
        probs.append(float(np.mean(hrs >= 1)))
        done += k
    p1 = one / done
    p2 = two / done
    return {
        "n": done,
        "seed": seed,
        "p_hr": p1,
        "p_2hr": p2,
        "expected_hr": total_hr / done,
        "mc_se": math.sqrt(max(p1 * (1 - p1), 0) / done),
        "batch_range": (max(probs) - min(probs)) if probs else 0.0,
        "converged": (max(probs) - min(probs) <= .006) if probs else False,
    }


def _bulk_prescreen(candidates):
    out = []
    # Network-heavy player calls run concurrently; Streamlit cache keeps repeat scans fast.
    def work(c):
        try:
            return _model_candidate(c, deep=False)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(work, c) for c in candidates]
        total = len(futures)
        bar = st.progress(0, text="Building HR power profiles...")
        done = 0
        for fut in as_completed(futures):
            done += 1
            r = fut.result()
            if r:
                out.append(r)
            bar.progress(done / max(total, 1), text=f"Building HR profiles {done}/{total}")
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
    conf_cls = "" if r.get("confidence") == "HIGH" else " med"
    return f'''<div class="{cls}">
      <div class="hr-rank">{medal} Rank {rank} • {confirmed}</div>
      <div class="hr-name">{_e(r.get('player_name'))}</div>
      <div class="hr-meta">{_e(r.get('team'))} vs {_e(r.get('opponent'))}<br>vs {_e(r.get('starter_name'))} • Bat #{_e(r.get('position'))} • {_e(r.get('first_pitch'))}</div>
      <div class="hr-prob">{r['p_hr']*100:.1f}%</div><div class="hr-prob-label">1+ Home Run probability • Fair {odds(r['p_hr'])}</div>
      <div class="hr-stats">
        <div class="hr-stat"><span>Season HR</span><b>{r.get('season_hr',0)}</b></div>
        <div class="hr-stat"><span>2+ HR</span><b>{r.get('p_2hr',0)*100:.1f}%</b></div>
        <div class="hr-stat"><span>Barrel%</span><b>{barrel*100:.1f}%</b></div>
        <div class="hr-stat"><span>Starter HR/9</span><b>{hr9:.2f}</b></div>
        <div class="hr-stat"><span>xSLG</span><b>{xslg:.3f}</b></div>
        <div class="hr-stat"><span>Recent HR</span><b>{r.get('recent_hr',0)} / L10</b></div>
        <div class="hr-stat"><span>Proj PA</span><b>{r.get('projected_pa',0):.1f}</b></div>
        <div class="hr-stat"><span>Data</span><b>{r.get('data_score',0)}/7</b></div>
      </div>
      <div class="hr-conf{conf_cls}">{_e(r.get('confidence'))}</div>
    </div>'''.replace("<b>None", "<b>—")


def _render_results(results):
    if not results:
        return
    st.markdown('<div class="hr-panel-head"><b>💣 Strongest Home Run Probabilities</b><span>pure probability ranking</span></div>', unsafe_allow_html=True)
    top = results[:5]
    st.markdown('<div class="hr-grid">' + ''.join(_card(r, i) for i, r in enumerate(top, 1)) + '</div>', unsafe_allow_html=True)
    if top:
        a = top[0]
        sim = a.get("sim") or {}
        st.markdown(
            f'<div class="hr-note"><b>Current HR #1:</b> {_e(a.get("player_name"))} • {a["p_hr"]*100:.1f}% 1+ HR • '
            f'Fair {odds(a["p_hr"])} • xHR {a.get("expected_hr",0):.3f} • {int(sim.get("n",0)):,} simulations • '
            f'MC SE {float(sim.get("mc_se",0))*100:.3f} pts • {"converged" if sim.get("converged") else "watch convergence"}.</div>',
            unsafe_allow_html=True,
        )
    with st.expander("📋 Full HR rankings"):
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
                "Barrel%": f"{(sf(sc.get('barrel_rate'),0) or 0)*100:.1f}%" if sc else "—",
                "xSLG": f"{sf(sc.get('xslg')):.3f}" if sf(sc.get('xslg')) is not None else "—",
                "Starter HR/9": f"{sf(r.get('pitcher_hr9')):.2f}" if sf(r.get('pitcher_hr9')) is not None else "—",
                "Confidence": r.get("confidence"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_home_run_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(CSS, unsafe_allow_html=True)
    day = schedule.current_selected_date()
    try:
        fresh, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh = pd.DataFrame()
        diag = {"date": str(day), "source": "none", "attempts": [{"provider": "HR V1.0", "error": str(exc)}]}

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
        '<div class="hr-title">💣 Home Run Command Center — V1.0</div>'
        '<div class="hr-sub">Ranks hitters strictly by modeled home-run probability. Season power, platoon HR rate, recent HR form, Statcast power quality, starter HR/9, park/weather and batting-order opportunity are modeled independently from sportsbook price.</div>'
        '<div class="hr-pills"><div class="hr-pill">🎯 Pure probability</div><div class="hr-pill">📡 Full verified slate</div><div class="hr-pill">🧪 Statcast power layer</div><div class="hr-pill">🔒 Other modules frozen</div></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr-panel"><div class="hr-panel-head"><b>🏆 Daily Home Run Scanner</b><span>full slate → deep finalists</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.5])
    with c1:
        include_live = st.checkbox("Include live games", value=False, key="hr10_live")
    with c2:
        depth = st.selectbox(
            "Simulation depth",
            ["Quick — 250K/finalist", "Standard — 500K/finalist", "Deep — 1M/finalist", "Final — 5M/finalist"],
            index=1,
            key="hr10_depth",
        )
    sims = {
        "Quick — 250K/finalist": 250_000,
        "Standard — 500K/finalist": 500_000,
        "Deep — 1M/finalist": 1_000_000,
        "Final — 5M/finalist": 5_000_000,
    }[depth]

    if st.button("🔥 SCAN FULL HOME RUN SLATE", use_container_width=True, type="primary", key="hr10_scan"):
        with st.spinner("Building confirmed + projected lineups..."):
            candidates, meta = _candidate_pool(games, include_live)
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
            bar = st.progress(0, text="Running HR finalist simulations...")
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
            st.session_state["hr10_results"] = deep
            st.session_state["hr10_meta"] = meta
    st.markdown('</div>', unsafe_allow_html=True)

    meta = st.session_state.get("hr10_meta")
    if meta:
        st.caption(
            f"Coverage: {meta.get('usable_games',0)}/{meta.get('checked',0)} actionable games • "
            f"confirmed hitters {meta.get('confirmed_hitters',0)} • projected hitters {meta.get('projected_hitters',0)}. "
            "Projected batting orders are never labeled confirmed and reduce confidence."
        )
    _render_results(st.session_state.get("hr10_results") or [])
