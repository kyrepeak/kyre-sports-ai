"""WNBA Spread V1.6.2 — Top-5 visual card foundation, Step 1.

Presentation-only wrapper over the verified V1.6.1 Spread production route.
The V1.6.1 exact-day availability repair, independent margin projection,
analytical probability, exact sportsbook market, 5,000,000-draw Monte Carlo,
convergence contract and final grading remain unchanged.

Step 1 adds visual cards for up to five existing one-candidate-per-game final
Spread outputs. Cards show team identity/logos, exact spread/price, Monte Carlo
cover probability, fair odds, no-vig edge, EV, projected cover cushion,
convergence and a presentation-only strength label. No model input, simulation,
qualification rule, candidate side or production result is modified.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v161 as prior
import wnba_schedule_v25 as schedule25

base = prior.base  # verified V1.6 production renderer

MODEL_VERSION = "WNBA SPREAD V1.6.2 • TOP-5 CARD STEP 1"

# Capture the genuine V1.6 Step-7 renderer once. The wrapper is installed only at
# the presentation seam so its returned detail/final/meta payloads are unchanged.
_ORIGINAL_STEP7 = base._render_step7


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _line(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{x:+.1f}".replace("+0.0", "PK").replace("-0.0", "PK")


def _odds(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x) or x == 0:
        return "—"
    return f"{x:+.0f}"


def _ev(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:+.1f}%"


def _fair(value) -> str:
    return _odds(value)


def _logo(team_id) -> str:
    try:
        return str(schedule25.logo_url(int(float(team_id))) or "")
    except Exception:
        return ""


def _is_home(row) -> bool:
    best = _norm(row.get("best_side"))
    home = _norm(row.get("home_team"))
    away = _norm(row.get("away_team"))
    if best and best == home:
        return True
    if best and best == away:
        return False
    # Fail-soft only for presentation; the underlying final row is untouched.
    return True


def _strength(row) -> tuple[str, str]:
    """Presentation label only; never feeds qualification or ranking math."""
    grade = str(row.get("grade") or "MONITOR").upper().strip()
    state = str(row.get("mc_state") or "MONITOR").upper().strip()
    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    ev = _num(row.get("best_ev"), np.nan)

    if state == "BLOCKED" or grade == "BLOCKED":
        return "BLOCKED", "blocked"
    if state != "READY" or grade == "MONITOR":
        return "MONITOR", "monitor"
    if grade != "QUALIFIED":
        return "NO PLAY", "nop"

    positive_ev = (not np.isfinite(ev)) or ev > 0
    if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.62 and edge >= 6.0 and positive_ev:
        return "ELITE", "elite"
    if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.59 and edge >= 4.0 and positive_ev:
        return "STRONG", "strong"
    return "MEDIUM", "medium"


def _presentation_order(final: pd.DataFrame) -> pd.DataFrame:
    """Order only the already-final one-per-game rows for visual Top-5 display."""
    if not isinstance(final, pd.DataFrame) or final.empty:
        return pd.DataFrame()
    work = final.copy()
    grade_rank = {"QUALIFIED": 4, "MONITOR": 3, "NO PLAY": 2, "BLOCKED": 0}
    work["_grade_rank"] = work.get("grade", "MONITOR").astype(str).str.upper().map(grade_rank).fillna(1)
    work["_ready_rank"] = work.get("mc_state", "MONITOR").astype(str).str.upper().eq("READY").astype(int)
    work["_cover_rank"] = pd.to_numeric(work.get("best_cover_no_push"), errors="coerce").fillna(-1.0)
    work["_edge_rank"] = pd.to_numeric(work.get("best_edge_pp"), errors="coerce").fillna(-999.0)
    work["_ev_rank"] = pd.to_numeric(work.get("best_ev"), errors="coerce").fillna(-999.0)
    return (
        work.sort_values(
            ["_grade_rank", "_ready_rank", "_cover_rank", "_edge_rank", "_ev_rank"],
            ascending=False,
            kind="stable",
        )
        .head(5)
        .reset_index(drop=True)
    )


def _card(row, rank: int) -> str:
    away = str(row.get("away_team") or "Away")
    home = str(row.get("home_team") or "Home")
    best = str(row.get("best_side") or "Team")
    is_home = _is_home(row)

    selected_id = row.get("home_team_id") if is_home else row.get("away_team_id")
    opp_id = row.get("away_team_id") if is_home else row.get("home_team_id")
    opponent = away if is_home else home
    selected_logo = escape(_logo(selected_id), quote=True)
    opp_logo = escape(_logo(opp_id), quote=True)
    selected_img = f'<img src="{selected_logo}" alt="{escape(best)} logo">' if selected_logo else "🏀"
    opp_img = f'<img src="{opp_logo}" alt="{escape(opponent)} logo">' if opp_logo else "🏀"

    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    market = _num(row.get("home_market_novig") if is_home else row.get("away_market_novig"), np.nan)
    fair = row.get("mc_home_fair_odds") if is_home else row.get("mc_away_fair_odds")
    push = _num(row.get("mc_push"), np.nan)
    mean_home = _num(row.get("projected_home_margin"), np.nan)
    side_margin = mean_home if is_home else (-mean_home if np.isfinite(mean_home) else np.nan)
    spread = _num(row.get("best_spread"), np.nan)
    cushion = side_margin + spread if np.isfinite(side_margin) and np.isfinite(spread) else np.nan

    strength, strength_class = _strength(row)
    grade = str(row.get("grade") or "MONITOR").upper()
    converged = bool(row.get("converged"))
    book = str(row.get("book") or "—")
    sims = int(_num(row.get("simulation_count"), 0) or 0)
    venue = str(row.get("venue") or "")
    tip = str(row.get("first_tip_et") or "")
    meta = " • ".join(x for x in [tip, venue] if x)

    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
    edge_text = "—" if not np.isfinite(edge) else f"{edge:+.1f} pp"
    cushion_text = "—" if not np.isfinite(cushion) else f"{cushion:+.1f} pts"
    mean_text = "—" if not np.isfinite(mean_home) else f"{mean_home:+.1f} pts"
    sims_text = f"{sims:,}" if sims else "—"

    return f"""
