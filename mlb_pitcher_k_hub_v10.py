"""MLB Pitcher Strikeouts O/U Monster V1.0.

PITCHER STRIKEOUTS ONLY. This module is isolated from every existing MLB/WNBA
market. It owns its verified MLB schedule, probable-starter pool, workload/K
projection and player-prop grading.

Projection inputs (sportsbook-independent):
- season K/BF and K/9 with empirical shrinkage
- recent 10 / recent 5 start K and workload form
- projected innings / batters faced / pitch-count context
- opponent confirmed lineup, otherwise last official lineup, with hitter K rates
- pitcher hand / platoon strikeout context where available
- workload volatility and pitcher sample reliability

Sportsbook layer:
- Odds-API.io event matching through the already-connected app key
- DraftKings/FanDuel (or configured books) pitcher-strikeout props
- market line/price is used only to grade Over/Under, never to create expected Ks
- missing/unposted lines remain blank and can be entered manually in the board
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import requests
import streamlit as st

import mlb_schedule_v32 as schedule
from engine import MLB_API, clamp, hitter_stats, hand_split, ipfloat, odds, season, sf
from live_odds_feed import fetch_multi_odds, decimal_to_american
from slate_lineup_v204 import build_slate_player_context
from slate_odds_feed_v201 import fetch_mlb_events, _match_event, _window_for_games

MODEL_VERSION = "Pitcher K V1.0"
LEAGUE_PITCHER_K_BF = 0.225
LEAGUE_HITTER_K_RATE = 0.225

CSS = r"""
<style>
.pk-hero{background:radial-gradient(circle at 8% 0%,rgba(56,189,248,.14),transparent 36%),linear-gradient(145deg,#101b2b,#07131f);border:1px solid #28506a;border-radius:22px;padding:20px 22px;margin:5px 0 16px}.pk-kicker{color:#55dcff;font-size:.67rem;font-weight:950;letter-spacing:.17em;text-transform:uppercase}.pk-title{color:#fff;font-size:2rem;font-weight:1000;line-height:1.05;margin-top:5px}.pk-sub{color:#9cadc0;font-size:.83rem;line-height:1.55;margin-top:8px}.pk-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.pk-pill{border:1px solid #28506a;background:#091a28;border-radius:999px;padding:6px 9px;color:#c6d8e7;font-size:.62rem;font-weight:850}
.pk-panel{border:1px solid #293f59;background:linear-gradient(150deg,#0d1929,#08131f);border-radius:18px;padding:15px 16px;margin:11px 0}.pk-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.pk-head b{color:#f7fafc;font-size:1.05rem}.pk-head span{color:#7c91aa;font-size:.58rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase}.pk-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.pk-card{border:1px solid #27445e;background:linear-gradient(145deg,#0c1a2c,#08131f);border-radius:18px;padding:15px;min-width:0}.pk-card.one{border-color:#c99f19;box-shadow:inset 4px 0 #d6ab18}.pk-rank{color:#50d8ff;font-size:.58rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.pk-name{color:#fff;font-size:1.1rem;font-weight:1000;margin-top:7px}.pk-meta{color:#8da1b8;font-size:.66rem;line-height:1.55;margin-top:4px}.pk-side{font-size:1.1rem;color:#fff;font-weight:950;margin-top:11px}.pk-prob{font-size:2.45rem;color:#fff;font-weight:1000;line-height:1;margin-top:3px}.pk-prob-label{color:#8298ae;font-size:.58rem;text-transform:uppercase;font-weight:900;margin-top:3px}.pk-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:12px}.pk-stat{border:1px solid #203b55;background:#081522;border-radius:11px;padding:8px}.pk-stat span{display:block;color:#718ba3;font-size:.48rem;text-transform:uppercase;font-weight:900}.pk-stat b{display:block;color:#f6f9fd;font-size:.82rem;margin-top:3px}.pk-conf{display:inline-flex;border:1px solid #1d654b;background:#0a3326;color:#7beeb8;border-radius:999px;padding:4px 7px;font-size:.52rem;font-weight:950;margin-top:9px}.pk-conf.med{border-color:#715917;background:#3b300d;color:#ffe07a}.pk-note{border-left:3px solid #50d8ff;background:#071c2c;color:#b8c3d0;padding:9px 11px;font-size:.68rem;line-height:1.55;margin-top:10px}.pk-market{color:#f8d879;font-size:.58rem;font-weight:850;margin-top:8px}
@media(max-width:780px){.pk-grid{grid-template-columns:1fr}.pk-title{font-size:1.55rem}.pk-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _e(v):
    return escape(str(v if v is not None else "—"))


def _norm_name(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _american_decimal(v):
    try:
        return decimal_to_american(float(v))
    except Exception:
        return None


def _fmt_american(v):
    try:
        return f"{int(v):+d}"
    except Exception:
        return "—"


@st.cache_data(ttl=600, show_spinner=False)
def _pitcher_profile(pid):
    pid = int(pid)
    person = requests.get(f"{MLB_API}/people/{pid}", timeout=15)
    person.raise_for_status()
    p = (person.json().get("people") or [{}])[0]
    r = requests.get(
        f"{MLB_API}/people/{pid}/stats",
        params={"stats": "season", "group": "pitching", "season": season()},
        timeout=15,
    )
    r.raise_for_status()
    groups = r.json().get("stats") or []
    s = groups[0]["splits"][0].get("stat", {}) if groups and groups[0].get("splits") else {}
    ip = ipfloat(s.get("inningsPitched", "0.0"))
    k = sf(s.get("strikeOuts"), 0) or 0
    bf = sf(s.get("battersFaced"), 0) or 0
    starts = int(sf(s.get("gamesStarted"), 0) or 0)
    pitches = sf(s.get("numberOfPitches"), 0) or 0
    return {
        "id": pid,
        "name": p.get("fullName", f"Pitcher {pid}"),
        "hand": (p.get("pitchHand") or {}).get("code", "?"),
        "ip": ip,
        "k": k,
        "bf": bf,
        "starts": starts,
        "games": int(sf(s.get("gamesPlayed"), 0) or 0),
        "pitches": pitches,
        "era": sf(s.get("era")),
        "whip": sf(s.get("whip")),
        "k9": (k * 9.0 / ip) if ip else None,
        "k_bf": (k / bf) if bf else ((k / (ip * 4.25)) if ip else None),
        "ip_start": (ip / starts) if starts else None,
    }


@st.cache_data(ttl=600, show_spinner=False)
def _pitcher_logs(pid, n=14):
    pid = int(pid)
    r = requests.get(
        f"{MLB_API}/people/{pid}/stats",
        params={"stats": "gameLog", "group": "pitching", "season": season()},
        timeout=15,
    )
    r.raise_for_status()
    groups = r.json().get("stats") or []
    splits = groups[0].get("splits", []) if groups else []
    out = []
    for sp in splits[-max(int(n) * 2, 20):]:
        s = sp.get("stat") or {}
        ip = ipfloat(s.get("inningsPitched", "0.0"))
        if ip < 2.0:
            continue
        out.append({
            "ip": ip,
            "k": sf(s.get("strikeOuts"), 0) or 0,
            "bf": sf(s.get("battersFaced"), 0) or 0,
            "pitches": sf(s.get("numberOfPitches"), 0) or 0,
            "runs": sf(s.get("runs"), 0) or 0,
            "hits": sf(s.get("hits"), 0) or 0,
            "walks": sf(s.get("baseOnBalls"), 0) or 0,
        })
    return out[-int(n):]


def _recent_summary(logs, n):
    rows = list(logs or [])[-int(n):]
    if not rows:
        return None
    def avg(field):
        vals = [float(x.get(field, 0) or 0) for x in rows]
        return float(np.mean(vals)) if vals else None
    ip_vals = [float(x.get("ip", 0) or 0) for x in rows]
    k_vals = [float(x.get("k", 0) or 0) for x in rows]
    return {
        "starts": len(rows),
        "k": avg("k"),
        "ip": avg("ip"),
        "bf": avg("bf"),
        "pitches": avg("pitches"),
        "k_sd": float(np.std(k_vals, ddof=1)) if len(k_vals) > 1 else 1.6,
        "ip_sd": float(np.std(ip_vals, ddof=1)) if len(ip_vals) > 1 else .75,
        "k_bf": (sum(x.get("k", 0) for x in rows) / sum(x.get("bf", 0) for x in rows)) if sum(x.get("bf", 0) for x in rows) > 0 else None,
    }


def _hitter_k_rate(pid, pitcher_hand):
    try:
        hs = hitter_stats(int(pid)) or {}
    except Exception:
        hs = {}
    ab = sf(hs.get("at_bats"), 0) or 0
    bb = sf(hs.get("walks"), 0) or 0
    so = sf(hs.get("strikeouts"), 0) or 0
    pa = max(ab + bb, 0)
    season_rate = so / pa if pa >= 20 else None

    split_rate = None
    split_ab = 0
    if str(pitcher_hand).upper() in {"R", "L"}:
        try:
            sp = hand_split(int(pid), str(pitcher_hand).upper()) or {}
            split_ab = sf(sp.get("at_bats"), 0) or 0
            split_so = sf(sp.get("strikeouts"), 0) or 0
            if split_ab >= 15:
                split_rate = split_so / split_ab
        except Exception:
            pass

    if season_rate is None and split_rate is None:
        return LEAGUE_HITTER_K_RATE, 0
    if season_rate is None:
        return clamp(split_rate, .08, .38), min(split_ab, 100)
    if split_rate is None:
        return clamp(season_rate, .08, .38), min(pa, 250)
    rel = split_ab / (split_ab + 120.0)
    return clamp(season_rate * (1-rel) + split_rate * rel, .08, .38), min(pa + split_ab, 350)


def _opponent_k_factor(game_ctx, opponent_side, pitcher_hand, lineup_confirmed):
    players = list((game_ctx or {}).get(f"{opponent_side}_lineup") or [])[:9]
    ids = []
    for p in players:
        try:
            ids.append(int(p.get("player_id")))
        except Exception:
            pass
    if not ids:
        return 1.0, LEAGUE_HITTER_K_RATE, 0

    rates = []
    sample = 0
    with ThreadPoolExecutor(max_workers=min(9, len(ids))) as pool:
        futures = {pool.submit(_hitter_k_rate, pid, pitcher_hand): pid for pid in ids}
        for fut in as_completed(futures):
            try:
                rate, n = fut.result()
                rates.append(rate)
                sample += int(n or 0)
            except Exception:
                pass
    if not rates:
        return 1.0, LEAGUE_HITTER_K_RATE, 0
    raw = float(np.mean(rates))
    # Projected lineups get heavier regression to league average.
    prior = 3.0 if lineup_confirmed else 6.0
    adj = (raw * len(rates) + LEAGUE_HITTER_K_RATE * prior) / (len(rates) + prior)
    factor = clamp(adj / LEAGUE_HITTER_K_RATE, .82, 1.20)
    return factor, adj, sample


def _build_pitcher_candidate(row, side, ctx):
    if side == "away":
        pid, name, team = row.get("away_pitcher_id"), row.get("away_pitcher"), row.get("away_team")
        opponent, opp_side = row.get("home_team"), "home"
    else:
        pid, name, team = row.get("home_pitcher_id"), row.get("home_pitcher"), row.get("home_team")
        opponent, opp_side = row.get("away_team"), "away"
    try:
        pid = int(pid)
    except Exception:
        return None
    if pid <= 0:
        return None
    pk = int(row.get("game_pk"))
    game_ctx = (ctx or {}).get(pk) or {}
    confirmed = bool(game_ctx.get(f"{opp_side}_lineup_confirmed"))
    return {
        "player_id": pid,
        "player_name": name or f"Pitcher {pid}",
        "team": team,
        "opponent": opponent,
        "game_pk": pk,
        "first_pitch": row.get("first_pitch_et"),
        "status": row.get("status"),
        "opponent_side": opp_side,
        "opp_lineup_confirmed": confirmed,
        "game_ctx": game_ctx,
    }


def _project_pitcher(c):
    p = _pitcher_profile(c["player_id"])
    logs = _pitcher_logs(c["player_id"], 14)
    l10 = _recent_summary(logs, 10)
    l5 = _recent_summary(logs, 5)

    season_kbf = p.get("k_bf") or LEAGUE_PITCHER_K_BF
    bf = max(float(p.get("bf", 0) or 0), 0)
    # Regress season K/BF toward league average; rookies remain appropriately uncertain.
    kbf = (season_kbf * bf + LEAGUE_PITCHER_K_BF * 120.0) / (bf + 120.0)
    if l10 and l10.get("k_bf") is not None:
        kbf = kbf * .82 + float(l10["k_bf"]) * .18
    if l5 and l5.get("k_bf") is not None:
        kbf = kbf * .92 + float(l5["k_bf"]) * .08

    season_ip = p.get("ip_start") or 5.0
    ip_proj = float(season_ip)
    if l10 and l10.get("ip") is not None:
        ip_proj = ip_proj * .45 + float(l10["ip"]) * .55
    if l5 and l5.get("ip") is not None:
        ip_proj = ip_proj * .75 + float(l5["ip"]) * .25
    ip_proj = clamp(ip_proj, 3.6, 7.2)

    opp_factor, opp_k_rate, opp_sample = _opponent_k_factor(
        c.get("game_ctx"), c.get("opponent_side"), p.get("hand"), c.get("opp_lineup_confirmed")
    )
    kbf = clamp(kbf * opp_factor, .10, .38)

    # Workload: recent BF is better than generic BF/IP when available.
    bf_per_ip = 4.25
    if l10 and l10.get("bf") and l10.get("ip"):
        bf_per_ip = clamp(float(l10["bf"]) / float(l10["ip"]), 3.75, 5.15)
    bf_proj = clamp(ip_proj * bf_per_ip, 15.0, 31.0)
    xk = bf_proj * kbf

    # Anchor a little to recent K/start without letting hot/cold streaks dominate.
    if l10 and l10.get("k") is not None:
        xk = xk * .84 + float(l10["k"]) * .16
    if l5 and l5.get("k") is not None:
        xk = xk * .93 + float(l5["k"]) * .07
    xk = clamp(xk, 1.2, 11.5)

    ip_sd = clamp((l10 or {}).get("ip_sd", .8) or .8, .45, 1.35)
    sample_rel = clamp(bf / 500.0, 0, 1)
    workload_rel = clamp(len(logs) / 10.0, 0, 1)
    lineup_rel = 1.0 if c.get("opp_lineup_confirmed") else .72
    reliability = .45 * sample_rel + .35 * workload_rel + .20 * lineup_rel
    confidence = "HIGH" if reliability >= .78 else "MEDIUM-HIGH" if reliability >= .60 else "MEDIUM" if reliability >= .42 else "LOW"

    return {
        **{k:v for k,v in c.items() if k != "game_ctx"},
        "hand": p.get("hand"),
        "era": p.get("era"),
        "whip": p.get("whip"),
        "season_k": p.get("k"),
        "season_ip": p.get("ip"),
        "season_k9": p.get("k9"),
        "season_kbf": p.get("k_bf"),
        "projected_ip": ip_proj,
        "projected_bf": bf_proj,
        "projected_k": xk,
        "model_kbf": kbf,
        "opp_k_rate": opp_k_rate,
        "opp_k_factor": opp_factor,
        "opp_sample": opp_sample,
        "l10": l10,
        "l5": l5,
        "ip_sd": ip_sd,
        "reliability": reliability,
        "confidence": confidence,
    }


def _simulate_distribution(r, n_sims, seed):
    rng = np.random.default_rng(int(seed))
    n = int(n_sims)
    ip = rng.normal(float(r["projected_ip"]), float(r["ip_sd"]), n)
    ip = np.clip(ip, 2.5, 8.0)
    bfpi = float(r["projected_bf"]) / max(float(r["projected_ip"]), .1)
    bf_noise = rng.normal(bfpi, .22, n)
    bf = np.rint(np.clip(ip * bf_noise, 10, 35)).astype(np.int16)

    rel = float(r.get("reliability", .5))
    p_sd = .030 * (1.15 - .55 * rel)
    p = rng.normal(float(r["model_kbf"]), p_sd, n)
    p = np.clip(p, .06, .42)
    ks = rng.binomial(bf, p).astype(np.int16)

    max_bucket = 15
    counts = np.bincount(np.minimum(ks, max_bucket + 1), minlength=max_bucket + 2)
    pmf = counts / float(n)
    low, high = np.quantile(ks, [.05, .95])
    return {
        "n": n,
        "seed": int(seed),
        "mean": float(np.mean(ks)),
        "median": float(np.median(ks)),
        "mode": int(np.argmax(counts)),
        "low90": int(low),
        "high90": int(high),
        "pmf": pmf.tolist(),
        "p4": float(np.mean(ks >= 4)),
        "p5": float(np.mean(ks >= 5)),
        "p6": float(np.mean(ks >= 6)),
        "p7": float(np.mean(ks >= 7)),
        "p8": float(np.mean(ks >= 8)),
        "p9": float(np.mean(ks >= 9)),
        "p10": float(np.mean(ks >= 10)),
    }


def _grade_line(sim, line):
    try:
        line = float(line)
    except Exception:
        return None
    pmf = np.asarray(sim.get("pmf") or [], dtype=float)
    if pmf.size == 0:
        return None
    # Final bucket represents 16+; ordinary pitcher props are safely below it.
    values = np.arange(pmf.size, dtype=float)
    p_over = float(pmf[values > line].sum())
    p_under = float(pmf[values < line].sum())
    p_push = float(pmf[values == line].sum()) if abs(line - round(line)) < 1e-9 else 0.0
    denom = p_over + p_under
    fair_over = p_over / denom if denom > 0 else .5
    fair_under = p_under / denom if denom > 0 else .5
    side = "OVER" if fair_over >= fair_under else "UNDER"
    win = fair_over if side == "OVER" else fair_under
    return {
        "line": line,
        "p_over": p_over,
        "p_under": p_under,
        "p_push": p_push,
        "fair_over": fair_over,
        "fair_under": fair_under,
        "side": side,
        "win_prob": win,
        "fair_odds": odds(win),
    }


def _configured_odds():
    try:
        key = str(st.secrets.get("ODDS_API_IO_KEY") or "").strip()
    except Exception:
        key = ""
    try:
        books_raw = str(st.secrets.get("ODDS_BOOKMAKERS") or "FanDuel,DraftKings")
    except Exception:
        books_raw = "FanDuel,DraftKings"
    books = tuple(x.strip() for x in books_raw.split(",") if x.strip())
    return key, books


def _prop_market_name(name):
    key = " ".join(str(name or "").lower().replace("_", " ").replace("/", " ").split())
    return "strikeout" in key and ("player" in key or "pitcher" in key or "prop" in key)


def _parse_props(payload, pitcher_names):
    wanted = {_norm_name(x): x for x in pitcher_names if x}
    out = {name: [] for name in wanted.values()}
    for book, markets in (payload.get("bookmakers") or {}).items():
        for market in markets or []:
            if not _prop_market_name((market or {}).get("name")):
                continue
            updated = (market or {}).get("updatedAt")
            for row in (market or {}).get("odds") or []:
                label = str((row or {}).get("label") or (row or {}).get("name") or "")
                norm = _norm_name(label)
                match = None
                for wn, original in wanted.items():
                    if wn and (wn in norm or norm in wn):
                        match = original
                        break
                if not match:
                    continue
                line = None
                for field in ("hdp", "line", "max", "total"):
                    line = sf((row or {}).get(field))
                    if line is not None:
                        break
                if line is None:
                    continue
                out[match].append({
                    "book": str(book),
                    "line": float(line),
                    "over_dec": sf((row or {}).get("over")),
                    "under_dec": sf((row or {}).get("under")),
                    "updatedAt": updated,
                })
    return out


def _market_board(quotes):
    quotes = list(quotes or [])
    if not quotes:
        return None
    counts = Counter(round(float(x["line"]), 3) for x in quotes)
    best_count = max(counts.values())
    modes = sorted([line for line, count in counts.items() if count == best_count])
    line = float(np.median(modes))
    same = [x for x in quotes if abs(float(x["line"]) - line) < 1e-6]
    best_over = max((x for x in same if x.get("over_dec")), key=lambda x: float(x["over_dec"]), default=None)
    best_under = max((x for x in same if x.get("under_dec")), key=lambda x: float(x["under_dec"]), default=None)
    return {
        "line": line,
        "best_over_book": (best_over or {}).get("book"),
        "best_over_price": _american_decimal((best_over or {}).get("over_dec")),
        "best_under_book": (best_under or {}).get("book"),
        "best_under_price": _american_decimal((best_under or {}).get("under_dec")),
        "over_dec": (best_over or {}).get("over_dec"),
        "under_dec": (best_under or {}).get("under_dec"),
        "quote_count": len(same),
    }


def _fetch_market_lines(games_df, pitcher_rows):
    key, books = _configured_odds()
    if not key or games_df is None or games_df.empty:
        return {}, {"connected": False, "events": 0, "props": 0}
    try:
        start_iso, end_iso = _window_for_games(games_df)
        events = fetch_mlb_events(key, start_iso, end_iso)
    except Exception as exc:
        return {}, {"connected": False, "events": 0, "props": 0, "error": str(exc)}

    match_by_pk = {}
    ids = []
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        event = _match_event(events, row)
        if event and event.get("id") is not None:
            match_by_pk[pk] = event
            ids.append(event.get("id"))
    if not ids:
        return {}, {"connected": True, "events": 0, "props": 0}

    try:
        payloads = fetch_multi_odds(key, tuple(ids), books)
    except Exception as exc:
        return {}, {"connected": False, "events": len(ids), "props": 0, "error": str(exc)}
    by_id = {str(x.get("id")): x for x in payloads if isinstance(x, dict) and x.get("id") is not None}
    out = {}
    prop_count = 0
    for pk, event in match_by_pk.items():
        payload = by_id.get(str(event.get("id")))
        if not payload:
            continue
        names = [x.get("player_name") for x in pitcher_rows if int(x.get("game_pk", -1)) == pk]
        parsed = _parse_props(payload, names)
        for name, quotes in parsed.items():
            board = _market_board(quotes)
            if board:
                out[(pk, _norm_name(name))] = board
                prop_count += 1
    return out, {"connected": True, "events": len(match_by_pk), "props": prop_count, "books": books}


def _card(r, rank):
    g = r["grade"]
    market = r.get("market") or {}
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    cls = "pk-card one" if rank == 1 else "pk-card"
    conf_cls = "" if r.get("confidence") == "HIGH" else " med"
    l10k = ((r.get("l10") or {}).get("k"))
    l5k = ((r.get("l5") or {}).get("k"))
    price = market.get("best_over_price") if g["side"] == "OVER" else market.get("best_under_price")
    book = market.get("best_over_book") if g["side"] == "OVER" else market.get("best_under_book")
    market_text = f"{book} {_fmt_american(price)}" if book and price is not None else "manual/model line"
    lineup = "✅ CONFIRMED OPP LINEUP" if r.get("opp_lineup_confirmed") else "🕒 PROJECTED OPP LINEUP"
    return f'''<div class="{cls}">
      <div class="pk-rank">{medal} Rank {rank} • {lineup}</div>
      <div class="pk-name">{_e(r.get('player_name'))}</div>
      <div class="pk-meta">{_e(r.get('team'))} vs {_e(r.get('opponent'))} • {_e(r.get('hand'))}HP • {_e(r.get('first_pitch'))}</div>
      <div class="pk-side">{g['side']} {g['line']:g}</div>
      <div class="pk-prob">{g['win_prob']*100:.1f}%</div><div class="pk-prob-label">true {g['side'].lower()} probability • Fair {g['fair_odds']} • Push {g['p_push']*100:.1f}%</div>
      <div class="pk-stats">
        <div class="pk-stat"><span>Expected K</span><b>{r['sim']['mean']:.2f}</b></div>
        <div class="pk-stat"><span>Median / Mode</span><b>{r['sim']['median']:.0f} / {r['sim']['mode']}</b></div>
        <div class="pk-stat"><span>Proj IP</span><b>{r['projected_ip']:.1f}</b></div>
        <div class="pk-stat"><span>Season K/9</span><b>{r['season_k9']:.1f if r.get('season_k9') is not None else '—'}</b></div>
        <div class="pk-stat"><span>L10 K</span><b>{float(l10k):.1f if l10k is not None else '—'}</b></div>
        <div class="pk-stat"><span>L5 K</span><b>{float(l5k):.1f if l5k is not None else '—'}</b></div>
        <div class="pk-stat"><span>Opp K rate</span><b>{r['opp_k_rate']*100:.1f}%</b></div>
        <div class="pk-stat"><span>90% range</span><b>{r['sim']['low90']}–{r['sim']['high90']}</b></div>
      </div>
      <div class="pk-market">Market: {market_text}</div>
      <div class="pk-conf{conf_cls}">{_e(r.get('confidence'))}</div>
    </div>'''


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(CSS, unsafe_allow_html=True)
    selected = schedule.current_selected_date()
    fresh, diag = schedule.games_for_date_with_diagnostics(selected)
    if fresh is not None and not fresh.empty:
        games_df = fresh
        st.success(f"⚾ Pitcher K slate verified • {selected} • {len(games_df)} game(s) • {(diag or {}).get('source','MLB')}")
    else:
        st.error(f"Pitcher K could not load a verified MLB slate for {selected}.")
        return

    st.markdown(f'''<div class="pk-hero"><div class="pk-kicker">KYRE SPORTS AI • MLB PITCHER PROP INTELLIGENCE</div><div class="pk-title">🔥 Pitcher Strikeouts O/U — V1.0</div><div class="pk-sub">Workload-first strikeout projection with season K rate, recent starts, opponent lineup strikeout tendency and Monte Carlo distribution. Sportsbook lines grade the model; they never drive expected Ks.</div><div class="pk-pills"><span class="pk-pill">✅ Verified MLB slate</span><span class="pk-pill">🎯 Opponent K index</span><span class="pk-pill">🧠 Workload model</span><span class="pk-pill">🎲 Monte Carlo</span><span class="pk-pill">📡 DK/FD props when posted</span></div></div>''', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1.35])
    with c1:
        include_live = st.checkbox("Include live games", value=False, key="pk10_live")
    with c2:
        depth = st.selectbox("Simulation depth", ["Fast — 250K/pitcher", "Standard — 1M/pitcher", "Deep — 5M/pitcher"], index=1, key="pk10_depth")
    sims = {"Fast — 250K/pitcher":250_000, "Standard — 1M/pitcher":1_000_000, "Deep — 5M/pitcher":5_000_000}[depth]

    if st.button("🔥 BUILD PITCHER STRIKEOUT BOARD", use_container_width=True, type="primary", key="pk10_build"):
        active = []
        for _, row in games_df.iterrows():
            status = str(row.get("status") or "").lower()
            if any(x in status for x in ("final", "completed", "cancel", "postpon", "suspended")):
                continue
            if not include_live and any(x in status for x in ("in progress", "live", "delayed")):
                continue
            active.append(row)
        try:
            ctx = build_slate_player_context(games_df)
        except Exception:
            ctx = {}
        candidates = []
        for row in active:
            for side in ("away", "home"):
                c = _build_pitcher_candidate(row, side, ctx)
                if c:
                    candidates.append(c)
        if not candidates:
            st.warning("No verified probable starters are available yet for this slate.")
        else:
            projected = []
            errors = []
            bar = st.progress(0, text="Building pitcher workload + opponent K profiles...")
            with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as pool:
                futs = {pool.submit(_project_pitcher, c): c for c in candidates}
                done = 0
                for fut in as_completed(futs):
                    done += 1
                    try:
                        r = fut.result()
                        if r:
                            projected.append(r)
                    except Exception as exc:
                        errors.append(f"{futs[fut].get('player_name')}: {exc}")
                    bar.progress(done / max(len(candidates),1), text=f"Pitcher profiles {done}/{len(candidates)}")
            bar.empty()

            market_lines, market_meta = _fetch_market_lines(games_df, projected)
            for r in projected:
                r["market"] = market_lines.get((int(r["game_pk"]), _norm_name(r.get("player_name"))))

            bar = st.progress(0, text="Running pitcher K distributions...")
            projected.sort(key=lambda x: x.get("projected_k", 0), reverse=True)
            for i, r in enumerate(projected, 1):
                seed = 281000 + int(r["game_pk"]) % 100000 + int(r["player_id"]) % 10000
                r["sim"] = _simulate_distribution(r, sims, seed)
                bar.progress(i / max(len(projected),1), text=f"Simulating {i}/{len(projected)} starters")
            bar.empty()
            st.session_state["pk10_results"] = projected
            st.session_state["pk10_market_meta"] = market_meta
            st.session_state["pk10_errors"] = errors

    results = st.session_state.get("pk10_results") or []
    if not results:
        st.info("Build the board to load probable starters, sportsbook K props and strikeout distributions.")
        return

    market_meta = st.session_state.get("pk10_market_meta") or {}
    if market_meta.get("connected"):
        st.info(f"📡 Pitcher props feed connected • {market_meta.get('events',0)} event(s) matched • {market_meta.get('props',0)} pitcher K market(s) found")
    else:
        st.warning("Pitcher prop odds are not available right now. Model projections still work; enter lines manually below.")

    editor_rows = []
    for r in results:
        m = r.get("market") or {}
        editor_rows.append({
            "Pitcher": r.get("player_name"),
            "Team": r.get("team"),
            "Opponent": r.get("opponent"),
            "Expected K": round(float(r["sim"]["mean"]), 2),
            "Line": m.get("line"),
            "Line Source": "MARKET" if m.get("line") is not None else "ENTER MANUALLY",
        })
    board = pd.DataFrame(editor_rows)
    edited = st.data_editor(
        board,
        hide_index=True,
        use_container_width=True,
        disabled=["Pitcher", "Team", "Opponent", "Expected K", "Line Source"],
        column_config={"Line": st.column_config.NumberColumn("K Line", min_value=0.0, max_value=15.0, step=0.5, format="%.1f")},
        key="pk10_lines_editor",
    )

    by_name_team = {(str(r.get("player_name")), str(r.get("team"))): r for r in results}
    graded = []
    for _, row in edited.iterrows():
        line = sf(row.get("Line"))
        if line is None:
            continue
        r = by_name_team.get((str(row.get("Pitcher")), str(row.get("Team"))))
        if not r:
            continue
        g = _grade_line(r["sim"], line)
        if not g:
            continue
        item = dict(r)
        item["grade"] = g
        graded.append(item)
    graded.sort(key=lambda x: (x["grade"]["win_prob"], x.get("reliability",0)), reverse=True)

    if graded:
        st.markdown('<div class="pk-panel"><div class="pk-head"><b>🏆 Strongest Pitcher Strikeout O/U Projections</b><span>MODEL PROBABILITY AT POSTED / ENTERED LINE</span></div><div class="pk-grid">', unsafe_allow_html=True)
        for i, r in enumerate(graded[:5], 1):
            st.markdown(_card(r, i), unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

        overs = sorted((x for x in graded if x["grade"]["side"] == "OVER"), key=lambda x:x["grade"]["win_prob"], reverse=True)[:5]
        unders = sorted((x for x in graded if x["grade"]["side"] == "UNDER"), key=lambda x:x["grade"]["win_prob"], reverse=True)[:5]
        with st.expander("📋 Top Over / Under boards", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Top Overs**")
                for x in overs:
                    g=x["grade"]; st.write(f"{x['player_name']} — O {g['line']:g} • {g['fair_over']*100:.1f}% • Fair {odds(g['fair_over'])}")
            with c2:
                st.markdown("**Top Unders**")
                for x in unders:
                    g=x["grade"]; st.write(f"{x['player_name']} — U {g['line']:g} • {g['fair_under']*100:.1f}% • Fair {odds(g['fair_under'])}")
    else:
        st.info("No pitcher K lines are posted yet. Enter a K line in the table to grade Over/Under immediately.")

    with st.expander("🎲 Full pitcher projection table", expanded=False):
        rows=[]
        for r in results:
            s=r["sim"]
            rows.append({"Pitcher":r["player_name"],"Team":r["team"],"Opp":r["opponent"],"xK":round(s["mean"],2),"Median":s["median"],"Mode":s["mode"],"xIP":round(r["projected_ip"],1),"K/9":round(r["season_k9"],1) if r.get("season_k9") is not None else None,"4+":round(s["p4"]*100,1),"5+":round(s["p5"]*100,1),"6+":round(s["p6"]*100,1),"7+":round(s["p7"]*100,1),"8+":round(s["p8"]*100,1),"9+":round(s["p9"]*100,1),"10+":round(s["p10"]*100,1),"Confidence":r["confidence"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    errs = st.session_state.get("pk10_errors") or []
    if errs:
        st.caption(f"Pitcher profile health: {len(results)}/{len(results)+len(errs)} probable starters modeled • {len(errs)} profile error(s).")
    else:
        st.success(f"✅ Pitcher K scan health • {len(results)} probable starters modeled • 0 profile errors")
