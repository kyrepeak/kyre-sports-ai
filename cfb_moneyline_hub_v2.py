"""College Football Moneyline Hub V2 — Step 5 raw Moneyline Model V1.

Additive wrapper over permanently frozen CFB Step 4 Moneyline UI.

Step 5 activates a transparent RAW pre-calibration model for the selected
Moneyline matchup. It consumes only frozen Step 2/3 verified data and the
additive `cfb_moneyline_model_v1` engine.

Still reserved for Step 6:
- calibrated/final P(win),
- fair moneyline,
- sportsbook comparison / edge / EV,
- final play grade,
- Monte Carlo calibration layer.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_hub_v3 as frozen_v3
import cfb_moneyline_hub_v1 as frozen_v1
import cfb_moneyline_model_v1 as model
import cfb_schedule_v1 as schedule
import cfb_team_data_v1 as team_data

MODEL_VERSION = "CFB MONEYLINE HUB V2 • STEP 5 MODEL V1"
FROZEN_CFB_MONEYLINE_HUB = "cfb_moneyline_hub_v1"
MARKET = "Moneyline"

_ET = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.cfb5-card{margin-top:11px;border:1px solid rgba(86,211,159,.28);border-radius:16px;
background:linear-gradient(145deg,#061812,#08151e);overflow:hidden}
.cfb5-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 11px;
border-bottom:1px solid rgba(86,211,159,.18)}
.cfb5-head span{color:#82e5b7;font-size:.49rem;font-weight:950;letter-spacing:.09em}
.cfb5-raw{border:1px solid #725f1e;border-radius:999px;background:#30280d;color:#f1d875;
padding:4px 7px;font-size:.42rem;font-weight:950}
.cfb5-leader{padding:12px 11px 6px}.cfb5-leader small{display:block;color:#6f9483;font-size:.43rem;
font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.cfb5-leader b{display:block;color:#effbf5;font-size:1.03rem;margin-top:2px}
.cfb5-probs{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:5px 11px 10px}
.cfb5-prob{border:1px solid rgba(86,211,159,.16);border-radius:11px;background:#071b14;padding:9px}
.cfb5-prob strong{display:block;color:#e7f8ef;font-size:1.05rem}.cfb5-prob span{display:block;
color:#789b8a;font-size:.44rem;text-transform:uppercase;margin-top:2px}
.cfb5-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 11px 11px}
.cfb5-metric{border:1px solid rgba(96,158,194,.18);border-radius:9px;background:#081722;padding:7px}
.cfb5-metric b{display:block;color:#e2edf3;font-size:.62rem}.cfb5-metric span{display:block;
color:#7690a0;font-size:.42rem;text-transform:uppercase;margin-top:2px}
.cfb5-note{border-top:1px solid rgba(86,211,159,.15);padding:8px 11px;color:#719083;
font-size:.44rem;line-height:1.45}
.cfb5-gated{margin-top:11px;border:1px solid #7d3d3d;border-radius:14px;background:#301414;padding:10px}
.cfb5-gated b{display:block;color:#ffaaa5;font-size:.58rem}.cfb5-gated span{display:block;color:#c98480;
font-size:.48rem;line-height:1.45;margin-top:3px}
.cfb5-features{margin-top:9px;border:1px solid rgba(91,140,166,.21);border-radius:14px;background:#07131d;padding:10px}
.cfb5-features-title{color:#76d9ff;font-size:.49rem;font-weight:950;letter-spacing:.08em}
.cfb5-feature-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}
.cfb5-feature{border:1px solid rgba(91,140,166,.17);border-radius:9px;background:#091824;padding:7px}
.cfb5-feature b{display:block;color:#dce9f0;font-size:.58rem}.cfb5-feature span{display:block;
color:#778f9e;font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb5-qb{margin-top:7px;color:#7e9388;font-size:.43rem;line-height:1.45}
.cfb5-qb b{color:#a8c9b8}
@media(max-width:760px){
  .cfb5-metrics,.cfb5-feature-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
</style>
"""


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    try:
        x = float(value)
    except Exception:
        return "—"
    sign = "+" if signed and x > 0 else ""
    return f"{sign}{x:.{digits}f}"


