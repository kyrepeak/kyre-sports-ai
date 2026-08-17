"""MLB batter component engines V1.0 — Total Bases, Runs, RBIs.

Isolated helper module for Matchup Explorer. It does not alter the frozen
standalone 1+ Hit, Home Run, H+R+RBI, pitcher K, game-market, live, or WNBA
models.

Principles:
- official MLB season/game-log data
- reuses the approved H+R+RBI matchup profile only for shared context
- Total Bases is simulated from PA-level 0/1B/2B/3B/HR outcomes
- Runs and RBIs are simulated independently from their own adjusted component
  rates with mild game-environment overdispersion
- sportsbook price is never a model input
"""
from __future__ import annotations

import math
import numpy as np
import requests

import mlb_hrrbi_hub_v10 as hrr
from engine import MLB_API, clamp, season, sf

VERSION = "MLB Batter Components V1.0"


def _official_profile(player_id):
    r = requests.get(
        f"{MLB_API}/people/{int(player_id)}/stats",
        params={"stats":"season", "group":"hitting", "season":season()},
        timeout=15,
    )
    r.raise_for_status()
    blocks = r.json().get("stats") or []
    s = blocks[0]["splits"][0].get("stat", {}) if blocks and blocks[0].get("splits") else {}
    pa = sf(s.get("plateAppearances"), 0) or 0
    ab = sf(s.get("atBats"), 0) or 0
    if pa <= 0 and ab > 0:
        pa = ab * 1.08
    return {
        "pa":pa,
        "ab":ab,
        "hits":sf(s.get("hits"),0) or 0,
        "doubles":sf(s.get("doubles"),0) or 0,
        "triples":sf(s.get("triples"),0) or 0,
        "hr":sf(s.get("homeRuns"),0) or 0,
        "tb":sf(s.get("totalBases"),0) or 0,
        "runs":sf(s.get("runs"),0) or 0,
        "rbi":sf(s.get("rbi"),0) or 0,
    }


def _recent_tb_rate(player_id, n=10):
    try:
        r = requests.get(
            f"{MLB_API}/people/{int(player_id)}/stats",
            params={"stats":"gameLog", "group":"hitting", "season":season()},
            timeout=15,
        )
        r.raise_for_status()
        blocks = r.json().get("stats") or []
        splits = blocks[0].get("splits", []) if blocks else []
        rows = splits[-int(n):]
        pa = tb = 0.0
        for sp in rows:
            s = sp.get("stat") or {}
            ab = sf(s.get("atBats"),0) or 0
            bb = sf(s.get("baseOnBalls"),0) or 0
            pa += max(ab + bb, 1.0)
            tb += sf(s.get("totalBases"),0) or 0
        return (tb/pa, len(rows), pa) if pa > 0 else (None, len(rows), 0)
    except Exception:
        return None, 0, 0


def _base_profile(candidate):
    r = hrr._profile_candidate(dict(candidate))
    if not r:
        return None
    return r


def _quantiles_from_counts(counts, n):
    probs = counts / max(float(n),1.0)
    cdf = np.cumsum(probs)
    median = int(np.searchsorted(cdf,.5))
    mode = int(np.argmax(counts))
    lo = int(np.searchsorted(cdf,.05))
    hi = int(np.searchsorted(cdf,.95))
    return median, mode, lo, hi


