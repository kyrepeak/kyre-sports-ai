"""College Football Moneyline Hub V5 — Step 6 final synthesis.

Additive UI over permanently frozen NCAA-scoreboard Hub V4 and frozen Step-5
Moneyline Model V1.

Step 6 activates:
- final structural-calibration P(win),
- fair model moneyline,
- structural uncertainty,
- model grade/tier,
- full-slate Top-5 Moneyline ranking on demand.

Sportsbook prices remain exactly 0% of model probability.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_moneyline_final_v1 as final_model
import cfb_moneyline_hub_v4 as prior
import cfb_moneyline_slate_v1 as slate
import cfb_schedule_v3 as schedule_v3

MODEL_VERSION = "CFB MONEYLINE HUB V5 • STEP 6 FINAL SYNTHESIS"
FROZEN_CFB_MONEYLINE_HUB = "cfb_moneyline_hub_v4"
MARKET = "Moneyline"

_ET = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.cfb6-card{margin-top:11px;border:1px solid rgba(76,220,157,.34);border-radius:17px;
background:linear-gradient(145deg,#061812,#071421);overflow:hidden}
.cfb6-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 11px;
border-bottom:1px solid rgba(76,220,157,.17)}
.cfb6-head span{color:#80e6b6;font-size:.50rem;font-weight:950;letter-spacing:.09em}
.cfb6-final{border:1px solid #2c7c59;border-radius:999px;background:#0a2e22;color:#8bf0bf;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb6-main{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,.9fr);gap:8px;padding:11px}
.cfb6-winner{border:1px solid rgba(76,220,157,.17);border-radius:13px;background:#071b14;padding:11px}
.cfb6-winner small{display:block;color:#6f9b85;font-size:.43rem;text-transform:uppercase;font-weight:900}
.cfb6-winner b{display:block;color:#eefbf4;font-size:1.13rem;margin-top:3px}
.cfb6-winner strong{display:block;color:#8ce9ba;font-size:1.52rem;margin-top:5px}
.cfb6-grade{border:1px solid rgba(103,179,222,.20);border-radius:13px;background:#081823;padding:11px}
.cfb6-grade small{display:block;color:#7693a3;font-size:.43rem;text-transform:uppercase;font-weight:900}
.cfb6-grade b{display:block;color:#eef7fb;font-size:1.18rem;margin-top:3px}
.cfb6-grade strong{display:block;color:#78dbff;font-size:.68rem;margin-top:4px}
.cfb6-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 11px 11px}
.cfb6-metric{border:1px solid rgba(91,147,177,.18);border-radius:9px;background:#081722;padding:7px}
.cfb6-metric b{display:block;color:#e3edf3;font-size:.62rem}.cfb6-metric span{display:block;
color:#758e9d;font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb6-note{border-top:1px solid rgba(76,220,157,.13);padding:9px 11px;color:#729082;
font-size:.44rem;line-height:1.5}
.cfb6-scan{margin-top:12px;border:1px solid rgba(92,170,218,.23);border-radius:15px;background:#071520;padding:11px}
.cfb6-scan-title{color:#75d9ff;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfb6-scan-sub{color:#7894a5;font-size:.46rem;line-height:1.45;margin-top:3px}
.cfb6-top{margin-top:7px;border:1px solid rgba(76,220,157,.18);border-radius:11px;background:#071a14;padding:9px}
.cfb6-top-head{display:flex;justify-content:space-between;gap:7px;align-items:center}
.cfb6-top-rank{color:#74dcff;font-size:.48rem;font-weight:950}.cfb6-top-team{color:#f0faf5;font-size:.78rem;font-weight:950}
.cfb6-top-prob{color:#89edbb;font-size:.78rem;font-weight:950}.cfb6-top-meta{color:#759081;font-size:.43rem;margin-top:4px}
@media(max-width:760px){
  .cfb6-main{grid-template-columns:1fr}.cfb6-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
</style>
"""


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _odds(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except Exception:
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    try:
        x = float(value)
    except Exception:
        return "—"
    prefix = "+" if signed and x > 0 else ""
    return f"{prefix}{x:.{digits}f}"


def _final_card(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    if not final.get("ready"):
        reasons = " • ".join(str(x) for x in final.get("reasons") or ["final synthesis unavailable"])
        return f"""
<div class="cfb5-gated">
  <b>STEP 6 FINAL SYNTHESIS GATED</b>
  <span>{escape(reasons)}. Fair model odds and final ranking are not invented.</span>
</div>
"""

    winner = escape(str(final.get("winner_team") or "—"))
    winner_p = _pct(final.get("winner_probability_final"))
    grade = escape(str(final.get("model_grade") or "PASS"))
    tier = escape(str(final.get("model_tier") or "PASS"))

    away_name = escape(str(away.get("team") or game.get("away_team") or "Away"))
    home_name = escape(str(home.get("team") or game.get("home_team") or "Home"))

    home_unc = final.get("home_probability_uncertainty") or {}
    margin_unc = final.get("margin_uncertainty") or {}

    return f"""
<div class="cfb6-card">
  <div class="cfb6-head">
    <span>STEP 6 • FINAL MONEYLINE SYNTHESIS</span>
    <b class="cfb6-final">FINAL MODEL ✅</b>
  </div>
  <div class="cfb6-main">
    <div class="cfb6-winner">
      <small>Final model winner • price-independent</small>
      <b>{winner}</b>
      <strong>{winner_p}</strong>
    </div>
    <div class="cfb6-grade">
      <small>Model grade</small>
      <b>{grade}</b>
      <strong>{tier}</strong>
    </div>
  </div>
  <div class="cfb6-grid">
    <div class="cfb6-metric"><b>{_pct(final.get('away_win_probability_final'))}</b><span>{away_name} final P(win)</span></div>
    <div class="cfb6-metric"><b>{_pct(final.get('home_win_probability_final'))}</b><span>{home_name} final P(win)</span></div>
    <div class="cfb6-metric"><b>{_odds(final.get('away_fair_moneyline'))}</b><span>{away_name} fair ML</span></div>
    <div class="cfb6-metric"><b>{_odds(final.get('home_fair_moneyline'))}</b><span>{home_name} fair ML</span></div>
    <div class="cfb6-metric"><b>{_num(final.get('projected_away_points'))} – {_num(final.get('projected_home_points'))}</b><span>Projected score • A-H</span></div>
    <div class="cfb6-metric"><b>{_num(final.get('projected_margin_home'), signed=True)}</b><span>Projected home margin</span></div>
    <div class="cfb6-metric"><b>{_pct(home_unc.get('p90_low'))}–{_pct(home_unc.get('p90_high'))}</b><span>Home P(win) structural 90%</span></div>
    <div class="cfb6-metric"><b>{_num(margin_unc.get('margin90_low'), signed=True)} to {_num(margin_unc.get('margin90_high'), signed=True)}</b><span>Margin structural 90%</span></div>
    <div class="cfb6-metric"><b>{_pct(final.get('reliability'))}</b><span>Reliability</span></div>
    <div class="cfb6-metric"><b>{_pct(final.get('feature_coverage'))}</b><span>Feature coverage</span></div>
    <div class="cfb6-metric"><b>{_num(final.get('calibration_temperature'), 2)}</b><span>Calibration temperature</span></div>
    <div class="cfb6-metric"><b>0%</b><span>Sportsbook probability weight</span></div>
  </div>
  <div class="cfb6-note">
    Calibration is structural reliability/coverage shrink — not sportsbook fitting and not
    claimed historical empirical calibration. Fair ML is derived only from final model P(win).
  </div>
</div>
"""


def _top_game_card(row: Mapping[str, Any]) -> str:
    game = row.get("game") or {}
    final = row.get("final") or {}
    winner = escape(str(final.get("winner_team") or "—"))
    matchup = escape(f"{game.get('away_team')} @ {game.get('home_team')}")
    grade = escape(str(final.get("model_grade") or "PASS"))
    fair = (
        final.get("home_fair_moneyline")
        if final.get("winner_side") == "home"
        else final.get("away_fair_moneyline")
    )
    score = f"{_num(final.get('projected_away_points'))}-{_num(final.get('projected_home_points'))}"

    return f"""
<div class="cfb6-top">
  <div class="cfb6-top-head">
    <div><span class="cfb6-top-rank">#{int(row.get('rank') or 0)} • {grade}</span>
    <div class="cfb6-top-team">{winner}</div></div>
    <div class="cfb6-top-prob">{_pct(final.get('winner_probability_final'))}</div>
  </div>
  <div class="cfb6-top-meta">
    {matchup} • fair ML {_odds(fair)} • projected {score} •
    reliability {_pct(final.get('reliability'))} • coverage {_pct(final.get('feature_coverage'))}
  </div>
</div>
"""


def render_moneyline_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🏁 COLLEGE FOOTBALL • MONEYLINE • Step 6 final synthesis ACTIVE • "
        "sportsbook probability weight 0%"
    )
    st.markdown(
        prior.frozen_step5.frozen_v1.identity_ui._CSS,
        unsafe_allow_html=True,
    )
    st.markdown(prior.frozen_step5.frozen_v3._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(prior.frozen_step5.frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(prior.frozen_step5._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb4-shell">
  <div class="cfb4-kicker">CFB STEP 6 • MONEYLINE FINAL SYNTHESIS</div>
  <div class="cfb4-title">🏆 College Football Moneyline</div>
  <div class="cfb4-sub">
    Complete NCAA slate + frozen Step-5 raw model + structural final calibration,
    fair model moneyline, uncertainty and Top-5 slate ranking.
  </div>
  <div class="cfb4-status">
    <span class="cfb4-pill good">SCHEDULE ✅</span>
    <span class="cfb4-pill good">TEAM DATA ✅</span>
    <span class="cfb4-pill good">RAW MODEL V1 ✅</span>
    <span class="cfb4-pill good">FINAL P(WIN) ✅</span>
    <span class="cfb4-pill good">FAIR ML ✅</span>
    <span class="cfb4-pill good">TOP-5 ✅</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_et = datetime.now(_ET).date()
    selected = st.date_input(
        "📅 CFB Moneyline slate date",
        value=today_et,
        key="cfb_step6_moneyline_date",
        help="Loads the current NCAA FBS date-scoped scoreboard and Step-6 final synthesis.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule_v3.load_with_diagnostics(selected_day)
    st.markdown(
        prior.frozen_step5.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Step 6 fails closed—"
            "no final probability, fair odds, ranking, or pick will be invented."
        )
        attempts = prior.frozen_step5._diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Moneyline matchup",
        options=list(range(len(games))),
        format_func=lambda i: prior.frozen_step5.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step6_moneyline_matchup_{selected_day}",
    )
    game = games[int(index)]

    selected_result = slate.analyze_game(game, selected_day)
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}

    st.markdown(
        prior.frozen_step5.frozen_v1._moneyline_hero(game, away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        prior.frozen_step5.frozen_v1._readiness_panel(game, away, home),
        unsafe_allow_html=True,
    )
    st.markdown(
        prior.frozen_step5._model_card(game, away, home, raw),
        unsafe_allow_html=True,
    )
    st.markdown(_final_card(game, away, home, final), unsafe_allow_html=True)

    st.session_state["cfb_moneyline_final_v1_game_id"] = str(
        game.get("identity_key") or game.get("game_id") or ""
    )
    st.session_state["cfb_moneyline_final_v1_selected"] = dict(final)

    feature_html = prior.frozen_step5._feature_panel(raw)
    if feature_html:
        st.markdown(feature_html, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb6-scan">
  <div class="cfb6-scan-title">🏆 FULL-SLATE TOP-5 MONEYLINE SCANNER</div>
  <div class="cfb6-scan-sub">
    Runs every verified game through the same frozen Step-5 raw model and Step-6
    final synthesis. Ranking is pure final win probability — sportsbook price is not used.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    scan_key = f"cfb_step6_top5_{selected_day}"
    scan_diag_key = f"cfb_step6_top5_diag_{selected_day}"

    if st.button(
        f"Run full {len(games)}-game Moneyline scan",
        key=f"cfb_step6_scan_button_{selected_day}",
        type="primary",
    ):
        with st.spinner(
            f"Analyzing {len(games)} verified games through Moneyline Model V1 + Step 6..."
        ):
            rows, scan_diag = slate.scan_slate(games, selected_day)
            st.session_state[scan_key] = final_model.rank_slate(rows, limit=5)
            st.session_state[scan_diag_key] = scan_diag

    top5 = st.session_state.get(scan_key) or []
    scan_diag = st.session_state.get(scan_diag_key) or {}

    if top5:
        st.caption(
            f"Scanner: {int(scan_diag.get('games_ready') or 0)} model-ready • "
            f"{int(scan_diag.get('games_gated') or 0)} gated • "
            f"{len(scan_diag.get('errors') or [])} errors"
        )
        for row in top5:
            st.markdown(_top_game_card(row), unsafe_allow_html=True)
    else:
        st.caption("Top-5 is generated only after you run the full-slate scan.")

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">FROZEN TEAM EVIDENCE • FINAL MODEL AUDIT</div>
  <div class="cfb3-sub">
    Step 6 does not alter Step-5 feature inputs. It calibrates the frozen raw probability
    conservatively and produces fair model odds/ranking.
  </div>
  {prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {prior.frozen_step5.frozen_v3._team_card(away)}
    {prior.frozen_step5.frozen_v3._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.info(
        "Step 6 is the final College Football Moneyline synthesis. Sportsbook prices have "
        "0% probability weight. Fair moneyline is model-derived; calibration is structural, "
        "not claimed historical empirical calibration."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        return prior.render_cfb_hub(
            market,
            section_header,
            status_info,
            team_logo,
            h,
        )
    return render_moneyline_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_CFB_MONEYLINE_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_final_card",
    "_top_game_card",
    "render_cfb_hub",
    "render_moneyline_hub",
]