<div class="ks-spread162-card {('rank1' if rank == 1 else '')}">
  <div class="ks-spread162-rank">{medal} RANK {rank} • <span>{escape(grade)}</span> <b>DISPLAY ORDER ONLY</b></div>
  <div class="ks-spread162-matchup">
    <div class="ks-spread162-side">
      <div class="ks-spread162-logo">{selected_img}</div>
      <div><div class="ks-spread162-team">{escape(best)}</div><div class="ks-spread162-pick">{escape(best)} {_line(spread)}</div></div>
    </div>
    <div class="ks-spread162-vs">vs</div>
    <div class="ks-spread162-side opp">
      <div class="ks-spread162-logo">{opp_img}</div>
      <div><div class="ks-spread162-team">{escape(opponent)}</div><div class="ks-spread162-sub">{escape(away)} @ {escape(home)}</div></div>
    </div>
  </div>
  {f'<div class="ks-spread162-meta">{escape(meta)}</div>' if meta else ''}
  <div class="ks-spread162-prob">{_pct(cover)}</div>
  <div class="ks-spread162-probsub">5M MC NO-PUSH COVER PROBABILITY • FAIR {_fair(fair)}</div>
  <div class="ks-spread162-badges">
    <span class="strength {strength_class}">PICK STRENGTH • {escape(strength)}</span>
    <span>PRODUCTION GRADE • {escape(grade)}</span>
    <span class="{('pass' if converged else 'warn')}">CONVERGENCE • {('PASS' if converged else 'CHECK')}</span>
  </div>
  <div class="ks-spread162-grid">
    <div><small>EXACT MARKET</small><strong>{_line(spread)} ({_odds(row.get('best_price'))})</strong></div>
    <div><small>BOOK</small><strong>{escape(book)}</strong></div>
    <div><small>MC COVER</small><strong>{_pct(cover)}</strong></div>
    <div><small>MARKET NO-VIG</small><strong>{_pct(market)}</strong></div>
    <div><small>NO-VIG EDGE</small><strong>{edge_text}</strong></div>
    <div><small>EV</small><strong>{_ev(row.get('best_ev'))}</strong></div>
    <div><small>PROJECTED HOME MARGIN</small><strong>{mean_text}</strong></div>
    <div><small>PROJECTED COVER CUSHION</small><strong>{cushion_text}</strong></div>
    <div><small>PUSH PROBABILITY</small><strong>{_pct(push)}</strong></div>
    <div><small>SIMULATIONS</small><strong>{sims_text}</strong></div>
  </div>
  <div class="ks-spread162-note">CARD STEP 1 • PICK IDENTITY + VERIFIED MODEL SNAPSHOT • existing V1.6.1 side, line, probability, edge, EV, convergence and qualification only. No new spread projection or reranking is fed back into production.</div>
</div>
"""


def _render_top5_step1(day_str: str, final: pd.DataFrame, meta: dict) -> None:
    st.markdown("### 🏆 Strongest WNBA Spread Picks — Top-5 Cards")
    st.caption(
        "CARD STEP 1 • Pick identity + model snapshot. Uses the existing V1.6 one-candidate-per-game final output after the actual 5M pass. "
        "Up to five are displayed; no fifth play is forced when the slate/model produces fewer candidates."
    )

    if not isinstance(final, pd.DataFrame) or final.empty:
        st.info("Top-5 Spread cards are waiting on the current Step-7 5,000,000-draw result. Run the verified Spread Monte Carlo above first.")
        return

    ranked = _presentation_order(final)
    if ranked.empty:
        st.info("No current final Spread candidates are available for Top-5 presentation.")
        return

    st.markdown(
        """