def _tb_model(candidate, sims=250_000):
    base = _base_profile(candidate)
    if not base:
        return {"error":"No shared matchup profile returned."}
    p = _official_profile(candidate["player_id"])
    pa = float(p.get("pa") or 0)
    if pa <= 0:
        return {"error":"No usable season PA sample."}

    # Use approved matchup-adjusted hit/HR rates; season extra-base composition
    # decides how non-HR hits split into singles/doubles/triples.
    hit_rate = float(base["hit_rate"])
    hr_rate = min(float(base["hr_rate"]), hit_rate)
    nonhr_hits = max(float(p["hits"] - p["hr"]), 1.0)
    dbl_share = clamp(float(p["doubles"])/nonhr_hits, .08, .40)
    tri_share = clamp(float(p["triples"])/nonhr_hits, 0.0, .08)
    if dbl_share + tri_share > .48:
        scale = .48/(dbl_share+tri_share)
        dbl_share *= scale; tri_share *= scale
    single_share = 1.0 - dbl_share - tri_share

    # Recent TB form is a small modifier, heavily shrunk.
    recent_rate, recent_games, recent_pa = _recent_tb_rate(candidate["player_id"],10)
    season_tb_pa = float(p["tb"])/pa if pa else 0.0
    tb_mult = 1.0
    if recent_rate is not None and recent_pa >= 18 and season_tb_pa > 0:
        rel = recent_pa/(recent_pa+70.0)
        tb_mult = 1.0 + clamp((recent_rate/season_tb_pa - 1.0)*.12*rel, -.08, .10)

    nonhr_rate = max(hit_rate-hr_rate, .001)
    p1 = nonhr_rate*single_share
    p2 = nonhr_rate*dbl_share
    p3 = nonhr_rate*tri_share
    p4 = hr_rate
    # Mild power-quality adjustment from recent TB form, while preserving hit prob.
    extra = clamp(tb_mult-1.0, -.08, .10)
    p4 *= 1.0 + extra*.70
    p2 *= 1.0 + extra*.45
    p3 *= 1.0 + extra*.25
    hit_sum = p1+p2+p3+p4
    if hit_sum > 0:
        scale = hit_rate/hit_sum
        p1*=scale; p2*=scale; p3*=scale; p4*=scale
    p0 = max(1.0-(p1+p2+p3+p4), .001)

    n = int(sims)
    rng = np.random.default_rng((int(candidate["player_id"])*991 + int(candidate["game_pk"])*37 + 12)%(2**32-1))
    target_pa = float(base["projected_pa"])
    counts = np.zeros(13,dtype=np.int64)  # 0..11, 12+
    total_sum = 0.0
    done=0
    batch=125_000
    probs=np.array([p0,p1,p2,p3,p4],dtype=float); probs=probs/probs.sum()
    values=np.array([0,1,2,3,4],dtype=np.int16)
    while done<n:
        k=min(batch,n-done)
        pas=np.clip(np.rint(rng.normal(target_pa,.38,k)).astype(np.int16),2,7)
        totals=np.zeros(k,dtype=np.int16)
        # Seven PA max; vectorize by active PA slot.
        for j in range(7):
            active=pas>j
            m=int(active.sum())
            if m:
                totals[active]+=rng.choice(values,size=m,p=probs)
        total_sum += float(totals.sum())
        counts += np.bincount(np.minimum(totals,12),minlength=13)[:13]
        done += k
    median,mode,lo,hi=_quantiles_from_counts(counts,done)
    ge=lambda x: float(counts[int(x):].sum()/done)
    return {
        "metric":"Total Bases","expected":total_sum/done,"median":median,"mode":mode,
        "p1":ge(1),"p2":ge(2),"p3":ge(3),"p4":ge(4),"range90":f"{lo}–{hi}",
        "n":done,"confidence":base.get("confidence","—"),"projected_pa":target_pa,
        "recent10": recent_rate*target_pa if recent_rate is not None else None,
        "profile":base,
    }


def _count_model(candidate, metric, sims=250_000):
    base = _base_profile(candidate)
    if not base:
        return {"error":"No shared matchup profile returned."}
    if metric == "Runs":
        rate=float(base["run_rate"]); key="runs"
    else:
        rate=float(base["rbi_rate"]); key="rbi"
    target_pa=float(base["projected_pa"])
    lam=max(rate*target_pa,.01)
    n=int(sims)
    rng=np.random.default_rng((int(candidate["player_id"])*1237 + int(candidate["game_pk"])*53 + (19 if key=="runs" else 31))%(2**32-1))
    counts=np.zeros(8,dtype=np.int64) # 0..6,7+
    total_sum=0.0; done=0; batch=125_000
    while done<n:
        k=min(batch,n-done)
        # Gamma latent factor gives realistic overdispersion and game-script variance.
        latent=rng.gamma(shape=7.0,scale=1/7.0,size=k)
        vals=rng.poisson(np.clip(lam*latent,0,4.5))
        vals=np.minimum(vals,7)
        total_sum += float(vals.sum())
        counts += np.bincount(vals,minlength=8)[:8]
        done += k
    median,mode,lo,hi=_quantiles_from_counts(counts,done)
    ge=lambda x: float(counts[int(x):].sum()/done)
    # Recent averages only as display context; matchup rate already contains capped recent blend.
    logs=base.get("logs") or []
    recent=None
    if logs:
        rows=logs[-10:]
        recent=sum(float(x.get("r" if key=="runs" else "rbi",0) or 0) for x in rows)/len(rows)
    return {
        "metric":metric,"expected":total_sum/done,"median":median,"mode":mode,
        "p1":ge(1),"p2":ge(2),"p3":ge(3),"range90":f"{lo}–{hi}",
        "n":done,"confidence":base.get("confidence","—"),"projected_pa":target_pa,
        "recent10":recent,"profile":base,
    }


def project_total_bases(candidate, sims=250_000):
    try:
        return _tb_model(candidate,sims)
    except Exception as exc:
        return {"error":f"{type(exc).__name__}: {exc}"}


def project_runs(candidate, sims=250_000):
    try:
        return _count_model(candidate,"Runs",sims)
    except Exception as exc:
        return {"error":f"{type(exc).__name__}: {exc}"}


def project_rbis(candidate, sims=250_000):
    try:
        return _count_model(candidate,"RBIs",sims)
    except Exception as exc:
        return {"error":f"{type(exc).__name__}: {exc}"}
