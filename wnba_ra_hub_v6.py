"""WNBA Rebounds + Assists V6 — Step 6 qualification + strongest daily Top 5.

Read-only market/qualification layer over verified V5.1.

Step 6 rules:
- preserve Steps 1-5 projection and Monte Carlo math exactly;
- use only VERIFIED true combined R+A same-book/same-line O/U pairs;
- sportsbook information enters only AFTER the Step-5 simulation;
- calculate side-specific no-vig edge and push-aware EV from the completed 5M result;
- require fresh market, READY player projection, sufficient history/data quality and
  Step-5 convergence before a side can qualify;
- simulate each unique player + exact line once and reuse that distribution across
  books/sides;
- keep at most one strongest qualified market per player;
- never force five picks. Zero through five may be published.

The polished Points-style photo/logo/reason-why cards remain reserved for Step 7.
No existing WNBA Points, Rebounds, Assists, PRA, Spread, Moneyline, Game Total,
Daily Picks, MLB or NFL code is modified here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import hashlib
import json
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_ra_hub_v51 as prior

v5 = prior.prior
v3 = v5.v3
v2 = v5.v2
market = v5.market
model = v5.model
ET = v5.ET

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V6 • STEP 6 QUALIFICATION + DAILY TOP 5"
FRESH_SECONDS = 15 * 60
MIN_HISTORY_GAMES = 10
MIN_PROJ_MIN = 10.0
MIN_MODEL_PROB = 0.55
MIN_EDGE = 0.030
MIN_EV = 0.030


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


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _odds(value):
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    i = int(round(x))
    return f"+{i}" if i > 0 else str(i)


def _pct(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _pp(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:+.{digits}f} pp"


def _american_profit(odds):
    x = _num(odds, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    return x / 100.0 if x > 0 else 100.0 / abs(x)


def _quote_age_seconds(updated_at):
    if not updated_at:
        return np.nan
    try:
        dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return np.nan


def _market_signature(markets: pd.DataFrame) -> str:
    if markets is None or markets.empty:
        return "NO_MARKET"
    cols = [c for c in (
        "game_id", "provider_player_id", "PLAYER_ID", "PLAYER_NAME", "book_id", "book",
        "line", "over_price", "under_price", "updated_at", "market_state",
    ) if c in markets.columns]
    work = markets.loc[:, cols].copy()
    for c in cols:
        work[c] = work[c].astype(str)
    work = work.sort_values(cols, kind="stable") if cols else work
    payload = work.to_dict("records")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _player_token(row) -> str:
    pid = str(row.get("PLAYER_ID") or "").replace(".0", "").strip()
    if pid:
        return f"pid:{pid}"
    espn = str(row.get("ESPN_PLAYER_ID") or "").replace(".0", "").strip()
    if espn:
        return f"espn:{espn}"
    return f"name:{_norm(row.get('PLAYER_NAME'))}|game:{row.get('game_id') or ''}"


def _pool_row(pool: pd.DataFrame, q):
    if pool is None or pool.empty:
        return None
    work = pool
    gid = str(q.get("game_id") or "")
    if gid and "game_id" in work.columns:
        same_game = work.loc[work["game_id"].astype(str).eq(gid)]
        if not same_game.empty:
            work = same_game

    qpid = str(q.get("PLAYER_ID") or "").replace(".0", "").strip()
    if qpid and "PLAYER_ID" in work.columns:
        ids = work["PLAYER_ID"].astype(str).str.replace(".0", "", regex=False)
        part = work.loc[ids.eq(qpid)]
        if len(part) == 1:
            return part.iloc[0]

    qespn = _safe_int(q.get("ESPN_PLAYER_ID"))
    if qespn and "ESPN_PLAYER_ID" in work.columns:
        vals = pd.to_numeric(work["ESPN_PLAYER_ID"], errors="coerce").fillna(0).astype(int)
        part = work.loc[vals.eq(qespn)]
        if len(part) == 1:
            return part.iloc[0]

    name = _norm(q.get("PLAYER_NAME"))
    if name and "PLAYER_NAME" in work.columns:
        part = work.loc[work["PLAYER_NAME"].map(_norm).eq(name)]
        if len(part) == 1:
            return part.iloc[0]
    return None


def _grade(model_prob, edge, ev, quality):
    p = _num(model_prob, 0.0)
    e = _num(edge, -9.0)
    v = _num(ev, -9.0)
    q = str(quality or "LOW").upper()
    if q == "HIGH" and p >= 0.60 and e >= 0.080 and v >= 0.080:
        return "ELITE", 3
    if p >= 0.57 and e >= 0.050 and v >= 0.050:
        return "STRONG", 2
    return "QUALIFIED", 1


def _evaluate_quote(day_str, player_row, projection, sim, quote, side):
    side = str(side).upper()
    is_over = side == "OVER"
    model_prob = _num(sim.get("p_over" if is_over else "p_under"), np.nan)
    win_raw = _num(sim.get("p_over_raw" if is_over else "p_under_raw"), np.nan)
    loss_raw = _num(sim.get("p_under_raw" if is_over else "p_over_raw"), np.nan)
    no_vig = _num(quote.get("no_vig_over" if is_over else "no_vig_under"), np.nan)
    price = _num(quote.get("over_price" if is_over else "under_price"), np.nan)
    fair = _num(sim.get("fair_over" if is_over else "fair_under"), np.nan)
    profit = _american_profit(price)
    edge = model_prob - no_vig if np.isfinite(model_prob) and np.isfinite(no_vig) else np.nan
    ev = win_raw * profit - loss_raw if all(np.isfinite(x) for x in (win_raw, loss_raw, profit)) else np.nan
    age = _quote_age_seconds(quote.get("updated_at"))
    fresh = bool(np.isfinite(age) and age <= FRESH_SECONDS)

    quality = str((projection or {}).get("data_quality") or "LOW").upper()
    history_games = int((projection or {}).get("history_games", 0) or 0)
    proj_min = _num((projection or {}).get("proj_min"), 0.0)
    player_status = str((projection or {}).get("player_status") or "").upper()
    blocked_status = any(flag in player_status for flag in ("OUT", "INACTIVE", "DOUBTFUL"))
    sim_complete = str((sim or {}).get("state") or "").upper() == "COMPLETE"
    converged = bool((sim or {}).get("converged"))
    market_verified = str(quote.get("market_state") or "").upper() == "VERIFIED"

    base_ok = (
        str((projection or {}).get("state") or "").upper() == "READY"
        and sim_complete and converged and market_verified and fresh
        and quality in {"HIGH", "MEDIUM"}
        and history_games >= MIN_HISTORY_GAMES
        and proj_min >= MIN_PROJ_MIN
        and not blocked_status
        and np.isfinite(model_prob) and np.isfinite(no_vig) and np.isfinite(ev)
    )
    qualified = bool(
        base_ok
        and model_prob >= MIN_MODEL_PROB
        and edge >= MIN_EDGE
        and ev >= MIN_EV
    )

    failures = []
    if not market_verified: failures.append("MARKET NOT VERIFIED")
    if not fresh: failures.append("STALE/UNKNOWN QUOTE")
    if not sim_complete: failures.append("5M INCOMPLETE")
    elif not converged: failures.append("CONVERGENCE FAIL")
    if quality not in {"HIGH", "MEDIUM"}: failures.append("LOW MODEL DATA")
    if history_games < MIN_HISTORY_GAMES: failures.append("THIN HISTORY")
    if proj_min < MIN_PROJ_MIN: failures.append("LOW PROJECTED MINUTES")
    if blocked_status: failures.append("PLAYER STATUS BLOCK")
    if np.isfinite(model_prob) and model_prob < MIN_MODEL_PROB: failures.append("MODEL PROB <55%")
    if np.isfinite(edge) and edge < MIN_EDGE: failures.append("EDGE <3PP")
    if np.isfinite(ev) and ev < MIN_EV: failures.append("EV <3%")

    grade, grade_rank = _grade(model_prob, edge, ev, quality) if qualified else ("NOT QUALIFIED", 0)
    return {
        "day": str(day_str),
        "game_id": str(player_row.get("game_id") or quote.get("game_id") or ""),
        "player_token": _player_token(player_row),
        "player": str(player_row.get("PLAYER_NAME") or quote.get("PLAYER_NAME") or "WNBA Player"),
        "team": str(player_row.get("TEAM_ABBREVIATION") or player_row.get("TEAM_NAME") or ""),
        "team_name": str(player_row.get("TEAM_NAME") or ""),
        "opponent": str(player_row.get("opponent_abbr") or player_row.get("opponent") or ""),
        "side": side,
        "line": _num(quote.get("line"), np.nan),
        "book": str(quote.get("book") or "Sportsbook"),
        "price": price,
        "model_prob": model_prob,
        "model_prob_raw": win_raw,
        "no_vig_prob": no_vig,
        "edge": edge,
        "edge_pp": 100.0 * edge if np.isfinite(edge) else np.nan,
        "ev": ev,
        "ev_pct": 100.0 * ev if np.isfinite(ev) else np.nan,
        "fair_odds": fair,
        "push_prob": _num(sim.get("p_push"), 0.0),
        "proj_ra": _num(projection.get("proj_ra"), np.nan),
        "proj_reb": _num(projection.get("proj_reb"), np.nan),
        "proj_ast": _num(projection.get("proj_ast"), np.nan),
        "proj_min": proj_min,
        "quality": quality,
        "history_games": history_games,
        "quote_age_seconds": age,
        "updated_at": str(quote.get("updated_at") or ""),
        "sims": int(sim.get("sims", 0) or 0),
        "batches": int(sim.get("batches", 0) or 0),
        "seed": int(sim.get("seed", 0) or 0),
        "mc_se": _num(sim.get("mc_se"), np.nan),
        "max_batch_diff": _num(sim.get("max_batch_diff"), np.nan),
        "converged": converged,
        "qualified": qualified,
        "grade": grade,
        "grade_rank": grade_rank,
        "failures": " • ".join(failures) if failures else "—",
    }


def _build_daily(day_str: str, pool: pd.DataFrame, markets: pd.DataFrame, progress=None):
    if pool is None or pool.empty or markets is None or markets.empty:
        return pd.DataFrame(), pd.DataFrame(), {"units": 0, "completed_units": 0, "simulations": 0}

    verified = markets.loc[markets.get("market_state", "").astype(str).str.upper().eq("VERIFIED")].copy()
    verified["line"] = pd.to_numeric(verified.get("line"), errors="coerce")
    verified = verified.loc[verified["line"].notna()].copy()
    if verified.empty:
        return pd.DataFrame(), pd.DataFrame(), {"units": 0, "completed_units": 0, "simulations": 0}

    unit_map = {}
    for idx, q in verified.iterrows():
        token = (
            str(q.get("game_id") or ""),
            str(q.get("PLAYER_ID") or q.get("ESPN_PLAYER_ID") or _norm(q.get("PLAYER_NAME"))),
            float(q.get("line")),
        )
        unit_map.setdefault(token, []).append(idx)

    projection_cache = {}
    records = []
    completed_units = 0
    total_sims = 0
    units = list(unit_map.items())

    for i, (unit_key, indices) in enumerate(units, start=1):
        first = verified.loc[indices[0]]
        prow = _pool_row(pool, first)
        if prow is None:
            continue
        ptoken = _player_token(prow)
        if ptoken not in projection_cache:
            _logs, _ctx, proj = v5._projection_payload(day_str, prow)
            projection_cache[ptoken] = proj
        projection = projection_cache[ptoken]
        line = float(unit_key[2])
        sim = model.run_standard(day_str, prow, line, projection)
        if str((sim or {}).get("state") or "").upper() == "COMPLETE":
            completed_units += 1
            total_sims += int(sim.get("sims", 0) or 0)

        for idx in indices:
            quote = verified.loc[idx]
            records.append(_evaluate_quote(day_str, prow, projection, sim, quote, "OVER"))
            records.append(_evaluate_quote(day_str, prow, projection, sim, quote, "UNDER"))

        if progress is not None:
            try:
                progress.progress(i / max(len(units), 1), text=f"5M R+A distributions {i}/{len(units)}")
            except Exception:
                pass

    evaluated = pd.DataFrame(records)
    if evaluated.empty:
        return evaluated, pd.DataFrame(), {"units": len(units), "completed_units": completed_units, "simulations": total_sims}

    qualified = evaluated.loc[evaluated["qualified"].eq(True)].copy()
    if not qualified.empty:
        qualified = qualified.sort_values(
            ["grade_rank", "edge", "ev", "model_prob", "quote_age_seconds"],
            ascending=[False, False, False, False, True],
            kind="stable",
        )
        # One strongest exact market per player. Never let multiple books/lines for
        # the same player occupy multiple Daily Top-5 slots.
        qualified = qualified.drop_duplicates("player_token", keep="first").head(5).reset_index(drop=True)
        qualified["rank"] = np.arange(1, len(qualified) + 1)

    return evaluated, qualified, {
        "units": len(units),
        "completed_units": completed_units,
        "simulations": total_sims,
        "evaluated_sides": int(len(evaluated)),
        "qualified_players": int(len(qualified)),
    }


def _result_key(day_str: str, signature: str) -> str:
    return f"wnba_ra_v6_daily::{day_str}::{signature}"


def _top_cards(top: pd.DataFrame) -> str:
    if top is None or top.empty:
        return ""
    cards = []
    for _, r in top.iterrows():
        grade = escape(str(r.get("grade") or "QUALIFIED"))
        player = escape(str(r.get("player") or "WNBA Player"))
        team = escape(str(r.get("team") or ""))
        opp = escape(str(r.get("opponent") or ""))
        side = escape(str(r.get("side") or ""))
        book = escape(str(r.get("book") or "Sportsbook"))
        line = _num(r.get("line"), np.nan)
        line_text = "—" if not np.isfinite(line) else f"{line:.1f}"
        cards.append(f'''<div class="kra6-pick">
<div class="kra6-rank">RANK {int(r.get('rank',0) or 0)} • {grade}</div>
<div class="kra6-name">{player}</div>
<div class="kra6-match">{team} vs {opp}</div>
<div class="kra6-selection">{side} R+A {line_text} <span>{book} • {_odds(r.get('price'))}</span></div>
<div class="kra6-hero"><b>{_pct(r.get('model_prob'))}</b><small>5M {side} PROBABILITY • FAIR {_odds(r.get('fair_odds'))}</small></div>
<div class="kra6-grid">
<div><small>NO-VIG</small><strong>{_pct(r.get('no_vig_prob'))}</strong></div>
<div><small>NO-VIG EDGE</small><strong>{_pp(r.get('edge'))}</strong></div>
<div><small>EV</small><strong>{_pct(r.get('ev'))}</strong></div>
<div><small>PROJ R+A</small><strong>{_num(r.get('proj_ra'),np.nan):.1f}</strong></div>
<div><small>PROJ REB / AST</small><strong>{_num(r.get('proj_reb'),np.nan):.1f} / {_num(r.get('proj_ast'),np.nan):.1f}</strong></div>
<div><small>MODEL DATA</small><strong>{escape(str(r.get('quality') or ''))}</strong></div>
<div><small>PUSH</small><strong>{_pct(r.get('push_prob'))}</strong></div>
<div><small>SIMULATIONS</small><strong>{int(r.get('sims',0) or 0):,}</strong></div>
</div>
</div>''')
    return "".join(cards)


def _css():
    st.markdown('''<style>
.kra6-wrap{background:#0a1827;border:1px solid #385a73;border-radius:18px;padding:14px;margin-top:18px}
.kra6-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;color:#83dbff;font-size:.72rem;font-weight:950;letter-spacing:.045em}
.kra6-head span:last-child{border:1px solid #287557;background:#0d3529;color:#83efbb;border-radius:999px;padding:6px 9px;font-size:.48rem}
.kra6-intro{color:#a8bdcc;font-size:.6rem;line-height:1.55;margin:8px 0 12px}
.kra6-pick{background:#071522;border:1px solid #355b76;border-radius:14px;padding:12px;margin:10px 0}
.kra6-rank{color:#82efba;font-size:.52rem;font-weight:950;letter-spacing:.045em}.kra6-name{color:#f7fbff;font-size:1.05rem;font-weight:950;margin:5px 0 2px}.kra6-match{color:#7f98aa;font-size:.56rem}
.kra6-selection{color:#ffe27d;font-size:.82rem;font-weight:900;margin:9px 0}.kra6-selection span{color:#a7b8c5;font-size:.55rem;margin-left:5px}
.kra6-hero{background:#081c2d;border:1px solid #406b87;border-radius:12px;padding:10px;margin-bottom:8px}.kra6-hero b{display:block;color:#f7fbff;font-size:1.55rem}.kra6-hero small{color:#8edcff;font-size:.52rem;font-weight:900}
.kra6-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kra6-grid div{background:#06121e;border:1px solid #294960;border-radius:9px;padding:8px}.kra6-grid small{display:block;color:#6f8799;font-size:.43rem;font-weight:950}.kra6-grid strong{display:block;color:#f5f9fc;font-size:.67rem;margin-top:2px}
</style>''', unsafe_allow_html=True)


def _render_step6():
    _css()
    raw_day = st.session_state.get("wnba_ra_v2_date")
    day = raw_day if raw_day is not None else pd.Timestamp.now(tz=ET).date()
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    try:
        pool, diag = v2._player_pool(day_str)
        reconciled, market_meta = market.reconcile_to_player_pool(day_str, pool)
    except Exception as exc:
        st.warning(f"Step 6 source check: {type(exc).__name__}. Steps 1–5 remain unchanged.")
        return

    signature = _market_signature(reconciled)
    key = _result_key(day_str, signature)
    saved = st.session_state.get(key)

    st.markdown('''<div class="kra6-wrap">
<div class="kra6-head"><span>STEP 6 • QUALIFICATION + STRONGEST DAILY TOP 5</span><span>POST-5M MARKET LAYER</span></div>
<div class="kra6-intro">Runs the existing Step-5 projection/5M distribution for every unique verified player + exact R+A line, then applies sportsbook price only afterward. Qualification requires convergence, a fresh exact paired market, ≥55% model probability, ≥+3.0 pp no-vig edge, ≥+3% push-aware EV, ≥10 history games and HIGH/MEDIUM model data. One market per player • never force five.</div>
</div>''', unsafe_allow_html=True)

    mstate = str((market_meta or {}).get("state") or "CHECK").upper()
    if mstate != "VERIFIED" or reconciled is None or reconciled.empty:
        st.warning("Step 6 is fail-closed because no verified combined R+A market board is available. Steps 1–5 are unchanged.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Verified pairs", int((market_meta or {}).get("verified_pairs", 0) or 0))
    c2.metric("Qualification floor", "55% / +3pp")
    c3.metric("EV floor", "+3%")

    run = st.button(
        "▶️ Run Daily 5M R+A Qualification",
        use_container_width=True,
        key=f"wnba_ra_v6_run::{day_str}::{signature}",
    )
    if run:
        progress = st.progress(0.0, text="Preparing verified R+A distributions…")
        with st.spinner("🎲 Running/reusing exact-line 5M R+A distributions and qualifying the daily board…"):
            evaluated, top, meta = _build_daily(day_str, pool, reconciled, progress=progress)
        progress.empty()
        saved = {
            "signature": signature,
            "day": day_str,
            "generated_at": pd.Timestamp.now(tz=ET).isoformat(),
            "evaluated": evaluated.to_dict("records") if not evaluated.empty else [],
            "top": top.to_dict("records") if not top.empty else [],
            "meta": meta,
        }
        st.session_state[key] = saved
        st.rerun()

    if not isinstance(saved, dict):
        st.info("Step 6 has not run for this exact market snapshot yet. Tap the Daily 5M Qualification button above. Existing Step-5 results stay intact.")
        return

    top = pd.DataFrame(saved.get("top") or [])
    evaluated = pd.DataFrame(saved.get("evaluated") or [])
    meta = dict(saved.get("meta") or {})

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("5M units", f"{int(meta.get('completed_units',0))}/{int(meta.get('units',0))}")
    d2.metric("Actual draws", f"{int(meta.get('simulations',0)):,}")
    d3.metric("Evaluated sides", int(meta.get("evaluated_sides", 0) or 0))
    d4.metric("Qualified players", int(meta.get("qualified_players", 0) or 0))

    if top.empty:
        st.warning("No R+A player currently clears every production qualification threshold. No picks are being forced onto the Daily Top 5.")
    else:
        st.success(f"✅ {len(top)} production-qualified R+A player pick(s) found. The card intentionally stops at {len(top)} instead of forcing five.")
        st.markdown(_top_cards(top), unsafe_allow_html=True)

    with st.expander("🔬 Step 6 full qualification audit", expanded=False):
        if evaluated.empty:
            st.write("No evaluated side rows are available.")
        else:
            cols = [c for c in (
                "player", "team", "opponent", "side", "line", "book", "price",
                "model_prob", "no_vig_prob", "edge_pp", "ev_pct", "proj_ra",
                "quality", "history_games", "quote_age_seconds", "converged",
                "qualified", "grade", "failures",
            ) if c in evaluated.columns]
            st.dataframe(evaluated[cols], use_container_width=True, hide_index=True)

    st.caption(
        "Step 6 is post-simulation only. No sportsbook probability, price, no-vig edge, EV, grade or ranking is fed back into projected REB, projected AST, projected R+A, variance/correlation or the 5M Monte Carlo. Step 7 will add the final Points-style photo/logo/reason-why cards."
    )


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    out = prior.render_wnba_ra_hub(section_header, status_info, team_logo, h)
    _render_step6()
    return out


def __getattr__(name):
    return getattr(prior, name)


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
