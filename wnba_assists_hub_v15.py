"""WNBA Assists V15 — Step 15 market-independent assist projection.

Preserves Assists Steps 1–14 and implements the first expected-assists model on
the independent basketball branch.

Architecture:
MODEL:  Steps 1–12 -> Step 15 -> Step 16 -> Step 17
MARKET: Steps 13–14 ---------------------> joins later at Steps 18/19

Step 15 rules:
- Step 12 must pass; SportsGameOdds / no-vig availability is irrelevant;
- use Step-4 projected minutes as the exposure anchor;
- use Step-6 regression-protected AST/36 as the player baseline;
- allow only bounded adjustments from current role shift, official opportunity
  tracking when independently informative, teammate conversion, opponent assist
  environment, positional matchup and expected pace;
- explicit proxy opportunity is validation/confidence context only so it cannot
  double-count Step-4/5/6 inputs from which that proxy was constructed;
- H2H remains 0% projection influence;
- sportsbook lines, posted prices, no-vig probabilities and provider fair odds
  remain 0% projection influence;
- the combined contextual adjustment is capped at +/-15% around the
  minutes-scaled stabilized player baseline;
- core rotation players must have all auditable model inputs or Step 15 fails
  closed.

No discrete distribution, Over/Under probability, fair model odds, EV or Monte
Carlo is enabled in this step.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v14 as step14

step13 = step14.step13
step12 = step14.step12
step11 = step14.step11
step3 = step14.step3
step4 = step14.step4
step5 = step14.step5
step6 = step14.step6
step7 = step14.step7
step8 = step14.step8
step9 = step14.step9
step10 = step14.step10
players = step14.players
sgo = step14.sgo

MODEL_VERSION = "WNBA ASSISTS V15 • STEP 15 MARKET-INDEPENDENT ASSIST PROJECTION"
_ET = ZoneInfo("America/New_York")
CORE_MINUTES = 10.0
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
RISK_STATUSES = {"QUESTIONABLE", "PROBABLE", "REPORTED", "DAY-TO-DAY"}
TOTAL_ADJUSTMENT_CAP = 0.15


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _clip(value: float, lo: float, hi: float) -> float:
    if not np.isfinite(value):
        return 0.0
    return float(np.clip(value, lo, hi))


def _unique_team_median(frame: pd.DataFrame, column: str) -> float:
    if frame is None or frame.empty or column not in frame.columns:
        return np.nan
    work = frame.copy()
    work["_ref_value"] = pd.to_numeric(work[column], errors="coerce")
    if "TEAM_ID_NUM" in work.columns:
        work["_ref_team"] = pd.to_numeric(work["TEAM_ID_NUM"], errors="coerce")
        work = work.drop_duplicates("_ref_team")
    vals = work["_ref_value"].dropna()
    vals = vals[np.isfinite(vals)]
    return float(vals.median()) if len(vals) else np.nan


def _position_references(frame: pd.DataFrame) -> dict[str, float]:
    refs: dict[str, float] = {}
    if frame is None or frame.empty or "OPP_POS_AST40_STABLE" not in frame.columns:
        return refs
    work = frame.copy()
    work["_bucket"] = work.get("POSITION_BUCKET", pd.Series("", index=work.index)).astype(str).str.upper()
    work["_value"] = pd.to_numeric(work["OPP_POS_AST40_STABLE"], errors="coerce")
    if "OPPONENT_TEAM_ID" in work.columns:
        work["_opp"] = pd.to_numeric(work["OPPONENT_TEAM_ID"], errors="coerce")
    else:
        work["_opp"] = work.get("OPPONENT", pd.Series("", index=work.index)).astype(str)
    work = work.drop_duplicates(["_bucket", "_opp"])
    for bucket, part in work.groupby("_bucket", dropna=False):
        vals = part["_value"].dropna()
        vals = vals[np.isfinite(vals)]
        if str(bucket) in {"GUARD", "WING", "BIG"} and len(vals):
            refs[str(bucket)] = float(vals.median())
    return refs


def _official_opportunity_reference(frame: pd.DataFrame) -> float:
    if frame is None or frame.empty:
        return np.nan
    mode = frame.get("OPPORTUNITY_MODE", pd.Series("", index=frame.index)).astype(str).str.upper()
    pot = pd.to_numeric(frame.get("OFFICIAL_POT_AST_BLEND"), errors="coerce")
    actual = pd.to_numeric(frame.get("OFFICIAL_TRACKING_AST"), errors="coerce")
    ratio = pot / actual.where(actual.gt(0.25))
    vals = ratio.loc[mode.eq("OFFICIAL WNBA PASSING TRACKING")].replace([np.inf, -np.inf], np.nan).dropna()
    vals = vals[(vals > 0.25) & (vals < 8.0)]
    return float(vals.median()) if len(vals) >= 2 else np.nan


def _relative_effect(value: float, reference: float, sensitivity: float, cap: float) -> float:
    if not np.isfinite(value) or not np.isfinite(reference) or reference <= 0:
        return 0.0
    return _clip((value / reference - 1.0) * sensitivity, -cap, cap)


def _confidence(row: pd.Series, missing_optional: int, total_adjustment: float) -> tuple[float, str]:
    score = 86.0

    minute_conf = str(row.get("MINUTE_CONFIDENCE") or "").upper()
    if minute_conf == "HIGH":
        score += 2.0
    elif minute_conf == "MEDIUM":
        score -= 3.0
    else:
        score -= 10.0

    volatility = str(row.get("FORM_VOLATILITY") or "").upper()
    if volatility == "LOW":
        score += 2.0
    elif volatility == "MEDIUM":
        score -= 2.0
    elif volatility == "HIGH":
        score -= 8.0
    else:
        score -= 4.0

    mode = str(row.get("OPPORTUNITY_MODE") or "").upper()
    if mode == "OFFICIAL WNBA PASSING TRACKING":
        score += 3.0
    else:
        score -= 3.0

    coverage = _num(row.get("TEAMMATE_SHOOTER_COVERAGE"))
    if np.isfinite(coverage):
        if coverage >= 0.90:
            score += 2.0
        elif coverage >= 0.75:
            score -= 3.0
        else:
            score -= 8.0
    else:
        score -= 6.0

    availability = str(row.get("AVAILABILITY") or "").upper()
    if availability in RISK_STATUSES or str(row.get("STATUS_RISK") or "").upper() == "YES":
        score -= 12.0

    proj_min = _num(row.get("PROJ_MIN"), 0.0)
    if proj_min < 10.0:
        score -= 8.0
    elif proj_min < 18.0:
        score -= 4.0

    form_games = _safe_int(row.get("FORM_GAMES"))
    if 0 < form_games < 8:
        score -= 4.0

    score -= min(12.0, 3.0 * max(0, int(missing_optional)))
    if abs(total_adjustment) >= TOTAL_ADJUSTMENT_CAP - 1e-6:
        score -= 3.0

    score = float(np.clip(score, 35.0, 95.0))
    if score >= 82.0:
        label = "HIGH"
    elif score >= 67.0:
        label = "MEDIUM"
    else:
        label = "LOW"
    return score, label


def _build_step15_projection(
    h2h_rows: pd.DataFrame,
    step12_ready: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not step12_ready:
        return pd.DataFrame(), {
            "ready": False,
            "state": "LOCKED",
            "reason": "Step 12 has not passed",
            "core_players": 0,
            "core_projected": 0,
        }
    if h2h_rows is None or h2h_rows.empty:
        return pd.DataFrame(), {
            "ready": False,
            "state": "CHECK",
            "reason": "Step 12 supplied no player model rows",
            "core_players": 0,
            "core_projected": 0,
        }

    out = h2h_rows.copy()

    # References are computed only from basketball-context columns already
    # carried by Steps 1–12. No sportsbook/no-vig columns enter this function.
    opp_ast_ref = _unique_team_median(out, "OPP_AST_ENV_STABLE")
    opp_ratio_ref = _unique_team_median(out, "OPP_AST_FGM_STABLE")
    pos_refs = _position_references(out)
    official_opp_ref = _official_opportunity_reference(out)

    new_numeric = (
        "BASELINE_EXPECTED_AST",
        "ROLE_EFFECT",
        "OPPORTUNITY_EFFECT",
        "CONVERSION_EFFECT",
        "OPPONENT_EFFECT",
        "POSITION_EFFECT",
        "PACE_EFFECT",
        "TOTAL_CONTEXT_EFFECT",
        "EXPECTED_ASSISTS",
        "PROJECTION_CONFIDENCE_SCORE",
    )
    for col in new_numeric:
        out[col] = np.nan
    out["PROJECTION_CONFIDENCE"] = "UNAVAILABLE"
    out["PROJECTION_STATE"] = "CHECK"
    out["PROJECTION_REASON"] = ""
    out["MARKET_INFLUENCE"] = "0%"
    out["H2H_INFLUENCE"] = "0%"
    out["PROJECTION_SOURCE"] = (
        "Steps 4-11 basketball model • Step 12 H2H carried for identity only (0% weight)"
    )
    out["PROJECTION_VERSION"] = MODEL_VERSION

    core_total = 0
    core_projected = 0
    active_projected = 0
    official_tracking_players = 0
    proxy_players = 0
    high_conf = 0
    medium_conf = 0
    low_conf = 0
    missing_core: list[str] = []

    for idx, row in out.iterrows():
        availability = str(row.get("AVAILABILITY") or "UNKNOWN").upper().strip()
        proj_min = _num(row.get("PROJ_MIN"), 0.0)
        is_active = bool(proj_min > 0.25 and availability not in ZERO_STATUSES)
        is_core = bool(proj_min >= CORE_MINUTES and availability not in ZERO_STATUSES)

        if is_core:
            core_total += 1

        if not is_active:
            out.at[idx, "PROJECTION_STATE"] = "ZERO / INACTIVE"
            out.at[idx, "PROJECTION_REASON"] = "zero projected minutes or unavailable status"
            continue

        stable36 = _num(row.get("STABILIZED_AST36_FORM"))
        conversion_index = _num(row.get("LINEUP_CONVERSION_INDEX"))
        opp_ast = _num(row.get("OPP_AST_ENV_STABLE"))
        opp_ratio = _num(row.get("OPP_AST_FGM_STABLE"))
        pos_ast40 = _num(row.get("OPP_POS_AST40_STABLE"))
        pace_factor = _num(row.get("PACE_OPPORTUNITY_FACTOR"))
        opportunity_index = _num(row.get("CREATION_OPPORTUNITY_INDEX"))
        pid = _safe_int(row.get("PLAYER_ID"))
        team_id = _safe_int(row.get("TEAM_ID_NUM") or row.get("TEAM_ID"))
        opponent_id = _safe_int(row.get("OPPONENT_TEAM_ID"))
        role = str(row.get("CREATION_ROLE") or "").strip()

        required = {
            "stabilized AST/36": stable36,
            "lineup conversion": conversion_index,
            "opponent assist environment": opp_ast,
            "position matchup": pos_ast40,
            "pace factor": pace_factor,
            "creation opportunity": opportunity_index,
        }
        missing = [name for name, value in required.items() if not np.isfinite(value)]
        if pid <= 0:
            missing.append("player identity")
        if team_id <= 0 or opponent_id <= 0:
            missing.append("team/opponent identity")
        if not role:
            missing.append("creator role")

        if missing:
            out.at[idx, "PROJECTION_STATE"] = "CHECK"
            out.at[idx, "PROJECTION_REASON"] = "missing " + ", ".join(missing)
            if is_core:
                missing_core.append(f"{row.get('PLAYER_NAME', 'Player')}: {', '.join(missing)}")
            continue

        baseline = max(0.0, stable36) * max(0.0, proj_min) / 36.0

        # 1) Role shift: only a verified current change receives a mean
        # adjustment. Static role labels are already embedded in the player form.
        role_effect = 0.0
        role_shift = str(row.get("ROLE_SHIFT") or "STABLE").upper()
        vacated = max(0.0, _num(row.get("VACATED_CREATION_SHARE"), 0.0))
        if role_shift.startswith("UP"):
            role_effect = _clip(0.01 + 0.35 * vacated, 0.0, 0.055)

        # 2) Opportunity: official potential-assist tracking may add a small,
        # relative signal. The Step-7 proxy gets 0 mean weight because that proxy
        # is itself built from minutes/role/form and would double-count baseline.
        opportunity_effect = 0.0
        opportunity_mode = str(row.get("OPPORTUNITY_MODE") or "").upper()
        if opportunity_mode == "OFFICIAL WNBA PASSING TRACKING":
            official_tracking_players += 1
            pot = _num(row.get("OFFICIAL_POT_AST_BLEND"))
            actual = _num(row.get("OFFICIAL_TRACKING_AST"))
            if np.isfinite(pot) and np.isfinite(actual) and actual > 0.25 and np.isfinite(official_opp_ref):
                ratio = pot / actual
                opportunity_effect = _relative_effect(ratio, official_opp_ref, 0.15, 0.025)
        else:
            proxy_players += 1

        # 3) Teammate conversion. Step-8 index is intentionally centered near 50.
        conversion_effect = _clip((conversion_index - 50.0) * 0.003, -0.04, 0.04)

        # 4) Team-level opponent environment, normalized to exact slate peers and
        # shrunk so a small slate cannot dominate the player baseline.
        opp_ast_effect = _relative_effect(opp_ast, opp_ast_ref, 0.30, 0.04)
        opp_ratio_effect = _relative_effect(opp_ratio, opp_ratio_ref, 0.30, 0.04)
        opponent_effect = _clip(0.65 * opp_ast_effect + 0.35 * opp_ratio_effect, -0.04, 0.04)

        # 5) Position matchup: stable Guard/Wing/Big allowance plus a very small
        # recent-vs-L20 directional component.
        bucket = str(row.get("POSITION_BUCKET") or "").upper()
        pos_ref = _num(pos_refs.get(bucket))
        pos_level = _relative_effect(pos_ast40, pos_ref, 0.25, 0.035)
        pos_recent_index = _num(row.get("OPP_POS_RECENT_INDEX"))
        pos_trend = 0.0
        if np.isfinite(pos_recent_index):
            pos_trend = _clip((pos_recent_index / 100.0 - 1.0) * 0.10, -0.012, 0.012)
        position_effect = _clip(pos_level + pos_trend, -0.04, 0.04)

        # 6) Pace: Step 11 already bounds the raw opportunity factor to 0.90–1.10.
        # Shrink that factor again before applying it to a player rate baseline.
        pace_effect = _clip((pace_factor - 1.0) * 0.65, -0.05, 0.05)

        total_effect = _clip(
            role_effect
            + opportunity_effect
            + conversion_effect
            + opponent_effect
            + position_effect
            + pace_effect,
            -TOTAL_ADJUSTMENT_CAP,
            TOTAL_ADJUSTMENT_CAP,
        )
        expected = max(0.0, baseline * (1.0 + total_effect))

        optional_missing = 0
        if opportunity_mode != "OFFICIAL WNBA PASSING TRACKING":
            optional_missing += 1
        if not np.isfinite(opp_ratio):
            optional_missing += 1
        if not np.isfinite(_num(row.get("TEAMMATE_SHOOTER_COVERAGE"))):
            optional_missing += 1

        conf_score, conf_label = _confidence(row, optional_missing, total_effect)

        out.at[idx, "BASELINE_EXPECTED_AST"] = baseline
        out.at[idx, "ROLE_EFFECT"] = role_effect
        out.at[idx, "OPPORTUNITY_EFFECT"] = opportunity_effect
        out.at[idx, "CONVERSION_EFFECT"] = conversion_effect
        out.at[idx, "OPPONENT_EFFECT"] = opponent_effect
        out.at[idx, "POSITION_EFFECT"] = position_effect
        out.at[idx, "PACE_EFFECT"] = pace_effect
        out.at[idx, "TOTAL_CONTEXT_EFFECT"] = total_effect
        out.at[idx, "EXPECTED_ASSISTS"] = expected
        out.at[idx, "PROJECTION_CONFIDENCE_SCORE"] = conf_score
        out.at[idx, "PROJECTION_CONFIDENCE"] = conf_label
        out.at[idx, "PROJECTION_STATE"] = "PASS"
        out.at[idx, "PROJECTION_REASON"] = "market-independent model inputs complete"

        active_projected += 1
        if is_core:
            core_projected += 1
        if conf_label == "HIGH":
            high_conf += 1
        elif conf_label == "MEDIUM":
            medium_conf += 1
        else:
            low_conf += 1

    ready = bool(core_total > 0 and core_projected == core_total)
    state = "VERIFIED" if ready else "CHECK"
    reason = "" if ready else (
        "one or more core rotation players lack a complete market-independent projection"
    )

    return out, {
        "ready": ready,
        "state": state,
        "reason": reason,
        "core_players": core_total,
        "core_projected": core_projected,
        "active_projected": active_projected,
        "official_tracking_players": official_tracking_players,
        "proxy_players": proxy_players,
        "high_confidence": high_conf,
        "medium_confidence": medium_conf,
        "low_confidence": low_conf,
        "missing_core": missing_core[:12],
        "opponent_ast_reference": opp_ast_ref,
        "opponent_ast_fgm_reference": opp_ratio_ref,
        "position_references": pos_refs,
        "official_opportunity_reference": official_opp_ref,
        "total_adjustment_cap": TOTAL_ADJUSTMENT_CAP,
        "sportsbook_inputs_used": 0,
        "h2h_weight": 0.0,
        "simulations": 0,
    }


def _render_step15(
    h2h_rows: pd.DataFrame,
    step12_ready: bool,
    day_str: str,
) -> tuple[bool, pd.DataFrame, dict[str, Any]]:
    st.markdown("### 🧠 Step 15 — Market-Independent Assist Projection")
    st.caption(
        "Expected assists from basketball inputs only. Step 15 scales the regression-protected AST/36 baseline to projected minutes, then applies bounded role/opportunity/conversion/opponent/position/pace context. Sportsbook lines, prices and no-vig probabilities have 0% influence; H2H remains 0%."
    )

    projection, diag = _build_step15_projection(h2h_rows, step12_ready)
    ready = bool(diag.get("ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Core rotation", int(diag.get("core_players") or 0))
    c2.metric(
        "Core projected",
        f"{int(diag.get('core_projected') or 0)}/{int(diag.get('core_players') or 0)}",
    )
    c3.metric("Sportsbook influence", "0%")
    c4.metric("H2H influence", "0%")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Active projections", int(diag.get("active_projected") or 0))
    d2.metric("Official tracking", int(diag.get("official_tracking_players") or 0))
    d3.metric("High confidence", int(diag.get("high_confidence") or 0))
    d4.metric("Simulations", "0")

    if ready:
        st.success(
            "✅ STEP 15 PASSED • every core rotation player has a complete market-independent expected-assists projection. The projection branch used no sportsbook line, posted price, no-vig probability or H2H adjustment."
        )
    else:
        st.warning(
            f"⚠️ STEP 15 CHECK • {diag.get('reason') or 'projection inputs incomplete'}. Step 16 remains locked."
        )
        if diag.get("missing_core"):
            st.caption("Core input holds: " + " • ".join(diag["missing_core"][:6]))

    if projection is not None and not projection.empty:
        view = projection.loc[projection["PROJECTION_STATE"].eq("PASS")].copy()
        if not view.empty:
            view["Player"] = view["PLAYER_NAME"].astype(str)
            view["Team"] = view.get("TEAM_ABBREVIATION", view.get("TEAM_NAME", pd.Series("", index=view.index))).astype(str)
            view["Opponent"] = view.get("OPPONENT", pd.Series("", index=view.index)).astype(str)
            view["Min"] = pd.to_numeric(view["PROJ_MIN"], errors="coerce").round(1)
            view["Stable AST/36"] = pd.to_numeric(view["STABILIZED_AST36_FORM"], errors="coerce").round(2)
            view["Baseline AST"] = pd.to_numeric(view["BASELINE_EXPECTED_AST"], errors="coerce").round(2)
            view["Role"] = (100.0 * pd.to_numeric(view["ROLE_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Opportunity"] = (100.0 * pd.to_numeric(view["OPPORTUNITY_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Conversion"] = (100.0 * pd.to_numeric(view["CONVERSION_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Opponent env"] = (100.0 * pd.to_numeric(view["OPPONENT_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Position"] = (100.0 * pd.to_numeric(view["POSITION_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Pace"] = (100.0 * pd.to_numeric(view["PACE_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Total adj"] = (100.0 * pd.to_numeric(view["TOTAL_CONTEXT_EFFECT"], errors="coerce")).map(lambda x: f"{x:+.1f}%")
            view["Expected AST"] = pd.to_numeric(view["EXPECTED_ASSISTS"], errors="coerce").round(2)
            view["Confidence"] = view["PROJECTION_CONFIDENCE"].astype(str)
            view["Confidence score"] = pd.to_numeric(view["PROJECTION_CONFIDENCE_SCORE"], errors="coerce").round(0).astype("Int64")
            view = view.sort_values(
                ["EXPECTED_ASSISTS", "PROJECTION_CONFIDENCE_SCORE"],
                ascending=[False, False],
            )
            st.dataframe(
                view[
                    [
                        "Player", "Team", "Opponent", "Min", "Stable AST/36", "Baseline AST",
                        "Role", "Opportunity", "Conversion", "Opponent env", "Position",
                        "Pace", "Total adj", "Expected AST", "Confidence", "Confidence score",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
            )

    if projection is not None and not projection.empty and ready:
        st.session_state[f"wnba_assists_v15_projection::{day_str}"] = projection.copy()
        st.session_state[f"wnba_assists_v15_diag::{day_str}"] = dict(diag)

    with st.expander("🧪 Step-15 projection methodology / isolation diagnostics", expanded=False):
        st.write("• Baseline = Step-6 stabilized AST/36 × Step-4 projected minutes / 36.")
        st.write("• Static creator role is not re-added to the baseline; only an explicit current vacated-creation role shift can move the mean.")
        st.write("• Official WNBA potential-assist tracking can add a small relative opportunity signal.")
        st.write("• Step-7 proxy opportunity has 0 mean weight because it is constructed from minutes/role/form already present in the baseline; it remains a validation/confidence signal.")
        st.write("• Step-8 teammate conversion is bounded to ±4%.")
        st.write("• Step-9 opponent assist environment is slate-normalized and bounded to ±4%.")
        st.write("• Step-10 Guard/Wing/Big context is slate-normalized with a small recent trend component and bounded to ±4%.")
        st.write("• Step-11 pace factor is shrunk again and bounded to ±5%.")
        st.write("• Combined contextual movement is capped at ±15% around the minutes-scaled stabilized player baseline.")
        st.write("• Step-12 H2H projection weight: 0%.")
        st.write("• SportsGameOdds / posted lines / posted odds / Step-14 no-vig probability used: NO.")
        st.write("• Distribution calibration created: NO — Step 16.")
        st.write("• Monte Carlo runs: 0 — Step 17.")
        st.write(f"• Opponent AST slate reference: {diag.get('opponent_ast_reference')}")
        st.write(f"• Opponent AST/FGM slate reference: {diag.get('opponent_ast_fgm_reference')}")
        st.write(f"• Position references: {diag.get('position_references', {})}")
        st.write(f"• Official opportunity ratio reference: {diag.get('official_opportunity_reference')}")
        st.write(f"• Core input holds: {diag.get('missing_core', [])}")

    return ready, projection, diag


def _render_step14_with_correct_dependency(
    exact_lines: pd.DataFrame,
    step13_ready: bool,
    step13_market_ready: bool,
    step13_diag: dict[str, Any],
    day_str: str,
):
    """Render preserved Step 14 while correcting only its old Step-15 lock wording."""
    old_info = st.info
    old_warning = st.warning

    def fixed_info(body, *args, **kwargs):
        text = str(body).replace(
            "The layer is armed and Step 15 remains locked until a real same-day market exists.",
            "The market branch is armed. Step 15 runs independently from verified Steps 1–12 and does not require a sportsbook market.",
        )
        return old_info(text, *args, **kwargs)

    def fixed_warning(body, *args, **kwargs):
        text = str(body).replace(
            "Step 15 remains locked.",
            "This market-branch hold does not lock Step 15; the projection branch depends only on verified Steps 1–12.",
        )
        return old_warning(text, *args, **kwargs)

    st.info = fixed_info
    st.warning = fixed_warning
    try:
        return step14._render_step14(
            exact_lines, step13_ready, step13_market_ready, step13_diag, day_str
        )
    finally:
        st.info = old_info
        st.warning = old_warning


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = step3.schedule.load_verified_wnba_slate(slate_day)
    verification = str(slate.get("verification") or "")

    st.markdown(
        """
        <style>
        .ks-ast-hero{padding:25px 27px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);}
        .ks-ast-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;}
        .ks-ast-title{margin-top:9px;color:#f8fafc;font-size:2.05rem;line-height:1.08;font-weight:950;}
        .ks-ast-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.62;font-weight:650;}
        .ks-ast-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="ks-ast-hero">
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 15</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–14 remain intact. Step 15 activates the independent expected-assists model from verified basketball inputs only. Sportsbook lines/no-vig stay on their separate market branch and have 0% influence on the projection.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">🧠 model branch: Steps 1–12 → 15</span>
          <span class="ks-ast-chip">⚖️ market branch: Steps 13–14</span>
          <span class="ks-ast-chip">🚫 zero simulations</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("### 📅 Step 2 — Verified Daily WNBA Slate")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected date", slate_day)
    c2.metric("Verification", verification or "CHECK")
    c3.metric("Games found", int(slate.get("games_found", 0)))
    c4.metric("WNBA teams validated", int(slate.get("teams_validated", 0)))
    if verification == "VERIFIED":
        st.success(
            f"✅ STEP 2 PASSED • {slate.get('games_found', 0)} same-day WNBA game(s) verified by the preserved Step-2 reconciliation layer."
        )
    elif verification == "NO GAMES":
        st.info(f"ℹ️ STEP 2 VERIFIED EMPTY • No WNBA games for {slate_day} ET.")
    else:
        st.error("⛔ STEP 2 CHECK • Same-day slate verification is incomplete.")

    st.markdown("### 🩺 Step 3 — Current Rosters + Same-Day Injury / Status")
    step3_ready_ui = step3._render_step3(slate, slate_day)
    merged, step3_diag = step4._step3_snapshot(slate, slate_day)
    step3_ready = bool(step3_ready_ui and step3_diag.get("ready"))
    step4_ready, minutes = step4._render_step4(slate, slate_day, merged, step3_ready)
    step5_ready, roles = step5._render_step5(slate, slate_day, minutes, step4_ready)
    step6_ready, form = step6._render_step6(slate, slate_day, roles, step5_ready)
    step7_ready, opportunity = step7._render_step7(slate, slate_day, form, step6_ready)
    step8_ready, conversion = step8._render_step8(slate, slate_day, opportunity, step7_ready)
    step9_ready, environment = step9._render_step9(slate, slate_day, conversion, step8_ready)
    step10_ready, position_rows = step10._render_step10(slate, slate_day, environment, step9_ready)
    step11_ready, pace_rows = step11._render_step11(slate, slate_day, position_rows, step10_ready)
    step12_ready, h2h_rows = step12._render_step12(slate, slate_day, pace_rows, step11_ready)
    step13_ready, step13_market_ready, exact_lines, step13_diag = step13._render_step13(
        slate, slate_day, h2h_rows, step12_ready
    )
    step14_ready, step14_market_ready, novig_rows, step14_diag = _render_step14_with_correct_dependency(
        exact_lines, step13_ready, step13_market_ready, step13_diag, slate_day
    )
    step15_ready, projection_rows, step15_diag = _render_step15(
        h2h_rows, step12_ready, slate_day
    )

    if st.button(
        "🔄 RECHECK ASSISTS STEPS 2–15",
        use_container_width=True,
        key="assists_step15_recheck",
    ):
        for fn in (
            step3.schedule.load_verified_wnba_slate,
            step3._current_rosters,
            step3._injury_feed,
            step4._season_schedule,
            step4._rotation_history,
            step5._creation_history,
            step5._official_usage_table,
            step6._season_form_pool,
            step6._recent_assist_history,
            step7._tracking_windows,
            step8._shooting_history,
            step8._raw_shooting_summary,
            step9._official_windows,
            step9._espn_environment,
            step10._position_history,
            step11._pace_history,
            step11._raw_team_possessions,
            step12._h2h_game_pool,
        ):
            try:
                fn.clear()
            except Exception:
                pass
        try:
            sgo.clear_cache()
        except Exception:
            pass
        try:
            players._espn_roster.clear()
            players._espn_season_schedule.clear()
            players._espn_game_summary.clear()
        except Exception:
            pass
        st.session_state.pop(f"wnba_assists_v15_projection::{slate_day}", None)
        st.session_state.pop(f"wnba_assists_v15_diag::{slate_day}", None)
        st.rerun()

    st.markdown("### 🧱 Assists Build Order — Current")
    state13 = str(step13_diag.get("state") or "CHECK")
    state14 = str(step14_diag.get("state") or "CHECK")
    note13 = (
        "Verified empty — no upcoming pregame"
        if state13 == "VERIFIED EMPTY"
        else "Exact same-book O/U • start/freshness gated"
    )
    note14 = (
        "Verified empty — awaits exact pregame pairs"
        if state14 == "VERIFIED EMPTY"
        else "Proportional same-book vig removal"
    )
    layers = [
        (1, "Isolated Assists page", "✅ LIVE", "Display shell preserved"),
        (2, "Verified daily WNBA slate", "✅ LIVE" if verification in {"VERIFIED", "NO GAMES"} else "⚠️ CHECK", "Exact ET date + provider reconciliation"),
        (3, "Current rosters + injuries/status", "✅ LIVE" if step3_ready else "⚠️ CHECK", "Fail-closed current identity + same-day status"),
        (4, "Projected minutes + rotation", "✅ LIVE" if step4_ready else "⚠️ CHECK", "L3/L5/L10 rotation + 200-minute team allocation"),
        (5, "Assist role + ball-handling / usage", "✅ LIVE" if step5_ready else "⚠️ CHECK", "Empirical creation responsibility + usage context"),
        (6, "Recent + season assist form", "✅ LIVE" if step6_ready else "⚠️ CHECK", "Season + L3/L5/L10 • regression protected"),
        (7, "Potential assists / passes / creation chances", "✅ LIVE" if step7_ready else "⚠️ CHECK", "Official tracking when available; honest proxy fallback"),
        (8, "Teammate shot-making + lineup conversion", "✅ LIVE" if step8_ready else "⚠️ CHECK", "Projected active finisher environment"),
        (9, "Opponent assist environment", "✅ LIVE" if step9_ready else "⚠️ CHECK", "Season + L10/L5/L3 assists allowed + AST/FGM"),
        (10, "Position matchup — Guard / Wing / Big", "✅ LIVE" if step10_ready else "⚠️ CHECK", "Exact-opponent position-tagged AST/40 context"),
        (11, "Pace + expected possession volume", "✅ LIVE" if step11_ready else "⚠️ CHECK", "Season + L10/L5/L3 possession environment"),
        (12, "Player vs opponent assist history", "✅ LIVE" if step12_ready else "⚠️ CHECK", "Exact-ID descriptive H2H • 0% projection influence"),
        (13, "Exact SportsGameOdds assist lines", "✅ LIVE" if step13_ready else ("⚠️ CHECK" if step12_ready else "🔒 LOCKED"), note13),
        (14, "Same-book no-vig", "✅ LIVE" if step14_ready else ("⚠️ CHECK" if step13_ready else "🔒 LOCKED"), note14),
        (15, "Market-independent assist projection", "✅ LIVE" if step15_ready else ("⚠️ CHECK" if step12_ready else "🔒 LOCKED"), "Expected assists • market influence 0%"),
        (16, "Uncertainty + distribution calibration", "➡️ NEXT" if step15_ready else "🔒 LOCKED", "Discrete assist count distribution"),
        (17, "5M Monte Carlo + convergence / sensitivity", "🔒 LOCKED", "Actual simulations only"),
        (18, "Line-specific O/U probability + fair odds", "🔒 LOCKED", "Requires model distribution + exact market line"),
        (19, "Model-vs-market edge + EV", "🔒 LOCKED", "Projection branch joins market branch here"),
        (20, "Risk-adjusted qualification + Top 5", "🔒 LOCKED", "Never force five"),
    ]
    for start in range(0, len(layers), 4):
        cols = st.columns(4, gap="small")
        for col, item in zip(cols, layers[start : start + 4]):
            with col:
                st.markdown(step3._layer_card(*item), unsafe_allow_html=True)

    footer13 = "EMPTY" if state13 == "VERIFIED EMPTY" else ("PASS" if step13_market_ready else "CHECK")
    footer14 = "EMPTY" if state14 == "VERIFIED EMPTY" else ("PASS" if step14_market_ready else "CHECK")
    st.caption(
        f"⚡ WNBA Assists V15 Step 15 • Step 2 {verification or 'CHECK'} • "
        f"Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • "
        f"Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • "
        f"Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • "
        f"Step 9 {'PASS' if step9_ready else 'CHECK'} • Step 10 {'PASS' if step10_ready else 'CHECK'} • "
        f"Step 11 {'PASS' if step11_ready else 'CHECK'} • Step 12 {'PASS' if step12_ready else 'CHECK'} • "
        f"Step 13 {footer13} • Step 14 {footer14} • Step 15 {'PASS' if step15_ready else 'CHECK'} • "
        "market influence 0% • H2H weight 0% • no distribution/Monte Carlo yet"
    )


__all__ = [
    "MODEL_VERSION",
    "_build_step15_projection",
    "_render_step15",
    "render_wnba_assists_hub",
]
