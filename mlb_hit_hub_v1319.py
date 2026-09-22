"""MLB 1+ Hit UI V13.19 — Step 4 favorable matchup gate + hit-spot ranking.

Additive post-model selection layer over permanently frozen Hits Steps 1-3.

The frozen V13 pipeline still:
- builds the same candidate pool,
- runs the same prescreen,
- deep-simulates the same finalists,
- produces the same probabilities,
- writes the same clean calibration history.

Step 4 changes ONLY the visible Top-5 board after deep simulations already exist.
Clearly tough model-relative matchups are excluded. Qualified hitters must also
clear minimum 1+ Hit probability and projected-AB gates. If fewer than five
qualify, fewer than five are shown rather than back-filling a tough matchup.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_hit_hub_v1318 as prior
import mlb_hit_hub_v133 as scanner
import mlb_hit_favorable_ranker_v1 as ranker

active, core, visual = prior.active, prior.core, prior.visual
UI_VERSION = "V13.19"
_BASE_PICK_HTML = prior._pick_html_v1318
_FROZEN_SCANNER = scanner._render_top_scanner_v133


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _edge_text(value: Any) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x * 100:+.1f} pts"


def _score_class(context: Mapping[str, Any]) -> str:
    label = str(context.get("matchup_label") or "").upper()
    score = _f(context.get("hit_spot_score")) or 0.0
    if label == "TOUGH":
        return "bad"
    if label == "FAVORABLE" and score >= 75:
        return "elite"
    if label == "FAVORABLE":
        return "good"
    return "neutral"


def _spot_strip(context: Mapping[str, Any] | None) -> str:
    c = dict(context or {})
    score = _f(c.get("hit_spot_score"))
    score_text = "N/A" if score is None else f"{score:.1f}/100"
    label = str(c.get("matchup_label") or "DATA LIMITED")
    rank = c.get("qualified_rank")
    original = c.get("original_deep_rank")
    gate = "QUALIFIED" if bool(c.get("qualified")) else "NOT QUALIFIED"
    cls = _score_class(c)
    return (
        '<div class="hit1319-strip">'
        '<div class="hit1319-left">'
        '<span class="hit1319-kicker">STEP 4 • FAVORABLE HIT-SPOT GATE</span>'
        f'<b class="{cls}">{escape(gate)} • {escape(label)}</b>'
        '</div>'
        '<div class="hit1319-metrics">'
        f'<span><b>{escape(score_text)}</b>Hit Spot</span>'
        f'<span><b>{escape(_edge_text(c.get("matchup_edge")))}</b>Matchup edge</span>'
        f'<span><b>{escape(str(rank or "—"))}</b>Qualified rank</span>'
        f'<span><b>{escape(str(original or "—"))}</b>Raw deep rank</span>'
        '</div>'
        '</div>'
    )


def _inject_spot(card: str, strip: str) -> str:
    text = str(card or "")
    if not strip or "hit1319-strip" in text:
        return text
    marker = '<div class="hit1318-profile">'
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx] + strip + text[idx:]
    marker = '<details class="hit1317-deep">'
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx] + strip + text[idx:]
    close = text.rfind("</div>")
    return text[:close] + strip + text[close:] if close >= 0 else text + strip


def _pick_html_v1319(result, rank):
    frozen = str(_BASE_PICK_HTML(result, rank) or "")
    context = dict((result or {}).get("_step4") or ranker.hit_spot_score(dict(result or {})))
    context.setdefault("qualified_rank", rank if context.get("qualified") else None)
    return _inject_spot(frozen, _spot_strip(context))


active._pick_html = _pick_html_v1319


def _board_summary(meta: Mapping[str, Any]) -> str:
    m = dict(meta or {})
    visible = int(m.get("visible_count") or 0)
    evaluated = int(m.get("finalists_evaluated") or 0)
    tough = int(m.get("tough_excluded") or 0)
    low_p = int(m.get("probability_excluded") or 0)
    low_ab = int(m.get("opportunity_excluded") or 0)
    state = "FULL QUALIFIED TOP 5" if visible >= 5 else f"ONLY {visible} QUALIFIED"
    return (
        '<div class="hit1319-board">'
        '<div><span>STEP 4 • SMART FAVORABLE SELECTION</span>'
        f'<b>{escape(state)}</b></div>'
        '<div class="hit1319-boardstats">'
        f'<span><b>{visible}/5</b>Shown</span>'
        f'<span><b>{evaluated}</b>Deep finalists</span>'
        f'<span><b>{tough}</b>Tough excluded</span>'
        f'<span><b>{low_p}</b>Below 60%</span>'
        f'<span><b>{low_ab}</b>Low opportunity</span>'
        '</div>'
        '<p>Qualified board only: 1+ Hit ≥ 60%, projected AB ≥ 3.8 and matchup not classified TOUGH. '
        'No tough-matchup backfill. The underlying V13 probabilities, simulations and frozen calibration-history ranking are unchanged.</p>'
        '</div>'
    )


def _render_top_scanner_step4(games_df):
    original_markdown = scanner.st.markdown

    def filtered_markdown(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")

        if "🔥 Strongest 1+ Hit Probabilities" in text:
            replacement = (
                '<div class="hit-panel-title"><b>🔥 Best Qualified 1+ Hit Spots</b>'
                '<span>favorable/neutral matchup gate → Hit Spot Score</span></div>'
            )
            return original_markdown(replacement, *args, **kwargs)

        if '<div class="hit-top-grid">' in text:
            results = list(st.session_state.get("hit133_results") or [])
            selected, meta = ranker.rank_favorable_results(results, limit=5)
            st.session_state["hit_step4_selected"] = selected
            st.session_state["hit_step4_meta"] = meta

            if selected:
                cards = "".join(scanner._pick_html(row, i) for i, row in enumerate(selected, 1))
                replacement = _board_summary(meta) + f'<div class="hit-top-grid">{cards}</div>'
            else:
                replacement = (
                    _board_summary(meta)
                    + '<div class="hit-empty">No deep finalist cleared the Step 4 favorable-hit gate. '
                    'The app will not force a tough matchup into the board just to fill five spots.</div>'
                )
            return original_markdown(replacement, *args, **kwargs)

        return original_markdown(body, *args, **kwargs)

    scanner.st.markdown = filtered_markdown
    try:
        return _FROZEN_SCANNER(games_df)
    finally:
        scanner.st.markdown = original_markdown


_CSS = r"""
<style>
.hit1319-strip{margin:8px 0;border:1px solid rgba(83,236,166,.26);border-radius:10px;background:linear-gradient(145deg,#08241c,#081722);padding:7px 8px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center}
.hit1319-kicker{display:block;color:#77e7b0;font-size:.38rem;font-weight:950;letter-spacing:.07em}.hit1319-left b{display:block;margin-top:2px;color:#cad9d2;font-size:.58rem}.hit1319-left b.elite{color:#7dffc0}.hit1319-left b.good{color:#8eeab8}.hit1319-left b.bad{color:#ff9d99}.hit1319-metrics{display:grid;grid-template-columns:repeat(4,auto);gap:5px}.hit1319-metrics span{border:1px solid #24473a;background:#0a1e18;border-radius:7px;padding:4px 5px;text-align:center;color:#668879;font-size:.31rem;text-transform:uppercase}.hit1319-metrics b{display:block;color:#e9fff5;font-size:.45rem;text-transform:none}
.hit1319-board{margin:8px 0 10px;border:1px solid #276a51;border-radius:13px;background:linear-gradient(145deg,#09251c,#07141e);padding:10px}.hit1319-board>div:first-child span{display:block;color:#72e4ae;font-size:.43rem;font-weight:950;letter-spacing:.08em}.hit1319-board>div:first-child b{display:block;color:#f1fff8;font-size:.76rem;margin-top:2px}.hit1319-boardstats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;margin-top:7px}.hit1319-boardstats span{border:1px solid #214538;background:#081b15;border-radius:8px;padding:5px;text-align:center;color:#6e9584;font-size:.33rem;text-transform:uppercase}.hit1319-boardstats b{display:block;color:#eafff5;font-size:.52rem}.hit1319-board p{margin:7px 0 0;color:#78998b;font-size:.40rem;line-height:1.45}
@media(max-width:700px){.hit1319-strip{grid-template-columns:1fr}.hit1319-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.hit1319-boardstats{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""
if "hit1319-strip" not in core.HIT_CSS:
    core.HIT_CSS += _CSS


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "🎯 Hit UI V13.19 • Step 4 favorable matchup gate + Hit Spot ranking ACTIVE • "
        "tough matchups excluded from visible board • Hit Model V13 probability unchanged"
    )
    original_scanner = scanner._render_top_scanner_v133
    scanner._render_top_scanner_v133 = _render_top_scanner_step4
    try:
        return prior.render_hit_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        scanner._render_top_scanner_v133 = original_scanner


__all__ = [
    "UI_VERSION",
    "_BASE_PICK_HTML",
    "_board_summary",
    "_inject_spot",
    "_pick_html_v1319",
    "_render_top_scanner_step4",
    "render_hit_hub",
]
