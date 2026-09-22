"""WNBA Rebounds + Assists V7 — Step 7 final Points-style daily pick cards.

Presentation-only layer over verified V6.

Step 7 rules:
- preserve Steps 1-6 exactly;
- consume only the saved Step-6 production-qualified Top-5 result for the exact
  current market snapshot;
- never rerun or alter projection, Monte Carlo, no-vig, EV, qualification or rank;
- add player photo, team/opponent logos, Last-5 ledger, deterministic reason-why,
  supporting evidence, concerns and display confidence;
- all Step-7 narrative is explanatory only and never feeds back into the model;
- never force five cards if Step 6 qualified fewer players.

No existing WNBA Points, Rebounds, Assists, PRA, Spread, Moneyline, Game Total,
Daily Picks, MLB or NFL model code is changed here.
"""
from __future__ import annotations

from html import escape
import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_ra_hub_v6 as prior

v5 = prior.v5
v3 = prior.v3
v2 = prior.v2
market = prior.market
ET = prior.ET

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V7 • STEP 7 FINAL DAILY PICK CARDS"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_int(value):
    try:
        return int(float(value))
    except Exception:
        return 0


def _pct(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _pp(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:+.{digits}f} pp"


def _odds(value):
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    i = int(round(x))
    return f"+{i}" if i > 0 else str(i)


def _fmt(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _age_text(seconds):
    x = _num(seconds, np.nan)
    if not np.isfinite(x):
        return "—"
    if x < 60:
        return f"{int(x)}s"
    if x < 3600:
        return f"{int(x // 60)}m"
    return f"{x / 3600.0:.1f}h"


def _pool_row_for_top(pool: pd.DataFrame, row):
    if pool is None or pool.empty:
        return None
    probe = {
        "game_id": row.get("game_id"),
        "PLAYER_NAME": row.get("player"),
    }
    return prior._pool_row(pool, probe)


def _img(url, alt, css_class, fallback=""):
    src = escape(str(url or ""), quote=True)
    alt_text = escape(str(alt or ""), quote=True)
    fb = escape(str(fallback or ""), quote=True)
    if src:
        if fb:
            onerror = f"this.onerror=null;this.src='{fb}';"
        else:
            onerror = "this.style.display='none';"
        return f'<img class="{css_class}" src="{src}" alt="{alt_text}" onerror="{onerror}">' 
    if fb:
        return f'<img class="{css_class}" src="{fb}" alt="{alt_text}">'
    return f'<div class="{css_class} kra7-placeholder">🏀</div>'


def _last5_payload(logs: pd.DataFrame, line: float, side: str):
    if logs is None or logs.empty:
        return [], {"games": 0, "avg": np.nan, "hits": 0, "rate": np.nan}
    work = logs.head(5).copy()
    rows = []
    hits = 0
    resolved = 0
    vals = []
    side = str(side or "").upper()
    for _, g in work.iterrows():
        ra = _num(g.get("RA"), np.nan)
        reb = _num(g.get("REB"), np.nan)
        ast = _num(g.get("AST"), np.nan)
        if np.isfinite(ra):
            vals.append(ra)
        if np.isfinite(ra) and np.isfinite(line):
            if ra == line:
                result = "PUSH"
                cls = "push"
            else:
                hit = (ra > line) if side == "OVER" else (ra < line)
                result = "HIT" if hit else "MISS"
                cls = "hit" if hit else "miss"
                resolved += 1
                hits += int(hit)
        else:
            result = "—"
            cls = "neutral"
        date = pd.to_datetime(g.get("game_date"), errors="coerce")
        date_text = date.strftime("%b %d") if not pd.isna(date) else "—"
        location = str(g.get("location") or "").upper()
        loc = "vs" if location == "HOME" else "@"
        opp = escape(str(g.get("opponent") or "Opponent"))
        rows.append({
            "date": date_text,
            "opp": f"{loc} {opp}",
            "reb": reb,
            "ast": ast,
            "ra": ra,
            "result": result,
            "cls": cls,
        })
    avg = float(np.mean(vals)) if vals else np.nan
    rate = hits / resolved if resolved else np.nan
    return rows, {"games": len(rows), "avg": avg, "hits": hits, "resolved": resolved, "rate": rate}


def _confidence(row):
    p = _num(row.get("model_prob"), 0.0)
    edge = _num(row.get("edge"), 0.0)
    ev = _num(row.get("ev"), 0.0)
    q = str(row.get("quality") or "LOW").upper()
    conv = bool(row.get("converged"))
    grade = str(row.get("grade") or "QUALIFIED").upper()
    if conv and q == "HIGH" and p >= 0.65 and edge >= 0.10 and ev >= 0.10:
        return "VERY HIGH", "elite"
    if conv and q in {"HIGH", "MEDIUM"} and (grade == "ELITE" or (p >= 0.60 and edge >= 0.05)):
        return "HIGH", "high"
    return "SOLID", "solid"


def _reason_payload(row, projection: dict, l5meta: dict):
    side = str(row.get("side") or "").upper()
    line = _num(row.get("line"), np.nan)
    proj = _num(row.get("proj_ra"), np.nan)
    p = _num(row.get("model_prob"), np.nan)
    edge = _num(row.get("edge"), np.nan)
    ev = _num(row.get("ev"), np.nan)
    q = str(row.get("quality") or "LOW").upper()
    age = _num(row.get("quote_age_seconds"), np.nan)
    push = _num(row.get("push_prob"), 0.0)
    proj_min = _num(row.get("proj_min"), np.nan)
    pace = _num((projection or {}).get("pace_factor"), np.nan)
    reb_env = _num((projection or {}).get("reb_env_factor"), np.nan)
    ast_env = _num((projection or {}).get("ast_env_factor"), np.nan)
    corr = _num((projection or {}).get("corr"), np.nan)

    cushion = (proj - line) if side == "OVER" else (line - proj)
    direction = "above" if side == "OVER" else "below"

    reasons = []
    supports = []
    concerns = []

    if np.isfinite(p):
        reasons.append(f"5M model gives the {side.title()} a {_pct(p)} no-push probability.")
    if np.isfinite(cushion):
        reasons.append(f"Projected R+A is {_fmt(abs(cushion))} {direction} the exact {line:.1f} line.")
    if np.isfinite(edge):
        reasons.append(f"Model beats the same-book no-vig market by {_pp(edge)}.")
    if np.isfinite(ev):
        supports.append(f"Push-aware EV is {_pct(ev)} at the verified price.")
    if q:
        supports.append(f"Model data quality is {q} with {int(row.get('history_games',0) or 0)} completed-game history samples.")
    if np.isfinite(proj_min):
        supports.append(f"Projected workload is {_fmt(proj_min)} minutes.")

    l5rate = _num(l5meta.get("rate"), np.nan)
    l5avg = _num(l5meta.get("avg"), np.nan)
    l5resolved = int(l5meta.get("resolved", 0) or 0)
    if np.isfinite(l5rate) and l5resolved:
        if l5rate >= 0.60:
            supports.append(f"Recent form supports the side: {int(l5meta.get('hits',0))}/{l5resolved} resolved Last-5 games hit this exact-line direction.")
        elif l5rate <= 0.40:
            concerns.append(f"Recent exact-line form is mixed/weak: {int(l5meta.get('hits',0))}/{l5resolved} resolved Last-5 games hit this side.")
    if np.isfinite(l5avg) and np.isfinite(line):
        recent_cushion = (l5avg - line) if side == "OVER" else (line - l5avg)
        if recent_cushion >= 1.0:
            supports.append(f"Last-5 R+A average is {_fmt(l5avg)}, giving this side a {_fmt(recent_cushion)}-stat recent cushion.")
        elif recent_cushion < 0:
            concerns.append(f"Last-5 R+A average is {_fmt(l5avg)}, which sits on the opposite side of the current {line:.1f} line.")

    env_vals = [x for x in (pace, reb_env, ast_env) if np.isfinite(x)]
    if env_vals:
        avg_env = float(np.mean(env_vals))
        favorable = (avg_env > 1.005 and side == "OVER") or (avg_env < 0.995 and side == "UNDER")
        unfavorable = (avg_env < 0.985 and side == "OVER") or (avg_env > 1.015 and side == "UNDER")
        if favorable:
            supports.append(f"Combined pace/rebound/assist environment leans with the selection ({avg_env:.3f}× average multiplier).")
        elif unfavorable:
            concerns.append(f"Matchup environment leans against the selection ({avg_env:.3f}× average multiplier).")

    if np.isfinite(cushion) and cushion < 1.0:
        concerns.append(f"Projection cushion is only {_fmt(max(cushion,0.0))} R+A, so normal game-to-game variance matters more.")
    if q == "MEDIUM":
        concerns.append("Model data is MEDIUM rather than HIGH, so uncertainty is wider.")
    if np.isfinite(age) and age > 10 * 60:
        concerns.append(f"Verified quote is {_age_text(age)} old and is approaching the 15-minute freshness cutoff.")
    if push >= 0.02:
        concerns.append(f"Push probability is {_pct(push)}, which trims resolved-side exposure.")
    if np.isfinite(corr) and abs(corr) >= 0.35:
        concerns.append(f"REB/AST correlation is {corr:+.2f}; the two components can move together more than usual.")

    if not concerns:
        concerns.append("No additional Step-7 concern trigger fired beyond normal player-prop variance.")

    return reasons[:3], supports[:4], concerns[:3]


def _last5_html(rows):
    if not rows:
        return '<div class="kra7-empty">No completed Last-5 ledger was available for this player.</div>'
    out = []
    for r in rows:
        out.append(f'''<div class="kra7-l5row">
<span>{escape(str(r.get('date') or '—'))}</span>
<span>{r.get('opp') or '—'}</span>
<span>{_fmt(r.get('reb'),0)}</span>
<span>{_fmt(r.get('ast'),0)}</span>
<strong>{_fmt(r.get('ra'),0)}</strong>
<b class="{escape(str(r.get('cls') or 'neutral'))}">{escape(str(r.get('result') or '—'))}</b>
</div>''')
    return "".join(out)


def _list_html(items):
    if not items:
        return '<div class="kra7-empty">—</div>'
    return "<ul>" + "".join(f"<li>{escape(str(x))}</li>" for x in items) + "</ul>"


def _card(row, pool: pd.DataFrame, day_str: str):
    prow = _pool_row_for_top(pool, row)
    if prow is None:
        return ""

    try:
        logs, _ctx, projection = v5._projection_payload(day_str, prow)
    except Exception:
        logs, projection = pd.DataFrame(), {}

    team_id = _safe_int(prow.get("TEAM_ID"))
    opp_id = _safe_int(prow.get("opponent_team_id"))
    espn_pid = _safe_int(prow.get("ESPN_PLAYER_ID"))
    player = escape(str(row.get("player") or prow.get("PLAYER_NAME") or "WNBA Player"))
    team = escape(str(row.get("team") or prow.get("TEAM_ABBREVIATION") or prow.get("TEAM_NAME") or ""))
    opp = escape(str(row.get("opponent") or prow.get("opponent_abbr") or prow.get("opponent") or ""))
    side = str(row.get("side") or "").upper()
    grade = escape(str(row.get("grade") or "QUALIFIED"))
    rank = int(row.get("rank", 0) or 0)
    line = _num(row.get("line"), np.nan)
    book = escape(str(row.get("book") or "Sportsbook"))

    team_logo = v2._logo(team_id) if team_id else ""
    opp_logo = v2._logo(opp_id) if opp_id else ""
    photo_url = v2._espn_headshot(espn_pid) if espn_pid else ""
    photo = _img(photo_url, player, "kra7-photo", team_logo)
    tlogo = _img(team_logo, team, "kra7-logo")
    ologo = _img(opp_logo, opp, "kra7-logo")

    l5rows, l5meta = _last5_payload(logs, line, side)
    reasons, supports, concerns = _reason_payload(row, projection, l5meta)
    confidence, conf_cls = _confidence(row)

    cushion = (_num(row.get("proj_ra"), np.nan) - line) if side == "OVER" else (line - _num(row.get("proj_ra"), np.nan))
    line_text = "—" if not np.isfinite(line) else f"{line:.1f}"

    return f'''<div class="kra7-card">
<div class="kra7-topline"><span>RANK {rank} • {grade}</span><span class="kra7-confidence {conf_cls}">DISPLAY CONFIDENCE • {confidence}</span></div>
<div class="kra7-header">
<div class="kra7-photo-wrap">{photo}</div>
<div class="kra7-id">
<div class="kra7-name">{player}</div>
<div class="kra7-match"><span>{tlogo}{team}</span><b>vs</b><span>{ologo}{opp}</span></div>
<div class="kra7-pick">{escape(side)} R+A {line_text} <small>{book} • {_odds(row.get('price'))}</small></div>
</div>
</div>

<div class="kra7-hero">
<div><small>5M {escape(side)} PROBABILITY</small><strong>{_pct(row.get('model_prob'))}</strong><span>FAIR {_odds(row.get('fair_odds'))}</span></div>
<div><small>PROJECTED R+A</small><strong>{_fmt(row.get('proj_ra'))}</strong><span>{_fmt(max(cushion,0.0))} directional cushion</span></div>
</div>

<div class="kra7-grid">
<div><small>NO-VIG MARKET</small><strong>{_pct(row.get('no_vig_prob'))}</strong></div>
<div><small>NO-VIG EDGE</small><strong>{_pp(row.get('edge'))}</strong></div>
<div><small>PUSH-AWARE EV</small><strong>{_pct(row.get('ev'))}</strong></div>
<div><small>PRICE</small><strong>{_odds(row.get('price'))}</strong></div>
<div><small>PROJECTED REB / AST</small><strong>{_fmt(row.get('proj_reb'))} / {_fmt(row.get('proj_ast'))}</strong></div>
<div><small>PROJECTED MINUTES</small><strong>{_fmt(row.get('proj_min'))}</strong></div>
<div><small>MODEL DATA</small><strong>{escape(str(row.get('quality') or ''))}</strong></div>
<div><small>QUOTE AGE</small><strong>{_age_text(row.get('quote_age_seconds'))}</strong></div>
<div><small>PUSH</small><strong>{_pct(row.get('push_prob'))}</strong></div>
<div><small>SIMULATIONS</small><strong>{int(row.get('sims',0) or 0):,}</strong></div>
</div>

<div class="kra7-section-title">LAST 5 • EXACT-LINE DIRECTION</div>
<div class="kra7-l5head"><span>DATE</span><span>OPP</span><span>REB</span><span>AST</span><span>R+A</span><span>{escape(side)}</span></div>
<div class="kra7-l5">{_last5_html(l5rows)}</div>
<div class="kra7-l5summary">Last-5 avg: <b>{_fmt(l5meta.get('avg'))} R+A</b> • Directional hits: <b>{int(l5meta.get('hits',0))}/{int(l5meta.get('resolved',0)) if int(l5meta.get('resolved',0)) else 0}</b></div>

<div class="kra7-two">
<div class="kra7-panel why"><h4>WHY THIS PICK</h4>{_list_html(reasons)}</div>
<div class="kra7-panel support"><h4>SUPPORTING SIGNALS</h4>{_list_html(supports)}</div>
</div>
<div class="kra7-panel concern"><h4>CONCERNS / VARIANCE</h4>{_list_html(concerns)}</div>

<div class="kra7-foot">Step 7 is explanation + presentation only. Rank, grade, probability, fair odds, EV, edge and qualification are inherited unchanged from the saved Step-6 result for this exact market snapshot.</div>
</div>'''


def _css():
    st.markdown('''<style>
.kra7-wrap{background:#0b1724;border:1px solid #41647d;border-radius:18px;padding:14px;margin:18px 0 10px}
.kra7-wrap h3{color:#f7fbff;margin:0 0 4px;font-size:1rem}.kra7-wrap p{color:#9bb0bf;font-size:.58rem;line-height:1.5;margin:0}.kra7-wrap b{color:#82efba}
.kra7-card{background:#06131f;border:1px solid #416985;border-radius:18px;padding:14px;margin:12px 0 18px;box-shadow:0 6px 24px rgba(0,0,0,.16)}
.kra7-topline{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;color:#82efba;font-size:.51rem;font-weight:950;letter-spacing:.045em}
.kra7-confidence{border-radius:999px;padding:5px 8px;font-size:.46rem;border:1px solid #496579;color:#b6c8d6}.kra7-confidence.elite{border-color:#25775a;color:#85efb9;background:#0a3025}.kra7-confidence.high{border-color:#3d718e;color:#92ddff;background:#0a2638}.kra7-confidence.solid{border-color:#806d32;color:#f6d978;background:#2d270d}
.kra7-header{display:flex;gap:12px;align-items:center;margin:11px 0}.kra7-photo-wrap{width:82px;height:82px;border:1px solid #3e627a;border-radius:16px;overflow:hidden;background:#0a1b29;display:flex;align-items:center;justify-content:center;flex:0 0 82px}.kra7-photo{width:100%;height:100%;object-fit:cover;object-position:center top}.kra7-placeholder{display:flex;align-items:center;justify-content:center;font-size:1.5rem}.kra7-id{min-width:0;flex:1}.kra7-name{color:#f8fbff;font-size:1.1rem;font-weight:950;line-height:1.15}.kra7-match{display:flex;align-items:center;gap:6px;margin-top:6px;color:#8fa6b7;font-size:.55rem}.kra7-match span{display:flex;align-items:center;gap:4px}.kra7-match b{color:#637b8c}.kra7-logo{width:22px;height:22px;object-fit:contain}.kra7-pick{color:#ffe17b;font-weight:950;font-size:.77rem;margin-top:8px}.kra7-pick small{color:#a8bbc8;font-size:.52rem;margin-left:4px}
.kra7-hero{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:10px 0}.kra7-hero>div{background:#081d2e;border:1px solid #426d8a;border-radius:13px;padding:11px}.kra7-hero small{display:block;color:#84cfee;font-size:.45rem;font-weight:950}.kra7-hero strong{display:block;color:#f7fbff;font-size:1.35rem;margin:3px 0}.kra7-hero span{color:#8ca7b8;font-size:.48rem;font-weight:850}
.kra7-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kra7-grid div{background:#06111c;border:1px solid #29495f;border-radius:10px;padding:8px}.kra7-grid small{display:block;color:#71899a;font-size:.42rem;font-weight:950}.kra7-grid strong{display:block;color:#f5f9fc;font-size:.66rem;margin-top:3px}
.kra7-section-title{color:#8edcff;font-size:.52rem;font-weight:950;letter-spacing:.05em;margin:14px 0 6px}.kra7-l5head,.kra7-l5row{display:grid;grid-template-columns:.8fr 1.35fr .65fr .65fr .7fr .9fr;gap:5px;align-items:center}.kra7-l5head{color:#688397;font-size:.40rem;font-weight:950;padding:0 6px 4px}.kra7-l5row{background:#071522;border:1px solid #203d51;border-radius:8px;padding:7px 6px;margin:4px 0;color:#b7c9d5;font-size:.48rem}.kra7-l5row strong{color:#f5f9fc}.kra7-l5row b{text-align:center;border-radius:999px;padding:3px 4px;font-size:.40rem}.kra7-l5row b.hit{background:#0b3327;color:#7df2ba}.kra7-l5row b.miss{background:#351a1e;color:#ff9ca5}.kra7-l5row b.push{background:#352f16;color:#ffe17a}.kra7-l5row b.neutral{background:#152431;color:#a5bac8}.kra7-l5summary{color:#7f99aa;font-size:.48rem;margin:7px 2px 2px}.kra7-l5summary b{color:#dceaf3}
.kra7-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.kra7-panel{border-radius:11px;padding:10px;border:1px solid #31536a;background:#071522}.kra7-panel h4{font-size:.48rem;letter-spacing:.05em;margin:0 0 6px}.kra7-panel ul{margin:0;padding-left:16px}.kra7-panel li{color:#bfd0db;font-size:.51rem;line-height:1.45;margin:4px 0}.kra7-panel.why h4{color:#ffe17a}.kra7-panel.support h4{color:#7df2ba}.kra7-panel.concern{margin-top:8px;border-color:#594c32;background:#17160f}.kra7-panel.concern h4{color:#ffc984}.kra7-empty{color:#71899a;font-size:.5rem}.kra7-foot{color:#657e90;font-size:.45rem;line-height:1.5;margin-top:10px}
@media(max-width:760px){.kra7-header{align-items:flex-start}.kra7-photo-wrap{width:72px;height:72px;flex-basis:72px}.kra7-two{grid-template-columns:1fr}.kra7-name{font-size:1rem}.kra7-l5head,.kra7-l5row{grid-template-columns:.75fr 1.15fr .6fr .6fr .65fr .8fr}}
</style>''', unsafe_allow_html=True)


def _render_step7():
    _css()
    raw_day = st.session_state.get("wnba_ra_v2_date")
    day = raw_day if raw_day is not None else pd.Timestamp.now(tz=ET).date()
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    try:
        pool, _diag = v2._player_pool(day_str)
        reconciled, market_meta = market.reconcile_to_player_pool(day_str, pool)
    except Exception as exc:
        st.warning(f"Step 7 source check: {type(exc).__name__}. Steps 1–6 remain unchanged.")
        return

    if str((market_meta or {}).get("state") or "").upper() != "VERIFIED" or reconciled is None or reconciled.empty:
        st.info("Step 7 is waiting for a verified current R+A market snapshot. Steps 1–6 remain unchanged.")
        return

    signature = prior._market_signature(reconciled)
    key = prior._result_key(day_str, signature)
    saved = st.session_state.get(key)

    st.markdown('''<div class="kra7-wrap"><h3>🏆 STEP 7 • FINAL DAILY R+A PICK CARDS</h3><p>Points-style presentation built strictly from the saved Step-6 qualified board. Player photo • both team logos • Last 5 • reason why • support • concerns • confidence. <b>No model math changes.</b></p></div>''', unsafe_allow_html=True)

    if not isinstance(saved, dict):
        st.info("Run Step 6 for this exact market snapshot first. Step 7 will not create or guess picks on its own.")
        return

    top = pd.DataFrame(saved.get("top") or [])
    if top.empty:
        st.warning("Step 6 produced no qualified R+A picks for this snapshot, so Step 7 correctly publishes no cards.")
        return

    cards = []
    for _, row in top.sort_values("rank", kind="stable").iterrows():
        html = _card(row, pool, day_str)
        if html:
            cards.append(html)
    if not cards:
        st.warning("Qualified picks exist, but Step 7 could not reconcile their player-card identities. No fallback cards were invented.")
        return

    st.success(f"✅ Final daily card built from {len(cards)} Step-6 qualified pick(s). Ranking and probabilities are unchanged.")
    st.markdown("".join(cards), unsafe_allow_html=True)
    st.caption("Step 7 is display/explanation only. The authoritative selection logic remains Step 6; the authoritative statistical distribution remains Step 5.")


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    out = prior.render_wnba_ra_hub(section_header, status_info, team_logo, h)
    _render_step7()
    return out


def __getattr__(name):
    return getattr(prior, name)


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
