"""NFL Moneyline V16 — visual upgrade Step 3: analysis / evidence sections.

Presentation-only wrapper over frozen V15. It adds compact, matchup-first
analysis and evidence panels beneath the certified Step 2 command center using
only already-computed frozen Moneyline state. No probability, Monte Carlo,
market, edge/EV, grading, game identity, availability, or stake logic changes.
"""
from __future__ import annotations

from html import escape
import math
from textwrap import dedent
from typing import Any

import nfl_moneyline_hub_v9 as presentation
import nfl_moneyline_hub_v15 as prior

MODEL_VERSION = "NFL MONEYLINE V16 • VISUAL STEP 3 • ANALYSIS / EVIDENCE"
FROZEN_PRIOR = "nfl_moneyline_hub_v15"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
VISUAL_UPGRADE_STEP = 3
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

_FROZEN_STEP2_CSS = prior._step2_css
_FROZEN_STEP2_MATCHUP = prior._command_center_matchup_html

_STEP3_CSS = r"""
<style data-nfl-moneyline-visual-step="3">
.kml16-analysis,.kml16-analysis *{box-sizing:border-box}
.kml16-analysis{
  margin:0 .82rem .82rem;
  padding-top:.14rem;
  border-top:1px solid rgba(88,201,255,.10);
}
.kml16-section-title{
  display:flex;align-items:flex-end;justify-content:space-between;gap:10px;
  margin:.72rem 0 .46rem;
}
.kml16-section-title b{
  color:#ecf6fd;font-size:.7rem;font-weight:950;letter-spacing:.055em;
  text-transform:uppercase
}
.kml16-section-title span{color:#668198;font-size:.45rem}
.kml16-overview{
  display:grid;grid-template-columns:.82fr 1.18fr;gap:.62rem
}
.kml16-panel{
  min-width:0;border:1px solid rgba(88,201,255,.14);border-radius:13px;
  background:linear-gradient(145deg,rgba(7,19,30,.98),rgba(6,15,24,.98));
  padding:.68rem
}
.kml16-panel h4{
  margin:0 0 .5rem;color:#8fdfff;font-size:.57rem;font-weight:950;
  letter-spacing:.075em;text-transform:uppercase
}
.kml16-facts{display:grid;grid-template-columns:1fr;gap:.38rem}
.kml16-fact{
  display:grid;grid-template-columns:76px minmax(0,1fr);gap:8px;
  align-items:start;padding-bottom:.34rem;border-bottom:1px solid rgba(88,201,255,.07)
}
.kml16-fact:last-child{border-bottom:0;padding-bottom:0}
.kml16-fact span{color:#667f96;font-size:.44rem;font-weight:900}
.kml16-fact b{
  min-width:0;color:#dce9f3;font-size:.54rem;font-weight:800;
  overflow:hidden;text-overflow:ellipsis
}
.kml16-factor-grid{display:grid;gap:.42rem}
.kml16-factor{
  display:grid;grid-template-columns:112px minmax(0,1fr) minmax(0,1fr);
  gap:7px;align-items:center;padding:.45rem .48rem;
  border:1px solid rgba(88,201,255,.08);border-radius:9px;background:#07131e
}
.kml16-factor>span{
  color:#738aa0;font-size:.43rem;font-weight:900;text-transform:uppercase
}
.kml16-factor div{min-width:0}
.kml16-factor div span{
  display:block;color:#668096;font-size:.39rem;font-weight:850
}
.kml16-factor div b{
  display:block;margin-top:2px;color:#edf5fb;font-size:.55rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml16-snapshots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.62rem}
.kml16-team-snapshot{
  min-width:0;border:1px solid rgba(88,201,255,.14);border-radius:13px;
  background:#07131e;padding:.66rem
}
.kml16-snap-head{display:flex;align-items:center;gap:8px;margin-bottom:.52rem}
.kml16-snap-head img{width:28px!important;height:28px!important;object-fit:contain}
.kml16-snap-head div{min-width:0}
.kml16-snap-head b{
  display:block;color:#eff7fd;font-size:.63rem;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis
}
.kml16-snap-head span{display:block;color:#698197;font-size:.42rem;margin-top:1px}
.kml16-snap-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.35rem}
.kml16-snap-stat{
  min-width:0;padding:.45rem;border:1px solid rgba(88,201,255,.08);
  border-radius:8px;background:#06101a
}
.kml16-snap-stat span{display:block;color:#687f94;font-size:.37rem;font-weight:900}
.kml16-snap-stat b{
  display:block;margin-top:2px;color:#e2edf5;font-size:.52rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml16-evidence{
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.42rem
}
.kml16-evidence-item{
  min-width:0;padding:.5rem;border:1px solid rgba(88,201,255,.10);
  border-radius:9px;background:#07131e
}
.kml16-evidence-item span{
  display:block;color:#657f96;font-size:.38rem;font-weight:900;
  text-transform:uppercase
}
.kml16-evidence-item b{
  display:block;margin-top:3px;color:#dce9f3;font-size:.5rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml16-note{
  margin-top:.48rem;color:#677f94;font-size:.42rem;line-height:1.4
}
@media(max-width:900px){
  .kml16-overview{grid-template-columns:1fr}
  .kml16-evidence{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media(max-width:620px){
  .kml16-analysis{margin:0 .65rem .65rem}
  .kml16-snapshots{grid-template-columns:1fr}
  .kml16-snap-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kml16-factor{grid-template-columns:1fr}
  .kml16-evidence{grid-template-columns:repeat(2,minmax(0,1fr))}
}
</style>
"""


