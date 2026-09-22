"""WNBA Points V1.9.8.4.26 — Step 11 game script + blowout / close-game context.

Presentation/context-only wrapper over V1.9.8.4.25. Adds Step 11 to the same
Top-5 WNBA Points cards after Step 10.

Step 11 reads the existing WNBA SportsGameOdds full-game spread/total transport,
forms a same-slate consensus from available books, and exposes team spread,
game total, implied team total, expected margin, competitive/blowout context and
a close-game/overtime proxy. Market prices never feed back into the protected
Points projection, Monte Carlo probability, calibration or Top-5 ordering.

Important firewall: close-game / overtime context is a market-spread proxy only;
no direct overtime probability is invented. Stale market rows can be displayed
for transparency but are not scored when no fresh-enough row is available.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198425 as prior
import wnba_sportsgameodds_v1 as sgo
import wnba_schedule_v25 as schedule25

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.26 • STEP 11 GAME SCRIPT + BLOWOUT / CLOSE-GAME AUDIT"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_STEP10_COMBINER = getattr(
    prior,
    "_kyre_v198426_base_step10_combiner",
    prior._step7_8_9_10,
)
setattr(prior, "_kyre_v198426_base_step10_combiner", _BASE_STEP10_COMBINER)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, signed=False, suffix="") -> str:
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    text = f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"
    return text + suffix


def _compact_html(html: str) -> str:
    return re.sub(r">\s+<", "><", str(html or "").strip())


def _age_text(value) -> str:
    x = _num(value, np.nan)
    if pd.isna(x):
        return "UNKNOWN"
    if x < 60:
        return f"{int(x)}s"
    if x < 3600:
        return f"{int(round(x / 60.0))}m"
    return f"{x / 3600.0:.1f}h"


def _game_row(day: str, team_id: int):
    try:
        slate = schedule25.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()
    if slate is None or slate.empty:
        return None
    try:
        tid = int(team_id)
    except Exception:
        return None
    match = slate.loc[
        slate["away_team_id"].astype(int).eq(tid)
        | slate["home_team_id"].astype(int).eq(tid)
    ]
    return None if match.empty else match.iloc[0]


@st.cache_data(ttl=120, show_spinner=False, max_entries=16)
def _market_snapshot_for_day(day_str: str):
    try:
        return sgo.market_snapshot(pd.to_datetime(day_str).strftime("%Y-%m-%d"))
    except Exception as exc:
        return {"state": "ERROR", "error": f"{type(exc).__name__}: {exc}", "game_lines": pd.DataFrame()}


def _consensus_for_game(day: str, data: dict) -> dict:
    try:
        tid = int(float(data.get("TEAM_ID")))
    except Exception:
        return {"state": "NO_TEAM"}
    sched = _game_row(day, tid)
    if sched is None:
        return {"state": "NO_GAME"}

    game_id = str(sched.get("game_id") or "")
    away_id = int(_num(sched.get("away_team_id"), 0))
    home_id = int(_num(sched.get("home_team_id"), 0))
    side = "away" if tid == away_id else "home" if tid == home_id else ""
    if not side:
        return {"state": "TEAM_MATCH_FAILURE"}

    snap = _market_snapshot_for_day(day)
    frame = snap.get("game_lines") if isinstance(snap, dict) else pd.DataFrame()
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return {
            "state": str((snap or {}).get("state") or "NO_MARKET"),
            "game_id": game_id,
            "side": side,
            "team": str(sched.get(f"{side}_team") or ""),
            "opponent": str(sched.get("home_team") if side == "away" else sched.get("away_team") or ""),
        }

    rows = frame.loc[frame["game_id"].astype(str).eq(game_id)].copy()
    if rows.empty:
        return {"state": "NO_GAME_MARKET", "game_id": game_id, "side": side}

    rows["age_seconds"] = pd.to_numeric(rows.get("age_seconds"), errors="coerce")
    fresh = rows.loc[rows["age_seconds"].notna() & rows["age_seconds"].le(1800)].copy()
    scored_rows = fresh if not fresh.empty else rows.iloc[0:0].copy()
    display_rows = fresh if not fresh.empty else rows.copy()

    spread_col = f"{side}_spread"
    spread_vals = pd.to_numeric(display_rows.get(spread_col), errors="coerce").dropna()
    total_vals = pd.to_numeric(display_rows.get("total"), errors="coerce").dropna()
    team_spread = float(spread_vals.median()) if not spread_vals.empty else np.nan
    total = float(total_vals.median()) if not total_vals.empty else np.nan
    expected_margin = -team_spread if pd.notna(team_spread) else np.nan
    implied_team = (total - team_spread) / 2.0 if pd.notna(total) and pd.notna(team_spread) else np.nan
    implied_opp = (total + team_spread) / 2.0 if pd.notna(total) and pd.notna(team_spread) else np.nan

    all_frame = frame.copy()
    all_frame["age_seconds"] = pd.to_numeric(all_frame.get("age_seconds"), errors="coerce")
    all_fresh = all_frame.loc[all_frame["age_seconds"].notna() & all_frame["age_seconds"].le(1800)].copy()
    total_baseline = np.nan
    implied_baseline = np.nan
    if not all_fresh.empty:
        per_game_totals = []
        implied_values = []
        for gid, grp in all_fresh.groupby(all_fresh["game_id"].astype(str)):
            tvals = pd.to_numeric(grp.get("total"), errors="coerce").dropna()
            if not tvals.empty:
                t = float(tvals.median())
                per_game_totals.append(t)
                for scol in ("away_spread", "home_spread"):
                    svals = pd.to_numeric(grp.get(scol), errors="coerce").dropna()
                    if not svals.empty:
                        implied_values.append((t - float(svals.median())) / 2.0)
        if per_game_totals:
            total_baseline = float(np.median(per_game_totals))
        if implied_values:
            implied_baseline = float(np.median(implied_values))

    abs_spread = abs(team_spread) if pd.notna(team_spread) else np.nan
    if pd.isna(team_spread):
        role = "UNKNOWN"
    elif team_spread <= -0.25:
        role = "FAVORITE"
    elif team_spread >= 0.25:
        role = "UNDERDOG"
    else:
        role = "PICK'EM"

    if pd.isna(abs_spread):
        blowout = "DATA LIMITED"
        fourth_q = "DATA LIMITED"
        close_proxy = "DATA LIMITED"
    elif abs_spread >= 10:
        blowout, fourth_q, close_proxy = "HIGH", "ELEVATED", "LOW"
    elif abs_spread >= 7:
        blowout, fourth_q, close_proxy = "ELEVATED", "WATCH", "LOW"
    elif abs_spread <= 3:
        blowout, fourth_q, close_proxy = "LOW", "NORMAL", "ELEVATED"
    elif abs_spread <= 5.5:
        blowout, fourth_q, close_proxy = "LOW-MODERATE", "NORMAL", "MODERATE"
    else:
        blowout, fourth_q, close_proxy = "MODERATE", "NORMAL-WATCH", "LOW-MODERATE"

    total_delta = total - total_baseline if pd.notna(total) and pd.notna(total_baseline) else np.nan
    implied_delta = implied_team - implied_baseline if pd.notna(implied_team) and pd.notna(implied_baseline) else np.nan
    ages = pd.to_numeric(rows.get("age_seconds"), errors="coerce").dropna()
    freshest_age = float(ages.min()) if not ages.empty else np.nan

    return {
        "state": "FRESH" if not fresh.empty else "STALE_OR_UNKNOWN",
        "provider_state": str((snap or {}).get("state") or ""),
        "game_id": game_id,
        "side": side,
        "team": str(sched.get(f"{side}_team") or ""),
        "opponent": str(sched.get("home_team") if side == "away" else sched.get("away_team") or ""),
        "spread": team_spread,
        "total": total,
        "expected_margin": expected_margin,
        "implied_team": implied_team,
        "implied_opp": implied_opp,
        "total_baseline": total_baseline,
        "total_delta": total_delta,
        "implied_baseline": implied_baseline,
        "implied_delta": implied_delta,
        "role": role,
        "blowout": blowout,
        "fourth_q": fourth_q,
        "close_proxy": close_proxy,
        "books": int(display_rows["book"].astype(str).nunique()) if "book" in display_rows.columns else int(len(display_rows)),
        "fresh_books": int(scored_rows["book"].astype(str).nunique()) if not scored_rows.empty and "book" in scored_rows.columns else 0,
        "freshest_age": freshest_age,
        "book_names": ", ".join(sorted(display_rows["book"].dropna().astype(str).unique().tolist())[:6]) if "book" in display_rows.columns else "",
    }


def _grade(ctx: dict):
    if str(ctx.get("state")) != "FRESH":
        return "DATA LIMITED", "limited", "NEUTRAL", 0, 0, ["fresh-enough full-game spread/total unavailable"]

    score = 0
    evidence = 0
    reasons = []
    spread = _num(ctx.get("spread"), np.nan)
    total_delta = _num(ctx.get("total_delta"), np.nan)
    implied_delta = _num(ctx.get("implied_delta"), np.nan)

    if pd.notna(spread):
        evidence += 1
        a = abs(spread)
        if a <= 4:
            score += 1; reasons.append("competitive spread supports fourth-quarter role")
        elif a >= 10:
            score -= 2; reasons.append("double-digit spread creates blowout/minutes risk")
        elif a >= 7:
            score -= 1; reasons.append("wide spread creates blowout watch")
        else:
            reasons.append("moderate spread")

    if pd.notna(total_delta):
        evidence += 1
        if total_delta >= 5:
            score += 1; reasons.append(f"game total {total_delta:+.1f} vs slate")
        elif total_delta <= -5:
            score -= 1; reasons.append(f"game total {total_delta:+.1f} vs slate")
        else:
            reasons.append(f"game total near slate ({total_delta:+.1f})")

    if pd.notna(implied_delta):
        evidence += 1
        if implied_delta >= 4:
            score += 1; reasons.append(f"team implied total {implied_delta:+.1f} vs slate-team baseline")
        elif implied_delta <= -4:
            score -= 1; reasons.append(f"team implied total {implied_delta:+.1f} vs slate-team baseline")
        else:
            reasons.append(f"team implied total near slate-team baseline ({implied_delta:+.1f})")

    if evidence < 2:
        return "DATA LIMITED", "limited", "NEUTRAL", score, evidence, reasons
    if score >= 3:
        return "ELITE GAME SCRIPT", "elite", "SUPPORTS SCORER", score, evidence, reasons
    if score >= 1:
        return "FAVORABLE", "favorable", "SUPPORTS SCORER", score, evidence, reasons
    if score <= -3:
        return "HARD GAME SCRIPT", "hard", "HURTS SCORER", score, evidence, reasons
    if score <= -1:
        return "BLOWOUT / SCRIPT WATCH", "watch", "HURTS SCORER", score, evidence, reasons
    return "NEUTRAL", "neutral", "NEUTRAL", score, evidence, reasons


def _step11_block(day: str, data: dict) -> str:
    ctx = _consensus_for_game(day, data)
    grade, grade_class, verdict, score, evidence, reasons = _grade(ctx)
    state = str(ctx.get("state") or "DATA LIMITED")
    reason_text = " • ".join(reasons) if reasons else "market evidence unavailable"
    spread = _num(ctx.get("spread"), np.nan)
    total = _num(ctx.get("total"), np.nan)
    expected_margin = _num(ctx.get("expected_margin"), np.nan)
    implied_team = _num(ctx.get("implied_team"), np.nan)
    implied_opp = _num(ctx.get("implied_opp"), np.nan)
    total_delta = _num(ctx.get("total_delta"), np.nan)
    implied_delta = _num(ctx.get("implied_delta"), np.nan)
    freshness = _age_text(ctx.get("freshest_age"))

    html = f"""
