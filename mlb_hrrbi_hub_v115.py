"""MLB H+R+RBI V1.0.15 — final Top-5 evidence summary.

Presentation/audit wrapper around verified H+R+RBI V1.0.14 Steps 1-11.
The Strongest-threshold Top-5 cards retain every verified layer and add one compact
final synthesis block inspired by the proven Pitcher-K evidence presentation:
- Pick Strength from the existing joint-event probability plus data quality,
- Overall Matchup from verified context alignment,
- Opportunity grade from lineup confirmation + projected PA,
- 0-100 Evidence Score with transparent weighted coverage,
- Supports / Concerns / Neutral / N/A signal summaries.

Model firewall: this final block never changes candidate selection, H/R/RBI rates,
joint-event Monte Carlo, threshold probability, fair odds, confidence or Top-5
ordering. Context signals are audit evidence only; unavailable signals reduce data
coverage rather than being guessed.
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st

import mlb_hrrbi_hub_v114 as prior
import mlb_hrrbi_hub_v106 as matchup_step
import mlb_hrrbi_hub_v111 as defense_step
import mlb_hrrbi_hub_v112 as bullpen_step
import mlb_hrrbi_hub_v113 as starter_step

MODEL_VERSION = "H+R+RBI V1.0.15"
base = prior.base
core = prior.core
_BASE_CARD = base._card


def _finite(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _threshold_rate(logs, threshold, n):
    rows = list(logs or [])[-max(1, int(n)):]
    vals = []
    for row in rows:
        try:
            total = (
                float(row.get("h", 0) or 0)
                + float(row.get("r", 0) or 0)
                + float(row.get("rbi", 0) or 0)
            )
            vals.append(total)
        except Exception:
            continue
    if not vals:
        return None
    return sum(1 for x in vals if x >= float(threshold)) / len(vals)


def _sig(name, state, weight, reason):
    return {
        "name": str(name),
        "state": state,
        "weight": float(weight),
        "reason": str(reason or ""),
    }


def _signal_rows(result, threshold):
    """Build independent audit signals. Never raises and never mutates result."""
    rows = []
    sim = result.get("sim") or {}
    try:
        p = float(core._threshold_prob(sim, threshold))
    except Exception:
        p = _finite(sim.get(f"p{int(threshold)}"), None)

    if p is None:
        rows.append(_sig("Model", "na", 28, "probability unavailable"))
    elif p >= 0.68:
        rows.append(_sig("Model", "support", 28, f"{p*100:.1f}% {threshold}+ probability"))
    elif p >= 0.60:
        rows.append(_sig("Model", "neutral", 28, f"{p*100:.1f}% {threshold}+ probability"))
    else:
        rows.append(_sig("Model", "concern", 28, f"{p*100:.1f}% {threshold}+ probability"))

    conf = str(result.get("confidence") or "").upper()
    if conf in {"HIGH", "MEDIUM-HIGH"}:
        rows.append(_sig("Data quality", "support", 12, conf))
    elif conf == "MEDIUM":
        rows.append(_sig("Data quality", "neutral", 12, conf))
    elif conf:
        rows.append(_sig("Data quality", "concern", 12, conf))
    else:
        rows.append(_sig("Data quality", "na", 12, "confidence unavailable"))

    pa = _finite(result.get("projected_pa"), None)
    confirmed = bool(result.get("lineup_confirmed"))
    spot = int(_finite(result.get("position"), 0) or 0)
    if pa is None:
        rows.append(_sig("Opportunity", "na", 14, "projected PA unavailable"))
    elif confirmed and pa >= 4.50 and 1 <= spot <= 5:
        rows.append(_sig("Opportunity", "support", 14, f"confirmed Bat #{spot} • {pa:.2f} PA"))
    elif pa >= 4.10:
        state = "neutral" if confirmed else "concern"
        label = "confirmed" if confirmed else "projected lineup"
        rows.append(_sig("Opportunity", state, 14, f"{label} • {pa:.2f} PA"))
    else:
        rows.append(_sig("Opportunity", "concern", 14, f"{pa:.2f} projected PA"))

    try:
        l5 = _threshold_rate(result.get("logs"), threshold, 5)
        l10 = _threshold_rate(result.get("logs"), threshold, 10)
        vals = [x for x in (l5, l10) if x is not None]
        if not vals:
            rows.append(_sig("Recent form", "na", 12, "recent game logs unavailable"))
        else:
            avg = sum(vals) / len(vals)
            if max(vals) >= 0.60 and avg >= 0.50:
                state = "support"
            elif max(vals) <= 0.40 and avg <= 0.35:
                state = "concern"
            else:
                state = "neutral"
            reason = " • ".join(
                x for x in (
                    f"L5 {l5*100:.0f}%" if l5 is not None else "",
                    f"L10 {l10*100:.0f}%" if l10 is not None else "",
                ) if x
            )
            rows.append(_sig("Recent form", state, 12, reason))
    except Exception:
        rows.append(_sig("Recent form", "na", 12, "recent form unavailable"))

    try:
        prof = matchup_step._platoon_profile(result)
        pitch_rows = matchup_step._pitch_type_matchup(result)
        grade, _cls = matchup_step._matchup_grade(prof, pitch_rows)
        g = str(grade).upper()
        state = "support" if g == "FAVORABLE" else "concern" if g == "TOUGH" else "neutral" if g == "BALANCED" else "na"
        rows.append(_sig("Pitch/platoon", state, 10, g))
    except Exception:
        rows.append(_sig("Pitch/platoon", "na", 10, "matchup context unavailable"))

    env = result.get("environment_model") if isinstance(result.get("environment_model"), dict) else {}
    env_adj = _finite((env or {}).get("total_adjustment"), None)
    if env_adj is None:
        rows.append(_sig("Environment", "na", 6, "park/weather adjustment unavailable"))
    elif env_adj >= 0.015:
        rows.append(_sig("Environment", "support", 6, f"{env_adj*100:+.1f}% existing model environment"))
    elif env_adj <= -0.015:
        rows.append(_sig("Environment", "concern", 6, f"{env_adj*100:+.1f}% existing model environment"))
    else:
        rows.append(_sig("Environment", "neutral", 6, f"{env_adj*100:+.1f}% existing model environment"))

    try:
        opp_id = defense_step._safe_id(result.get("opponent_team_id"))
        season_ctx = defense_step._season_profile(opp_id)
        recent_ctx = defense_step._recent_team_prevention(opp_id, defense_step._selected_day())
        grade, _cls, hitter_ctx = defense_step._prevention_grade(season_ctx, recent_ctx)
        state = "support" if hitter_ctx == "SUPPORTS HITTER" else "concern" if hitter_ctx == "HURTS HITTER" else "neutral"
        if str(grade).upper() == "DATA LIMITED":
            state = "na"
        rows.append(_sig("Opponent defense", state, 8, str(grade)))
    except Exception:
        rows.append(_sig("Opponent defense", "na", 8, "run-prevention context unavailable"))

    try:
        relievers, mix, split, bullpen, quality, exposure, workload = bullpen_step._bullpen_context(result)
        grade, _cls, hitter_ctx = bullpen_step._grade(mix, split, bullpen, workload)
        state = "support" if hitter_ctx == "SUPPORTS HITTER" else "concern" if hitter_ctx == "HURTS HITTER" else "neutral"
        if str(grade).upper() == "DATA LIMITED":
            state = "na"
        rows.append(_sig("Bullpen path", state, 5, str(grade)))
    except Exception:
        rows.append(_sig("Bullpen path", "na", 5, "bullpen path unavailable"))

    try:
        starter_id = starter_step._safe_id(result.get("starter_id"))
        year = starter_step._season_year()
        season_ctx = starter_step._official_pitching_season(starter_id, year)
        recent_ctx = starter_step._official_recent_starts(starter_id, year, 5)
        exposure = starter_step._existing_exposure(result)
        hook, _hook_cls = starter_step._hook_label(season_ctx, recent_ctx)
        grade, _cls, hitter_ctx = starter_step._starter_grade(result, season_ctx, recent_ctx, exposure, hook)
        state = "support" if hitter_ctx == "SUPPORTS HITTER" else "concern" if hitter_ctx == "HURTS HITTER" else "neutral"
        if str(grade).upper() == "DATA LIMITED":
            state = "na"
        rows.append(_sig("Starter exposure", state, 5, str(grade)))
    except Exception:
        rows.append(_sig("Starter exposure", "na", 5, "starter workload unavailable"))

    # Step 11 intentionally has no historical tendency score yet. Preserve that
    # transparency rather than turning a confirmed name into false predictive evidence.
    try:
        officials = prior._officials_for_game(result.get("game_pk"))
        hp = (officials or {}).get("home_plate") or {}
        hp_name = str(hp.get("name") or "").strip()
        reason = f"{hp_name} confirmed; historical zone tendencies not scored" if hp_name else "historical zone tendencies not available"
    except Exception:
        reason = "umpire tendency data unavailable"
    rows.append(_sig("Umpire tendency", "na", 0, reason))

    return rows


def _evidence_score(rows):
    scorable = [r for r in rows if r.get("weight", 0) > 0]
    total_weight = sum(float(r.get("weight", 0)) for r in scorable) or 1.0
    available = [r for r in scorable if r.get("state") != "na"]
    available_weight = sum(float(r.get("weight", 0)) for r in available)
    if available_weight <= 0:
        return 0, 0.0
    value = {"support": 1.0, "neutral": 0.55, "concern": 0.10}
    alignment = sum(float(r["weight"]) * value.get(r.get("state"), 0.0) for r in available) / available_weight
    coverage = available_weight / total_weight
    score = round(100.0 * (0.75 * alignment + 0.25 * coverage))
    return int(max(0, min(100, score))), float(coverage)


def _opportunity_grade(result):
    pa = _finite(result.get("projected_pa"), None)
    confirmed = bool(result.get("lineup_confirmed"))
    spot = int(_finite(result.get("position"), 0) or 0)
    if pa is None:
        return "DATA LIMITED"
    if confirmed and pa >= 4.70 and 1 <= spot <= 5:
        return "ELITE"
    if confirmed and pa >= 4.35:
        return "STRONG"
    if pa >= 4.00:
        return "MEDIUM"
    return "LIMITED"


def _matchup_grade(rows):
    names = {"Pitch/platoon", "Environment", "Opponent defense", "Bullpen path", "Starter exposure"}
    context = [r for r in rows if r.get("name") in names and r.get("state") != "na"]
    if len(context) < 3:
        return "DATA LIMITED"
    supports = sum(1 for r in context if r.get("state") == "support")
    concerns = sum(1 for r in context if r.get("state") == "concern")
    net = supports - concerns
    if supports >= 4 and concerns == 0:
        return "ELITE"
    if net >= 2:
        return "STRONG"
    if net <= -2:
        return "HARD"
    return "MEDIUM"


def _pick_strength(result, threshold, evidence_score):
    sim = result.get("sim") or {}
    try:
        p = float(core._threshold_prob(sim, threshold))
    except Exception:
        p = _finite(sim.get(f"p{int(threshold)}"), 0.0) or 0.0
    conf = str(result.get("confidence") or "").upper()
    confirmed = bool(result.get("lineup_confirmed"))
    if p >= 0.78 and evidence_score >= 80 and conf == "HIGH" and confirmed:
        return "ELITE"
    if p >= 0.68 and evidence_score >= 65:
        return "STRONG"
    if p >= 0.60:
        return "MEDIUM"
    return "LOW"


def _summary_strip(result, threshold):
    rows = _signal_rows(result, threshold)
    score, coverage = _evidence_score(rows)
    pick = _pick_strength(result, threshold, score)
    matchup = _matchup_grade(rows)
    opportunity = _opportunity_grade(result)

    supports = [r["name"] for r in rows if r.get("state") == "support"]
    concerns = [r["name"] for r in rows if r.get("state") == "concern"]
    neutral = [r["name"] for r in rows if r.get("state") == "neutral"]
    unavailable = [r["name"] for r in rows if r.get("state") == "na"]

    def joined(items, empty="None"):
        return " • ".join(items) if items else empty

    badge_cls = {
        "ELITE": "elite", "STRONG": "strong", "MEDIUM": "medium",
        "HARD": "hard", "LIMITED": "limited", "LOW": "hard",
        "DATA LIMITED": "limited",
    }

    available_count = sum(1 for r in rows if r.get("weight", 0) > 0 and r.get("state") != "na")
    scorable_count = sum(1 for r in rows if r.get("weight", 0) > 0)

    return (
        '<div class="hrr115-final">'
        '<div class="hrr115-head"><span>FINAL • TOP-5 EVIDENCE SUMMARY</span><b>RANKING UNCHANGED</b></div>'
        '<div class="hrr115-badges">'
        f'<span class="{badge_cls.get(pick,"medium")}">PICK STRENGTH • {escape(pick)}</span>'
        f'<span class="{badge_cls.get(matchup,"medium")}">MATCHUP • {escape(matchup)}</span>'
        f'<span class="{badge_cls.get(opportunity,"medium")}">OPPORTUNITY • {escape(opportunity)}</span>'
        f'<span class="evidence">EVIDENCE • {score}/100</span>'
        '</div>'
        '<div class="hrr115-reasons">'
        f'<div class="support"><strong>✅ Supports:</strong> {escape(joined(supports))}</div>'
        f'<div class="concern"><strong>⚠️ Concerns:</strong> {escape(joined(concerns))}</div>'
        '</div>'
        f'<div class="hrr115-small"><strong>Neutral:</strong> {escape(joined(neutral))}</div>'
        f'<div class="hrr115-small"><strong>N/A / not scored:</strong> {escape(joined(unavailable))}</div>'
        f'<div class="hrr115-coverage">Evidence coverage {available_count}/{scorable_count} weighted signals • {coverage*100:.0f}% weighted coverage</div>'
        '<div class="hrr115-note">Audit synthesis only • Evidence Score measures agreement + data coverage across verified context layers. It does not change the joint-event probability, fair odds, confidence, candidate pool or Top-5 order.</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr115-final{margin:8px 0 6px;padding:10px;border:1px solid #6b5b22;background:linear-gradient(145deg,#17140a,#08131d);border-radius:13px;box-shadow:inset 3px 0 #d6ab18}
.hrr115-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.hrr115-head span{font-size:.44rem;letter-spacing:.09em;color:#ffd86d;font-weight:1000;text-transform:uppercase}.hrr115-head b{font-size:.40rem;color:#9caec0;letter-spacing:.06em}
.hrr115-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.hrr115-badges span{border:1px solid #465564;background:#111d29;color:#cbd8e5;border-radius:999px;padding:5px 8px;font-size:.47rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}.hrr115-badges .elite,.hrr115-badges .strong{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hrr115-badges .medium{border-color:#756019;background:#392f0c;color:#f4d66d}.hrr115-badges .hard{border-color:#7b3c39;background:#361615;color:#ff9f9a}.hrr115-badges .limited{border-color:#465564;background:#16202a;color:#a8b4c0}.hrr115-badges .evidence{border-color:#385b72;background:#0b1d29;color:#9edbff}
.hrr115-reasons{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.hrr115-reasons>div{border:1px solid #263d51;background:#081522;border-radius:10px;padding:8px 9px;font-size:.52rem;line-height:1.45;font-weight:800}.hrr115-reasons .support{border-color:#1c6449;background:#0a2a20;color:#8ce9bc}.hrr115-reasons .concern{border-color:#76581b;background:#30270d;color:#ffe087}.hrr115-reasons strong{color:#f7fbff}.hrr115-small{font-size:.46rem;color:#98a8b7;line-height:1.45;margin-top:5px}.hrr115-small strong{color:#cdd7e1}.hrr115-coverage{font-size:.45rem;color:#88c4df;font-weight:850;margin-top:6px}.hrr115-note{font-size:.42rem;color:#7e8994;line-height:1.4;margin-top:5px}.hrr115-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #6b5b22;background:#17140a;color:#ffe184;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
@media(max-width:700px){.hrr115-reasons{grid-template-columns:1fr}.hrr115-head{align-items:flex-start}.hrr115-badges span{font-size:.44rem}}
</style>
"""

if "hrr115-final" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v115(result, rank, threshold):
    """Verified Steps 1-11 first; final synthesis can never suppress the card."""
    html = _BASE_CARD(result, rank, threshold)
    try:
        strip = _summary_strip(result, threshold)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


base._card = _card_v115


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr115-step-badge">🏆 H+R+RBI V1.0.15 • Steps 1–11 + final evidence summary active</div>',
        unsafe_allow_html=True,
    )
    return prior.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