def _safe(value: Any, fallback: str = "") -> str:
    return presentation._safe(value, fallback)


def _num(value: Any) -> float:
    return presentation._num(value)


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    n = _num(value)
    return "—" if not math.isfinite(n) else f"{n:.{digits}f}{suffix}"


def _profile(side: str, game: dict) -> dict:
    abbr = _safe(game.get(f"{side}_abbr")).upper()
    profiles = presentation.st.session_state.get("nfl_moneyline_v4_strength_profiles") or {}
    return profiles.get(abbr) or {}


def _profile_values(profile: dict) -> dict:
    blended = profile.get("blended") or {}
    current = profile.get("current") or {}
    return {
        "ready": bool(profile.get("ready")),
        "quality": _safe(profile.get("quality"), "CHECK"),
        "strength": _fmt(profile.get("strength_index")),
        "win_pct": _fmt((_num(blended.get("win_pct")) * 100.0) if math.isfinite(_num(blended.get("win_pct"))) else math.nan, 1, "%"),
        "ppg": _fmt(blended.get("ppg")),
        "papg": _fmt(blended.get("papg")),
        "recent": _fmt(blended.get("recent6_diff_pg"), 1),
        "current_games": str(int(current.get("games") or 0)),
    }


def _factor_row(label: str, away_abbr: str, away_value: str, home_abbr: str, home_value: str) -> str:
    return (
        '<div class="kml16-factor">'
        f'<span>{escape(label)}</span>'
        f'<div><span>{escape(away_abbr)}</span><b>{escape(away_value)}</b></div>'
        f'<div><span>{escape(home_abbr)}</span><b>{escape(home_value)}</b></div>'
        "</div>"
    )


def _snapshot_html(game: dict, side: str, values: dict) -> str:
    team = _safe(game.get(f"{side}_team"), side.title())
    abbr = _safe(game.get(f"{side}_abbr"), "NFL").upper()
    record = _safe(game.get(f"{side}_record"), "—")
    return dedent(f"""
    <section class="kml16-team-snapshot kml16-{escape(side)}-snapshot">
      <div class="kml16-snap-head">
        {presentation._team_logo(game, side)}
        <div><b>{escape(team)}</b><span>{escape(abbr)} • {escape(record)} • profile {escape(values["quality"])}</span></div>
      </div>
      <div class="kml16-snap-grid">
        <div class="kml16-snap-stat"><span>WIN %</span><b>{escape(values["win_pct"])}</b></div>
        <div class="kml16-snap-stat"><span>PF / G</span><b>{escape(values["ppg"])}</b></div>
        <div class="kml16-snap-stat"><span>PA / G</span><b>{escape(values["papg"])}</b></div>
        <div class="kml16-snap-stat"><span>RECENT L6 DIFF</span><b>{escape(values["recent"])}</b></div>
      </div>
    </section>
    """).strip()


