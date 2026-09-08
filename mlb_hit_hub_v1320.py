"""MLB 1+ Hit UI V13.20 — Step 5 opposing-starter vulnerability.

Additive post-model selection layer over permanently frozen Hits Steps 1-4.

Step 5 deepens the "favorable player" filter by evaluating the opposing starter
with official MLB + Baseball Savant starter-quality context (ERA/WHIP/H9/K-BB,
xERA/xBA allowed, FIP, recent form and TTO when available).

The frozen Step 4 qualified board is preserved as the base. Step 5:
- hard-excludes only ELITE / VERY TOUGH starters when profile data is sufficiently complete,
- reranks remaining qualifiers with 72% frozen Step-4 Hit Spot Score + 28%
  starter-vulnerability score,
- never changes Hit Model V13 probability, Monte Carlo, candidate generation,
  deep finalist simulations or calibration/history.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_hit_hub_v1319 as prior
import mlb_hit_hub_v133 as scanner
import mlb_hit_starter_vulnerability_v1 as starter

active, core, visual = prior.active, prior.core, prior.visual
UI_VERSION = "V13.20"
_BASE_PICK_HTML = prior._pick_html_v1319
_FROZEN_STEP4_SUMMARY = prior._board_summary
_FROZEN_STEP4_RANKER = prior.ranker.rank_favorable_results


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _fmt(value: Any, digits: int = 2) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x:.{digits}f}"


def _pct(value: Any, digits: int = 1) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x * 100:.{digits}f}%"


def _starter_strip(context: Mapping[str, Any] | None) -> str:
    c = dict(context or {})
    profile = dict(c.get("starter_profile") or {})
    label = str(c.get("starter_vulnerability_label") or "DATA LIMITED")
    cls = "good" if "HITTER FRIENDLY" in label else "bad" if "TOUGH" in label else "neutral"
    gate = "EXCLUDED" if c.get("hard_tough_starter") else "STARTER CLEARED"
    gate_cls = "bad" if c.get("hard_tough_starter") else "good"

    recent5 = dict(profile.get("recent5") or {})
    return (
        '<div class="hit1320-starter">'
        '<div class="hit1320-top">'
        '<div><span class="hit1320-kicker">STEP 5 • OPPOSING STARTER VULNERABILITY</span>'
        f'<b class="{cls}">{escape(label)}</b></div>'
        f'<span class="hit1320-gate {gate_cls}">{escape(gate)}</span>'
        '</div>'
        '<div class="hit1320-grid">'
        f'<span><b>{escape(_fmt(c.get("starter_vulnerability_score"),1))}/100</b>Vulnerability</span>'
        f'<span><b>{escape(_fmt(profile.get("era")))}</b>ERA</span>'
        f'<span><b>{escape(_fmt(profile.get("xera")))}</b>xERA</span>'
        f'<span><b>{escape(_fmt(profile.get("fip")))}</b>FIP</span>'
        f'<span><b>{escape(_fmt(profile.get("whip")))}</b>WHIP</span>'
        f'<span><b>{escape(_fmt(profile.get("h9")))}</b>H/9</span>'
        f'<span><b>{escape(_pct(profile.get("xba_allowed")))}</b>xBA allowed</span>'
        f'<span><b>{escape(_fmt(recent5.get("era")))}</b>L5 ERA</span>'
        '</div>'
        '<div class="hit1320-foot">'
        f'<span>Starter strength {escape(_fmt(c.get("starter_strength_score"),1))}/100</span>'
        f'<span>Profile data {escape(_fmt(c.get("starter_profile_score"),0))}/100</span>'
        f'<span>Step 5 score {escape(_fmt(c.get("step5_score"),1))}/100</span>'
        f'<span>TTO: {escape(str(profile.get("third_time_label") or "PENDING"))}</span>'
        '</div>'
        '<p>Hard gate activates only with sufficient starter-profile completeness and strength coverage. '
        'Very tough/elite starters are not back-filled into the visible board. '
        '<b>Probability / simulation impact: NONE.</b></p>'
        '</div>'
    )


def _inject_starter(card: str, strip: str) -> str:
    text = str(card or "")
    if not strip or "hit1320-starter" in text:
        return text
    marker = '<div class="hit1319-strip">'
    idx = text.find(marker)
    if idx >= 0:
        # Put Step 5 immediately after the frozen Step 4 strip.
        end = text.find("</div>", idx)
        if end >= 0:
            end += len("</div>")
            return text[:end] + strip + text[end:]
    marker = '<div class="hit1318-profile">'
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx] + strip + text[idx:]
    return text + strip


def _pick_html_v1320(result, rank):
    frozen = str(_BASE_PICK_HTML(result, rank) or "")
    ctx = dict((result or {}).get("_step5") or {})
    return _inject_starter(frozen, _starter_strip(ctx))


active._pick_html = _pick_html_v1320


def _step5_rank_adapter(results, limit=5):
    return starter.rank_results(results, starter.build_starter_profile, limit=limit)


def _step5_board_summary(meta: Mapping[str, Any]) -> str:
    m = dict(meta or {})
    visible = int(m.get("visible_count") or 0)
    hard = int(m.get("hard_tough_starters_excluded") or 0)
    q4 = int(m.get("step4_qualified_count") or 0)
    final_state = "FULL QUALIFIED TOP 5" if visible >= 5 else f"ONLY {visible} QUALIFIED"
    return (
        _FROZEN_STEP4_SUMMARY(m)
        + '<div class="hit1320-board">'
        '<span>STEP 5 • STARTER QUALITY CHECK</span>'
        f'<b>{escape(final_state)} • {hard} elite/very-tough starter exclusion(s)</b>'
        f'<p>{q4} hitter(s) cleared the frozen Step 4 gate before starter-quality refinement. '
        'Final order blends 72% frozen Hit Spot Score with 28% starter vulnerability. '
        'No elite/very-tough starter backfill.</p>'
        '</div>'
    )


_CSS = r"""
<style>
.hit1320-starter{margin:8px 0;border:1px solid #38506c;border-radius:10px;background:linear-gradient(145deg,#0a1725,#0a1f28);padding:8px}
.hit1320-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.hit1320-kicker{display:block;color:#72c7ff;font-size:.37rem;font-weight:950;letter-spacing:.07em}.hit1320-top b{display:block;color:#dce9f5;font-size:.57rem;margin-top:2px}.hit1320-top b.good{color:#7ef0b5}.hit1320-top b.bad{color:#ff9c98}
.hit1320-gate{border-radius:999px;padding:4px 6px;font-size:.36rem;font-weight:950;border:1px solid #425567}.hit1320-gate.good{color:#7ef0b5;border-color:#276247;background:#0b2e22}.hit1320-gate.bad{color:#ff9c98;border-color:#713d3b;background:#311716}
.hit1320-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.hit1320-grid span{border:1px solid #253c4e;background:#081622;border-radius:7px;padding:5px;text-align:center;color:#6f8496;font-size:.31rem;text-transform:uppercase}.hit1320-grid b{display:block;color:#eef6fc;font-size:.46rem;text-transform:none}
.hit1320-foot{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}.hit1320-foot span{border:1px solid #2a4051;border-radius:999px;padding:4px 6px;background:#0b1823;color:#95a9b8;font-size:.34rem;font-weight:800}.hit1320-starter p{margin:6px 0 0;color:#748896;font-size:.36rem;line-height:1.45}.hit1320-starter p b{color:#9edcff}
.hit1320-board{margin:7px 0 10px;border:1px solid #355878;border-radius:11px;background:#091723;padding:8px}.hit1320-board span{display:block;color:#74c9ff;font-size:.39rem;font-weight:950;letter-spacing:.07em}.hit1320-board b{display:block;color:#eef8ff;font-size:.62rem;margin-top:2px}.hit1320-board p{margin:5px 0 0;color:#7891a4;font-size:.36rem;line-height:1.4}
@media(max-width:700px){.hit1320-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""
if "hit1320-starter" not in core.HIT_CSS:
    core.HIT_CSS += _CSS


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🧱 Hit UI V13.20 • Step 5 starter vulnerability ACTIVE • "
        "elite/very-tough starters filtered when data is sufficient • "
        "Hit Model V13 probability unchanged"
    )

    old_ranker = prior.ranker.rank_favorable_results
    old_summary = prior._board_summary
    prior.ranker.rank_favorable_results = _step5_rank_adapter
    prior._board_summary = _step5_board_summary
    try:
        return prior.render_hit_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior.ranker.rank_favorable_results = old_ranker
        prior._board_summary = old_summary


__all__ = [
    "UI_VERSION",
    "_BASE_PICK_HTML",
    "_inject_starter",
    "_pick_html_v1320",
    "_starter_strip",
    "_step5_board_summary",
    "_step5_rank_adapter",
    "render_hit_hub",
]
