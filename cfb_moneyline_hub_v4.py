"""College Football Moneyline Hub V4 — full FBS slate fallback.

Additive correctness layer over permanently frozen mixed-division Hub V3.

The only runtime change is the schedule provider:
- schedule: cfb_schedule_v3
- team data: frozen hotfix cfb_team_data_v2
- model: frozen cfb_moneyline_model_v1 through Hub V2 helpers

No Step-6 calibration, fair moneyline, sportsbook edge, or Monte Carlo is
introduced here.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_moneyline_hub_v2 as frozen_step5
import cfb_moneyline_hub_v3 as frozen_hotfix
import cfb_schedule_v3 as schedule_v3
import cfb_team_data_v2 as team_data_v2

MODEL_VERSION = "CFB MONEYLINE HUB V4 • FULL FBS SLATE FALLBACK"
FROZEN_CFB_MONEYLINE_HUB = "cfb_moneyline_hub_v3"
MARKET = "Moneyline"

_ET = ZoneInfo("America/New_York")


def render_moneyline_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🛠️ CFB full-slate fallback ACTIVE • verified FBS team-directory filter • "
        "frozen Step 5 Moneyline Model V1 unchanged"
    )
    st.markdown(
        frozen_step5.frozen_v1.identity_ui._CSS,
        unsafe_allow_html=True,
    )
    st.markdown(frozen_step5.frozen_v3._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(frozen_step5.frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(frozen_step5._CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb4-shell">
  <div class="cfb4-kicker">CFB STEP 5 • MONEYLINE MODEL V1</div>
  <div class="cfb4-title">🏆 College Football Moneyline</div>
  <div class="cfb4-sub">
    Verified full FBS slate identity + frozen team evidence + transparent raw
    pre-calibration winner model. Step 6 still owns final calibration and fair moneyline.
  </div>
  <div class="cfb4-status">
    <span class="cfb4-pill good">ROUTE ✅</span>
    <span class="cfb4-pill good">FULL FBS SLATE ✅</span>
    <span class="cfb4-pill good">TEAM DATA ✅</span>
    <span class="cfb4-pill good">MIXED-DIVISION FIX ✅</span>
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
        help=(
            "Loads the verified full FBS slate, repairs eligible team evidence, "
            "and runs frozen Moneyline Model V1."
        ),
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule_v3.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_step5.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Moneyline Model V1 "
            "fails closed—no winner probability, score, or pick will be invented."
        )
        attempts = frozen_step5._diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Moneyline matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_step5.frozen_v1.identity_ui._matchup_label(
            games[int(i)]
        ),
        key=f"cfb_step5_moneyline_matchup_{selected_day}",
    )
    game = games[int(index)]

    profiles, team_diag = team_data_v2.load_matchup_team_data(
        game,
        selected_day,
    )
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(
        frozen_step5.frozen_v1._moneyline_hero(game, away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen_step5.frozen_v1._readiness_panel(game, away, home),
        unsafe_allow_html=True,
    )

    output = frozen_step5.model.project_matchup(game, away, home)
    st.session_state["cfb_moneyline_model_v1_game_id"] = str(
        game.get("game_id") or game.get("identity_key") or ""
    )
    st.session_state["cfb_moneyline_model_v1_selected"] = dict(output)

    st.markdown(
        frozen_step5._model_card(game, away, home, output),
        unsafe_allow_html=True,
    )
    feature_html = frozen_step5._feature_panel(output)
    if feature_html:
        st.markdown(feature_html, unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">FROZEN STEP 3 EVIDENCE • MODEL INPUT AUDIT</div>
  <div class="cfb3-sub">
    Full-slate repair changes schedule completeness only. Frozen Step-5 model
    math consumes these profiles read-only.
  </div>
  {frozen_step5.frozen_v3._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_step5.frozen_v3._team_card(away)}
    {frozen_step5.frozen_v3._team_card(home)}
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
                "Venue": g.get("venue"),
                "Status": g.get("status"),
                "Identity": g.get("identity_key"),
                "Source": g.get("schedule_source"),
            }
            for g in games
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    attempts = frozen_step5._diag_rows(team_diag)
    if attempts:
        with st.expander("Moneyline team-data provider diagnostics"):
            st.dataframe(attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 5 remains RAW / PRE-CALIBRATION. Sportsbook prices cannot influence P(win). "
        "Fair moneyline, market edge/EV, final play grading and Monte Carlo remain OFF until Step 6+."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        return frozen_hotfix.render_cfb_hub(
            market,
            section_header,
            status_info,
            team_logo,
            h,
        )
    return render_moneyline_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


__all__ = [
    "FROZEN_CFB_MONEYLINE_HUB",
    "MARKET",
    "MODEL_VERSION",
    "render_cfb_hub",
    "render_moneyline_hub",
]