def _analysis_html(
    game: dict,
    final: dict,
    mc_out: dict,
    snap: dict,
    contexts: dict,
    gameplans: dict,
) -> str:
    away_abbr = _safe(game.get("away_abbr"), "AWY").upper()
    home_abbr = _safe(game.get("home_abbr"), "HME").upper()
    away_profile = _profile("away", game)
    home_profile = _profile("home", game)
    away_vals = _profile_values(away_profile)
    home_vals = _profile_values(home_profile)

    regular_season = _safe(game.get("season_type")).lower() != "preseason"
    away_qb = presentation._qb_snapshot(contexts.get(away_abbr) or {}, gameplans.get(away_abbr) or {}, regular_season)
    home_qb = presentation._qb_snapshot(contexts.get(home_abbr) or {}, gameplans.get(home_abbr) or {}, regular_season)

    depth_ready = bool(
        presentation.st.session_state.get("nfl_moneyline_v3_depth_ready")
        or presentation.st.session_state.get("nfl_moneyline_v2_depth_ready")
    )
    injury_ready = bool(
        presentation.st.session_state.get("nfl_moneyline_v3_injuries_ready")
        or presentation.st.session_state.get("nfl_moneyline_v2_injuries_ready")
    )
    prereq = final.get("prerequisites") or {}
    market_quality = _safe((snap or {}).get("quality"), prereq.get("market_quality") or "CHECK")
    mc_state = "CONVERGED" if (mc_out or {}).get("converged") else "CHECK"
    sims = int((mc_out or {}).get("simulations") or 0)
    sim_text = "5M" if sims >= 5_000_000 else (f"{sims:,}" if sims else "—")

    factors = "".join([
        _factor_row("Strength index", away_abbr, away_vals["strength"], home_abbr, home_vals["strength"]),
        _factor_row("Offense PF/G", away_abbr, away_vals["ppg"], home_abbr, home_vals["ppg"]),
        _factor_row("Defense PA/G", away_abbr, away_vals["papg"], home_abbr, home_vals["papg"]),
        _factor_row("Recent L6 diff", away_abbr, away_vals["recent"], home_abbr, home_vals["recent"]),
        _factor_row("QB / availability", away_abbr, f'{away_qb["starter"]} • {away_qb["plan_state"]}', home_abbr, f'{home_qb["starter"]} • {home_qb["plan_state"]}'),
    ])

    return dedent(f"""
    <div class="kml16-analysis" data-step3-analysis="true">
      <div class="kml16-section-title">
        <b>ANALYSIS / EVIDENCE</b><span>Frozen model state • presentation only</span>
      </div>

      <div class="kml16-overview">
        <section class="kml16-panel kml16-quickfacts">
          <h4>QUICK FACTS</h4>
          <div class="kml16-facts">
            <div class="kml16-fact"><span>GAME TIME</span><b>{escape(_safe(game.get("tip_et"), "TBD"))}</b></div>
            <div class="kml16-fact"><span>VENUE</span><b>{escape(_safe(game.get("venue"), "Venue TBD"))}</b></div>
            <div class="kml16-fact"><span>LOCATION</span><b>{escape(_safe(game.get("location"), "—"))}</b></div>
            <div class="kml16-fact"><span>BROADCAST</span><b>{escape(_safe(game.get("broadcast"), "—"))}</b></div>
            <div class="kml16-fact"><span>PHASE</span><b>{escape(_safe(game.get("season_type"), "NFL"))}</b></div>
          </div>
        </section>

        <section class="kml16-panel kml16-factors">
          <h4>KEY MATCHUP FACTORS</h4>
          <div class="kml16-factor-grid">{factors}</div>
        </section>
      </div>

      <div class="kml16-section-title">
        <b>TEAM SNAPSHOT</b><span>Existing frozen strength-profile evidence</span>
      </div>
      <div class="kml16-snapshots">
        {_snapshot_html(game, "away", away_vals)}
        {_snapshot_html(game, "home", home_vals)}
      </div>

      <div class="kml16-section-title">
        <b>EVIDENCE &amp; GUARDRAILS</b><span>No new model ownership</span>
      </div>
      <section class="kml16-panel">
        <div class="kml16-evidence">
          <div class="kml16-evidence-item"><span>AWAY PROFILE</span><b>{escape(away_vals["quality"])}</b></div>
          <div class="kml16-evidence-item"><span>HOME PROFILE</span><b>{escape(home_vals["quality"])}</b></div>
          <div class="kml16-evidence-item"><span>QB / INJURY</span><b>{"READY" if depth_ready and injury_ready else "CHECK"}</b></div>
          <div class="kml16-evidence-item"><span>MONTE CARLO</span><b>{escape(mc_state)} • {escape(sim_text)}</b></div>
          <div class="kml16-evidence-item"><span>MARKET QUALITY</span><b>{escape(market_quality)}</b></div>
        </div>
        <div class="kml16-note">Sportsbook prices remain comparison-only • sportsbook influence on model P(win): 0.0% • stake sizing OFF • V15 Step 2 and all frozen analytical ownership remain unchanged.</div>
      </section>
    </div>
    """).strip().replace("\n", "")


def _analysis_matchup_html(
    game: dict,
    final: dict,
    edge_out: dict,
    mc_out: dict,
    snap: dict,
    contexts: dict,
    gameplans: dict,
) -> str:
    base = _FROZEN_STEP2_MATCHUP(game, final, edge_out, mc_out, snap, contexts, gameplans)
    extra = _analysis_html(game, final, mc_out, snap, contexts, gameplans)
    if "</article>" not in base:
        return base + extra
    head, tail = base.rsplit("</article>", 1)
    return head + extra + "</article>" + tail


def _step3_css(base: str) -> str:
    return str(base or "") + _STEP3_CSS


def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V16 direct handler is Moneyline only.")

    original_step2_css = prior._step2_css
    original_matchup = prior._command_center_matchup_html

    prior._step2_css = lambda base: _step3_css(original_step2_css(base))
    prior._command_center_matchup_html = _analysis_matchup_html
    try:
        return prior.render_nfl_hub(market)
    finally:
        prior._command_center_matchup_html = original_matchup
        prior._step2_css = original_step2_css


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRESENTATION",
    "FROZEN_PRIOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "_analysis_html",
    "_analysis_matchup_html",
    "_step3_css",
    "render_nfl_hub",
]
