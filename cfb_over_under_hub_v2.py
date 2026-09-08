"""College Football Over/Under Hub V2 — Step 8 raw total model.

Additive UI over permanently frozen Step-7 Over/Under foundation.

Step 8 activates:
- projected away/home points for total analysis,
- projected game total,
- Over / Under / push probabilities at a user-entered analysis line,
- structural uncertainty and model confidence.

The analysis line is a comparison threshold only and has exactly 0% weight in
the projection. Sportsbook feeds/prices, edge/EV, slate ranking, final picks,
and Monte Carlo remain OFF.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_hub_v1 as frozen_v1
import cfb_over_under_model_v1 as model

MODEL_VERSION = "CFB OVER/UNDER HUB V2 • STEP 8 RAW TOTAL MODEL"
FROZEN_OVER_UNDER_HUB = "cfb_over_under_hub_v1"
MARKET = "Over/Under"

_CSS = r"""
<style>
.cfb8-shell{border:1px solid rgba(247,193,78,.30);border-radius:17px;
background:linear-gradient(145deg,#171204,#101723);padding:14px;margin-top:8px}
.cfb8-kicker{color:#ffd978;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb8-title{color:#fff9e8;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb8-sub{color:#afa487;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb8-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb8-pill{border:1px solid #62562f;border-radius:999px;background:#211c0b;color:#d7c989;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb8-pill.good{border-color:#287355;background:#0a2d22;color:#83e7b6}
.cfb8-pill.wait{border-color:#765f1c;background:#30280e;color:#f2d675}
.cfb8-model{margin-top:11px;border:1px solid rgba(247,193,78,.28);border-radius:16px;
background:linear-gradient(145deg,#15180f,#111723);overflow:hidden}
.cfb8-head{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:10px 11px;border-bottom:1px solid rgba(247,193,78,.16)}
.cfb8-head b{color:#ffd978;font-size:.51rem;letter-spacing:.08em}
.cfb8-raw{border:1px solid #765f1c;border-radius:999px;background:#30280e;color:#f2d675;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb8-main{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);gap:8px;padding:11px}
.cfb8-total{border:1px solid rgba(247,193,78,.18);border-radius:13px;background:#191c13;padding:11px}
.cfb8-total small,.cfb8-lean small{display:block;color:#958d76;font-size:.43rem;text-transform:uppercase;font-weight:900}
.cfb8-total strong{display:block;color:#fff1bd;font-size:1.65rem;margin-top:4px}
.cfb8-total b{display:block;color:#d4c69c;font-size:.57rem;margin-top:4px}
.cfb8-lean{border:1px solid rgba(126,231,180,.18);border-radius:13px;background:#071912;padding:11px}
.cfb8-lean strong{display:block;color:#88ebba;font-size:1.25rem;margin-top:4px}
.cfb8-lean b{display:block;color:#b7d8c6;font-size:.55rem;margin-top:4px}
.cfb8-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 11px 11px}
.cfb8-metric{border:1px solid rgba(247,193,78,.13);border-radius:9px;background:#171a12;padding:7px}
.cfb8-metric b{display:block;color:#f4ecd7;font-size:.65rem}.cfb8-metric span{display:block;
color:#9e957e;font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb8-note{border-top:1px solid rgba(247,193,78,.12);padding:9px 11px;color:#928a73;
font-size:.44rem;line-height:1.5}
.cfb8-gated{margin-top:10px;border:1px solid #743a34;border-radius:13px;background:#301510;padding:10px}
.cfb8-gated b{display:block;color:#ffb0a8;font-size:.57rem}.cfb8-gated span{display:block;
color:#c78982;font-size:.48rem;line-height:1.45;margin-top:3px}
.cfb8-components{margin-top:9px;border:1px solid rgba(247,193,78,.16);border-radius:12px;background:#14170f;padding:9px}
.cfb8-components-title{color:#ffd978;font-size:.48rem;font-weight:950;letter-spacing:.07em}
.cfb8-components-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}
.cfb8-component{border:1px solid rgba(247,193,78,.12);border-radius:8px;background:#181b12;padding:6px}
.cfb8-component b{display:block;color:#e9dfc5;font-size:.58rem}.cfb8-component span{display:block;color:#978f79;
font-size:.39rem;text-transform:uppercase;margin-top:2px}
@media(max-width:760px){
  .cfb8-main{grid-template-columns:1fr}.cfb8-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb8-components-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfb8-title{font-size:1.20rem}
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


def _model_card(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        reasons = " • ".join(
            escape(str(x))
            for x in output.get("reasons") or ["Step 8 model unavailable"]
        )
        return f"""
<div class="cfb8-gated">
  <b>STEP 8 TOTAL MODEL GATED</b>
  <span>{reasons}. No projected total or Over/Under probability is invented.</span>
</div>
"""

    away_name = escape(str(away.get("team") or game.get("away_team") or "Away"))
    home_name = escape(str(home.get("team") or game.get("home_team") or "Home"))
    interval = output.get("total_uncertainty_90") or {}
    lean = escape(str(output.get("model_lean") or "PASS"))

    return f"""
<div class="cfb8-model">
  <div class="cfb8-head">
    <b>STEP 8 • RAW OVER/UNDER MODEL V1</b>
    <span class="cfb8-raw">RAW MODEL • NOT FINAL PICK</span>
  </div>
  <div class="cfb8-main">
    <div class="cfb8-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'))}</strong>
      <b>{away_name} {_num(output.get('projected_away_points'))} • {home_name} {_num(output.get('projected_home_points'))}</b>
    </div>
    <div class="cfb8-lean">
      <small>Raw model lean • Step 9 ranking still off</small>
      <strong>{lean}</strong>
      <b>Analysis line {_num(output.get('analysis_line'))}</b>
    </div>
  </div>
  <div class="cfb8-grid">
    <div class="cfb8-metric"><b>{_pct(output.get('over_probability'))}</b><span>P(Over)</span></div>
    <div class="cfb8-metric"><b>{_pct(output.get('under_probability'))}</b><span>P(Under)</span></div>
    <div class="cfb8-metric"><b>{_pct(output.get('push_probability'))}</b><span>P(Push)</span></div>
    <div class="cfb8-metric"><b>{escape(str(output.get('confidence') or 'LOW'))}</b><span>Model confidence</span></div>
    <div class="cfb8-metric"><b>{_pct(output.get('reliability'))}</b><span>Reliability</span></div>
    <div class="cfb8-metric"><b>{_pct((output.get('feature_coverage') or {}).get('score'))}</b><span>Feature coverage</span></div>
    <div class="cfb8-metric"><b>{_num(interval.get('low'))}–{_num(interval.get('high'))}</b><span>Total structural 90%</span></div>
    <div class="cfb8-metric"><b>0%</b><span>Analysis-line projection weight</span></div>
  </div>
  <div class="cfb8-note">
    The entered total line is a threshold only. It changes P(Over)/P(Under) but cannot change
    projected points or projected total. No sportsbook feed or price is used. Uncertainty is
    structural, not claimed historical empirical calibration.
  </div>
</div>
"""


def _components_panel(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        return ""
    c = output.get("components") or {}
    return f"""
<div class="cfb8-components">
  <div class="cfb8-components-title">MODEL COMPONENT AUDIT</div>
  <div class="cfb8-components-grid">
    <div class="cfb8-component"><b>{_num(c.get('away_base_points'))}</b><span>Away base points</span></div>
    <div class="cfb8-component"><b>{_num(c.get('home_base_points'))}</b><span>Home base points</span></div>
    <div class="cfb8-component"><b>{_num(c.get('away_recent_adjustment'), 2)}</b><span>Away recent adj</span></div>
    <div class="cfb8-component"><b>{_num(c.get('home_recent_adjustment'), 2)}</b><span>Home recent adj</span></div>
    <div class="cfb8-component"><b>{_num(c.get('away_efficiency_adjustment'), 2)}</b><span>Away efficiency adj</span></div>
    <div class="cfb8-component"><b>{_num(c.get('home_efficiency_adjustment'), 2)}</b><span>Home efficiency adj</span></div>
    <div class="cfb8-component"><b>{_num(output.get('structural_total_sigma'), 2)}</b><span>Structural total sigma</span></div>
    <div class="cfb8-component"><b>{_pct(output.get('sample_factor'))}</b><span>Sample factor</span></div>
  </div>
</div>
"""


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🏈 COLLEGE FOOTBALL • OVER/UNDER • Step 8 raw total model ACTIVE • "
        "analysis-line projection weight 0%"
    )
    st.markdown(frozen_v1.identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v1.frozen_team_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb8-shell">
  <div class="cfb8-kicker">CFB STEP 8 • OVER/UNDER MODEL V1</div>
  <div class="cfb8-title">↕️ College Football Over/Under</div>
  <div class="cfb8-sub">
    Certified scoring foundation + raw projected total + Over/Under probability at a
    user-entered comparison line. The line has 0% influence on the projection.
  </div>
  <div class="cfb8-status">
    <span class="cfb8-pill good">CURRENT NCAA SLATE ✅</span>
    <span class="cfb8-pill good">TEAM DATA ✅</span>
    <span class="cfb8-pill good">PROJECTED TOTAL ✅</span>
    <span class="cfb8-pill good">O/U PROBABILITY ✅</span>
    <span class="cfb8-pill good">LINE WEIGHT 0% ✅</span>
    <span class="cfb8-pill wait">TOP-5 / FINAL PICK ⏳ STEP 9</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Over/Under slate date",
        value=frozen_v1.datetime.now(frozen_v1._ET).date(),
        key="cfb_step8_over_under_date",
        help="Loads the certified current NCAA scoreboard and frozen Step-7 scoring foundation.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Step 8 fails closed—"
            "no projected total or Over/Under probability is invented."
        )
        attempts = frozen_v1._diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Over/Under matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step8_over_under_matchup_{selected_day}",
    )
    game = games[int(index)]

    profiles, team_diag = frozen_v1.team_data.load_matchup_team_data(
        game,
        selected_day,
    )
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(frozen_v1._hero(game, away, home), unsafe_allow_html=True)
    st.markdown(
        frozen_v1._readiness_panel(game, away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_v1._environment_panel(away, home),
        unsafe_allow_html=True,
    )

    identity = str(game.get("identity_key") or game.get("game_id") or index)
    analysis_line = st.number_input(
        "🎯 Analysis total line — comparison threshold only (0% projection weight)",
        min_value=float(model.MIN_ANALYSIS_LINE),
        max_value=float(model.MAX_ANALYSIS_LINE),
        value=50.5,
        step=0.5,
        key=f"cfb_step8_analysis_line_{selected_day}_{identity}",
        help=(
            "This line is not used to build the projection. Changing it only changes "
            "the Over/Under probability comparison against the same projected total."
        ),
    )

    output = model.project_matchup(
        game,
        away,
        home,
        float(analysis_line),
    )

    st.markdown(_model_card(game, away, home, output), unsafe_allow_html=True)
    components = _components_panel(output)
    if components:
        st.markdown(components, unsafe_allow_html=True)

    st.session_state["cfb_over_under_model_v1_game_id"] = identity
    st.session_state["cfb_over_under_model_v1_selected"] = dict(output)

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">CERTIFIED TEAM EVIDENCE • STEP 8 INPUT AUDIT</div>
  <div class="cfb3-sub">
    The Step-8 model reads the frozen Step-7 foundation. It does not alter Moneyline,
    schedule identity, or certified team-data values.
  </div>
  {frozen_v1.frozen_team_ui._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_v1.frozen_team_ui._team_card(away)}
    {frozen_v1.frozen_team_ui._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander(f"Full verified Over/Under slate • {selected_day}"):
        rows = [
            {
                "Matchup": f"{g.get('away_team')} @ {g.get('home_team')}",
                "Kickoff ET": g.get("kickoff_et"),
                "Away conf": g.get("away_conference"),
                "Home conf": g.get("home_conference"),
                "Venue": g.get("venue"),
                "Status": g.get("status"),
                "NCAA ID": g.get("game_id"),
            }
            for g in games
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    attempts = frozen_v1._diag_rows(team_diag)
    if attempts:
        with st.expander("Over/Under team-data provider diagnostics"):
            st.dataframe(attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 8 activates the raw projected total and Over/Under probabilities. "
        "Sportsbook feeds/prices, edge/EV, slate ranking, final picks, and Monte Carlo "
        "remain OFF. Step 9 owns the final Over/Under ranking layer."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Step 8 Over/Under hub received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_OVER_UNDER_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel",
    "_model_card",
    "render_cfb_hub",
    "render_over_under_hub",
]