def _model_card(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        reasons = " • ".join(str(x) for x in output.get("reasons") or ["model inputs incomplete"])
        return f"""
<div class="cfb5-gated">
  <b>STEP 5 MODEL GATED • NO RAW PROBABILITY</b>
  <span>{escape(reasons)}. No values are invented when mandatory frozen inputs are missing.</span>
</div>
"""

    away_name = escape(str(away.get("team") or game.get("away_team") or "Away"))
    home_name = escape(str(home.get("team") or game.get("home_team") or "Home"))
    leader = escape(str(output.get("raw_model_leader_team") or "—"))
    away_p = _pct(output.get("away_win_probability_raw"))
    home_p = _pct(output.get("home_win_probability_raw"))
    projected_away = _num(output.get("projected_away_points_raw"))
    projected_home = _num(output.get("projected_home_points_raw"))
    margin = _num(output.get("projected_margin_home_raw"), signed=True)
    total = _num(output.get("projected_total_raw"))
    reliability = _pct(output.get("reliability"))
    coverage = _pct((output.get("feature_coverage") or {}).get("score"))
    confidence = escape(str(output.get("confidence") or "LOW"))

    return f"""
<div class="cfb5-card">
  <div class="cfb5-head">
    <span>STEP 5 • MONEYLINE MODEL V1</span>
    <b class="cfb5-raw">RAW • PRE-CALIBRATION</b>
  </div>
  <div class="cfb5-leader">
    <small>Raw model leader • not a final betting pick</small>
    <b>{leader}</b>
  </div>
  <div class="cfb5-probs">
    <div class="cfb5-prob"><strong>{away_p}</strong><span>{away_name} raw P(win)</span></div>
    <div class="cfb5-prob"><strong>{home_p}</strong><span>{home_name} raw P(win)</span></div>
  </div>
  <div class="cfb5-metrics">
    <div class="cfb5-metric"><b>{projected_away} – {projected_home}</b><span>Raw projected score • A-H</span></div>
    <div class="cfb5-metric"><b>{margin}</b><span>Home margin</span></div>
    <div class="cfb5-metric"><b>{total}</b><span>Raw projected total</span></div>
    <div class="cfb5-metric"><b>{confidence}</b><span>Input confidence</span></div>
    <div class="cfb5-metric"><b>{reliability}</b><span>Small-sample reliability</span></div>
    <div class="cfb5-metric"><b>{coverage}</b><span>Feature coverage</span></div>
    <div class="cfb5-metric"><b>NO</b><span>Sportsbook input</span></div>
    <div class="cfb5-metric"><b>STEP 6</b><span>Final calibration</span></div>
  </div>
  <div class="cfb5-note">
    Raw V1 probability is derived only from frozen team/game evidence and is intentionally
    shrunk for small samples/data gaps. Fair moneyline, market edge, EV, final recommendation
    and Monte Carlo remain locked.
  </div>
</div>
"""


def _feature_panel(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        return ""

    c = output.get("components") or {}
    coverage = (output.get("feature_coverage") or {}).get("components") or {}

    def state(key: str) -> str:
        return "✓" if coverage.get(key) else "LIMITED"

    return f"""
<div class="cfb5-features">
  <div class="cfb5-features-title">MODEL V1 • TRANSPARENT FEATURE CONTRIBUTIONS</div>
  <div class="cfb5-feature-grid">
    <div class="cfb5-feature"><b>{_num(c.get('away_base_points'))} / {_num(c.get('home_base_points'))}</b><span>Base scoring • A/H</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('away_recent_adjustment'), signed=True)} / {_num(c.get('home_recent_adjustment'), signed=True)}</b><span>Recent adjustment • {state('recent')}</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('away_efficiency_adjustment'), signed=True)} / {_num(c.get('home_efficiency_adjustment'), signed=True)}</b><span>Efficiency adj • {state('efficiency')}</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('turnover_edge_home_points'), signed=True)}</b><span>Home turnover edge • {state('turnovers')}</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('sos_edge_home_points'), signed=True)}</b><span>Home SOS edge • {state('sos')}</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('home_field_points'), signed=True)}</b><span>Home field</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('away_qb_adjustment_points'), signed=True)}</b><span>Away QB points</span></div>
    <div class="cfb5-feature"><b>{_num(c.get('home_qb_adjustment_points'), signed=True)}</b><span>Home QB points</span></div>
  </div>
  <div class="cfb5-qb">
    <b>QB firewall:</b> away {escape(str(c.get('away_qb_state') or 'UNVERIFIED • ZERO IMPACT'))} •
    home {escape(str(c.get('home_qb_state') or 'UNVERIFIED • ZERO IMPACT'))}.
    Missing QB data is never guessed and has exactly zero Step-5 impact.
  </div>
</div>
"""


def _diag_rows(diag: Mapping[str, Any]) -> list[dict[str, Any]]:
    return frozen_v1._diag_rows(diag)


def render_moneyline_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render Step-4 Moneyline presentation plus additive Step-5 raw model."""
    st.caption("🏈 COLLEGE FOOTBALL • MONEYLINE • Step 5 Moneyline Model V1 ACTIVE")
    st.markdown(frozen_v1.identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v3._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb4-shell">
  <div class="cfb4-kicker">CFB STEP 5 • MONEYLINE MODEL V1</div>
  <div class="cfb4-title">🏆 College Football Moneyline</div>
  <div class="cfb4-sub">
    Frozen schedule identity + frozen team evidence + transparent raw pre-calibration
    winner model. Step 6 still owns final calibration and fair moneyline.
  </div>
  <div class="cfb4-status">
    <span class="cfb4-pill good">ROUTE ✅</span>
    <span class="cfb4-pill good">SCHEDULE + ID ✅</span>
    <span class="cfb4-pill good">TEAM DATA ✅</span>
    <span class="cfb4-pill good">MONEYLINE UI ✅</span>
    <span class="cfb4-pill good">RAW MODEL V1 ✅</span>
    <span class="cfb4-pill wait">FINAL CALIBRATION ⏳</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_et = datetime.now(_ET).date()
    selected = st.date_input(
        "📅 CFB Moneyline slate date",
        value=today_et,
        key="cfb_step5_moneyline_date",
        help="Loads frozen NCAA schedule/team evidence and runs raw Moneyline Model V1.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )

    if not games:
        st.warning(
            "No verified FBS games were returned for this date. Moneyline Model V1 fails closed—"
            "no winner probability, score, or pick will be invented."
        )
        attempts = _diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Moneyline matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step5_moneyline_matchup_{selected_day}",
    )
    game = games[int(index)]

    profiles, team_diag = team_data.load_matchup_team_data(game, selected_day)
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(frozen_v1._moneyline_hero(game, away, home), unsafe_allow_html=True)
    st.markdown(frozen_v1._readiness_panel(game, away, home), unsafe_allow_html=True)

    output = model.project_matchup(game, away, home)
    st.session_state["cfb_moneyline_model_v1_game_id"] = str(
        game.get("game_id") or game.get("identity_key") or ""
    )
    st.session_state["cfb_moneyline_model_v1_selected"] = dict(output)

    st.markdown(_model_card(game, away, home, output), unsafe_allow_html=True)
    feature_html = _feature_panel(output)
    if feature_html:
        st.markdown(feature_html, unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">FROZEN STEP 3 EVIDENCE • MODEL INPUT AUDIT</div>
  <div class="cfb3-sub">
    Step 5 consumes these frozen profiles read-only. It does not modify their values.
  </div>
  {frozen_v3._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_v3._team_card(away)}
    {frozen_v3._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander(f"Full verified Moneyline slate • {selected_day}"):
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

    attempts = _diag_rows(team_diag)
    if attempts:
        with st.expander("Moneyline team-data provider diagnostics"):
            st.dataframe(attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 5 output is RAW / PRE-CALIBRATION. Sportsbook prices cannot influence P(win). "
        "Fair moneyline, market edge/EV, final play grading and Monte Carlo remain OFF until Step 6+."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Moneyline advances to Step 5; other CFB pages remain frozen."""
    if market != MARKET:
        return frozen_v1.render_cfb_hub(market, section_header, status_info, team_logo, h)
    return render_moneyline_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_CFB_MONEYLINE_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_feature_panel",
    "_model_card",
    "render_cfb_hub",
    "render_moneyline_hub",
]
