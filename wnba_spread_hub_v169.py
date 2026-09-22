"""WNBA Spread V1.6.9 — Top-5 Card Step 7: final pick breakdown.

Presentation-only wrapper over the verified V1.6.8 Step-6 card layer. Step 7
ties together already-rendered Steps 1-6 into a compact final summary:
production grade, Pick Strength, model-output confidence, context-data confidence,
context risk, strongest supporting factors, strongest conflicting factors and a
plain-English final spread thesis.

Step 7 does not create a new projection or ranking. It reuses the existing
verified final candidate row plus cached descriptive helpers already used by
Steps 2-5. Nothing is fed into the protected V1.6.1 projected margin,
SportsGameOdds market, analytical probability, 5,000,000 Monte Carlo,
convergence, qualification, selected side, edge/EV, Pick Strength or ranking.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v163 as step3
import wnba_spread_hub_v165 as step4
import wnba_spread_hub_v166 as step5
import wnba_spread_hub_v168 as previous

base = previous.base
MODEL_VERSION = "WNBA SPREAD V1.6.9 • TOP-5 CARD STEP 7 FINAL BREAKDOWN"
_ORIGINAL_INSTALL_STEP6 = previous._install_step6


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _compact_html(fragment: str) -> str:
    return "".join(line.strip() for line in str(fragment or "").splitlines())


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _pp(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:+.1f} pp"


def _pts(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:+.1f} pts"


def _line(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    if abs(x) < 1e-9:
        return "PK"
    return f"{x:+.1f}"


def _odds(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x) or abs(x) < 1e-9:
        return "—"
    return f"{x:+.0f}"


def _safe_context(day_str: str, row) -> dict:
    """Reuse cached Step 2-5 helpers without making a second model."""
    out = {
        "history": {},
        "selected_form": {},
        "opponent_form": {},
        "selected_adv": {},
        "opponent_adv": {},
        "selected_injuries": pd.DataFrame(),
        "opponent_injuries": pd.DataFrame(),
        "injury_provider": {},
    }
    try:
        selected_is_home = step3.prior._is_home(row)
        away_id, home_id, _ = step3.prior._resolved_team_ids(str(day_str), row)
        if not away_id or not home_id:
            return out

        away_name = str(row.get("away_team") or "Away")
        home_name = str(row.get("home_team") or "Home")
        selected_id = int(home_id if selected_is_home else away_id)
        opponent_id = int(away_id if selected_is_home else home_id)
        selected_name = str(row.get("best_side") or (home_name if selected_is_home else away_name))
        opponent_name = away_name if selected_is_home else home_name

        try:
            out["history"] = step3.prior._history_summary(str(day_str), row) or {}
        except Exception:
            pass

        try:
            results, provider = step3.prior._official_history_results(str(day_str))
            if str((provider or {}).get("state") or "").upper() == "READY":
                out["selected_form"] = step3._form_profile(results, day_str, selected_id, selected_name) or {}
                out["opponent_form"] = step3._form_profile(results, day_str, opponent_id, opponent_name) or {}
        except Exception:
            pass

        try:
            pair = step4._pair_advanced(str(day_str), selected_id, opponent_id) or {}
            out["selected_adv"] = pair.get("selected") or {}
            out["opponent_adv"] = pair.get("opponent") or {}
        except Exception:
            pass

        try:
            injuries, provider = step5._league_injury_snapshot()
            out["injury_provider"] = provider or {}
            out["selected_injuries"] = step5._injuries_for_team(injuries, selected_id)
            out["opponent_injuries"] = step5._injuries_for_team(injuries, opponent_id)
        except Exception:
            pass
    except Exception:
        pass
    return out


def _model_confidence(row) -> tuple[str, str, str]:
    grade = str(row.get("grade") or "MONITOR").upper()
    state = str(row.get("mc_state") or "MONITOR").upper()
    converged = bool(row.get("converged"))
    sims = int(_num(row.get("simulation_count"), 0) or 0)
    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)

    if grade == "QUALIFIED" and state == "READY" and converged and sims >= 5_000_000:
        if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.60 and edge >= 5.0:
            return "HIGH", "good", "Qualified production row • 5M simulation complete • convergence passed."
        return "MEDIUM-HIGH", "good", "Qualified production row with completed converged Monte Carlo."
    if state == "BLOCKED" or grade == "BLOCKED":
        return "LOW", "bad", "Production row is blocked."
    if not converged or state != "READY":
        return "LOW", "warn", "Monte Carlo readiness or convergence requires review."
    return "MEDIUM", "mid", "Production output is available but not in the strongest qualified state."


def _data_confidence(ctx: dict) -> tuple[str, str, str]:
    score = 0
    notes = []

    hist = ctx.get("history") or {}
    if str(hist.get("state") or "").upper() == "READY":
        score += 1
        rel = str(hist.get("reliability") or "LOW").upper()
        notes.append(f"H2H {rel.lower()} sample")
    else:
        notes.append("H2H unavailable/none")

    sf = ctx.get("selected_form") or {}
    of = ctx.get("opponent_form") or {}
    if str(sf.get("state") or "").upper() == "READY" and str(of.get("state") or "").upper() == "READY":
        gp = min(int(sf.get("games") or 0), int(of.get("games") or 0))
        score += 2 if gp >= 20 else 1
        notes.append("season form verified")
    else:
        notes.append("form partial")

    sa = ctx.get("selected_adv") or {}
    oa = ctx.get("opponent_adv") or {}
    adv_n = min(int(sa.get("samples") or 0), int(oa.get("samples") or 0))
    if adv_n >= 5:
        score += 2
        notes.append("recent advanced 5/5")
    elif adv_n >= 1:
        score += 1
        notes.append("advanced partial")
    else:
        notes.append("advanced unavailable")

    provider = ctx.get("injury_provider") or {}
    if str(provider.get("state") or "").upper() == "READY":
        score += 1
        notes.append("current injury feed connected")
    else:
        notes.append("injury feed unavailable")

    if score >= 5:
        return "HIGH", "good", " • ".join(notes)
    if score >= 3:
        return "MEDIUM", "mid", " • ".join(notes)
    return "LOW", "warn", " • ".join(notes)


def _injury_severity(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    if "severity" not in frame.columns:
        return int(len(frame))
    vals = pd.to_numeric(frame["severity"], errors="coerce").fillna(0)
    return int((vals >= 4).sum() * 2 + (vals == 3).sum())


def _context_factors(day_str: str, row, ctx: dict):
    selected_is_home = step3.prior._is_home(row)
    selected_name = str(row.get("best_side") or (row.get("home_team") if selected_is_home else row.get("away_team")) or "Selected team")
    opponent_name = str((row.get("away_team") if selected_is_home else row.get("home_team")) or "Opponent")

    spread = _num(row.get("best_spread"), np.nan)
    cover = _num(row.get("best_cover_no_push"), np.nan)
    market = _num(row.get("home_market_novig") if selected_is_home else row.get("away_market_novig"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    home_margin = _num(row.get("projected_home_margin"), np.nan)
    selected_margin = home_margin if selected_is_home else (-home_margin if np.isfinite(home_margin) else np.nan)
    cushion = selected_margin + spread if np.isfinite(selected_margin) and np.isfinite(spread) else np.nan
    converged = bool(row.get("converged"))
    sims = int(_num(row.get("simulation_count"), 0) or 0)

    supports = []
    conflicts = []
    risk_points = 0

    if np.isfinite(cover) and np.isfinite(market):
        diff = 100.0 * (cover - market)
        if diff >= 3.0:
            supports.append(f"5M cover probability {_pct(cover)} is {diff:+.1f} pp above the no-vig market.")
        elif diff <= -3.0:
            conflicts.append(f"Model cover probability is {abs(diff):.1f} pp below the no-vig market.")

    if np.isfinite(cushion):
        if cushion >= 2.5:
            supports.append(f"Projected mean keeps {selected_name} {_pts(cushion)} inside the selected spread.")
        elif cushion > 0:
            supports.append(f"Projected mean still covers, but only by {_pts(cushion)}.")
            risk_points += 1
        else:
            conflicts.append(f"Projected mean sits {abs(cushion):.1f} pts outside the selected spread.")
            risk_points += 2

    if converged and sims >= 5_000_000:
        supports.append("5,000,000-draw Monte Carlo passed the existing convergence contract.")

    sf = ctx.get("selected_form") or {}
    of = ctx.get("opponent_form") or {}
    sel_l5 = _num(sf.get("l5_margin"), np.nan)
    opp_l5 = _num(of.get("l5_margin"), np.nan)
    if np.isfinite(sel_l5) and np.isfinite(opp_l5):
        form_gap = sel_l5 - opp_l5
        if form_gap >= 5.0:
            supports.append(f"Recent form margin favors {selected_name} by {form_gap:+.1f} pts/game over the last five.")
        elif form_gap <= -5.0:
            conflicts.append(f"Last-five scoring margin favors {opponent_name} by {abs(form_gap):.1f} pts/game.")
            risk_points += 1

    sa = ctx.get("selected_adv") or {}
    oa = ctx.get("opponent_adv") or {}
    sel_net = _num(sa.get("netrtg"), np.nan)
    opp_net = _num(oa.get("netrtg"), np.nan)
    if np.isfinite(sel_net) and np.isfinite(opp_net):
        net_gap = sel_net - opp_net
        if net_gap >= 5.0:
            supports.append(f"Recent NetRtg profile favors {selected_name} by {net_gap:+.1f}.")
        elif net_gap <= -5.0:
            conflicts.append(f"Recent NetRtg profile favors {opponent_name} by {abs(net_gap):.1f}.")
            risk_points += 1

    hist = ctx.get("history") or {}
    h2h_margin = _num(hist.get("avg_margin"), np.nan)
    h2h_games = int(hist.get("games") or 0)
    if h2h_games > 0 and np.isfinite(h2h_margin):
        rel = str(hist.get("reliability") or "LOW").lower()
        if h2h_margin >= 5.0:
            supports.append(f"Current-season H2H margin favors {selected_name} by {h2h_margin:+.1f} ({h2h_games} games, {rel} reliability).")
        elif h2h_margin <= -5.0:
            conflicts.append(f"Current-season H2H margin favors {opponent_name} by {abs(h2h_margin):.1f} ({h2h_games} games, {rel} reliability).")
            if h2h_games >= 3:
                risk_points += 1

    sel_inj = _injury_severity(ctx.get("selected_injuries"))
    opp_inj = _injury_severity(ctx.get("opponent_injuries"))
    if opp_inj > sel_inj:
        supports.append(f"Current injury snapshot has more severe availability flags on {opponent_name}.")
    elif sel_inj > opp_inj:
        conflicts.append(f"Current injury snapshot has more severe availability flags on {selected_name}.")
        risk_points += 1

    if np.isfinite(spread) and abs(spread) >= 8.0:
        risk_points += 2
    if np.isfinite(edge) and edge >= 10.0:
        risk_points += 1

    supports = supports[:4]
    conflicts = conflicts[:4]
    if not supports:
        supports = ["No additional descriptive support was strong enough to add beyond the production output."]
    if not conflicts:
        conflicts = ["No major descriptive conflict was identified from the currently connected context layers."]

    if risk_points >= 5:
        risk_level, risk_class = "HIGH", "bad"
    elif risk_points >= 3:
        risk_level, risk_class = "MEDIUM-HIGH", "warn"
    elif risk_points >= 1:
        risk_level, risk_class = "MEDIUM", "mid"
    else:
        risk_level, risk_class = "LOW", "good"

    return {
        "supports": supports,
        "conflicts": conflicts,
        "risk_level": risk_level,
        "risk_class": risk_class,
        "selected_name": selected_name,
        "opponent_name": opponent_name,
        "spread": spread,
        "cover": cover,
        "market": market,
        "edge": edge,
        "selected_margin": selected_margin,
        "cushion": cushion,
    }


def _final_thesis(row, factors: dict) -> str:
    selected = factors["selected_name"]
    opponent = factors["opponent_name"]
    spread = factors["spread"]
    cover = factors["cover"]
    edge = factors["edge"]
    cushion = factors["cushion"]
    selected_margin = factors["selected_margin"]

    if np.isfinite(selected_margin) and selected_margin < 0 and np.isfinite(spread) and spread > 0 and np.isfinite(cushion) and cushion > 0:
        path = (
            f"The production model does not need {selected} to win outright: its mean has {opponent} winning by "
            f"{abs(selected_margin):.1f}, leaving {selected} {cushion:.1f} points inside {_line(spread)}."
        )
    elif np.isfinite(cushion) and cushion > 0:
        path = f"The projected mean clears the selected spread by {cushion:.1f} points."
    elif np.isfinite(cushion):
        path = "The projected mean does not clear the selected spread; distribution upside is carrying the cover case."
    else:
        path = "The mean spread cushion is unavailable."

    return (
        f"{selected} {_line(spread)} remains the existing production selection at {_pct(cover)} 5M MC cover probability"
        f"{(' with ' + _pp(edge) + ' no-vig edge') if np.isfinite(edge) else ''}. "
        f"{path} The final summary is explanatory only: contextual conflicts can raise risk without changing the verified production probability or qualification."
    )


def _factor_html(items: list[str], kind: str) -> str:
    icon = "✓" if kind == "support" else "!"
    return "".join(
        f'<div class="ks-spread169-factor {kind}"><span>{icon}</span><p>{escape(str(text))}</p></div>'
        for text in items
    )


def _final_block(day_str: str, row) -> str:
    try:
        ctx = _safe_context(day_str, row)
        factors = _context_factors(day_str, row, ctx)
        model_conf, model_class, model_note = _model_confidence(row)
        data_conf, data_class, data_note = _data_confidence(ctx)
        risk_level = factors["risk_level"]
        risk_class = factors["risk_class"]

        selected = factors["selected_name"]
        spread = factors["spread"]
        cover = factors["cover"]
        edge = factors["edge"]
        cushion = factors["cushion"]
        grade = str(row.get("grade") or "MONITOR").upper()
        strength, strength_class = step3.prior._strength(row)
        fair = row.get("mc_home_fair_odds") if step3.prior._is_home(row) else row.get("mc_away_fair_odds")
        book = str(row.get("book") or "—")
        price = row.get("best_price")
        ev = _num(row.get("best_ev"), np.nan)
        thesis = _final_thesis(row, factors)
        logo = ""
        try:
            away_id, home_id, _ = step3.prior._resolved_team_ids(str(day_str), row)
            selected_id = home_id if step3.prior._is_home(row) else away_id
            logo = step3.prior._logo(int(selected_id)) if selected_id else ""
        except Exception:
            logo = ""
        logo_html = f'<img src="{escape(str(logo), quote=True)}" alt="{escape(selected)} logo">' if logo else "🏀"

        support_html = _factor_html(factors["supports"], "support")
        conflict_html = _factor_html(factors["conflicts"], "conflict")
        ev_text = "—" if not np.isfinite(ev) else f"{100.0*ev:+.1f}%"
    except Exception as exc:
        return _compact_html(f"""
        <div class="ks-spread169-wrap">
          <div class="ks-spread169-head"><span>STEP 7 • FINAL PICK BREAKDOWN + RISK / CONFIDENCE SUMMARY</span><span class="ks-spread169-chip warn">SUMMARY CHECK</span></div>
          <div class="ks-spread169-empty">The final explanatory summary could not be assembled. Steps 1–6 and the verified production Spread output remain unchanged.</div>
          <div class="ks-spread169-note">Diagnostic • {escape(str(exc)[:180])}</div>
        </div>
        """)

    return _compact_html(f"""
    <div class="ks-spread169-wrap">
      <div class="ks-spread169-head"><span>STEP 7 • FINAL PICK BREAKDOWN + RISK / CONFIDENCE SUMMARY</span><span class="ks-spread169-chip good">FINAL SUMMARY • READ ONLY</span></div>
      <div class="ks-spread169-scope">Ties together existing Steps 1–6 • no new projection • no probability adjustment • no reranking</div>

      <div class="ks-spread169-pick">
        <span class="ks-spread169-logo">{logo_html}</span>
        <span><small>FINAL PRODUCTION SELECTION</small><b>{escape(selected)} {_line(spread)}</b><em>{escape(book)} • {_odds(price)} • fair {_odds(fair)}</em></span>
        <span class="ks-spread169-prob">{_pct(cover)}</span>
      </div>

      <div class="ks-spread169-badges">
        <span class="ks-spread169-chip {escape(str(strength_class))}">PICK STRENGTH • {escape(str(strength))}</span>
        <span class="ks-spread169-chip good">GRADE • {escape(grade)}</span>
        <span class="ks-spread169-chip {model_class}">MODEL OUTPUT CONFIDENCE • {model_conf}</span>
        <span class="ks-spread169-chip {data_class}">CONTEXT DATA CONFIDENCE • {data_conf}</span>
        <span class="ks-spread169-chip {risk_class}">CONTEXT RISK • {risk_level}</span>
      </div>

      <div class="ks-spread169-grid">
        <div><small>5M MC COVER</small><strong>{_pct(cover)}</strong></div>
        <div><small>NO-VIG EDGE</small><strong>{_pp(edge)}</strong></div>
        <div><small>MEAN COVER CUSHION</small><strong>{_pts(cushion)}</strong></div>
        <div><small>EV</small><strong>{ev_text}</strong></div>
      </div>

      <div class="ks-spread169-confidence">
        <div><small>MODEL CONFIDENCE BASIS</small><strong>{escape(model_note)}</strong></div>
        <div><small>DATA CONFIDENCE BASIS</small><strong>{escape(data_note)}</strong></div>
      </div>

      <div class="ks-spread169-columns">
        <div class="ks-spread169-factorbox"><small>STRONGEST SUPPORTING FACTORS</small>{support_html}</div>
        <div class="ks-spread169-factorbox"><small>STRONGEST CONFLICTING / RISK FACTORS</small>{conflict_html}</div>
      </div>

      <div class="ks-spread169-thesis"><small>FINAL SPREAD THESIS</small><strong>{escape(thesis)}</strong></div>
      <div class="ks-spread169-note">Final card summary only • every probability, line, fair price, EV, production grade, Pick Strength and ranking remains the existing verified output from the protected Spread chain. Context confidence/risk labels are explanatory presentation labels and are NOT FED BACK INTO the model.</div>
    </div>
    """)


def _form_plus_step7(day_str: str, row) -> str:
    return previous._form_plus_step6(day_str, row) + _final_block(day_str, row)


def _install_step7() -> None:
    _ORIGINAL_INSTALL_STEP6()
    step3._form_block = _form_plus_step7


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    previous._install_step6 = _install_step7

    st.markdown(
        """
