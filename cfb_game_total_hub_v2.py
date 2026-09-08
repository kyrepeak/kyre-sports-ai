"""College Football Game Total Hub V2 — Step 11 distribution model.

Additive UI over permanently frozen Step-10 Game Total foundation.

Step 11 activates:
- independent projected combined score,
- discrete integer total distribution,
- median and mode,
- exact-total probabilities,
- standard total-band probabilities,
- percentile totals,
- structural 80% / 90% uncertainty ranges,
- reliability / feature coverage / model confidence.

Sportsbook totals/prices, market probabilities, edge/EV, final picks, slate
ranking, and Monte Carlo remain OFF. Step 12 owns final Game Total synthesis
and ranking.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_hub_v1 as frozen_v1
import cfb_game_total_model_v1 as model

MODEL_VERSION = "CFB GAME TOTAL HUB V2 • STEP 11 DISTRIBUTION"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v1"
MARKET = "Game Total"

_CSS = r"""
<style>
.cfb11-shell{border:1px solid rgba(167,128,255,.30);border-radius:17px;
background:linear-gradient(145deg,#14102a,#0b1725);padding:14px;margin-top:8px}
.cfb11-kicker{color:#bda5ff;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb11-title{color:#f8f5ff;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb11-sub{color:#a49ab8;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb11-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb11-pill{border:1px solid #514674;border-radius:999px;background:#1a1530;color:#c0b3de;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb11-pill.good{border-color:#326a55;background:#09251c;color:#86e6b8}
.cfb11-pill.wait{border-color:#62511f;background:#2b250c;color:#e6cf78}
.cfb11-model{margin-top:11px;border:1px solid rgba(167,128,255,.25);border-radius:16px;
background:linear-gradient(145deg,#11102a,#0b1722);overflow:hidden}
.cfb11-head{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:10px 11px;border-bottom:1px solid rgba(167,128,255,.14)}
.cfb11-head b{color:#bda5ff;font-size:.51rem;letter-spacing:.08em}
.cfb11-raw{border:1px solid #665696;border-radius:999px;background:#21183d;color:#d0c1ff;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb11-main{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);gap:8px;padding:11px}
.cfb11-total{border:1px solid rgba(167,128,255,.17);border-radius:13px;background:#17142d;padding:11px}
.cfb11-total small,.cfb11-shape small{display:block;color:#958aa8;font-size:.43rem;text-transform:uppercase;font-weight:900}
.cfb11-total strong{display:block;color:#e9ddff;font-size:1.72rem;margin-top:4px}
.cfb11-total b{display:block;color:#c8bdd8;font-size:.57rem;margin-top:4px}
.cfb11-shape{border:1px solid rgba(126,231,180,.18);border-radius:13px;background:#071912;padding:11px}
.cfb11-shape strong{display:block;color:#88ebba;font-size:1.15rem;margin-top:4px}
.cfb11-shape b{display:block;color:#b8d8c6;font-size:.55rem;margin-top:4px}
.cfb11-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 11px 11px}
.cfb11-metric{border:1px solid rgba(167,128,255,.13);border-radius:9px;background:#17142a;padding:7px}
.cfb11-metric b{display:block;color:#efe8fb;font-size:.65rem}.cfb11-metric span{display:block;
color:#998fa7;font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb11-note{border-top:1px solid rgba(167,128,255,.11);padding:9px 11px;color:#8d849b;
font-size:.44rem;line-height:1.5}
.cfb11-panel{margin-top:10px;border:1px solid rgba(167,128,255,.17);border-radius:14px;background:#111326;padding:10px}
.cfb11-panel-title{color:#bda5ff;font-size:.51rem;font-weight:950;letter-spacing:.08em}
.cfb11-panel-sub{color:#9189a0;font-size:.44rem;line-height:1.45;margin-top:3px}
.cfb11-band-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:8px}
.cfb11-band{border:1px solid rgba(167,128,255,.12);border-radius:9px;background:#17152b;padding:7px}
.cfb11-band b{display:block;color:#eee5ff;font-size:.65rem}.cfb11-band span{display:block;color:#988da8;
font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb11-exact-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;margin-top:8px}
.cfb11-exact{border:1px solid rgba(126,231,180,.12);border-radius:9px;background:#0a1914;padding:7px}
.cfb11-exact b{display:block;color:#8cebbc;font-size:.65rem}.cfb11-exact span{display:block;color:#789687;
font-size:.40rem;text-transform:uppercase;margin-top:2px}
.cfb11-gated{margin-top:10px;border:1px solid #743a34;border-radius:13px;background:#301510;padding:10px}
.cfb11-gated b{display:block;color:#ffb0a8;font-size:.57rem}.cfb11-gated span{display:block;
color:#c78982;font-size:.48rem;line-height:1.45;margin-top:3px}
@media(max-width:760px){
  .cfb11-main{grid-template-columns:1fr}.cfb11-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb11-band-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb11-exact-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb11-title{font-size:1.20rem}
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


def _distribution_card(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        reasons = " • ".join(
            escape(str(x))
            for x in output.get("reasons") or ["Step 11 distribution unavailable"]
        )
        return f"""
<div class="cfb11-gated">
  <b>STEP 11 GAME TOTAL MODEL GATED</b>
  <span>{reasons}. No projected combined total or probability distribution is invented.</span>
</div>
"""

    p = output.get("percentiles") or {}
    i80 = output.get("structural_interval_80") or {}
    i90 = output.get("structural_interval_90") or {}

    return f"""
<div class="cfb11-model">
  <div class="cfb11-head">
    <b>STEP 11 • GAME TOTAL DISTRIBUTION V1</b>
    <span class="cfb11-raw">ANALYTIC DISTRIBUTION • NOT FINAL RANKING</span>
  </div>
  <div class="cfb11-main">
    <div class="cfb11-total">
      <small>Projected combined score</small>
      <strong>{_num(output.get('projected_combined_total'))}</strong>
      <b>structural sigma {_num(output.get('structural_total_sigma'), 2)}</b>
    </div>
    <div class="cfb11-shape">
      <small>Distribution center</small>
      <strong>Median {int(output.get('median_total') or 0)} • Mode {int(output.get('mode_total') or 0)}</strong>
      <b>Mode exact-total probability {_pct(output.get('mode_probability'))}</b>
    </div>
  </div>
  <div class="cfb11-grid">
    <div class="cfb11-metric"><b>{int(p.get('p10') or 0)}</b><span>P10 total</span></div>
    <div class="cfb11-metric"><b>{int(p.get('p25') or 0)}</b><span>P25 total</span></div>
    <div class="cfb11-metric"><b>{int(p.get('p75') or 0)}</b><span>P75 total</span></div>
    <div class="cfb11-metric"><b>{int(p.get('p90') or 0)}</b><span>P90 total</span></div>
    <div class="cfb11-metric"><b>{int(i80.get('low') or 0)}–{int(i80.get('high') or 0)}</b><span>Structural 80%</span></div>
    <div class="cfb11-metric"><b>{int(i90.get('low') or 0)}–{int(i90.get('high') or 0)}</b><span>Structural 90%</span></div>
    <div class="cfb11-metric"><b>{_pct(output.get('reliability'))}</b><span>Reliability</span></div>
    <div class="cfb11-metric"><b>{escape(str(output.get('confidence') or 'LOW'))}</b><span>Model confidence</span></div>
  </div>
  <div class="cfb11-note">
    This is an independent Game Total distribution with no sportsbook line or price.
    Uncertainty is structural and is not claimed as historical empirical calibration.
    Step 12 owns final synthesis and slate ranking.
  </div>
</div>
"""


def _band_panel(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        return ""
    bands = output.get("standard_bands") or []
    cards = "".join(
        f'<div class="cfb11-band"><b>{_pct(row.get("probability"))}</b>'
        f'<span>Total {escape(str(row.get("label") or "—"))}</span></div>'
        for row in bands
    )
    return f"""
<div class="cfb11-panel">
  <div class="cfb11-panel-title">STANDARD TOTAL-BAND PROBABILITIES</div>
  <div class="cfb11-panel-sub">
    Distribution mass across fixed combined-score ranges. These are model probabilities,
    not sportsbook Over/Under prices.
  </div>
  <div class="cfb11-band-grid">{cards}</div>
</div>
"""


def _around_projection_panel(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        return ""
    around = output.get("around_projection") or {}
    cards = []
    for key, label in (
        ("within_3", "Within ±3"),
        ("within_7", "Within ±7"),
        ("within_10", "Within ±10"),
    ):
        item = around.get(key) or {}
        cards.append(
            f'<div class="cfb11-band"><b>{_pct(item.get("probability"))}</b>'
            f'<span>{label} • {int(item.get("low") or 0)}–{int(item.get("high") or 0)}</span></div>'
        )
    return f"""
<div class="cfb11-panel">
  <div class="cfb11-panel-title">PROBABILITY AROUND PROJECTED TOTAL</div>
  <div class="cfb11-panel-sub">
    Probability that the integer combined score lands near the Step-11 projection.
  </div>
  <div class="cfb11-band-grid">{''.join(cards)}</div>
</div>
"""


def _exact_panel(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        return ""
    rows = output.get("top_exact_totals") or []
    cards = "".join(
        f'<div class="cfb11-exact"><b>{int(row.get("total") or 0)}</b>'
        f'<span>{_pct(row.get("probability"))} exact</span></div>'
        for row in rows
    )
    return f"""
<div class="cfb11-panel">
  <div class="cfb11-panel-title">MOST LIKELY EXACT COMBINED TOTALS</div>
  <div class="cfb11-panel-sub">
    Highest-probability integer totals from the full discrete structural distribution.
  </div>
  <div class="cfb11-exact-grid">{cards}</div>
</div>
"""


def _components_panel(output: Mapping[str, Any]) -> str:
    if not output.get("ready"):
        return ""
    c = output.get("components") or {}
    coverage = output.get("feature_coverage") or {}
    return f"""
<div class="cfb11-panel">
  <div class="cfb11-panel-title">STEP 11 MODEL COMPONENT AUDIT</div>
  <div class="cfb11-band-grid">
    <div class="cfb11-band"><b>{_num(c.get('away_base_points'))}</b><span>Away base points</span></div>
    <div class="cfb11-band"><b>{_num(c.get('home_base_points'))}</b><span>Home base points</span></div>
    <div class="cfb11-band"><b>{_num(c.get('base_combined_total'))}</b><span>Base combined total</span></div>
    <div class="cfb11-band"><b>{_num(c.get('recent_total_adjustment'), 2)}</b><span>Recent total adj</span></div>
    <div class="cfb11-band"><b>{_num(c.get('efficiency_total_adjustment'), 2)}</b><span>Efficiency total adj</span></div>
    <div class="cfb11-band"><b>{_pct(coverage.get('score'))}</b><span>Feature coverage</span></div>
    <div class="cfb11-band"><b>{_pct(output.get('sample_factor'))}</b><span>Sample factor</span></div>
  </div>
</div>
"""


def _distribution_rows(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Combined Total": int(row.get("total") or 0),
            "Probability": float(row.get("probability") or 0.0),
            "Probability %": round(100.0 * float(row.get("probability") or 0.0), 3),
        }
        for row in output.get("distribution") or []
        if float(row.get("probability") or 0.0) >= 0.0001
    ]


def render_game_total_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption(
        "🏈 COLLEGE FOOTBALL • GAME TOTAL • Step 11 distribution model ACTIVE • "
        "sportsbook input 0%"
    )
    st.markdown(frozen_v1.identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v1.team_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(frozen_v1._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb11-shell">
  <div class="cfb11-kicker">CFB STEP 11 • GAME TOTAL DISTRIBUTION V1</div>
  <div class="cfb11-title">🧮 College Football Game Total</div>
  <div class="cfb11-sub">
    Frozen Step-10 foundation + independent projected combined score + full integer
    total distribution, percentiles, bands, and structural uncertainty.
  </div>
  <div class="cfb11-status">
    <span class="cfb11-pill good">PROJECTED TOTAL ✅</span>
    <span class="cfb11-pill good">MEDIAN / MODE ✅</span>
    <span class="cfb11-pill good">EXACT TOTALS ✅</span>
    <span class="cfb11-pill good">BANDS ✅</span>
    <span class="cfb11-pill good">PERCENTILES ✅</span>
    <span class="cfb11-pill good">UNCERTAINTY ✅</span>
    <span class="cfb11-pill wait">FINAL / RANKING ⏳ STEP 12</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=frozen_v1.datetime.now(frozen_v1._ET).date(),
        key="cfb_step11_game_total_date",
        help="Loads the certified NCAA scoreboard and frozen Step-10 foundation.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Step 11 fails "
            "closed—no projected combined score or distribution is invented."
        )
        attempts = frozen_v1._diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step11_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    profiles, team_diag = frozen_v1.team_data.load_matchup_team_data(
        game,
        selected_day,
    )
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(frozen_v1._hero(game, away, home), unsafe_allow_html=True)
    st.markdown(frozen_v1._readiness_panel(game, away, home), unsafe_allow_html=True)
    st.markdown(frozen_v1._environment_panel(away, home), unsafe_allow_html=True)

    output = model.project_distribution(game, away, home)
    st.markdown(_distribution_card(output), unsafe_allow_html=True)

    for panel in (
        _band_panel(output),
        _around_projection_panel(output),
        _exact_panel(output),
        _components_panel(output),
    ):
        if panel:
            st.markdown(panel, unsafe_allow_html=True)

    identity = str(game.get("identity_key") or game.get("game_id") or index)
    st.session_state["cfb_game_total_model_v1_game_id"] = identity
    st.session_state["cfb_game_total_model_v1_selected"] = dict(output)

    if output.get("ready"):
        rows = _distribution_rows(output)
        if rows:
            with st.expander("Full Step-11 integer total distribution"):
                st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">CERTIFIED TEAM EVIDENCE • STEP 11 INPUT AUDIT</div>
  <div class="cfb3-sub">
    Step 11 reads the frozen Step-10 schedule/team-data foundation. It does not
    modify Moneyline, Over/Under, or their frozen models.
  </div>
  {frozen_v1.team_ui._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_v1.team_ui._team_card(away)}
    {frozen_v1.team_ui._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    attempts = frozen_v1._diag_rows(team_diag)
    if attempts:
        with st.expander("Game Total team-data provider diagnostics"):
            st.dataframe(attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 11 activates the independent Game Total distribution only. "
        "Sportsbook totals/prices, market probabilities, edge/EV, final picks, "
        "slate ranking, and Monte Carlo remain OFF. Step 12 owns final synthesis."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Step 11 Game Total hub received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_around_projection_panel",
    "_band_panel",
    "_components_panel",
    "_distribution_card",
    "_distribution_rows",
    "_exact_panel",
    "render_cfb_hub",
    "render_game_total_hub",
]
