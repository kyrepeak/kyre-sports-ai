"""CFB Over/Under Intelligence V2 — Upgrade Step 2 ranking UI.

Additive presentation wrapper over permanently frozen Upgrade Step 1.

Step 2 appends a Rankings + Conference + Records panel to the Step-1 matchup
header. It consumes display-only evidence from cfb_over_under_rankings_v1 and
leaves every frozen Step-8/Step-9 model output untouched.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v1 as frozen_v1
import cfb_over_under_rankings_v1 as rankings

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 2 RANKINGS"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v1"
MARKET = "Over/Under"

_FROZEN_STEP1_HERO = frozen_v1._enhanced_hero

_CSS = r"""
<style>
.cfbou2-panel{margin:9px 0 2px;border:1px solid rgba(245,190,76,.25);border-radius:18px;
background:linear-gradient(145deg,#171307,#111a22 55%,#0b151d);overflow:hidden}
.cfbou2-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(245,190,76,.14);background:rgba(26,20,6,.30)}
.cfbou2-head b{color:#ffd978;font-size:.53rem;font-weight:950;letter-spacing:.09em}
.cfbou2-head span{border:1px solid #66511e;border-radius:999px;padding:4px 7px;background:#2b240d;
color:#f1d67d;font-size:.40rem;font-weight:950;white-space:nowrap}
.cfbou2-sub{padding:7px 12px;color:#8da0aa;font-size:.43rem;line-height:1.45;border-bottom:1px solid rgba(245,190,76,.08)}
.cfbou2-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou2-team{border:1px solid rgba(154,190,211,.16);border-radius:14px;background:rgba(5,17,25,.62);overflow:hidden}
.cfbou2-team-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;padding:10px 10px 8px}
.cfbou2-name{color:#f4fbff;font-size:.90rem;font-weight:950;line-height:1.1}
.cfbou2-conf{color:#89a3b1;font-size:.43rem;font-weight:850;margin-top:4px}
.cfbou2-record{border:1px solid #315067;border-radius:999px;background:#0a2230;color:#a5d6ed;
padding:4px 7px;font-size:.42rem;font-weight:950;white-space:nowrap}
.cfbou2-polls{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:0 10px 8px}
.cfbou2-poll{border:1px solid rgba(111,161,189,.15);border-radius:9px;background:#091a24;padding:7px 6px}
.cfbou2-poll strong{display:block;color:#dceaf1;font-size:.61rem}.cfbou2-poll span{display:block;color:#6d8b9b;
font-size:.34rem;text-transform:uppercase;font-weight:900;margin-top:2px}
.cfbou2-records{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:0 10px 9px}
.cfbou2-rec{border:1px solid rgba(117,154,174,.12);border-radius:8px;background:#08151d;padding:6px}
.cfbou2-rec strong{display:block;color:#cfe0e8;font-size:.50rem}.cfbou2-rec span{display:block;color:#657d8a;
font-size:.32rem;text-transform:uppercase;margin-top:2px}
.cfbou2-label{padding:7px 10px 5px;border-top:1px solid rgba(245,190,76,.08);color:#dcbf68;
font-size:.37rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase}
.cfbou2-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou2-metric{border:1px solid rgba(93,183,227,.13);border-radius:9px;background:#081923;padding:7px 6px;min-width:0}
.cfbou2-metric strong{display:block;color:#7edcff;font-size:.64rem}.cfbou2-metric.def strong{color:#8de7b6}
.cfbou2-metric span{display:block;color:#708a98;font-size:.31rem;text-transform:uppercase;font-weight:900;
line-height:1.25;margin-top:2px}.cfbou2-metric em{display:block;color:#59727f;font-size:.29rem;font-style:normal;
line-height:1.25;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cfbou2-foot{padding:8px 11px;border-top:1px solid rgba(245,190,76,.08);color:#687d87;font-size:.37rem;line-height:1.45}
.cfbou2-warn{margin:10px;border:1px solid #705d22;border-radius:11px;background:#2d260d;color:#d9c478;
padding:9px;font-size:.43rem;line-height:1.45}
@media(max-width:760px){
  .cfbou2-grid{grid-template-columns:1fr}.cfbou2-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfbou2-head{align-items:flex-start}.cfbou2-head span{white-space:normal;text-align:center}
}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _rank_display(item: Mapping[str, Any]) -> str:
    rank = item.get("rank")
    state = _clean(item.get("state")).lower()
    try:
        if rank is not None:
            return f"#{int(rank)}"
    except Exception:
        pass
    if state == "unranked":
        return "NR"
    if state == "not_released":
        return "NOT YET"
    if state == "not_applicable":
        return "N/A"
    return "—"


def _metric_html(metric: Mapping[str, Any]) -> str:
    label = escape(_clean(metric.get("label")) or "Metric")
    rank = metric.get("rank")
    try:
        rank_text = f"#{int(rank)}" if rank is not None else "—"
    except Exception:
        rank_text = "—"
    value = escape(_clean(metric.get("value")) or "value unavailable")
    key = _clean(metric.get("key")).lower()
    klass = " def" if "defense" in key else ""
    return f"""
<div class="cfbou2-metric{klass}">
  <strong>{rank_text}</strong>
  <span>{label}</span>
  <em>{value}</em>
</div>
"""


def _team_panel(side: Mapping[str, Any]) -> str:
    metrics = side.get("metrics") or {}
    ordered = [
        metrics.get(key) or {
            "key": key,
            "label": key.replace("_", " ").title(),
            "rank": None,
            "value": "",
        }
        for key in rankings._METRIC_ORDER
    ]
    metric_html = "".join(_metric_html(metric) for metric in ordered)
    coverage = float(side.get("metric_coverage") or 0.0)
    return f"""
<div class="cfbou2-team">
  <div class="cfbou2-team-top">
    <div>
      <div class="cfbou2-name">{escape(_clean(side.get('team')) or 'Team')}</div>
      <div class="cfbou2-conf">{escape(_clean(side.get('conference')) or 'Conference unavailable')} • {escape(_clean(side.get('division')) or 'CFB')}</div>
    </div>
    <div class="cfbou2-record">{escape(_clean(side.get('record')) or '—')}</div>
  </div>
  <div class="cfbou2-polls">
    <div class="cfbou2-poll"><strong>{_rank_display(side.get('ap') or {})}</strong><span>AP</span></div>
    <div class="cfbou2-poll"><strong>{_rank_display(side.get('coaches') or {})}</strong><span>Coaches</span></div>
    <div class="cfbou2-poll"><strong>{_rank_display(side.get('cfp') or {})}</strong><span>CFP</span></div>
  </div>
  <div class="cfbou2-records">
    <div class="cfbou2-rec"><strong>{escape(_clean(side.get('home_record')) or '—')}</strong><span>Home</span></div>
    <div class="cfbou2-rec"><strong>{escape(_clean(side.get('away_record')) or '—')}</strong><span>Road</span></div>
    <div class="cfbou2-rec"><strong>{escape(_clean(side.get('recent_form')) or '—')}</strong><span>Recent form</span></div>
  </div>
  <div class="cfbou2-label">KYRE matchup ranking profile • NCAA category ranks • {100.0 * coverage:.0f}% coverage</div>
  <div class="cfbou2-metrics">{metric_html}</div>
</div>
"""


def _rankings_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    context = rankings.build_ranking_context(game, away, home)
    if not context.get("ready"):
        return """
<div class="cfbou2-panel">
  <div class="cfbou2-head"><b>🏆 RANKINGS • CONFERENCE • RECORDS</b><span>MODEL WEIGHT 0%</span></div>
  <div class="cfbou2-warn">
    Supplemental ranking tables are unavailable for this matchup right now.
    Frozen AP/conference/record evidence remains visible in the Step-1 header,
    and no ranking value is invented.
  </div>
</div>
"""

    coverage = 100.0 * float(context.get("metric_coverage") or 0.0)
    return f"""
<div class="cfbou2-panel">
  <div class="cfbou2-head">
    <b>🏆 UPGRADE STEP 2 • RANKINGS + CONFERENCE + RECORDS</b>
    <span>DISPLAY EVIDENCE • MODEL WEIGHT 0%</span>
  </div>
  <div class="cfbou2-sub">
    AP / Coaches / CFP context plus official NCAA team-category ranks.
    CFP shows NOT YET before November. NR means the poll exists but the team is
    outside the ranked field. Category coverage for this matchup: {coverage:.0f}%.
  </div>
  <div class="cfbou2-grid">
    {_team_panel(context.get('away') or {})}
    {_team_panel(context.get('home') or {})}
  </div>
  <div class="cfbou2-foot">
    “KYRE matchup ranking profile” is a presentation grouping of official NCAA category ranks,
    not a new power-rating formula. Step 2 does not alter projected total, OVER/UNDER/PASS,
    Top-5 order, reliability, analysis-line behavior, sportsbook inputs, or simulation math.
  </div>
</div>
"""


def _enhanced_hero_v2(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_STEP1_HERO(game, away, home) + _rankings_panel(game, away, home)


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render frozen Upgrade Step 1 with only its hero function extended."""
    st.caption("🏆 CFB O/U INTELLIGENCE V2 • Upgrade Step 2 • rankings + conference + records")
    st.markdown(_CSS, unsafe_allow_html=True)

    original = frozen_v1._enhanced_hero
    frozen_v1._enhanced_hero = _enhanced_hero_v2
    try:
        return frozen_v1.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v1._enhanced_hero = original


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 2 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_enhanced_hero_v2",
    "_metric_html",
    "_rank_display",
    "_rankings_panel",
    "_team_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
