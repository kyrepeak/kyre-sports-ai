"""College Football Over/Under Hub V3 — Step 9 final selection + Top-5.

Additive UI over permanently frozen Step-8 Over/Under Hub V2.

Step 9 activates:
- transparent OVER / UNDER / PASS qualification for a selected matchup,
- model grade/tier,
- per-game manual analysis-line board,
- full-slate scan,
- Top-5 qualified Over/Under opportunities ranked by pure model probability.

Each analysis line remains a comparison threshold only with exactly 0%
projection weight. No sportsbook feed/price, market-implied probability,
edge/EV, or Monte Carlo is used.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_final_v1 as final_model
import cfb_over_under_hub_v2 as frozen_v2
import cfb_over_under_slate_v1 as slate

MODEL_VERSION = "CFB OVER/UNDER HUB V3 • STEP 9 FINAL RANKING"
FROZEN_OVER_UNDER_HUB = "cfb_over_under_hub_v2"
MARKET = "Over/Under"

_CSS = r"""
<style>
.cfb9-shell{border:1px solid rgba(126,231,180,.30);border-radius:17px;
background:linear-gradient(145deg,#071912,#101723);padding:14px;margin-top:8px}
.cfb9-kicker{color:#83e7b6;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb9-title{color:#f1fff8;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb9-sub{color:#8fa99b;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb9-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb9-pill{border:1px solid #315745;border-radius:999px;background:#0a2118;color:#a9cfbb;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb9-pill.good{border-color:#287355;background:#0a2d22;color:#83e7b6}
.cfb9-final{margin-top:11px;border:1px solid rgba(126,231,180,.27);border-radius:16px;
background:linear-gradient(145deg,#071912,#091724);overflow:hidden}
.cfb9-head{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:10px 11px;border-bottom:1px solid rgba(126,231,180,.15)}
.cfb9-head b{color:#83e7b6;font-size:.51rem;letter-spacing:.08em}
.cfb9-lock{border:1px solid #277353;border-radius:999px;background:#0b2d22;color:#84e7b6;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb9-main{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);gap:8px;padding:11px}
.cfb9-pick{border:1px solid rgba(126,231,180,.18);border-radius:13px;background:#081c14;padding:11px}
.cfb9-pick small,.cfb9-grade small{display:block;color:#719382;font-size:.43rem;text-transform:uppercase;font-weight:900}
.cfb9-pick strong{display:block;color:#8cf0be;font-size:1.58rem;margin-top:4px}
.cfb9-pick b{display:block;color:#d1e8dc;font-size:.60rem;margin-top:4px}
.cfb9-grade{border:1px solid rgba(100,181,225,.19);border-radius:13px;background:#081824;padding:11px}
.cfb9-grade strong{display:block;color:#78dbff;font-size:1.25rem;margin-top:4px}
.cfb9-grade b{display:block;color:#d6e9f2;font-size:.57rem;margin-top:4px}
.cfb9-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 11px 11px}
.cfb9-metric{border:1px solid rgba(126,231,180,.13);border-radius:9px;background:#0a1914;padding:7px}
.cfb9-metric b{display:block;color:#e4f2eb;font-size:.64rem}.cfb9-metric span{display:block;
color:#7c9788;font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb9-note{border-top:1px solid rgba(126,231,180,.12);padding:9px 11px;color:#758f82;
font-size:.44rem;line-height:1.5}
.cfb9-board{margin-top:12px;border:1px solid rgba(100,181,225,.23);border-radius:15px;background:#071520;padding:11px}
.cfb9-board-title{color:#78dbff;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfb9-board-sub{color:#7c98a8;font-size:.46rem;line-height:1.45;margin-top:3px}
.cfb9-top{margin-top:7px;border:1px solid rgba(126,231,180,.18);border-radius:11px;background:#071a14;padding:9px}
.cfb9-top-head{display:flex;justify-content:space-between;gap:7px;align-items:center}
.cfb9-top-rank{color:#74dcff;font-size:.48rem;font-weight:950}
.cfb9-top-team{color:#f0faf5;font-size:.78rem;font-weight:950}
.cfb9-top-prob{color:#89edbb;font-size:.78rem;font-weight:950}
.cfb9-top-meta{color:#759081;font-size:.43rem;margin-top:4px;line-height:1.45}
.cfb9-pass{margin-top:10px;border:1px solid #6e5a1d;border-radius:13px;background:#2d260d;padding:10px}
.cfb9-pass b{display:block;color:#f4da78;font-size:.57rem}.cfb9-pass span{display:block;
color:#b9a963;font-size:.48rem;line-height:1.45;margin-top:3px}
@media(max-width:760px){
  .cfb9-main{grid-template-columns:1fr}.cfb9-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb9-title{font-size:1.20rem}
}
</style>
"""


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _final_card(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    if not final.get("ready"):
        reasons = " • ".join(
            escape(str(x))
            for x in final.get("reasons") or ["Step 9 synthesis unavailable"]
        )
        return f"""
<div class="cfb9-pass">
  <b>STEP 9 FINAL SELECTION GATED</b>
  <span>{reasons}. No final Over/Under selection is invented.</span>
</div>
"""

    selection = escape(str(final.get("selection") or "PASS"))
    candidate = escape(str(final.get("candidate_side") or "PASS"))
    grade = escape(str(final.get("grade") or "PASS"))
    tier = escape(str(final.get("tier") or "NO PLAY"))
    matchup = escape(
        f"{game.get('away_team') or 'Away'} @ {game.get('home_team') or 'Home'}"
    )

    return f"""
<div class="cfb9-final">
  <div class="cfb9-head">
    <b>STEP 9 • FINAL OVER/UNDER SELECTION</b>
    <span class="cfb9-lock">FINAL RULES ✅</span>
  </div>
  <div class="cfb9-main">
    <div class="cfb9-pick">
      <small>Final selection • {matchup}</small>
      <strong>{selection}</strong>
      <b>Candidate {candidate} • {_pct(final.get('selection_probability'))}</b>
    </div>
    <div class="cfb9-grade">
      <small>Model grade / tier</small>
      <strong>{grade}</strong>
      <b>{tier}</b>
    </div>
  </div>
  <div class="cfb9-grid">
    <div class="cfb9-metric"><b>{_num(final.get('projected_total'))}</b><span>Projected total</span></div>
    <div class="cfb9-metric"><b>{_num(final.get('analysis_line'))}</b><span>Analysis line</span></div>
    <div class="cfb9-metric"><b>{_num(final.get('projection_line_distance'))}</b><span>|Projection - line|</span></div>
    <div class="cfb9-metric"><b>{_pct(final.get('push_probability'))}</b><span>P(Push)</span></div>
    <div class="cfb9-metric"><b>{_pct(final.get('reliability'))}</b><span>Reliability</span></div>
    <div class="cfb9-metric"><b>{_pct(final.get('feature_coverage'))}</b><span>Feature coverage</span></div>
    <div class="cfb9-metric"><b>{_pct(final.get('conditional_no_push_probability'))}</b><span>Candidate P | no push</span></div>
    <div class="cfb9-metric"><b>0%</b><span>Line projection weight</span></div>
  </div>
  <div class="cfb9-note">
    PASS means the candidate side did not clear Step-9 probability/reliability/coverage
    thresholds. The final rule does not change Step-8 projection math. No sportsbook feed,
    price, market probability, EV, or Monte Carlo is used.
  </div>
</div>
"""


def _top_card(row: Mapping[str, Any]) -> str:
    game = row.get("game") or {}
    final = row.get("final") or {}
    matchup = escape(
        f"{game.get('away_team') or 'Away'} @ {game.get('home_team') or 'Home'}"
    )
    selection = escape(str(final.get("selection") or "PASS"))
    grade = escape(str(final.get("grade") or "PASS"))

    return f"""
<div class="cfb9-top">
  <div class="cfb9-top-head">
    <div>
      <span class="cfb9-top-rank">#{int(row.get('rank') or 0)} • GRADE {grade}</span>
      <div class="cfb9-top-team">{selection} • {matchup}</div>
    </div>
    <div class="cfb9-top-prob">{_pct(final.get('selection_probability'))}</div>
  </div>
  <div class="cfb9-top-meta">
    line {_num(final.get('analysis_line'))} • projected {_num(final.get('projected_total'))} •
    distance {_num(final.get('projection_line_distance'))} • reliability {_pct(final.get('reliability'))} •
    coverage {_pct(final.get('feature_coverage'))} • push {_pct(final.get('push_probability'))}
  </div>
</div>
"""


def _editor_records(edited: Any) -> list[dict[str, Any]]:
    if hasattr(edited, "to_dict"):
        try:
            return list(edited.to_dict("records"))
        except Exception:
            pass
    if isinstance(edited, list):
        return [dict(row) for row in edited]
    return []


def _line_board_rows(
    games: list[Mapping[str, Any]],
    selected_identity: str,
    selected_line: float,
) -> list[dict[str, Any]]:
    rows = []
    for game in games:
        identity = str(game.get("identity_key") or game.get("game_id") or "")
        rows.append({
            "Use": identity == selected_identity,
            "Matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
            "Kickoff ET": game.get("kickoff_et"),
            "Analysis Line": float(selected_line) if identity == selected_identity else 50.5,
            "Identity": identity,
        })
    return rows


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🏈 COLLEGE FOOTBALL • OVER/UNDER • Step 9 FINAL • "
        "manual lines • projection weight 0%"
    )
    st.markdown(frozen_v2.frozen_v1.identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v2.frozen_v1.frozen_team_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(frozen_v2.frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v2._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb9-shell">
  <div class="cfb9-kicker">CFB STEP 9 • OVER/UNDER FINAL RANKING</div>
  <div class="cfb9-title">↕️ College Football Over/Under</div>
  <div class="cfb9-sub">
    Frozen Step-8 projected-total model + transparent qualification rules +
    per-game manual line board + full-slate Top-5 ranking.
  </div>
  <div class="cfb9-status">
    <span class="cfb9-pill good">PROJECTED TOTAL ✅</span>
    <span class="cfb9-pill good">O/U PROBABILITY ✅</span>
    <span class="cfb9-pill good">FINAL O/U/PASS ✅</span>
    <span class="cfb9-pill good">TOP-5 ✅</span>
    <span class="cfb9-pill good">LINE WEIGHT 0% ✅</span>
    <span class="cfb9-pill good">SPORTSBOOK FEED 0% ✅</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Over/Under slate date",
        value=frozen_v2.frozen_v1.datetime.now(frozen_v2.frozen_v1._ET).date(),
        key="cfb_step9_over_under_date",
        help="Loads the certified NCAA scoreboard and frozen Step-8 model inputs.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = frozen_v2.frozen_v1.schedule.load_with_diagnostics(
        selected_day
    )
    st.markdown(
        frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Step 9 fails "
            "closed—no final selection or Top-5 ranking is invented."
        )
        attempts = frozen_v2.frozen_v1._diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Over/Under matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_v2.frozen_v1.identity_ui._matchup_label(
            games[int(i)]
        ),
        key=f"cfb_step9_over_under_matchup_{selected_day}",
    )
    game = games[int(index)]
    identity = str(game.get("identity_key") or game.get("game_id") or index)

    selected_line = st.number_input(
        "🎯 Selected-game analysis total line — threshold only (0% projection weight)",
        min_value=float(frozen_v2.model.MIN_ANALYSIS_LINE),
        max_value=float(frozen_v2.model.MAX_ANALYSIS_LINE),
        value=50.5,
        step=0.5,
        key=f"cfb_step9_selected_line_{selected_day}_{identity}",
    )

    selected_result = slate.analyze_game(
        game,
        selected_day,
        float(selected_line),
    )
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}

    st.markdown(
        frozen_v2.frozen_v1._hero(game, away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_v2.frozen_v1._readiness_panel(game, away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_v2.frozen_v1._environment_panel(away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_v2._model_card(game, away, home, raw),
        unsafe_allow_html=True,
    )

    components = frozen_v2._components_panel(raw)
    if components:
        st.markdown(components, unsafe_allow_html=True)

    st.markdown(_final_card(game, final), unsafe_allow_html=True)

    st.session_state["cfb_over_under_final_v1_game_id"] = identity
    st.session_state["cfb_over_under_final_v1_selected"] = dict(final)

    st.markdown(
        """
<div class="cfb9-board">
  <div class="cfb9-board-title">🏆 FULL-SLATE OVER/UNDER LINE BOARD + TOP-5</div>
  <div class="cfb9-board-sub">
    Check Use for the games you want analyzed and enter that game's total line.
    Lines are manual comparison thresholds only. The scanner does not fetch sportsbook
    totals or prices, and the line cannot change the model projection.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    editor = st.data_editor(
        _line_board_rows(games, identity, float(selected_line)),
        use_container_width=True,
        hide_index=True,
        key=f"cfb_step9_line_board_{selected_day}",
    )
    records = _editor_records(editor)

    scan_key = f"cfb_step9_top5_{selected_day}"
    diag_key = f"cfb_step9_scan_diag_{selected_day}"

    selected_lines: dict[str, float] = {}
    for row in records:
        if not bool(row.get("Use")):
            continue
        row_identity = str(row.get("Identity") or "")
        try:
            line = float(row.get("Analysis Line"))
        except Exception:
            continue
        if row_identity:
            selected_lines[row_identity] = line

    if st.button(
        f"Run Over/Under scan for {len(selected_lines)} selected games",
        key=f"cfb_step9_scan_button_{selected_day}",
        type="primary",
        disabled=not bool(selected_lines),
    ):
        with st.spinner(
            f"Analyzing {len(selected_lines)} games through frozen Step 8 + Step 9..."
        ):
            rows, scan_diag = slate.scan_slate(
                games,
                selected_day,
                selected_lines,
            )
            st.session_state[scan_key] = final_model.rank_slate(rows, limit=5)
            st.session_state[diag_key] = scan_diag

    top5 = st.session_state.get(scan_key) or []
    scan_diag = st.session_state.get(diag_key) or {}

    if scan_diag:
        st.caption(
            f"Scanner: {int(scan_diag.get('games_analyzed') or 0)} analyzed • "
            f"{int(scan_diag.get('final_ready') or 0)} final-ready • "
            f"{int(scan_diag.get('qualified_plays') or 0)} qualified • "
            f"{len(scan_diag.get('errors') or [])} errors"
        )

    if top5:
        for row in top5:
            st.markdown(_top_card(row), unsafe_allow_html=True)
    elif scan_diag:
        st.warning(
            "No scanned game cleared the Step-9 qualification thresholds. "
            "That is a real PASS, not a forced Top-5."
        )
    else:
        st.caption(
            "Enter/check per-game lines above, then run the scan. Top-5 only ranks "
            "games that actually clear the final qualification rules."
        )

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">CERTIFIED TEAM EVIDENCE • STEP 9 AUDIT</div>
  <div class="cfb3-sub">
    Step 9 ranks frozen Step-8 outputs; it does not alter schedule identity,
    team evidence, projected points, or projected total.
  </div>
  {frozen_v2.frozen_v1.frozen_team_ui._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_v2.frozen_v1.frozen_team_ui._team_card(away)}
    {frozen_v2.frozen_v1.frozen_team_ui._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.info(
        "Step 9 completes the College Football Over/Under section. Final selection "
        "rules are structural thresholds, not claimed historical empirical calibration. "
        "No sportsbook price/market probability, edge/EV, or Monte Carlo is used."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Step 9 Over/Under hub received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_OVER_UNDER_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_editor_records",
    "_final_card",
    "_line_board_rows",
    "_top_card",
    "render_cfb_hub",
    "render_over_under_hub",
]
