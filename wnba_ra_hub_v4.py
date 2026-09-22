"""WNBA Rebounds + Assists V4 — Step 4 opportunity + matchup context.

Preserves verified Steps 1-3 and adds a read-only basketball opportunity layer:
- minutes/role stability and recent R+A per-36;
- player rebound share and assist share from recent team box totals;
- recent team/opponent pace environment;
- team assist production + opponent assist allowance proxy;
- opponent/team missed-field-goal environment for rebound opportunity context;
- opponent rebound allowance proxy;
- current availability/injury context.

Official tracking fields such as potential assists and rebound chances are NOT
available in the verified ESPN box feed used by this route. V4 explicitly labels
its box-score proxies and never represents them as tracking data.

No R+A projection, probability, Monte Carlo, fair odds, model edge, EV,
qualification, reason-why score, ranking or Top-5 publication is created here.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_ra_hub_v3 as prior
import wnba_ra_context_v1 as context

v2 = prior.prior
players = prior.players
schedule24 = prior.schedule24
market = prior.market
ET = prior.ET

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V4 • STEP 4 OPPORTUNITY + MATCHUP CONTEXT"
_V3_STEP3 = prior._step3_block


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _fmt(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _count_text(obj: dict) -> str:
    reports = int((obj or {}).get("reports", 0) or 0)
    out = int((obj or {}).get("out", 0) or 0)
    uncertain = int((obj or {}).get("uncertain", 0) or 0)
    return f"{reports} report(s) • {out} out/doubtful • {uncertain} uncertain"


def _step4_block(day_str: str, player_row, markets: pd.DataFrame) -> str:
    team_id = _safe_int(player_row.get("TEAM_ID"))
    opp_id = _safe_int(player_row.get("opponent_team_id"))
    espn_id = _safe_int(player_row.get("ESPN_PLAYER_ID"))
    player_name = str(player_row.get("PLAYER_NAME") or "WNBA Player")
    team_name = str(player_row.get("TEAM_NAME") or player_row.get("TEAM_ABBREVIATION") or "Team")
    opp_name = str(player_row.get("opponent") or "Opponent")

    try:
        logs = prior._player_current_team_log(day_str, team_id, espn_id, player_name)
        ctx = context.build_context(day_str, player_row, logs)
    except Exception as exc:
        return f'''<div class="kra4-step4">
<div class="kra4-head"><span>STEP 4 • R+A OPPORTUNITY + MATCHUP ENGINE</span><span class="kra4-chip warn">CONTEXT CHECK</span></div>
<div class="kra4-empty">The descriptive opportunity layer could not fully resolve on this render. Steps 1–3 remain unchanged.</div>
<div class="kra4-note">Fail-soft diagnostic • {escape(type(exc).__name__)} • no projection, probability or ranking was created.</div>
</div>'''

    role = ctx.get("role") or {}
    team_env = ctx.get("team_env") or {}
    opp_env = ctx.get("opp_env") or {}
    team_adv = ctx.get("team_adv") or {}
    opp_adv = ctx.get("opp_adv") or {}
    av = ctx.get("availability") or {}

    reliability = str(ctx.get("reliability") or "LOW").upper()
    rel_cls = "good" if reliability == "HIGH" else ("mid" if reliability == "MEDIUM" else "warn")
    state = str(ctx.get("state") or "PARTIAL").upper()

    role_label = str(role.get("role") or "CHECK").upper()
    role_cls = str(role.get("role_cls") or "warn")
    player_status = escape(str(av.get("player_status") or "STATUS CHECK"))
    snapshot_scope = escape(str(av.get("snapshot_scope") or "CURRENT SNAPSHOT"))
    detail = escape(str(av.get("player_detail") or ""))

    team_pace = _num(team_adv.get("PACE"), np.nan)
    opp_pace = _num(opp_adv.get("PACE"), np.nan)
    blended = _num(ctx.get("blended_pace"), np.nan)
    assist_proxy = _num(ctx.get("assist_env_proxy"), np.nan)
    team_ast = _num(team_env.get("team_ast"), np.nan)
    opp_ast_allowed = _num(opp_env.get("opp_ast"), np.nan)
    opp_misses = _num(opp_env.get("team_misses"), np.nan)
    team_misses = _num(team_env.get("team_misses"), np.nan)
    opp_reb_allowed = _num(opp_env.get("opp_reb"), np.nan)
    team_reb = _num(team_env.get("team_reb"), np.nan)

    assist_read = (
        f"{escape(team_name)} has produced {_fmt(team_ast)} assists/game over its recent verified sample; "
        f"{escape(opp_name)} has allowed {_fmt(opp_ast_allowed)} opponent assists/game. "
        f"The simple descriptive assist-environment blend is {_fmt(assist_proxy)}."
    )
    rebound_read = (
        f"{escape(opp_name)} has missed {_fmt(opp_misses)} field goals/game recently, a defensive-rebound opportunity proxy for {escape(team_name)}. "
        f"{escape(team_name)} has missed {_fmt(team_misses)} field goals/game, an offensive-rebound opportunity proxy. "
        f"{escape(opp_name)} has allowed {_fmt(opp_reb_allowed)} opponent rebounds/game."
    )

    sample_text = (
        f"Role share sample {int(role.get('share_games',0) or 0)}/5 • "
        f"team box {int(team_env.get('games',0) or 0)}/5 • opponent box {int(opp_env.get('games',0) or 0)}/5 • "
        f"pace {int(team_adv.get('games',0) or 0)}/5 + {int(opp_adv.get('games',0) or 0)}/5"
    )

    return f'''<div class="kra4-step4">
<div class="kra4-head"><span>STEP 4 • R+A OPPORTUNITY + MATCHUP ENGINE</span><span class="kra4-chip {rel_cls}">{reliability} DATA RELIABILITY</span></div>
<div class="kra4-intro">Read-only basketball context • completed games strictly before this slate • no future-game leakage.<br>{escape(sample_text)}</div>

<div class="kra4-subhead">PLAYER ROLE + OPPORTUNITY</div>
<div class="kra4-grid">
<div><small>SEASON MIN</small><strong>{_fmt(role.get('season_min'))}</strong></div>
<div><small>L10 MIN</small><strong>{_fmt(role.get('l10_min'))}</strong></div>
<div><small>L5 MIN</small><strong>{_fmt(role.get('l5_min'))}</strong></div>
<div><small>L10 MIN VOLATILITY</small><strong>{_fmt(role.get('l10_min_sd'))} SD</strong></div>
<div><small>L5 R+A / 36</small><strong>{_fmt(role.get('l5_ra36'))}</strong></div>
<div><small>ROLE TREND</small><strong class="{role_cls}">{escape(role_label)}</strong></div>
<div><small>L5 REBOUND SHARE PROXY</small><strong>{_pct(role.get('l5_reb_share'))}</strong></div>
<div><small>L5 ASSIST SHARE PROXY</small><strong>{_pct(role.get('l5_ast_share'))}</strong></div>
</div>

<div class="kra4-subhead">MATCHUP OPPORTUNITY ENVIRONMENT</div>
<div class="kra4-grid">
<div><small>{escape(team_name)} RECENT PACE EST.</small><strong>{_fmt(team_pace)}</strong></div>
<div><small>{escape(opp_name)} RECENT PACE EST.</small><strong>{_fmt(opp_pace)}</strong></div>
<div><small>BLENDED RECENT PACE</small><strong>{_fmt(blended)}</strong></div>
<div><small>ASSIST ENV. PROXY</small><strong>{_fmt(assist_proxy)}</strong></div>
<div><small>TEAM AST / GAME</small><strong>{_fmt(team_ast)}</strong></div>
<div><small>OPP AST ALLOWED / GAME</small><strong>{_fmt(opp_ast_allowed)}</strong></div>
<div><small>OPP MISSED FG / GAME</small><strong>{_fmt(opp_misses)}</strong></div>
<div><small>TEAM MISSED FG / GAME</small><strong>{_fmt(team_misses)}</strong></div>
<div><small>OPP REB ALLOWED / GAME</small><strong>{_fmt(opp_reb_allowed)}</strong></div>
<div><small>TEAM REB / GAME</small><strong>{_fmt(team_reb)}</strong></div>
</div>

<div class="kra4-read"><small>ASSIST CONTEXT READ</small><strong>{assist_read}</strong></div>
<div class="kra4-read"><small>REBOUND CONTEXT READ</small><strong>{rebound_read}</strong></div>

<div class="kra4-subhead">AVAILABILITY + ROTATION CONTEXT</div>
<div class="kra4-grid">
<div><small>PLAYER STATUS</small><strong>{player_status}</strong></div>
<div><small>SNAPSHOT SCOPE</small><strong>{snapshot_scope}</strong></div>
<div class="wide"><small>{escape(team_name)} AVAILABILITY</small><strong>{escape(_count_text(av.get('team') or {}))}</strong></div>
<div class="wide"><small>{escape(opp_name)} AVAILABILITY</small><strong>{escape(_count_text(av.get('opponent') or {}))}</strong></div>
</div>
{f'<div class="kra4-detail">Player report detail • {detail}</div>' if detail else ''}

<div class="kra4-tracking"><b>TRACKING DATA NOTE</b> • Official potential assists and rebound-chance tracking are not available from this verified ESPN box feed. The share/miss/assist fields above are explicitly labeled box-score proxies and will not be treated as official tracking metrics.</div>
<div class="kra4-note">Source • {escape(str(ctx.get('source') or 'ESPN WNBA context'))} • Step 4 state {escape(state)} • descriptive only • NOT FED INTO an R+A projection, Monte Carlo, probability, fair odds, edge, EV, qualification, reason-why score or ranking.</div>
</div>'''


def _step3_plus_step4(day_str: str, player_row, markets: pd.DataFrame) -> str:
    return _V3_STEP3(day_str, player_row, markets) + _step4_block(day_str, player_row, markets)


def _install_step4_seam():
    # V3's existing player card resolves this module-global helper at render time.
    # Replacing only the descriptive HTML seam keeps Steps 1-3 behavior intact.
    prior._step3_block = _step3_plus_step4


def _css():
    prior._css()
    st.markdown('''<style>
.kra4-step4{background:#0a1928;border:1px solid #3a5d76;border-radius:16px;padding:12px;margin-top:14px}.kra4-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#79d8ff;font-size:.58rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.kra4-intro,.kra4-empty{color:#c9d7e2;font-size:.63rem;line-height:1.5;margin:8px 0}.kra4-subhead{color:#a7c8dd;font-size:.55rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:13px 0 7px}.kra4-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kra4-grid div,.kra4-read{background:#07131f;border:1px solid #24445c;border-radius:10px;padding:9px}.kra4-grid .wide{grid-column:1/-1}.kra4-grid small,.kra4-read small{display:block;color:#718ba0;font-size:.45rem;font-weight:950;letter-spacing:.035em}.kra4-grid strong{display:block;color:#f6fbff;font-size:.72rem;margin-top:3px;line-height:1.35}.kra4-grid strong.good{color:#7df2ba}.kra4-grid strong.mid{color:#ffe17a}.kra4-grid strong.warn{color:#ffc984}.kra4-read{margin-top:7px}.kra4-read strong{display:block;color:#dbe8f1;font-size:.62rem;line-height:1.5;margin-top:4px;font-weight:650}.kra4-chip{display:inline-block;border-radius:999px;padding:5px 7px;font-size:.48rem;font-weight:950;white-space:nowrap}.kra4-chip.good{border:1px solid #237a59;background:#0b3327;color:#7df2ba}.kra4-chip.mid{border:1px solid #826c16;background:#3a3009;color:#ffe17a}.kra4-chip.warn{border:1px solid #7c5832;background:#352516;color:#ffc984}.kra4-detail{color:#cbd9e3;font-size:.55rem;line-height:1.45;margin-top:7px}.kra4-tracking{margin-top:9px;padding:9px;border:1px solid #6c5b28;background:#2c260f;border-radius:10px;color:#f4d77a;font-size:.54rem;line-height:1.5}.kra4-note{color:#6f8799;font-size:.49rem;line-height:1.5;margin-top:9px}
@media(max-width:760px){.kra4-head{align-items:flex-start;flex-wrap:wrap}}
</style>''', unsafe_allow_html=True)


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_step4_seam()
    _css()
    st.markdown('''<div class="kra2-route"><h2>🏀 WNBA Rebounds + Assists</h2><p>Built one verified layer at a time to match the finished Points-card experience while keeping existing WNBA markets isolated.</p><span class="kra2-step">STEPS 1–4 • IDENTITY + EXACT MARKET + FORM / HISTORY + OPPORTUNITY / MATCHUP</span></div>''', unsafe_allow_html=True)

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
        st.warning("R+A market rows are not fully paired/reconciled; exact-line hit-rate fields stay fail-closed.")

    st.caption("Steps 3–4 context • verified ESPN WNBA completed-game summaries strictly before selected slate • current-team history + labeled opportunity proxies • no production R+A model yet.")
    v2._schedule_cards(schedule)
    if pool is None or pool.empty:
        st.info("Verified player pool is unavailable for this slate.")
        return

    row = v2._selected_row(pool)
    prior._player_card(day_str, row, reconciled, market_meta)
    v2._full_boards(pool, reconciled)
    if st.button("🔄 Refresh exact R+A markets", use_container_width=True, key=f"wnba_ra_v2_refresh_{day_str}"):
        market.clear_cache()
        st.rerun()

    st.info("🔒 STEP 4 BOUNDARY • Opportunity/matchup information is descriptive only. No R+A projection, Monte Carlo, fair odds, model edge, EV, qualification, reason-why engine or Top-5 ranking has been added yet.")


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