<style>
.kyre-v198426-step11{{background:#171822;border:1px solid #665f87;border-radius:15px;padding:12px;margin-top:10px}}
.kyre-v198426-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#c8b9ff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
.kyre-v198426-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
.kyre-v198426-grade.elite,.kyre-v198426-grade.favorable{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198426-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
.kyre-v198426-grade.watch{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
.kyre-v198426-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198426-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198426-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198426-grid div{{border:1px solid #4e496a;border-radius:10px;padding:8px;background:#10111a}}
.kyre-v198426-grid small{{display:block;color:#9f96c2;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198426-grid strong{{display:block;color:#f6f3ff;font-size:.82rem;margin-top:3px;word-break:break-word}}
.kyre-v198426-detail{{background:#10111a;border:1px solid #4e496a;border-radius:10px;padding:9px;color:#ddd8ef;font-size:.66rem;line-height:1.52;margin-top:8px}}
.kyre-v198426-detail b{{color:#c8b9ff}}
.kyre-v198426-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#1d1b2b;border:1px solid #665f87;color:#f7f4ff;font-size:.68rem;font-weight:850}}
.kyre-v198426-note{{color:#89839f;font-size:.57rem;line-height:1.42;margin-top:7px}}
@media(max-width:760px){{.kyre-v198426-head{{align-items:flex-start;flex-direction:column}}}}
</style>
<div class="kyre-v198426-step11">
<div class="kyre-v198426-head"><span>STEP 11 • GAME SCRIPT + BLOWOUT / OVERTIME CONTEXT</span><span class="kyre-v198426-grade {grade_class}">{escape(grade)}</span></div>
<div class="kyre-v198426-grid">
<div><small>TEAM MARKET ROLE</small><strong>{escape(str(ctx.get('role') or '—'))}</strong></div><div><small>TEAM SPREAD</small><strong>{_fmt(spread,1,True)}</strong></div>
<div><small>GAME TOTAL</small><strong>{_fmt(total,1)}</strong></div><div><small>EXPECTED MARGIN</small><strong>{_fmt(expected_margin,1,True)}</strong></div>
<div><small>IMPLIED TEAM TOTAL</small><strong>{_fmt(implied_team,1)}</strong></div><div><small>IMPLIED OPP TOTAL</small><strong>{_fmt(implied_opp,1)}</strong></div>
<div><small>TOTAL VS SLATE</small><strong>{_fmt(total_delta,1,True)}</strong></div><div><small>TEAM TOTAL VS SLATE</small><strong>{_fmt(implied_delta,1,True)}</strong></div>
<div><small>BLOWOUT RISK</small><strong>{escape(str(ctx.get('blowout') or '—'))}</strong></div><div><small>4Q MINUTES RISK</small><strong>{escape(str(ctx.get('fourth_q') or '—'))}</strong></div>
<div><small>CLOSE-GAME / OT PROXY</small><strong>{escape(str(ctx.get('close_proxy') or '—'))}</strong></div><div><small>MARKET FRESHNESS</small><strong>{escape(freshness)}</strong></div>
<div><small>BOOKS AVAILABLE</small><strong>{int(ctx.get('books') or 0)}</strong></div><div><small>FRESH BOOKS SCORED</small><strong>{int(ctx.get('fresh_books') or 0)}</strong></div>
</div>
<div class="kyre-v198426-detail"><b>Game-script evidence</b> • {evidence} scored signals • score {score:+d}<br><b>Read</b> • {escape(reason_text)}<br><b>Sportsbook source</b> • SportsGameOdds WNBA full-game spread/total • {escape(str(ctx.get('book_names') or 'no book rows'))}<br><b>Freshness state</b> • {escape(state)} • rows older than 30 minutes are not scored when no fresh row is available<br><b>Overtime firewall</b> • close-game/OT context is inferred only as a spread-based proximity proxy; no direct overtime probability is claimed</div>
<div class="kyre-v198426-verdict">Game-script context • {escape(verdict)}</div>
<div class="kyre-v198426-note">Audit/context only • Step 11 does not feed sportsbook spread/total, blowout risk or close-game context back into the protected Points projection, Monte Carlo probability, calibration or Top-5 ordering.</div>
</div>
"""
    return _compact_html(html)


def _step7_8_9_10_11(day: str, data: dict) -> str:
    return _BASE_STEP10_COMBINER(day, data) + _step11_block(day, data)


def _install() -> None:
    # V1.9.8.4.25's installer dynamically assigns its _step7_8_9_10 global into
    # the final Step-9 render seam. Replace that global first, then let the full
    # established install chain execute so Steps 2-10 and all repairs remain.
    prior._step7_8_9_10 = _step7_8_9_10_11
    prior._install()


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎬 Points V1.9.8.4.26 • Step 11 game-script/blowout/close-game audit ACTIVE • "
        "SportsGameOdds spread+total • stale rows not scored • model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
