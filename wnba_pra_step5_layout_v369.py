"""WNBA PRA V3.6.9 — compact Step-5 Top-5 presentation layout.

Presentation-only wrapper over V3.6.8. Keeps the exact V2.8 Step-5 candidate
payload, eligibility gate, PRA sorting, identity, cached defense context, cached
current-season matchup history and existing-field projection path. This version
only compacts the HTML layout so the five cards are easier to scan on tablet and
mobile.

No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking, selection, data-provider or cache logic is
changed. Repeated source/guardrail prose is moved from every card to one board
footer; no displayed metric is removed.
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st

import wnba_pra_step5_path_v368 as prior

history_layer = prior.history_layer
defense_layer = prior.defense_layer
cards = prior.cards
v28 = prior.v28

MODEL_VERSION = "PRA V3.6.9 • STEP-5 COMPACT CARD LAYOUT • MODEL PRESERVED"

_LAYOUT_CSS = r"""
<style>
/* V3.6.9 affects only the Step-5 Top-5 presentation container. */
.w369-board .w28-topgrid{gap:10px!important;align-items:start}
.w369-card{border:1px solid #304663;background:#091624;border-radius:14px;padding:10px;min-width:0}
.w369-card.first{border-color:#ff72ac;box-shadow:inset 3px 0 0 #ff72ac}
.w369-eyebrow{display:flex;align-items:center;justify-content:space-between;gap:8px;color:#63ddff;font-size:.43rem;font-weight:950;letter-spacing:.03em}
.w369-layerchips{display:flex;gap:3px;flex-wrap:wrap;justify-content:flex-end}
.w369-chip{border:1px solid #29465d;background:#0a1926;border-radius:999px;padding:2px 5px;color:#86a5b9;font-size:.31rem;font-weight:900;white-space:nowrap}
.w369-hero{display:flex;align-items:center;gap:9px;margin-top:6px;min-width:0}
.w369-hero-main{min-width:0;flex:1}
.w369-match{display:flex;align-items:center;gap:5px;margin-top:4px;min-width:0}
.w369-meta{color:#7f95ac;font-size:.43rem;margin-top:5px;line-height:1.25}
.w369-scoreline{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-top:6px}
.w369-pra{font-size:1.25rem;color:#79efba;font-weight:1000;line-height:1}
.w369-pra span{font-size:.36rem;color:#7489a4;text-transform:uppercase;margin-left:3px}
.w369-split{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:7px}
.w369-split div{border:1px solid #233850;background:#081421;border-radius:7px;padding:5px 6px}
.w369-split span{display:block;color:#6c839e;font-size:.31rem;text-transform:uppercase;font-weight:900}
.w369-split b{display:block;color:#fff;font-size:.55rem;margin-top:1px}
.w369-box{border-radius:9px;padding:7px;margin-top:7px;min-width:0}
.w369-boxhead{display:flex;align-items:center;justify-content:space-between;gap:6px;min-width:0}
.w369-boxhead b{font-size:.43rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.w369-boxhead span{font-size:.36rem;font-weight:900;white-space:nowrap}
.w369-grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:3px;margin-top:5px}
.w369-grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:3px;margin-top:5px}
.w369-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3px;margin-top:5px}
.w369-metric{border:1px solid #263c50;background:#07131f;border-radius:7px;padding:5px 6px;min-width:0}
.w369-metric span{display:block;color:#72899e;font-size:.29rem;font-weight:900;letter-spacing:.035em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.w369-metric b{display:block;color:#eef6ff;font-size:.5rem;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.w369-subline{display:flex;justify-content:space-between;gap:6px;align-items:center;margin-top:4px;color:#718da0;font-size:.31rem;line-height:1.25}
.w369-subline span{min-width:0}
.w369-subline .right{white-space:nowrap;text-align:right}
.w369-boardnote{border:1px solid #29445a;background:#081522;border-radius:10px;padding:8px 10px;margin-top:9px;color:#7390a4;font-size:.43rem;line-height:1.45}
@media(max-width:900px){
  .w369-card{padding:9px}
  .w369-grid4{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:620px){
  .w369-grid4{grid-template-columns:repeat(4,minmax(0,1fr))}
  .w369-card{padding:9px}
}
@media(max-width:430px){
  .w369-grid4{grid-template-columns:repeat(2,minmax(0,1fr))}
  .w369-layerchips{display:none}
}
</style>
"""


def _num(value, default=float("nan")):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1):
    x = _num(value)
    return "N/A" if not math.isfinite(x) else f"{x:.{digits}f}"


def _signed(value, digits=1):
    x = _num(value)
    return "N/A" if not math.isfinite(x) else f"{x:+.{digits}f}"


def _metric(label: str, value: str, value_color: str = "#eef6ff") -> str:
    return (
        '<div class="w369-metric">'
        f'<span>{escape(label)}</span>'
        f'<b style="color:{value_color}">{escape(str(value))}</b>'
        '</div>'
    )


def _compact_defense_box(obj: dict, opponent: str) -> str:
    obj = obj if isinstance(obj, dict) else {}
    grade, grade_color = defense_layer._matchup_grade(obj)
    rank = obj.get("PA_RANK")
    total = obj.get("LEAGUE_TEAMS")
    rank_text = f"#{int(rank)}/{int(total)}" if rank and total else "N/A"
    samples = int(_num(obj.get("ADV_GAMES"), 0) or 0)

    return (
        '<div class="w369-box" style="border:1px solid #31536a;background:#071927">'
        '<div class="w369-boxhead">'
        f'<b style="color:#dff5ff">🛡️ {escape(opponent)} DEFENSE</b>'
        f'<span style="color:{grade_color}">{escape(grade)}</span>'
        '</div>'
        '<div class="w369-grid4">'
        f'{_metric("DEF RTG L10*", _fmt(obj.get("DRTG_L10"),1))}'
        f'{_metric("PACE L10*", _fmt(obj.get("PACE_L10"),1))}'
        f'{_metric("PTS ALLOW SZN", _fmt(obj.get("PA"),1))}'
        f'{_metric("PTS ALLOW L10", _fmt(obj.get("L10_PA"),1))}'
        '</div>'
        '<div class="w369-subline">'
        f'<span>Rank {escape(rank_text)} • REB N/A • AST N/A</span>'
        f'<span class="right">Sample {samples} GP</span>'
        '</div></div>'
    )


def _compact_history_box(obj: dict, opponent: str) -> str:
    obj = obj if isinstance(obj, dict) else {}
    games = int(_num(obj.get("games"), 0) or 0)
    meetings = int(_num(obj.get("team_meetings"), 0) or 0)
    season = int(_num(obj.get("season"), 0) or 0)

    if games <= 0:
        return (
            '<div class="w369-box" style="border:1px solid #5a476f;background:#141126">'
            '<div class="w369-boxhead">'
            f'<b style="color:#eadcff">📚 VS {escape(opponent)} • HISTORY</b>'
            '<span style="color:#a899ba">NO PLAYER SAMPLE</span>'
            '</div>'
            '<div class="w369-subline">'
            '<span>No current-season player matchup history.</span>'
            f'<span class="right">Team mtgs {meetings}</span>'
            '</div></div>'
        )

    warning = "⚠️ SMALL SAMPLE" if games <= 2 else "RECENT SAMPLE"
    warning_color = "#ffe083" if games <= 2 else "#b59aca"
    recent = obj.get("recent_pra") or []
    recent_text = " • ".join(_fmt(x, 0) for x in recent) if recent else "N/A"

    return (
        '<div class="w369-box" style="border:1px solid #5a476f;background:#141126">'
        '<div class="w369-boxhead">'
        f'<b style="color:#eadcff">📚 VS {escape(opponent)} • HISTORY</b>'
        f'<span style="color:{warning_color}">{warning}</span>'
        '</div>'
        '<div class="w369-grid3">'
        f'{_metric("GP", str(games), "#f4edff")}'
        f'{_metric("AVG MIN", _fmt(obj.get("avg_min"),1), "#f4edff")}'
        f'{_metric("AVG PRA", _fmt(obj.get("avg_pra"),1), "#f4edff")}'
        f'{_metric("PTS", _fmt(obj.get("avg_pts"),1), "#f4edff")}'
        f'{_metric("REB", _fmt(obj.get("avg_reb"),1), "#f4edff")}'
        f'{_metric("AST", _fmt(obj.get("avg_ast"),1), "#f4edff")}'
        '</div>'
        '<div class="w369-subline">'
        f'<span><b>Recent PRA:</b> {escape(recent_text)}</span>'
        f'<span class="right">{season} mtgs {meetings}</span>'
        '</div></div>'
    )


def _compact_path_box(p: dict) -> str:
    source_pra = _fmt(p.get("source_pra"), 1)
    base_min = _fmt(p.get("base_min"), 1)
    proj_min = _fmt(p.get("proj_min"), 1)
    min_delta = _signed(p.get("min_delta"), 1)
    base_usg = _fmt(p.get("base_usg"), 1)
    proj_usg = _fmt(p.get("proj_usg"), 1)
    role_delta = _signed(p.get("role_delta"), 1)
    final_pra = _fmt(p.get("pra"), 1)

    minutes = f"{base_min}→{proj_min}" if base_min != "N/A" and proj_min != "N/A" else "N/A"
    usage = f"{base_usg}→{proj_usg}" if base_usg != "N/A" and proj_usg != "N/A" else "N/A"

    return (
        '<div class="w369-box" style="border:1px solid #315d72;background:#0a1b27">'
        '<div class="w369-boxhead">'
        '<b style="color:#9ee9ff">🧭 PROJECTION PATH</b>'
        '<span style="color:#65a7bb">V2.8 STORED FIELDS</span>'
        '</div>'
        '<div class="w369-grid4">'
        f'{_metric("SEASON PRA", source_pra)}'
        f'{_metric("MINUTES", minutes)}'
        f'{_metric("ROLE / USG", usage)}'
        f'{_metric("FINAL PRA", final_pra, "#7ff2c2")}'
        '</div>'
        '<div class="w369-subline">'
        f'<span>MIN Δ {escape(min_delta)} • USG Δ {escape(role_delta)}</span>'
        '<span class="right">Matchup/O-U OFF</span>'
        '</div></div>'
    )


def _render_top5_v369(picks):
    """Same V3.6.8 payload and data; compact presentation only."""
    if not picks:
        st.markdown(
            '<div class="w2-empty">No eligible Step 5 projections are available.</div>',
            unsafe_allow_html=True,
        )
        return

    day = st.session_state.get("wnba_pra_v2_date")
    player_ids, teams = cards._identity_maps(day)
    defenses = defense_layer._opponent_context_map(day)
    histories = history_layer._board_history_map(day, picks, defenses)
    rendered = []

    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = (
            "STARTER"
            if p["starter"]
            else p["status"]
            if p["status"] != "NO DESIGNATION"
            else "ACTIVE"
        )
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")
        pid = player_ids.get(cards._player_key(name))
        tm = cards._team_meta(teams, team)
        om = cards._team_meta(teams, opponent)
        defense = defenses.get(defense_layer._norm(opponent), {})
        history = histories.get(cards._player_key(name), {})

        headshot = cards._headshot_html(pid, name)
        team_logo = cards._logo_html(tm, team, f"{team} logo")
        opp_logo = cards._logo_html(om, opponent, f"{opponent} logo")

        rendered.append(
            f'<div class="w369-card{first}">'
            '<div class="w369-eyebrow">'
            f'<span>#{i} STEP-5 PRA</span>'
            '<div class="w369-layerchips">'
            '<span class="w369-chip">ID</span><span class="w369-chip">DEF</span>'
            '<span class="w369-chip">H2H</span><span class="w369-chip">PATH</span>'
            '</div></div>'
            '<div class="w369-hero">'
            f'{headshot}'
            '<div class="w369-hero-main">'
            f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
            '<div class="w369-match">'
            f'{team_logo}<span style="color:#8da3b8;font-size:.45rem;font-weight:800">vs</span>{opp_logo}'
            '</div>'
            f'<div class="w369-meta">{escape(team)} vs {escape(opponent)} • {escape(status)} • {p["min"]:.1f} MIN</div>'
            '</div></div>'
            '<div class="w369-scoreline">'
            f'<div class="w369-pra">{p["pra"]:.1f}<span>Projected PRA</span></div>'
            '</div>'
            '<div class="w369-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div>'
            f'<div><span>REB</span><b>{p["r"]:.1f}</b></div>'
            f'<div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            f'<div><span>USG</span><b>{v28._fmt(p["usg"],1)}</b></div>'
            '</div>'
            f'{_compact_defense_box(defense, opponent)}'
            f'{_compact_history_box(history, opponent)}'
            f'{_compact_path_box(p)}'
            '</div>'
        )

    st.markdown(
        _LAYOUT_CSS
        + '<div class="w23-summary w369-board">'
        '<div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">Same Step-5 ranking and projections, now in a compact scan-first layout. Identity, defense, matchup history and projection path remain presentation-only.</div>'
        f'<div class="w28-topgrid">{"".join(rendered)}</div>'
        '<div class="w369-boardnote">'
        '<b>Display-layer guardrail:</b> Defense and H2H do not alter V2.8 projection/ranking. '
        'Projection Path uses existing V2.8 stored fields only; no minutes-only PRA or O/U probability is manufactured. '
        'Defense pace/ratings are approximate cached context; REB/AST allowed remain N/A until verified.'
        '</div></div>',
        unsafe_allow_html=True,
    )


def install():
    """Install V3.6.8 data/path stack, then replace only its card renderer."""
    prior.install()

    # Do not replace adjusted_top5: V3.6.8 already carries the verified display
    # fields while preserving the exact V2.8 eligibility/sort behavior.
    v28._render_top5 = _render_top5_v369
    cards._render_top5 = _render_top5_v369
    cards.v28._render_top5 = _render_top5_v369
    defense_layer.cards._render_top5 = _render_top5_v369
    defense_layer.cards.v28._render_top5 = _render_top5_v369


def begin_render():
    prior.begin_render()
    install()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
