"""MLB Matchup Explorer V5.9 — Cleanup Step 15 step-strength badges.

Presentation-only wrapper over certified Cleanup Step 14. Every captured V2 Step
1-12 card receives an H+R+RBI-style strength pill that says whether the existing
certified evidence leans toward the batter, the pitcher, or neutral. This layer
never changes probability, calibration, Monte Carlo, ranking, selector identity,
or Moneyline logic.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import streamlit as st

import mlb_matchup_hub_v53 as scouting
import mlb_matchup_hub_v54 as current

VERSION = "MLB Matchup Hub V5.9 • Cleanup Step 15"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_STEP14_PRESENTATION = "mlb_matchup_hub_v54"
FROZEN_STEP13_PRESENTATION = "mlb_matchup_hub_v53"

_STEP15_CSS = r"""
<style>
.mx55-edge{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:5px 9px;font-size:.49rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;white-space:nowrap;border:1px solid;box-shadow:inset 0 0 18px rgba(255,255,255,.02)}
.mx55-edge.batter{color:#85f0ae;border-color:#278e59;background:linear-gradient(135deg,#0d3c27,#0a241a)}
.mx55-edge.pitcher{color:#ff9999;border-color:#9f4141;background:linear-gradient(135deg,#421919,#281011)}
.mx55-edge.neutral{color:#f3d87d;border-color:#8a742c;background:linear-gradient(135deg,#3a310d,#211d0c)}
.mx55-edge.pending{color:#9db0c3;border-color:#46586b;background:#101a26}
.mx55-legend{border:1px solid #364c63;border-radius:13px;background:#0a1420;padding:8px 10px;margin:10px 0 12px;color:#8fa5ba;font-size:.53rem;line-height:1.45}
.mx55-legend b{color:#dfeaf3}.mx55-legend .bat{color:#85f0ae}.mx55-legend .pit{color:#ff9999}.mx55-legend .neu{color:#f3d87d}
@media(max-width:640px){
  .mx55-edge{font-size:.44rem;padding:4px 7px;letter-spacing:.035em}
  .mx55-legend{font-size:.48rem;padding:7px 8px;margin:8px 0 10px}
  .mxv2-top{gap:6px!important}
}
</style>
"""


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _step_number(source: str) -> int | None:
    match = re.search(r"mxv2-step(\d+)\b", str(source or ""), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract(source: str, pattern: str) -> float | None:
    match = re.search(pattern, str(source or ""), flags=re.IGNORECASE | re.DOTALL)
    return _float(match.group(1)) if match else None


def _edge(label: str, kind: str) -> dict[str, str]:
    return {"label": label, "kind": kind}


def _centered_score_edge(score: float | None, high_favors_batter: bool = True) -> dict[str, str]:
    """Turn an existing certified 0-100 context index into a display-only edge pill.

    The V2 context indices are centered at 50. Step 11 already treats starter and
    bullpen strength as adverse to the hitter, so those two are inverted here for
    human-readable batter-vs-pitcher direction. No probability is recalculated.
    """
    if score is None:
        return _edge("EDGE PENDING", "pending")
    batter_score = float(score) if high_favors_batter else 100.0 - float(score)
    if batter_score >= 75:
        return _edge("ELITE BATTER EDGE", "batter")
    if batter_score >= 65:
        return _edge("STRONG BATTER EDGE", "batter")
    if batter_score >= 55:
        return _edge("LEAN BATTER", "batter")
    if batter_score > 45:
        return _edge("NEUTRAL", "neutral")
    if batter_score > 35:
        return _edge("LEAN PITCHER", "pitcher")
    if batter_score > 25:
        return _edge("STRONG PITCHER EDGE", "pitcher")
    return _edge("ELITE PITCHER EDGE", "pitcher")


def _hitter_skill_edge(skill: float | None) -> dict[str, str]:
    """Display-only read of Step 2's already-rendered neutral hitter skill."""
    if skill is None:
        return _edge("EDGE PENDING", "pending")
    if skill >= .300:
        return _edge("ELITE BATTER EDGE", "batter")
    if skill >= .280:
        return _edge("STRONG BATTER EDGE", "batter")
    if skill >= .260:
        return _edge("LEAN BATTER", "batter")
    if skill >= .230:
        return _edge("NEUTRAL", "neutral")
    if skill >= .215:
        return _edge("LEAN PITCHER", "pitcher")
    if skill >= .195:
        return _edge("STRONG PITCHER EDGE", "pitcher")
    return _edge("ELITE PITCHER EDGE", "pitcher")


def _opportunity_edge(expected_pa: float | None) -> dict[str, str]:
    """More already-projected PA means more opportunity for the hitter to record a hit."""
    if expected_pa is None:
        return _edge("EDGE PENDING", "pending")
    if expected_pa >= 4.80:
        return _edge("ELITE BATTER EDGE", "batter")
    if expected_pa >= 4.50:
        return _edge("STRONG BATTER EDGE", "batter")
    if expected_pa >= 4.20:
        return _edge("LEAN BATTER", "batter")
    if expected_pa >= 3.80:
        return _edge("NEUTRAL", "neutral")
    if expected_pa >= 3.50:
        return _edge("LEAN PITCHER", "pitcher")
    if expected_pa >= 3.20:
        return _edge("STRONG PITCHER EDGE", "pitcher")
    return _edge("ELITE PITCHER EDGE", "pitcher")


def _probability_edge(probability_pct: float | None) -> dict[str, str]:
    """Human-readable strength tier for an already-computed 1+ hit probability."""
    if probability_pct is None:
        return _edge("EDGE PENDING", "pending")
    if probability_pct >= 75:
        return _edge("ELITE BATTER EDGE", "batter")
    if probability_pct >= 68:
        return _edge("STRONG BATTER EDGE", "batter")
    if probability_pct >= 60:
        return _edge("LEAN BATTER", "batter")
    if probability_pct >= 52:
        return _edge("NEUTRAL", "neutral")
    if probability_pct >= 44:
        return _edge("LEAN PITCHER", "pitcher")
    if probability_pct >= 36:
        return _edge("STRONG PITCHER EDGE", "pitcher")
    return _edge("ELITE PITCHER EDGE", "pitcher")


def _strength_for_step(step_html: str) -> dict[str, str]:
    """Read only values already printed by the certified V2 Step card."""
    step = _step_number(step_html)
    if step == 1:
        if "• READY" in step_html:
            return _edge("NEUTRAL • VERIFIED", "neutral")
        return _edge("NEUTRAL • PARTIAL", "neutral")
    if step == 2:
        skill = _extract(step_html, r"Neutral skill</span><b>([0-9.]+)")
        return _hitter_skill_edge(skill)
    if step == 3:
        score = _extract(step_html, r"Starter quality index</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=False)
    if step == 4:
        score = _extract(step_html, r"Platoon/BvP context index</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=True)
    if step == 5:
        score = _extract(step_html, r"Pitch-mix verdict</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=True)
    if step == 6:
        score = _extract(step_html, r"Batted-ball verdict</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=True)
    if step == 7:
        score = _extract(step_html, r"Environment verdict</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=True)
    if step == 8:
        score = _extract(step_html, r"Relief-path verdict</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=False)
    if step == 9:
        expected_pa = _extract(step_html, r"Expected PA</span><b>([0-9.]+)")
        return _opportunity_edge(expected_pa)
    if step == 10:
        score = _extract(step_html, r"Recent-form verdict</b>\s*•.*?•\s*([0-9.]+)/100")
        return _centered_score_edge(score, high_favors_batter=True)
    if step == 11:
        p1 = _extract(step_html, r"(?:RAW )?P\(1\+ HIT\)</span><b>([0-9.]+)%")
        return _probability_edge(p1)
    if step == 12:
        p1 = _extract(step_html, r"FINAL P\(1\+ HIT\)</span><b>([0-9.]+)%")
        return _probability_edge(p1)
    return _edge("EDGE PENDING", "pending")


def _decorate_step(step_html: str) -> str:
    """Add one strength pill beside the existing data/readiness pill."""
    edge = _strength_for_step(step_html)
    pill = f'<div class="mx55-edge {edge["kind"]}">{edge["label"]}</div>'
    match = re.search(r'(<div class="mxv2-badge">.*?</div>)', step_html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return step_html
    return step_html[: match.end()] + pill + step_html[match.end() :]


def _strength_scouting_wrapper(original: Callable[..., str]):
    def wrapped(context, step_html, raw, final, notices):
        decorated = [_decorate_step(source) for source in list(step_html or [])]
        output = original(context, decorated, raw, final, notices)
        legend = (
            '<div class="mx55-legend"><b>STEP STRENGTH</b> • '
            '<span class="bat">GREEN = BATTER EDGE</span> • '
            '<span class="pit">RED = PITCHER EDGE</span> • '
            '<span class="neu">GOLD = NEUTRAL</span> • '
            'direction is a presentation read of each Step’s existing certified evidence; it does not alter V2 probability.</div>'
        )
        marker = '<div class="mxv2-step '
        return output.replace(marker, legend + marker, 1) if marker in output else output
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Step 14 unchanged, decorating only its finished Steps 1-12 card HTML."""
    st.markdown(_STEP15_CSS, unsafe_allow_html=True)
    original_scouting = scouting._scouting_html
    scouting._scouting_html = _strength_scouting_wrapper(original_scouting)
    try:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        scouting._scouting_html = original_scouting


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP13_PRESENTATION",
    "FROZEN_STEP14_PRESENTATION",
    "VERSION",
    "_decorate_step",
    "_strength_for_step",
    "render_matchup_hub",
]