<style>
.ks-spread169-wrap{background:linear-gradient(145deg,#0b1b2b,#081520);border:1px solid #52708a;border-radius:17px;padding:13px;margin-top:15px;box-shadow:inset 3px 0 0 #d5aa18}
.ks-spread169-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;color:#b6e2ff;font-size:.60rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.ks-spread169-scope{color:#8198aa;font-size:.53rem;margin:7px 0 10px}
.ks-spread169-chip{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;font-size:.42rem;font-weight:950;white-space:nowrap}.ks-spread169-chip.good,.ks-spread169-chip.elite,.ks-spread169-chip.strong{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread169-chip.mid,.ks-spread169-chip.medium{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread169-chip.warn,.ks-spread169-chip.monitor,.ks-spread169-chip.nop{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread169-chip.bad,.ks-spread169-chip.blocked{border-color:#7a3941;background:#35171b;color:#ffadb5}
.ks-spread169-pick{display:grid;grid-template-columns:44px 1fr auto;align-items:center;gap:10px;background:#07131f;border:1px solid #36546d;border-radius:12px;padding:11px}.ks-spread169-logo{width:42px;height:42px;display:flex;align-items:center;justify-content:center}.ks-spread169-logo img{max-width:42px;max-height:42px;object-fit:contain}.ks-spread169-pick small{display:block;color:#7f95a7;font-size:.43rem;font-weight:950}.ks-spread169-pick b{display:block;color:#fff;font-size:.82rem;margin-top:2px}.ks-spread169-pick em{display:block;color:#8ca2b2;font-style:normal;font-size:.50rem;margin-top:3px}.ks-spread169-prob{color:#fff;font-size:1.55rem;font-weight:1000}
.ks-spread169-badges{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0}.ks-spread169-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ks-spread169-grid div,.ks-spread169-confidence div{background:#07131f;border:1px solid #284b64;border-radius:9px;padding:8px}.ks-spread169-grid small,.ks-spread169-confidence small,.ks-spread169-factorbox>small,.ks-spread169-thesis small{display:block;color:#718ba0;font-size:.42rem;font-weight:950;letter-spacing:.035em}.ks-spread169-grid strong{display:block;color:#f6fbff;font-size:.69rem;margin-top:3px}
.ks-spread169-confidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:8px}.ks-spread169-confidence strong{display:block;color:#cbdbe6;font-size:.54rem;line-height:1.45;margin-top:4px}
.ks-spread169-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}.ks-spread169-factorbox{background:#081522;border:1px solid #284b64;border-radius:10px;padding:9px}.ks-spread169-factor{display:grid;grid-template-columns:18px 1fr;gap:5px;align-items:start;margin-top:7px}.ks-spread169-factor span{width:17px;height:17px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.49rem;font-weight:1000}.ks-spread169-factor.support span{background:#0b3327;color:#7df2ba;border:1px solid #237a59}.ks-spread169-factor.conflict span{background:#352516;color:#ffc984;border:1px solid #7c5832}.ks-spread169-factor p{margin:0;color:#d3e1ea;font-size:.54rem;line-height:1.45}
.ks-spread169-thesis{margin-top:8px;background:#0a1d2c;border:1px solid #4b6980;border-radius:10px;padding:10px}.ks-spread169-thesis strong{display:block;color:#fff1b2;font-size:.62rem;line-height:1.55;margin-top:5px}.ks-spread169-note{color:#6f8799;font-size:.49rem;line-height:1.45;margin-top:8px}.ks-spread169-empty{color:#c8d7e3;font-size:.63rem;line-height:1.5;margin-top:8px}
@media(max-width:760px){.ks-spread169-head{align-items:flex-start}.ks-spread169-pick{grid-template-columns:40px 1fr}.ks-spread169-prob{grid-column:2;font-size:1.35rem}.ks-spread169-columns,.ks-spread169-confidence{grid-template-columns:1fr}.ks-spread169-chip{font-size:.40rem}}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "🏁 Spread V1.6.9 • Top-5 Card Steps 1–7 COMPLETE • final breakdown + supporting/conflicting factors + "
        "model/data confidence + context risk • production model and ranking remain unchanged"
    )
    return previous.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(previous, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
