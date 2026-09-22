'''WNBA Rebounds + Assists V5 — Step 5 projection + 5M correlated Monte Carlo.

Preserves verified Steps 1-4. Step 5 is the first statistical R+A model:
- REB and AST means are projected separately;
- sportsbook data is excluded from projection construction;
- historical REB/AST dependence is preserved with a sample-shrunk correlation;
- a real 5,000,000-draw batched Monte Carlo is run only on user request;
- exact-line Over/Under/push probabilities, fair odds and convergence are shown.

No no-vig model edge, EV, qualification, reason-why score, Daily Picks or Top-5
ranking is created in Step 5. Those remain reserved for Step 6+.
'''
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_ra_hub_v4 as prior
import wnba_ra_hub_v3 as v3
import wnba_ra_context_v1 as context
import wnba_ra_model_v1 as model

v2 = v3.prior
players = v3.players
schedule24 = v3.schedule24
market = v3.market
ET = v3.ET

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V5 • STEP 5 PROJECTION + 5M MC"
_ORIGINAL_STEP3 = v3._step3_block


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


def _fmt(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _pct(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _odds(value):
    try:
        x = int(round(float(value)))
        return f"+{x}" if x > 0 else str(x)
    except Exception:
        return "—"


def _sim_key(day_str, row, line):
    pid = str(row.get("ESPN_PLAYER_ID") or row.get("PLAYER_ID") or row.get("PLAYER_NAME") or "player")
    gid = str(row.get("game_id") or "game")
    ltxt = "na" if not np.isfinite(_num(line, np.nan)) else f"{float(line):.3f}"
    return f"wnba_ra_v5_mc::{day_str}::{gid}::{pid}::{ltxt}"


def _projection_payload(day_str, row):
    tid = _safe_int(row.get("TEAM_ID"))
    pid = _safe_int(row.get("ESPN_PLAYER_ID"))
    name = str(row.get("PLAYER_NAME") or "WNBA Player")
    try:
        logs = v3._player_current_team_log(day_str, tid, pid, name)
        ctx = context.build_context(day_str, row, logs)
        proj = model.project_ra(row, logs, ctx)
    except Exception as exc:
        logs = pd.DataFrame()
        ctx = {}
        proj = {"state": "ERROR", "error": type(exc).__name__, "model_version": model.MODEL_VERSION}
    return logs, ctx, proj


def _step5_block(day_str, row, markets, projection, sim_result):
    line_info = v3._line_basis(row, markets)
    line = _num(line_info.get("line"), np.nan)
    books = escape(str(line_info.get("books") or ""))
    pairs = int(line_info.get("pairs") or 0)
    state = str((projection or {}).get("state") or "CHECK").upper()

    if state != "READY":
        status = escape(str((projection or {}).get("player_status") or state))
        return f'''<div class="kra5-step5">
<div class="kra5-head"><span>STEP 5 • R+A PROJECTION + 5M MONTE CARLO</span><span class="kra5-chip warn">MODEL LOCKED</span></div>
<div class="kra5-empty">Projection state: {status}. Step 5 will not publish a simulated probability until the player/history/status inputs are eligible.</div>
<div class="kra5-note">Steps 1–4 remain unchanged. No sportsbook line or price can repair a blocked statistical projection.</div>
</div>'''

    line_text = "—" if not np.isfinite(line) else f"{line:.1f}"
    quality = escape(str(projection.get("data_quality") or "CHECK"))
    qcls = "good" if quality == "HIGH" else ("mid" if quality == "MEDIUM" else "warn")
    corr = _num(projection.get("corr"), np.nan)
    raw_corr = _num(projection.get("raw_corr"), np.nan)
    corr_text = "—" if not np.isfinite(corr) else f"{corr:+.3f}"
    raw_text = "—" if not np.isfinite(raw_corr) else f"{raw_corr:+.3f}"
    market_basis = (
        f"Exact current line basis • R+A {line_text} • {pairs} verified book pair(s)"
        + (f" • {books}" if books else "")
        if np.isfinite(line)
        else "No verified exact R+A line is available; projection can display, market probability remains locked."
    )

    sim = sim_result if isinstance(sim_result, dict) else {}
    complete = str(sim.get("state") or "").upper() == "COMPLETE"
    if complete:
        convergence = "PASS" if bool(sim.get("converged")) else "FAIL"
        conv_cls = "good" if bool(sim.get("converged")) else "warn"
        sim_html = f'''
<div class="kra5-subhead">5,000,000-DRAW MARKET-LINE RESULT</div>
<div class="kra5-hero">
<div><small>5M OVER {line_text}</small><strong>{_pct(sim.get("p_over"))}</strong><span>FAIR {_odds(sim.get("fair_over"))}</span></div>
<div><small>5M UNDER {line_text}</small><strong>{_pct(sim.get("p_under"))}</strong><span>FAIR {_odds(sim.get("fair_under"))}</span></div>
</div>
<div class="kra5-grid">
<div><small>PUSH PROBABILITY</small><strong>{_pct(sim.get("p_push"))}</strong></div>
<div><small>SIMULATED MEAN R+A</small><strong>{_fmt(sim.get("mean_ra"))}</strong></div>
<div><small>MEDIAN R+A</small><strong>{_fmt(sim.get("median_ra"),0)}</strong></div>
<div><small>MODE R+A</small><strong>{_fmt(sim.get("mode_ra"),0)}</strong></div>
<div><small>P10 / P90</small><strong>{_fmt(sim.get("p10"),0)} / {_fmt(sim.get("p90"),0)}</strong></div>
<div><small>SIM R+A SD</small><strong>{_fmt(sim.get("sd_ra"))}</strong></div>
<div><small>SIMULATIONS</small><strong>{int(sim.get("sims",0) or 0):,}</strong></div>
<div><small>BATCHES</small><strong>{int(sim.get("batches",0) or 0)}</strong></div>
<div><small>RANDOM SEED</small><strong>{int(sim.get("seed",0) or 0)}</strong></div>
<div><small>MC STANDARD ERROR</small><strong>{100.0*_num(sim.get("mc_se"),0.0):.3f} pp</strong></div>
<div><small>MAX BATCH DIFFERENCE</small><strong>{100.0*_num(sim.get("max_batch_diff"),0.0):.3f} pp</strong></div>
<div><small>CONVERGENCE</small><strong class="{conv_cls}">{convergence}</strong></div>
</div>'''
    else:
        sim_html = '''<div class="kra5-pending"><b>5M MONTE CARLO NOT RUN YET</b><br>The statistical projection is ready. Use the Step-5 run control above the player card to execute the exact-line 5,000,000-draw simulation.</div>'''

    return f'''<div class="kra5-step5">
<div class="kra5-head"><span>STEP 5 • R+A PROJECTION + 5M MONTE CARLO</span><span class="kra5-chip {qcls}">{quality} MODEL DATA</span></div>
<div class="kra5-intro">First production R+A probability layer • REB and AST projected separately • correlated jointly • sportsbook excluded from projection.<br>{market_basis}</div>

<div class="kra5-subhead">STATISTICAL PROJECTION • BEFORE SPORTSBOOK</div>
<div class="kra5-grid">
<div><small>PROJECTED MINUTES</small><strong>{_fmt(projection.get("proj_min"))}</strong></div>
<div><small>PROJECTED R+A</small><strong>{_fmt(projection.get("proj_ra"))}</strong></div>
<div><small>PROJECTED REBOUNDS</small><strong>{_fmt(projection.get("proj_reb"))}</strong></div>
<div><small>PROJECTED ASSISTS</small><strong>{_fmt(projection.get("proj_ast"))}</strong></div>
<div><small>REB RATE / 36</small><strong>{_fmt(projection.get("reb36"))}</strong></div>
<div><small>AST RATE / 36</small><strong>{_fmt(projection.get("ast36"))}</strong></div>
<div><small>PACE MULTIPLIER</small><strong>{_fmt(projection.get("pace_factor"),3)}×</strong></div>
<div><small>REB ENV. MULTIPLIER</small><strong>{_fmt(projection.get("reb_env_factor"),3)}×</strong></div>
<div><small>AST ENV. MULTIPLIER</small><strong>{_fmt(projection.get("ast_env_factor"),3)}×</strong></div>
<div><small>UNCERTAINTY MULTIPLIER</small><strong>{_fmt(projection.get("uncertainty_mult"),3)}×</strong></div>
<div><small>REB SD</small><strong>{_fmt(projection.get("reb_sd"))}</strong></div>
<div><small>AST SD</small><strong>{_fmt(projection.get("ast_sd"))}</strong></div>
<div><small>REB↔AST CORRELATION</small><strong>{corr_text}</strong></div>
<div><small>RAW HISTORICAL CORR.</small><strong>{raw_text}</strong></div>
<div><small>CORRELATION SAMPLE</small><strong>{int(projection.get("corr_games",0) or 0)} game(s)</strong></div>
<div><small>HISTORY SAMPLE</small><strong>{int(projection.get("history_games",0) or 0)} game(s)</strong></div>
</div>

<div class="kra5-method"><b>MODEL CONSTRUCTION</b> • Season/L10/L5 minutes and separate REB/AST rates form the baseline. Step-4 pace, rebound and assist environments enter only as shrunken, capped matchup multipliers. H2H hit rate and sportsbook probability are not projection inputs. Historical REB/AST correlation is shrunk toward zero before covariance is simulated.</div>
{sim_html}
<div class="kra5-note">Step 5 creates projection + exact-line probability + fair odds only. No no-vig edge, EV, qualification, strongest-pick score, reason-why grade or Top-5 ranking is produced here.</div>
</div>'''


def _css():
    prior._css()
    st.markdown('''<style>
.kra5-step5{background:#0a1928;border:1px solid #3a5d76;border-radius:16px;padding:12px;margin-top:14px}
.kra5-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#79d8ff;font-size:.58rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.kra5-intro,.kra5-empty{color:#c9d7e2;font-size:.63rem;line-height:1.5;margin:8px 0}
.kra5-subhead{color:#a7c8dd;font-size:.55rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:13px 0 7px}
.kra5-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
.kra5-grid div{background:#07131f;border:1px solid #24445c;border-radius:10px;padding:9px}
.kra5-grid small,.kra5-hero small{display:block;color:#718ba0;font-size:.45rem;font-weight:950;letter-spacing:.035em}
.kra5-grid strong{display:block;color:#f6fbff;font-size:.72rem;margin-top:3px;line-height:1.35}
.kra5-grid strong.good{color:#7df2ba}.kra5-grid strong.warn{color:#ffc984}
.kra5-chip{display:inline-block;border-radius:999px;padding:5px 7px;font-size:.48rem;font-weight:950;white-space:nowrap}
.kra5-chip.good{border:1px solid #237a59;background:#0b3327;color:#7df2ba}.kra5-chip.mid{border:1px solid #826c16;background:#3a3009;color:#ffe17a}.kra5-chip.warn{border:1px solid #7c5832;background:#352516;color:#ffc984}
.kra5-hero{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:8px}
.kra5-hero>div{background:#061522;border:1px solid #3d647f;border-radius:12px;padding:11px}
.kra5-hero strong{display:block;color:#f6fbff;font-size:1.25rem;margin:4px 0}.kra5-hero span{color:#8fdcff;font-size:.54rem;font-weight:850}
.kra5-method,.kra5-pending{margin-top:9px;padding:10px;border-radius:10px;font-size:.55rem;line-height:1.55}
.kra5-method{border:1px solid #355873;background:#081827;color:#cbdce8}.kra5-pending{border:1px solid #6c5b28;background:#2c260f;color:#f4d77a}
.kra5-note{color:#6f8799;font-size:.49rem;line-height:1.5;margin-top:9px}
@media(max-width:760px){.kra5-head{align-items:flex-start;flex-wrap:wrap}}
</style>''', unsafe_allow_html=True)


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _css()
    st.markdown('''<div class="kra2-route"><h2>🏀 WNBA Rebounds + Assists</h2><p>Built one verified layer at a time to match the finished Points-card experience while keeping existing WNBA markets isolated.</p><span class="kra2-step">STEPS 1–5 • IDENTITY + EXACT MARKET + FORM / HISTORY + OPPORTUNITY / MATCHUP + PROJECTION / 5M MC</span></div>''', unsafe_allow_html=True)

    day = st.date_input("📅 R+A slate date", value=pd.Timestamp.now(tz=ET).date(), key="wnba_ra_v2_date")
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule = schedule24.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        st.info(f"No verified WNBA games were found for {day_str}.")
        return

    pool, diag = v2._player_pool(day_str)
    with st.spinner("🎯 Verifying exact combined R+A sportsbook markets…"):
        reconciled, market_meta = market.reconcile_to_player_pool(day_str, pool)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", int(diag.get("games", len(schedule)) or 0))
    c2.metric("Verified players", int(diag.get("players", 0) or 0))
    c3.metric("R+A paired rows", int((market_meta or {}).get("verified_pairs", 0) or 0))
    c4.metric("Market state", str((market_meta or {}).get("state") or "CHECK").replace("_", " ").title())

    if str(diag.get("state") or "").upper() == "VERIFIED":
        st.success("✅ Step 1 identity remains verified.")
    else:
        st.warning("⚠️ Step 1 identity needs a source check; later steps stay fail-closed.")

    mstate = str((market_meta or {}).get("state") or "CHECK").upper()
    if mstate == "VERIFIED":
        st.success("✅ Step 2 exact R+A market remains verified • true combined market + paired O/U + player identity.")
    elif mstate == "NO_OPEN_RA_MARKETS":
        st.info("No open true combined Rebounds + Assists markets are posted right now. Nothing is synthesized from separate props.")
    elif mstate == "NO_API_KEY":
        st.warning("SportsGameOdds API key is unavailable to the R+A route; market-dependent comparisons stay locked.")
    elif mstate == "PROVIDER_ERROR":
        st.warning(f"SportsGameOdds R+A source check • {(market_meta or {}).get('error') or 'provider error'}")
    else:
        st.warning("R+A market rows are not fully paired/reconciled; exact-line probability stays fail-closed.")

    st.caption("Steps 3–5 use verified pre-slate ESPN history/context. Step 5 sportsbook isolation: line is used only after the statistical projection to evaluate O/U/push probability.")
    v2._schedule_cards(schedule)
    if pool is None or pool.empty:
        st.info("Verified player pool is unavailable for this slate.")
        return

    row = v2._selected_row(pool)
    logs, ctx, projection = _projection_payload(day_str, row)
    line_info = v3._line_basis(row, reconciled)
    line = _num(line_info.get("line"), np.nan)
    sim_key = _sim_key(day_str, row, line)
    sim_result = st.session_state.get(sim_key)

    ready = str((projection or {}).get("state") or "").upper() == "READY"
    can_run = ready and np.isfinite(line)

    st.markdown("#### 🧠 Step 5 simulation control")
    if ready:
        if np.isfinite(line):
            st.caption(
                f"Projection ready • {_fmt(projection.get('proj_reb'))} REB + "
                f"{_fmt(projection.get('proj_ast'))} AST = {_fmt(projection.get('proj_ra'))} R+A • "
                f"market line {line:.1f}"
            )
        else:
            st.caption(f"Projection ready • {_fmt(projection.get('proj_ra'))} R+A • no verified exact line")
    else:
        st.warning(f"Step 5 projection is not simulation-ready: {str((projection or {}).get('state') or 'CHECK')}.")

    run = st.button(
        "▶️ Run 5,000,000 R+A Monte Carlo",
        use_container_width=True,
        disabled=not can_run,
        key=f"wnba_ra_v5_run::{day_str}::{row.get('ESPN_PLAYER_ID') or row.get('PLAYER_ID') or row.get('PLAYER_NAME')}",
    )
    if run:
        with st.spinner("🎲 Running 5,000,000 correlated R+A simulations…"):
            sim_result = model.run_standard(day_str, row, line, projection)
            st.session_state[sim_key] = sim_result

    def _combined(day_value, player_row, markets):
        return (
            _ORIGINAL_STEP3(day_value, player_row, markets)
            + prior._step4_block(day_value, player_row, markets)
            + _step5_block(day_value, player_row, markets, projection, sim_result)
        )

    original = v3._step3_block
    v3._step3_block = _combined
    try:
        v3._player_card(day_str, row, reconciled, market_meta)
    finally:
        v3._step3_block = original

    v2._full_boards(pool, reconciled)
    if st.button("🔄 Refresh exact R+A markets", use_container_width=True, key=f"wnba_ra_v2_refresh_{day_str}"):
        market.clear_cache()
        st.rerun()

    st.info("🔒 STEP 5 BOUNDARY • The R+A projection and actual 5M Monte Carlo now exist. No no-vig model edge, EV, qualification, strongest-pick/reason-why engine or Top-5 ranking has been added yet.")


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
