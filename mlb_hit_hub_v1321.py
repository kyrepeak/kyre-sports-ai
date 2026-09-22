"""MLB 1+ Hit UI V13.21 — strict no-TOUGH visible-board hotfix.

Additive correctness wrapper over permanently frozen Hits Step 5 / UI V13.20.

The prior Step 4/5 gates used composite matchup/starter scores. The frozen Step-2
card badge uses a different certified rule (ERA <= 3.35 OR WHIP <= 1.12 OR
K% >= 27), which allowed a hitter to pass the composite gates while still
showing a red TOUGH starter badge.

V13.21 closes that display/selection mismatch:
- calls the full frozen Step-5 qualified ranker,
- removes any row whose opposing-starter profile maps to the certified Step-2
  TOUGH grade,
- never back-fills those rows,
- preserves all Hit Model V13 probability/simulation/candidate/calibration math.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import mlb_hit_hub_v1320 as prior
import mlb_hit_strict_no_tough_v1 as strict

active, core, visual = prior.active, prior.core, prior.visual
UI_VERSION = "V13.21"
_BASE_PICK_HTML = prior._pick_html_v1320
_FROZEN_STEP5_SUMMARY = prior._step5_board_summary


def _strict_strip(context: Mapping[str, Any] | None) -> str:
    c = dict(context or {})
    grade = str(c.get("certified_step2_starter_grade") or "DATA LIMITED")
    rank = c.get("strict_rank")
    cls = "good" if grade != "TOUGH" else "bad"
    return (
        '<div class="hit1321-strict">'
        '<span>STRICT MATCHUP GATE</span>'
        f'<b class="{cls}">STEP-2 STARTER GRADE • {escape(grade)}</b>'
        f'<em>Visible rank {escape(str(rank or "—"))} • TOUGH starter grades are excluded, never back-filled.</em>'
        '</div>'
    )


def _inject_strict(card: str, strip: str) -> str:
    text = str(card or "")
    if not strip or "hit1321-strict" in text:
        return text
    marker = '<div class="hit1320-starter">'
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx] + strip + text[idx:]
    marker = '<div class="hit1319-strip">'
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx] + strip + text[idx:]
    return text + strip


def _pick_html_v1321(result, rank):
    frozen = str(_BASE_PICK_HTML(result, rank) or "")
    ctx = dict((result or {}).get("_strict_no_tough") or {})
    return _inject_strict(frozen, _strict_strip(ctx))


active._pick_html = _pick_html_v1321


def _strict_rank_adapter(results, profile_lookup, limit=5):
    return strict.strict_rank_results(results, profile_lookup, limit=limit)


def _strict_board_summary(meta: Mapping[str, Any]) -> str:
    m = dict(meta or {})
    excluded = int(m.get("strict_tough_excluded") or 0)
    visible = int(m.get("strict_visible_count") or m.get("visible_count") or 0)
    base = _FROZEN_STEP5_SUMMARY(m)
    return (
        base
        + '<div class="hit1321-board">'
        '<span>STRICT NO-TOUGH HOTFIX</span>'
        f'<b>{visible} visible • {excluded} Step-2 TOUGH starter pick(s) removed</b>'
        '<p>The visible board now obeys the same certified starter-grade thresholds displayed on each card. '
        'ERA ≤ 3.35, WHIP ≤ 1.12, or K% ≥ 27% is a TOUGH starter grade and is excluded. '
        'No TOUGH backfill.</p>'
        '</div>'
    )


_CSS = r"""
<style>
.hit1321-strict{margin:8px 0;border:1px solid #24674b;border-radius:10px;background:linear-gradient(145deg,#082219,#071721);padding:7px 8px}
.hit1321-strict span{display:block;color:#70e6ad;font-size:.36rem;font-weight:950;letter-spacing:.08em}.hit1321-strict b{display:block;font-size:.55rem;margin-top:2px}.hit1321-strict b.good{color:#87f2bd}.hit1321-strict b.bad{color:#ff9e99}.hit1321-strict em{display:block;color:#789b8c;font-size:.34rem;font-style:normal;margin-top:3px}
.hit1321-board{margin:7px 0 10px;border:1px solid #26664b;border-radius:11px;background:#081c15;padding:8px}.hit1321-board span{display:block;color:#70e6ad;font-size:.39rem;font-weight:950;letter-spacing:.07em}.hit1321-board b{display:block;color:#effff7;font-size:.62rem;margin-top:2px}.hit1321-board p{margin:5px 0 0;color:#7e9c8f;font-size:.36rem;line-height:1.42}
</style>
"""
if "hit1321-strict" not in core.HIT_CSS:
    core.HIT_CSS += _CSS


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🛡️ Hit UI V13.21 • STRICT no-TOUGH visible gate ACTIVE • "
        "certified Step-2 starter-grade alignment • no TOUGH backfill • "
        "Hit Model V13 probability unchanged"
    )

    old_rank = prior.starter.rank_results
    old_summary = prior._step5_board_summary
    prior.starter.rank_results = _strict_rank_adapter
    prior._step5_board_summary = _strict_board_summary
    try:
        return prior.render_hit_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior.starter.rank_results = old_rank
        prior._step5_board_summary = old_summary


__all__ = [
    "UI_VERSION",
    "_BASE_PICK_HTML",
    "_inject_strict",
    "_pick_html_v1321",
    "_strict_board_summary",
    "_strict_rank_adapter",
    "_strict_strip",
    "render_hit_hub",
]
