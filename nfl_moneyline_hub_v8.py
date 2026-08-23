"""Kyre Sports AI — NFL Moneyline V8 final decision / grading layer.

Builds on V7 without changing Steps 1-7. The final layer evaluates the already
computed model, market and uncertainty diagnostics and assigns a production state.

Hard rule: eligibility gates are evaluated BEFORE quantitative grading. During
preseason, Step 3 game-plan/QB-rotation verification is a mandatory veto gate.
If that gate is unresolved the result is GATED, regardless of model edge or EV.
Regular-season games do not require a preseason rotation plan.

Quantitative grading (only after every hard gate passes):
- QUALIFIED: edge >= 5 pp, EV >= 5%, uncertainty-floor edge >= 2 pp and
  uncertainty-floor EV >= 2%;
- LEAN / WATCH: edge >= 2.5 pp, EV >= 2%, uncertainty-floor edge/EV >= 0;
- HIGH UNCERTAINTY: headline edge/EV positive but the uncertainty floor loses
  its positive edge/EV, or the sampled-P 5th-95th width is > 15 pp;
- NO PLAY: otherwise.

This module does not change Step-4C or Step-6 probabilities, sportsbook prices,
Monte Carlo, no-vig normalization or Step-7 EV. It only consumes their stored
outputs and applies transparent final-production rules.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v7 as v7
import nfl_moneyline_hub_v431 as v431

MODEL_VERSION = "NFL MONEYLINE V8.0 • FINAL DECISION + GRADING"

QUALIFIED_EDGE = 0.050
QUALIFIED_EV = 0.050
QUALIFIED_FLOOR_EDGE = 0.020
QUALIFIED_FLOOR_EV = 0.020
LEAN_EDGE = 0.025
LEAN_EV = 0.020
MAX_COMFORTABLE_INTERVAL = 0.150


def _safe(value, default="") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or default


def _num(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def _finite(value) -> bool:
    return bool(np.isfinite(_num(value)))


def _fmt_pct(value, digits=1):
    n = _num(value)
    return "—" if not np.isfinite(n) else f"{100.0*n:.{digits}f}%"


def _fmt_pp(value, digits=1):
    n = _num(value)
    if not np.isfinite(n):
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{100.0*n:.{digits}f} pp"


def _fmt_ev(value, digits=1):
    n = _num(value)
    if not np.isfinite(n):
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{100.0*n:.{digits}f}%"


def _fmt_ml(value):
    n = _num(value)
    if not np.isfinite(n):
        return "—"
    x = int(round(n))
    return f"+{x}" if x > 0 else str(x)


def _quality_rank(value) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(_safe(value).upper(), 0)


def _season_type(game: dict) -> str:
    text = _safe(game.get("season_type")).lower()
    return text or "unknown"


def _prerequisite_state(game: dict, gid: str, edge_out: dict, mc_out: dict, snap: dict, profiles: dict, calibration: dict) -> dict:
    reasons = []

    if not st.session_state.get("nfl_moneyline_v43_probability_ready"):
        reasons.append("Step 4C calibrated probability not ready")
    if not st.session_state.get("nfl_moneyline_v5_market_ready"):
        reasons.append("Step 5 sportsbook market not ready")
    if not st.session_state.get("nfl_moneyline_v6_mc_ready") or not (mc_out or {}).get("converged"):
        reasons.append("Step 6 Monte Carlo not converged")
    if not st.session_state.get("nfl_moneyline_v7_edge_ready") or not (edge_out or {}).get("ready"):
        reasons.append("Step 7 edge/EV diagnostics not ready")

    cal_quality = _safe((calibration or {}).get("quality"), "LOW").upper()
    if not (calibration or {}).get("ready") or _quality_rank(cal_quality) < 1:
        reasons.append("calibration quality below production minimum")

    market_quality = _safe((snap or {}).get("quality"), "LOW").upper()
    if not (snap or {}).get("ready") or _quality_rank(market_quality) < 1:
        reasons.append("market quality below production minimum")

    away_abbr = _safe(game.get("away_abbr")).upper()
    home_abbr = _safe(game.get("home_abbr")).upper()
    away_quality = _safe((profiles.get(away_abbr) or {}).get("quality"), "LOW").upper()
    home_quality = _safe((profiles.get(home_abbr) or {}).get("quality"), "LOW").upper()
    if _quality_rank(away_quality) < 1 or _quality_rank(home_quality) < 1:
        reasons.append("Step 4A historical data quality below production minimum")

    preseason = _season_type(game) == "preseason"
    gameplan_ready = bool(st.session_state.get("nfl_moneyline_v3_gameplan_ready"))
    if preseason and not gameplan_ready:
        reasons.append("preseason QB participation / rotation is not fully verified")

    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "preseason": preseason,
        "gameplan_ready": gameplan_ready,
        "calibration_quality": cal_quality,
        "market_quality": market_quality,
        "away_data_quality": away_quality,
        "home_data_quality": home_quality,
    }


def _grade_side(side_out: dict, mc_out: dict, side: str) -> dict:
    if not side_out or not side_out.get("ready"):
        return {"grade": "NO PLAY", "score": -999.0, "reason": "comparison inputs incomplete"}

    edge = _num(side_out.get("edge"))
    ev = _num(side_out.get("ev"))
    floor_edge = _num(side_out.get("conservative_edge"))
    floor_ev = _num(side_out.get("conservative_ev"))

    p05 = _num(mc_out.get("p05_probability"))
    p95 = _num(mc_out.get("p95_probability"))
    width = p95 - p05 if np.isfinite(p05) and np.isfinite(p95) else np.nan

    if side == "home" and np.isfinite(width):
        # Complementing away probability preserves interval width.
        width = float(width)

    if not all(np.isfinite(x) for x in (edge, ev, floor_edge, floor_ev)):
        return {"grade": "NO PLAY", "score": -999.0, "reason": "non-finite grade inputs"}

    if edge >= QUALIFIED_EDGE and ev >= QUALIFIED_EV and floor_edge >= QUALIFIED_FLOOR_EDGE and floor_ev >= QUALIFIED_FLOOR_EV:
        grade = "QUALIFIED"
        reason = "headline and uncertainty-floor edge/EV clear full thresholds"
    elif edge > 0 and ev > 0 and (floor_edge <= 0 or floor_ev <= 0 or (np.isfinite(width) and width > MAX_COMFORTABLE_INTERVAL)):
        grade = "HIGH UNCERTAINTY"
        reason = "headline advantage does not remain comfortably positive through uncertainty"
    elif edge >= LEAN_EDGE and ev >= LEAN_EV and floor_edge >= 0 and floor_ev >= 0:
        grade = "LEAN / WATCH"
        reason = "positive edge/EV survives uncertainty but misses full qualification thresholds"
    else:
        grade = "NO PLAY"
        reason = "production edge/EV thresholds are not met"

    # Ordering score is diagnostic only; it does not change threshold eligibility.
    score = 2.0 * floor_edge + floor_ev + 0.5 * edge + 0.5 * ev
    return {
        "grade": grade,
        "score": float(score),
        "reason": reason,
        "edge": edge,
        "ev": ev,
        "floor_edge": floor_edge,
        "floor_ev": floor_ev,
        "interval_width": width,
    }


def _build_final(game: dict, gid: str, edge_out: dict, mc_out: dict, snap: dict, profiles: dict, calibration: dict) -> dict:
    prereq = _prerequisite_state(game, gid, edge_out, mc_out, snap, profiles, calibration)
    away_grade = _grade_side((edge_out or {}).get("away") or {}, mc_out or {}, "away")
    home_grade = _grade_side((edge_out or {}).get("home") or {}, mc_out or {}, "home")

    candidates = [("away", away_grade), ("home", home_grade)]
    leader_side, leader_grade = max(candidates, key=lambda x: x[1].get("score", -999.0))

    if not prereq["eligible"]:
        final_state = "GATED"
    else:
        final_state = leader_grade.get("grade", "NO PLAY")

    return {
        "ready": bool(edge_out and edge_out.get("ready")),
        "eligible": prereq["eligible"],
        "state": final_state,
        "prerequisites": prereq,
        "away_grade": away_grade,
        "home_grade": home_grade,
        "leader_side": leader_side,
        "leader_grade": leader_grade,
    }


def _render_side_snapshot(team: str, side_out: dict, grade: dict):
    st.markdown(f"##### {team}")
    a, b, c = st.columns(3)
    a.metric("Model P(win)", _fmt_pct(side_out.get("model_p")))
    b.metric("No-vig market", _fmt_pct(side_out.get("market_p")))
    c.metric("Edge", _fmt_pp(side_out.get("edge")))
    x, y, z = st.columns(3)
    x.metric("Best ML", _fmt_ml(side_out.get("best_price")))
    y.metric("EV", _fmt_ev(side_out.get("ev")))
    z.metric("Floor EV", _fmt_ev(side_out.get("conservative_ev")))
    st.caption(f"Quantitative layer: {grade.get('grade')} • {grade.get('reason')}")


def _render_final_game(game: dict, final: dict, edge_out: dict):
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    st.markdown(f"#### Final decision — {away} @ {home}")

    if not final.get("ready"):
        st.warning("🔴 NO PLAY • final-decision inputs are incomplete.")
        return

    state = final.get("state")
    prereq = final.get("prerequisites") or {}
    leader_side = final.get("leader_side")
    leader_team = away if leader_side == "away" else home

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Final state", f"🔒 {state}" if state == "GATED" else state)
    m2.metric("Quantitative leader", leader_team)
    m3.metric("Calibration", prereq.get("calibration_quality") or "—")
    m4.metric("Market quality", prereq.get("market_quality") or "—")

    if state == "GATED":
        st.warning(
            "🔒 FINAL DECISION GATED • all downstream math is diagnostic only. "
            + " • ".join(prereq.get("reasons") or ["required production input is unresolved"])
        )
    elif state == "QUALIFIED":
        st.success(f"🟢 QUALIFIED • {leader_team} clears headline and uncertainty-floor production thresholds.")
    elif state == "LEAN / WATCH":
        st.info(f"🟡 LEAN / WATCH • {leader_team} has a positive but sub-threshold production profile.")
    elif state == "HIGH UNCERTAINTY":
        st.warning(f"🟠 HIGH UNCERTAINTY • {leader_team}'s headline advantage weakens materially under uncertainty.")
    else:
        st.error("🔴 NO PLAY • neither side clears the final production thresholds.")

    left, right = st.columns(2)
    with left:
        _render_side_snapshot(away, (edge_out or {}).get("away") or {}, final.get("away_grade") or {})
    with right:
        _render_side_snapshot(home, (edge_out or {}).get("home") or {}, final.get("home_grade") or {})

    with st.expander("🏆 Final grading rules", expanded=False):
        st.markdown(
            "**Hard gates first:** verified upstream model/market layers, calibration ≥ MEDIUM, market quality ≥ MEDIUM, "
            "historical data quality ≥ MEDIUM, Step-6 convergence; preseason additionally requires verified QB participation/rotation.  \n\n"
            "**🟢 QUALIFIED:** edge ≥ 5 pp, EV ≥ 5%, uncertainty-floor edge ≥ 2 pp, uncertainty-floor EV ≥ 2%.  \n"
            "**🟡 LEAN / WATCH:** edge ≥ 2.5 pp, EV ≥ 2%, uncertainty-floor edge/EV ≥ 0.  \n"
            "**🟠 HIGH UNCERTAINTY:** headline edge/EV positive but uncertainty-floor edge/EV is non-positive, or sampled-P interval > 15 pp.  \n"
            "**🔴 NO PLAY:** otherwise.  \n"
            "**🔒 GATED overrides every quantitative grade.**"
        )
        st.caption("Final grading consumes stored outputs only. It never alters the model probability, Monte Carlo, sportsbook prices, no-vig normalization or EV calculation.")


def _render_final_decision() -> bool:
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(schedule, day_str, now_et=pd.Timestamp.now(tz=foundation.ET))

    edge_outputs = st.session_state.get("nfl_moneyline_v7_edge_outputs") or {}
    mc_outputs = st.session_state.get("nfl_moneyline_v6_mc_outputs") or {}
    snapshots = st.session_state.get("nfl_moneyline_v5_market_snapshots") or {}
    profiles = st.session_state.get("nfl_moneyline_v4_strength_profiles") or {}
    calibration = v431.v43._fit_calibration_model()

    st.markdown("### 🏆 Final Decision — Moneyline Grading")
    st.caption(
        "Eligibility gates → data/model quality → 5M convergence → market quality → headline edge/EV → uncertainty-floor edge/EV. "
        "Preseason Step 3 is a mandatory final-output veto gate."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Final decision cannot run because no verified pregame matchup is available.")
        st.session_state["nfl_moneyline_v8_final_ready"] = False
        return False
    if not st.session_state.get("nfl_moneyline_v7_edge_ready"):
        st.warning("Final decision cannot run until Step 7 edge/EV diagnostics are READY.")
        st.session_state["nfl_moneyline_v8_final_ready"] = False
        return False

    outputs = {}
    eligible_count = 0
    gated_count = 0
    qualified_count = 0

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        final = _build_final(
            game, gid,
            edge_outputs.get(gid, {}),
            mc_outputs.get(gid, {}),
            snapshots.get(gid, {}),
            profiles,
            calibration,
        )
        outputs[gid] = final
        if final.get("eligible"):
            eligible_count += 1
        if final.get("state") == "GATED":
            gated_count += 1
        if final.get("state") == "QUALIFIED":
            qualified_count += 1

    a, b, c, d = st.columns(4)
    a.metric("Games evaluated", f"{len(outputs)}/{len(pregame)}")
    b.metric("Final-grade eligible", f"{eligible_count}/{len(pregame)}")
    c.metric("Gated", str(gated_count))
    d.metric("Qualified", str(qualified_count))

    if gated_count:
        st.warning("🔒 FINAL OUTPUT GATED • quantitative diagnostics are preserved, but at least one hard production gate is unresolved.")
    elif eligible_count == len(pregame):
        st.success("✅ FINAL GRADING ACTIVE • every verified pregame matchup passed the hard production gates.")
    else:
        st.warning("⚠️ FINAL GRADING CHECK • at least one matchup has incomplete prerequisites.")

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        _render_final_game(game, outputs.get(gid, {}), edge_outputs.get(gid, {}))

    st.info(
        "FINAL FIREWALL • a sportsbook price can affect EV comparison, but it cannot change the model P(win). "
        "A strong model edge cannot override a failed eligibility/data-integrity gate."
    )

    st.session_state["nfl_moneyline_v8_final_outputs"] = outputs
    st.session_state["nfl_moneyline_v8_final_ready"] = bool(eligible_count == len(pregame))
    return bool(eligible_count == len(pregame))


def render_nfl_moneyline_hub():
    """Render V7 unchanged and inject final decision before production locks."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"injected": False, "eligible": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            if '<span class="knfl-ml-chip">STEP 7</span>' in body:
                body = body.replace('<span class="knfl-ml-chip">STEP 7</span>', '<span class="knfl-ml-chip">FINAL</span>')
            if body.strip() == "### 🔒 Moneyline production locks" and not state["injected"]:
                state["injected"] = True
                state["eligible"] = _render_final_decision()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            layers = set(data["Layer"].astype(str).tolist())
            if "No-vig edge / EV / final grading" in layers:
                data = data.copy()
                mask = data["Layer"].astype(str) == "No-vig edge / EV / final grading"
                if state.get("eligible"):
                    data.loc[mask, "State"] = "FINAL GRADING ACTIVE"
                else:
                    data.loc[mask, "State"] = "STEP 7 READY • FINAL DECISION GATED"
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 7 compares"):
            body = (
                "Final Decision consumes the completed Step-4C/5/6/7 outputs and applies hard data-integrity gates before transparent edge/EV thresholds. "
                "During preseason, unresolved Step-3 QB participation/rotation forces a GATED final state regardless of quantitative edge."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return v7.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
