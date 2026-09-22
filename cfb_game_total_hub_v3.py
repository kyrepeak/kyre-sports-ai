"""College Football Game Total Hub V3 — Step 12 final synthesis + Top-5.

Additive UI over permanently frozen Step-11 Game Total Hub V2.

Step 12 completes the College Football Game Total section with:
- final forecast qualification,
- transparent grade/tier,
- strongest total range summary,
- full-slate scan,
- Top-5 Game Total forecasts ranked by forecast strength.

This remains an independent forecast page, not a sportsbook betting-pick layer.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_final_v1 as final_model
import cfb_game_total_hub_v2 as frozen_v2
import cfb_game_total_slate_v1 as slate

MODEL_VERSION = "CFB GAME TOTAL HUB V3 • STEP 12 FINAL"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v2"
MARKET = "Game Total"

_CSS = r"""
<style>
.cfb12-shell{border:1px solid rgba(255,196,92,.30);border-radius:17px;
background:linear-gradient(145deg,#231809,#111620);padding:14px;margin-top:8px}
.cfb12-kicker{color:#ffd17a;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb12-title{color:#fff8ea;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb12-sub{color:#b6a78b;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb12-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb12-pill{border:1px solid #6a5534;border-radius:999px;background:#2a1d0d;color:#e6c989;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb12-pill.good{border-color:#326a55;background:#09251c;color:#86e6b8}
.cfb12-final{margin-top:11px;border:1px solid rgba(255,196,92,.23);border-radius:16px;
background:linear-gradient(145deg,#20180d,#101821);overflow:hidden}
.cfb12-head{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:10px 11px;border-bottom:1px solid rgba(255,196,92,.13)}
.cfb12-head b{color:#ffd17a;font-size:.51rem;letter-spacing:.08em}
.cfb12-lock{border:1px solid #277353;border-radius:999px;background:#0b2d22;color:#84e7b6;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb12-main{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);gap:8px;padding:11px}
.cfb12-pick{border:1px solid rgba(255,196,92,.17);border-radius:13px;background:#21180c;padding:11px}
.cfb12-pick small,.cfb12-grade small{display:block;color:#a89270;font-size:.43rem;text-transform:uppercase;font-weight:900}
.cfb12-pick strong{display:block;color:#ffe19d;font-size:1.65rem;margin-top:4px}
.cfb12-pick b{display:block;color:#e9d5aa;font-size:.60rem;margin-top:4px}
.cfb12-grade{border:1px solid rgba(126,231,180,.18);border-radius:13px;background:#071912;padding:11px}
.cfb12-grade strong{display:block;color:#88ebba;font-size:1.25rem;margin-top:4px}
.cfb12-grade b{display:block;color:#c5e6d2;font-size:.57rem;margin-top:4px}
.cfb12-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 11px 11px}
.cfb12-metric{border:1px solid rgba(255,196,92,.12);border-radius:9px;background:#20190e;padding:7px}
.cfb12-metric b{display:block;color:#f4ead4;font-size:.64rem}.cfb12-metric span{display:block;
color:#a08e6f;font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb12-note{border-top:1px solid rgba(255,196,92,.10);padding:9px 11px;color:#98896f;
font-size:.44rem;line-height:1.5}
.cfb12-top{margin-top:8px;border:1px solid rgba(126,231,180,.18);border-radius:11px;background:#071a14;padding:9px}
.cfb12-top-head{display:flex;justify-content:space-between;gap:7px;align-items:center}
.cfb12-rank{color:#ffd17a;font-size:.48rem;font-weight:950}
.cfb12-team{color:#f0faf5;font-size:.78rem;font-weight:950}
.cfb12-score{color:#89edbb;font-size:.78rem;font-weight:950}
.cfb12-meta{color:#759081;font-size:.43rem;margin-top:4px;line-height:1.45}
.cfb12-pass{margin-top:10px;border:1px solid #6e5a1d;border-radius:13px;background:#2d260d;padding:10px}
.cfb12-pass b{display:block;color:#f4da78;font-size:.57rem}.cfb12-pass span{display:block;
color:#b9a963;font-size:.48rem;line-height:1.45;margin-top:3px}
@media(max-width:760px){
.cfb12-main{grid-template-columns:1fr}.cfb12-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.cfb12-title{font-size:1.20rem}}
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


def _final_card(game: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not final.get("ready"):
        reasons = " • ".join(
            escape(str(x))
            for x in final.get("reasons") or ["Step 12 final synthesis unavailable"]
        )
        return f"""
<div class="cfb12-pass">
  <b>STEP 12 FINAL GAME TOTAL GATED</b>
  <span>{reasons}. No final Game Total forecast is invented.</span>
</div>
"""

    matchup = escape(
        f"{game.get('away_team') or 'Away'} @ {game.get('home_team') or 'Home'}"
    )
    status = escape(str(final.get("forecast_status") or "PASS"))
    grade = escape(str(final.get("grade") or "PASS"))
    tier = escape(str(final.get("tier") or "NO RANK"))
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    i80 = final.get("structural_interval_80") or {}

    return f"""
<div class="cfb12-final">
  <div class="cfb12-head">
    <b>STEP 12 • FINAL GAME TOTAL FORECAST</b>
    <span class="cfb12-lock">CFB COMPLETE ✅</span>
  </div>
  <div class="cfb12-main">
    <div class="cfb12-pick">
      <small>{matchup} • {status}</small>
      <strong>{_num(final.get('projected_combined_total'))}</strong>
      <b>Core 50% range {int(core.get('low') or 0)}–{int(core.get('high') or 0)}</b>
    </div>
    <div class="cfb12-grade">
      <small>Forecast grade / tier</small>
      <strong>{grade}</strong>
      <b>{tier}</b>
    </div>
  </div>
  <div class="cfb12-grid">
    <div class="cfb12-metric"><b>{int(final.get('median_total') or 0)}</b><span>Median total</span></div>
    <div class="cfb12-metric"><b>{int(final.get('mode_total') or 0)}</b><span>Mode total</span></div>
    <div class="cfb12-metric"><b>{escape(str(band.get('label') or '—'))}</b><span>Most likely band</span></div>
    <div class="cfb12-metric"><b>{_pct(band.get('probability'))}</b><span>Band probability</span></div>
    <div class="cfb12-metric"><b>{int(i80.get('low') or 0)}–{int(i80.get('high') or 0)}</b><span>Structural 80%</span></div>
    <div class="cfb12-metric"><b>{_pct(final.get('within_7_probability'))}</b><span>Within ±7</span></div>
    <div class="cfb12-metric"><b>{_pct(final.get('reliability'))}</b><span>Reliability</span></div>
    <div class="cfb12-metric"><b>{_pct(final.get('forecast_strength'))}</b><span>Forecast strength</span></div>
  </div>
  <div class="cfb12-note">
    Final Game Total means the model's strongest independent combined-score forecast,
    not a sportsbook bet. No betting line, price, market probability, EV, or Monte Carlo
    is used anywhere in this final layer.
  </div>
</div>
"""


def _top_card(row: Mapping[str, Any]) -> str:
    game = row.get("game") or {}
    final = row.get("final") or {}
    matchup = escape(
        f"{game.get('away_team') or 'Away'} @ {game.get('home_team') or 'Home'}"
    )
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    return f"""
<div class="cfb12-top">
  <div class="cfb12-top-head">
    <div>
      <span class="cfb12-rank">#{int(row.get('rank') or 0)} • GRADE {escape(str(final.get('grade') or '—'))}</span>
      <div class="cfb12-team">{matchup}</div>
    </div>
    <div class="cfb12-score">{_num(final.get('projected_combined_total'))}</div>
  </div>
  <div class="cfb12-meta">
    strength {_pct(final.get('forecast_strength'))} • core {int(core.get('low') or 0)}–{int(core.get('high') or 0)} •
    band {escape(str(band.get('label') or '—'))} ({_pct(band.get('probability'))}) •
    reliability {_pct(final.get('reliability'))}
  </div>
</div>
"""


def render_game_total_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🏈 COLLEGE FOOTBALL • GAME TOTAL • Step 12 FINAL • "
        "independent forecast • sportsbook influence 0%"
    )
    st.markdown(frozen_v2.frozen_v1.identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v2.frozen_v1.team_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(frozen_v2.frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v2._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb12-shell">
  <div class="cfb12-kicker">CFB STEP 12 • FINAL GAME TOTAL SYNTHESIS</div>
  <div class="cfb12-title">🏁 College Football Game Total — Final</div>
  <div class="cfb12-sub">
    Frozen Step-11 distribution + final forecast qualification + grade/tier +
    full-slate Top-5 ranking. This completes the College Football build.
  </div>
  <div class="cfb12-status">
    <span class="cfb12-pill good">FINAL FORECAST ✅</span>
    <span class="cfb12-pill good">CORE RANGE ✅</span>
    <span class="cfb12-pill good">GRADE / TIER ✅</span>
    <span class="cfb12-pill good">TOP-5 ✅</span>
    <span class="cfb12-pill good">SPORTSBOOK 0% ✅</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=frozen_v2.frozen_v1.datetime.now(frozen_v2.frozen_v1._ET).date(),
        key="cfb_step12_game_total_date",
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
            "No verified FBS-scoped games were returned for this date. Step 12 fails "
            "closed—no final forecast or ranking is invented."
        )
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_v2.frozen_v1.identity_ui._matchup_label(
            games[int(i)]
        ),
        key=f"cfb_step12_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    selected_result = slate.analyze_game(game, selected_day)
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
        frozen_v2.frozen_v1._environment_panel(away, home),
        unsafe_allow_html=True,
    )
    st.markdown(frozen_v2._distribution_card(raw), unsafe_allow_html=True)
    st.markdown(_final_card(game, final), unsafe_allow_html=True)

    for panel in (
        frozen_v2._band_panel(raw),
        frozen_v2._around_projection_panel(raw),
        frozen_v2._exact_panel(raw),
        frozen_v2._components_panel(raw),
    ):
        if panel:
            st.markdown(panel, unsafe_allow_html=True)

    scan_key = f"cfb_step12_top5_{selected_day}"
    diag_key = f"cfb_step12_scan_diag_{selected_day}"

    if st.button(
        "Run final Game Total Top-5 scan",
        type="primary",
        key=f"cfb_step12_scan_button_{selected_day}",
    ):
        with st.spinner("Scanning the verified CFB slate through Steps 11–12..."):
            rows, diag = slate.scan_slate(games, selected_day)
            st.session_state[scan_key] = final_model.rank_slate(rows, limit=5)
            st.session_state[diag_key] = diag

    top5 = st.session_state.get(scan_key) or []
    diag = st.session_state.get(diag_key) or {}

    if diag:
        st.caption(
            f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • "
            f"{int(diag.get('final_ready') or 0)} final-ready • "
            f"{int(diag.get('qualified_forecasts') or 0)} ranked-eligible • "
            f"{len(diag.get('errors') or [])} errors"
        )

    if top5:
        st.markdown("### 🏆 Top-5 Game Total Forecasts")
        for row in top5:
            st.markdown(_top_card(row), unsafe_allow_html=True)
    elif diag:
        st.warning(
            "No game cleared the Step-12 forecast qualification thresholds. "
            "The system will not force a Top-5."
        )
    else:
        st.caption(
            "Run the final slate scan to rank the strongest qualified Game Total forecasts."
        )

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">CERTIFIED TEAM EVIDENCE • FINAL CFB AUDIT</div>
  <div class="cfb3-sub">
    Step 12 only synthesizes and ranks frozen Step-11 outputs. Moneyline and
    Over/Under remain permanently frozen and unchanged.
  </div>
  {frozen_v2.frozen_v1.team_ui._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_v2.frozen_v1.team_ui._team_card(away)}
    {frozen_v2.frozen_v1.team_ui._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.success(
        "🏁 College Football Steps 1–12 are complete. Moneyline, Over/Under, "
        "and Game Total are all finished under additive freeze protection."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Step 12 Game Total hub received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_final_card",
    "_top_card",
    "render_cfb_hub",
    "render_game_total_hub",
]