<style>
.ks-spread162-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 18px}
.ks-spread162-card{background:linear-gradient(145deg,#0b2034,#071521);border:1px solid #315c78;border-radius:22px;padding:17px;box-shadow:0 8px 24px rgba(0,0,0,.18)}
.ks-spread162-card.rank1{border-color:#d5aa18;box-shadow:inset 5px 0 0 #d5aa18,0 8px 24px rgba(0,0,0,.20)}
.ks-spread162-rank{color:#66ddff;font-size:.62rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:12px}.ks-spread162-rank span{color:#9ef3d0}.ks-spread162-rank b{float:right;color:#6f8293;font-size:.48rem}
.ks-spread162-matchup{display:grid;grid-template-columns:1fr 26px 1fr;align-items:center;gap:7px}.ks-spread162-side{display:flex;align-items:center;gap:9px}.ks-spread162-side.opp{justify-content:flex-end;text-align:right}.ks-spread162-logo{width:54px;height:54px;display:flex;align-items:center;justify-content:center}.ks-spread162-logo img{max-width:54px;max-height:54px;object-fit:contain}.ks-spread162-team{color:#fff;font-size:.92rem;font-weight:950;line-height:1.15}.ks-spread162-pick{color:#ffe17a;font-size:.75rem;font-weight:900;margin-top:4px}.ks-spread162-sub{color:#7f95a7;font-size:.58rem;margin-top:4px}.ks-spread162-vs{text-align:center;color:#6e8394;font-size:.68rem;font-weight:900}.ks-spread162-meta{color:#7f95a7;font-size:.60rem;margin:9px 0 3px}
.ks-spread162-prob{font-size:2.75rem;font-weight:1000;color:#fff;line-height:1;margin-top:16px}.ks-spread162-probsub{font-size:.55rem;color:#7890a5;font-weight:900;letter-spacing:.035em;margin-top:5px}
.ks-spread162-badges{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.ks-spread162-badges span{border:1px solid #355873;background:#0b1824;color:#bed4e3;border-radius:999px;padding:6px 8px;font-size:.49rem;font-weight:950;letter-spacing:.035em}.ks-spread162-badges .elite,.ks-spread162-badges .strong,.ks-spread162-badges .pass{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread162-badges .medium{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread162-badges .monitor,.ks-spread162-badges .nop,.ks-spread162-badges .warn{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread162-badges .blocked{border-color:#7a3941;background:#35171b;color:#ff9aa5}
.ks-spread162-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.ks-spread162-grid div{background:#081522;border:1px solid #284b64;border-radius:11px;padding:9px}.ks-spread162-grid small{display:block;color:#718ba0;font-size:.47rem;font-weight:950;letter-spacing:.04em}.ks-spread162-grid strong{display:block;color:#f6fbff;font-size:.78rem;margin-top:3px}.ks-spread162-note{color:#6f8799;font-size:.54rem;line-height:1.45;margin-top:10px}
@media(max-width:760px){.ks-spread162-wrap{grid-template-columns:1fr}.ks-spread162-rank b{float:none;display:block;margin-top:3px}.ks-spread162-logo{width:48px;height:48px}.ks-spread162-logo img{max-width:48px;max-height:48px}.ks-spread162-prob{font-size:2.45rem}}
</style>
        """,
        unsafe_allow_html=True,
    )
    cards = "".join(_card(row, i + 1) for i, (_, row) in enumerate(ranked.iterrows()))
    st.markdown(f'<div class="ks-spread162-wrap">{cards}</div>', unsafe_allow_html=True)

    qualified = int(ranked.get("grade", pd.Series(dtype=object)).astype(str).str.upper().eq("QUALIFIED").sum())
    st.caption(
        f"Current card set • {len(ranked)} one-per-game candidate(s) • {qualified} QUALIFIED • "
        "visual ordering uses existing production grade → MC cover → no-vig edge → EV only. Production payload and per-game selection are unchanged."
    )


def _render_step7_with_top5(day_str: str, pregame: pd.DataFrame, board: pd.DataFrame, probability_ready: bool):
    detail, final, meta = _ORIGINAL_STEP7(day_str, pregame, board, probability_ready)
    _render_top5_step1(day_str, final, meta if isinstance(meta, dict) else {})
    return detail, final, meta


def _install() -> None:
    # V1.6 resolves this module-global function when render_wnba_spread_hub runs.
    # Replacing only this UI seam ensures the Top-5 cards consume the exact final
    # payload that the current Step 7 just validated/rendered.
    base._render_step7 = _render_step7_with_top5


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎨 Spread V1.6.2 • Top-5 Card Step 1 ACTIVE • team logos + exact spread + 5M probability + pick strength • production model/ranking unchanged"
    )
    return prior.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
