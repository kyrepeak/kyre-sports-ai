"""NFL Rushing Yards V2 — Step 3 market-blind projection page.

Additive presentation wrapper over frozen Rushing Yards V1. V1 remains the
certified owner of Steps 1-2. V2 advances only Step 3 by consuming the already
validated V1 context object through ``nfl_rushing_yards_projection_v1``.

Live sportsbook lines, probability, Monte Carlo, fair-line, EV, ranking,
recommendation, grading, stake sizing and wager actions remain OFF. Passing
Yards is not imported or modified.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_rushing_yards_hub_v1 as prior
import nfl_rushing_yards_projection_v1 as projection

MODEL_VERSION = "NFL RUSHING YARDS V2 • STEP 3 MARKET-BLIND BASELINE PROJECTION"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v1"

_ORIGINAL_CONTEXT_BOARD = prior._render_context_board
_ORIGINAL_MARKDOWN = st.markdown

_STEP3_CSS = r'''
<style>
.krush-fill{width:75%!important}
.krush-proj-banner{border:1px solid #426f51;border-radius:14px;background:#102019;padding:10px 12px;margin:10px 0;color:#a8ddb8;font-size:.63rem;line-height:1.5}
.krush-proj-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:8px 0 12px}
.krush-proj{border:1px solid #315540;background:#0b1812;border-radius:15px;padding:11px;min-width:0}
.krush-proj-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.krush-proj-name{color:#f2f8f4;font-size:.78rem;font-weight:950}.krush-proj-sub{color:#70877a;font-size:.52rem;margin-top:3px;line-height:1.4}
.krush-proj-grade{font-size:.50rem;font-weight:950;border:1px solid #496352;border-radius:999px;padding:4px 7px;color:#c0d0c5;white-space:nowrap}
.krush-proj-grade.green{color:#8be2ac;border-color:#3f7651;background:#10271a}.krush-proj-grade.watch{color:#efca74;border-color:#7a683c;background:#2a2413}
.krush-proj-hero{display:grid;grid-template-columns:1.2fr repeat(2,minmax(0,1fr));gap:6px;margin-top:9px}
.krush-proj-metric{border-top:1px solid #23402e;padding-top:7px}.krush-proj-metric b{display:block;color:#f2f8f4;font-size:.92rem}.krush-proj-metric span{display:block;color:#657b6c;font-size:.46rem;text-transform:uppercase;font-weight:900;margin-top:2px}
.krush-proj-explain{margin-top:8px;padding-top:7px;border-top:1px solid #1e3527;color:#789081;font-size:.51rem;line-height:1.55}
.krush-withheld{border-left:3px solid #846f42;background:#211d13;border-radius:8px;padding:8px 10px;color:#c9b985;font-size:.56rem;line-height:1.45;margin:6px 0}
@media(max-width:760px){.krush-proj-grid{grid-template-columns:1fr}.krush-proj-hero{grid-template-columns:1fr 1fr}.krush-proj-hero>div:first-child{grid-column:1/-1}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    rendered = f"{number:.{digits}f}"
    return rendered.rstrip("0").rstrip(".") if digits > 0 else rendered


def _advance_step3_copy(body: Any) -> Any:
    """Advance only the frozen V1 presentation copy while V2 owns the render."""
    if not isinstance(body, str):
        return body
    replacements = (
        (
            "Step 2 now adds verified current-roster rushing workload and opponent run-front context from the Kyre Sports API. Projection and market math remain intentionally OFF until later certified steps.",
            "Step 3 adds a transparent market-blind rushing-yards baseline on top of verified current-roster workload and opponent run-front context. Live market, probability, EV, grading and staking remain locked for Step 4.",
        ),
        (
            '<span class="krush-chip lock">🔒 MODEL OFF</span>',
            '<span class="krush-chip">✅ PROJECTION ENGINE</span>',
        ),
        (
            '<div class="krush-tool"><div class="icon">⚡</div><b>Explosiveness</b><span>Advanced efficiency and big-play profile come next.</span></div>',
            '<div class="krush-tool live"><div class="icon">🧮</div><b>Baseline Projection ✅</b><span>Verified workload × blended player/opponent rushing efficiency.</span></div>',
        ),
        ("2 OF 4 • DATA LIVE", "3 OF 4 • PROJECTION LIVE"),
        (
            '<span class="krush-stage">3 • PROJECTION ENGINE</span>',
            '<span class="krush-stage on">3 • PROJECTION ENGINE ✅</span>',
        ),
        (
            "Projection and sportsbook logic remain OFF.",
            "The production API remains facts-only; Step 3 projection is computed separately below. Sportsbook logic remains OFF.",
        ),
        (
            "🧊 <b>Frozen-line guard:</b> Step 2 adds read-only exact-ID player and matchup context only. It does not alter the certified Passing Yards chain, projection math, probability logic, FanDuel transport, grading, freshness rules, or any CFB surface. Rushing Yards model/market logic remains OFF and sportsbook projection influence remains 0.0%.",
            "🧊 <b>Frozen-line guard:</b> Step 3 adds only the isolated Rushing Yards market-blind baseline projection. The certified Passing Yards chain, FanDuel transport, probability, live market, EV, grading, ranking, recommendation, staking and every CFB surface remain untouched. Sportsbook projection influence remains 0.0%.",
        ),
    )
    out = body
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def _markdown_v2(body: Any, *args: Any, **kwargs: Any):
    return _ORIGINAL_MARKDOWN(_advance_step3_copy(body), *args, **kwargs)


def _projection_card(row: dict[str, Any], team_name: str) -> str:
    grade = _safe(row.get("coverage_grade"), "CHECK").upper()
    css = grade.lower() if grade.lower() in {"green", "watch"} else ""
    components = row.get("efficiency_components") or []
    component_text = " • ".join(
        f"{_safe(item.get('key'))}: {_num(item.get('value'), 2)} ({_num(float(item.get('normalized_weight', 0)) * 100, 0)}%)"
        for item in components
    ) or "verified efficiency components unavailable"
    return f'''
    <article class="krush-proj">
      <div class="krush-proj-top">
        <div>
          <div class="krush-proj-name">{escape(_safe(row.get('player_name'), 'Unknown rusher'))} • Baseline Projection</div>
          <div class="krush-proj-sub">{escape(team_name)} • ESPN athlete {escape(_safe(row.get('official_athlete_id')))} • opponent ESPN team {escape(_safe(row.get('opponent_official_team_id')))}</div>
        </div>
        <span class="krush-proj-grade {css}">{escape(grade)}</span>
      </div>
      <div class="krush-proj-hero">
        <div class="krush-proj-metric"><b>{escape(_num(row.get('projection_yards'), 1))}</b><span>Baseline Rush Yards</span></div>
        <div class="krush-proj-metric"><b>{escape(_num(row.get('expected_carries'), 1))}</b><span>Expected Carries</span></div>
        <div class="krush-proj-metric"><b>{escape(_num(row.get('expected_yards_per_carry'), 2))}</b><span>Expected YPC</span></div>
      </div>
      <div class="krush-proj-explain">
        <b>{escape(_safe(row.get('formula'), 'expected carries × expected YPC'))}</b><br>
        {escape(_safe(row.get('workload_source'), 'verified workload'))} • {escape(_safe(row.get('coverage_basis'), 'coverage check'))}<br>
        Efficiency blend: {escape(component_text)}<br>
        Team run-front attempts/yards/TD context remains visible but is not converted into unsupported player-share adjustments.
      </div>
    </article>
    '''


def _render_step3_projection(context: dict[str, Any], event_id: str) -> None:
    _ORIGINAL_MARKDOWN(
        '<div class="krush-section"><h3>🧮 Step 3 • Market-Blind Baseline Projection</h3><span>WORKLOAD × EFFICIENCY • SPORTSBOOK 0%</span></div>',
        unsafe_allow_html=True,
    )
    _ORIGINAL_MARKDOWN(
        '<div class="krush-proj-banner">✅ Step 3 uses only verified football evidence from Step 2. Expected carries stay anchored to the player workload baseline. Expected YPC blends player efficiency with opponent YPC allowed. No sportsbook line, probability, EV, grade, rank, recommendation or stake enters this number.</div>',
        unsafe_allow_html=True,
    )

    result = projection.build_event_projections(context)
    if not result.get("ready"):
        st.warning(
            "Step 3 projection failed closed. No rushing-yards number was guessed. "
            f"Reason: {result.get('reason') or 'verified projection evidence incomplete'}"
        )
        return

    team_names = {
        _safe(team.get("official_team_id"), ""): _safe(team.get("team_name"), _safe(team.get("team_abbreviation"), "NFL Team"))
        for team in (context.get("teams") or [])
        if isinstance(team, dict)
    }
    cards = "".join(
        _projection_card(row, team_names.get(_safe(row.get("official_team_id"), ""), "NFL Team"))
        for row in (result.get("projections") or [])
    )
    _ORIGINAL_MARKDOWN(f'<div class="krush-proj-grid">{cards}</div>', unsafe_allow_html=True)

    withheld = result.get("withheld") or []
    if withheld:
        with st.expander(f"Why {len(withheld)} verified rusher(s) have no Step 3 projection"):
            for row in withheld:
                _ORIGINAL_MARKDOWN(
                    '<div class="krush-withheld">'
                    f'<b>{escape(_safe(row.get("player_name"), "Unknown rusher"))}</b> • ESPN athlete {escape(_safe(row.get("official_athlete_id")))}<br>'
                    f'{escape(_safe(row.get("reason"), "projection evidence incomplete"))}'
                    '</div>',
                    unsafe_allow_html=True,
                )

    st.caption(
        f"✅ {result.get('projection_count', 0)} market-blind projection(s) • ESPN event {event_id} • "
        f"schema {projection.SCHEMA_VERSION} • sportsbook influence 0.0% • Monte Carlo OFF • market/EV/grading/staking OFF"
    )


def _render_context_board_v2(games) -> None:
    """Render frozen Step 2 first, then add Step 3 only from its validated context."""
    _ORIGINAL_CONTEXT_BOARD(games)
    event_id = _safe(st.session_state.get("nfl_rushing_yards_step2_event"), "")
    if not event_id.isdigit():
        return
    context = prior._load_rushing_context(event_id)
    if context.get("ready") is not True or context.get("data_available") is not True:
        return
    _render_step3_projection(context, event_id)


def render_nfl_rushing_yards_hub() -> None:
    """Render frozen Steps 1-2 plus isolated Step 3 projection."""
    _ORIGINAL_MARKDOWN(_STEP3_CSS, unsafe_allow_html=True)
    original_context_board = prior._render_context_board
    original_markdown = prior.st.markdown
    prior._render_context_board = _render_context_board_v2
    prior.st.markdown = _markdown_v2
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._render_context_board = original_context_board
        prior.st.markdown = original_markdown


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V2 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_render_context_board_v2",
    "_render_step3_projection",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
