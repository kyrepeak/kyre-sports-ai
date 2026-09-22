"""NFL Moneyline V15 — visual upgrade Step 2: matchup command center.

Presentation-only wrapper over frozen V14. Re-composes the already-computed V9
Moneyline matchup payload into premium side-by-side team command cards. Model
probability, fair line, market no-vig, best price, edge/EV, Monte Carlo,
availability, final grading, and all frozen analytical ownership are unchanged.
"""
from __future__ import annotations

from html import escape
import math
from textwrap import dedent
from typing import Any

import nfl_moneyline_hub_v9 as presentation
import nfl_moneyline_hub_v14 as prior

MODEL_VERSION = "NFL MONEYLINE V15 • VISUAL STEP 2 • MATCHUP COMMAND CENTER"
FROZEN_PRIOR = "nfl_moneyline_hub_v14"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
VISUAL_UPGRADE_STEP = 2
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

_STEP2_CSS = r"""
<style data-nfl-moneyline-visual-step="2">
.kml15-card,.kml15-card *{box-sizing:border-box}
.kml15-card{
  margin:.68rem 0 .82rem;
  overflow:hidden;
  border:1px solid rgba(88,201,255,.22);
  border-radius:18px;
  background:
    radial-gradient(circle at 92% 0%,rgba(88,201,255,.08),transparent 28%),
    linear-gradient(155deg,#091522,#061018);
  box-shadow:0 16px 42px rgba(0,0,0,.22),0 0 24px rgba(46,168,255,.04);
}
.kml15-top{
  display:flex;align-items:flex-start;justify-content:space-between;gap:12px;
  padding:.82rem .9rem .74rem;
  border-bottom:1px solid rgba(88,201,255,.12);
  background:linear-gradient(90deg,rgba(88,201,255,.055),transparent);
}
.kml15-kicker{
  color:#58c9ff;font-size:.55rem;font-weight:950;letter-spacing:.11em;
  text-transform:uppercase
}
.kml15-matchup{
  margin:.14rem 0 0;color:#f4f8fc;font-size:1.03rem;font-weight:950;
  letter-spacing:-.02em
}
.kml15-meta{margin-top:.22rem;color:#748ca2;font-size:.57rem;line-height:1.35}
.kml15-health{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.kml15-health span{
  border:1px solid #2a506d;background:#091a29;color:#9ddcf6;
  border-radius:999px;padding:4px 7px;font-size:.46rem;font-weight:900
}
.kml15-health .good{border-color:#287b61;color:#79efbd}
.kml15-health .watch{border-color:#806d2e;color:#f2d77b}
.kml15-health .warn{border-color:#8b6032;color:#f1b56f}
.kml15-health .bad{border-color:#7e3741;color:#f199a6}
.kml15-grid{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.78rem;
  padding:.82rem
}
.kml15-team{
  min-width:0;overflow:hidden;border:1px solid rgba(88,201,255,.17);
  border-radius:16px;background:rgba(7,18,29,.96)
}
.kml15-team-accent{
  height:3px;background:linear-gradient(90deg,#58c9ff,rgba(88,201,255,.06))
}
.kml15-team-head{
  display:flex;align-items:flex-start;justify-content:space-between;gap:8px;
  padding:.72rem .76rem .62rem
}
.kml15-id{display:flex;align-items:center;gap:9px;min-width:0}
.kml15-id img{width:38px!important;height:38px!important;object-fit:contain}
.kml15-id div{min-width:0}
.kml15-id b{
  display:block;color:#f4f8fc;font-size:.82rem;line-height:1.15;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml15-id span{display:block;margin-top:2px;color:#6f879d;font-size:.5rem}
.kml15-grade{
  border:1px solid #35536a;border-radius:999px;padding:4px 7px;
  color:#aac0d2;font-size:.46rem;font-weight:950;white-space:nowrap
}
.kml15-grade.good{border-color:#287b61;color:#79efbd}
.kml15-grade.watch{border-color:#806d2e;color:#f2d77b}
.kml15-grade.warn{border-color:#8b6032;color:#f1b56f}
.kml15-grade.bad{border-color:#7e3741;color:#f199a6}
.kml15-qb{
  margin:0 .76rem .64rem;padding:.58rem .62rem;
  border:1px solid rgba(88,201,255,.11);border-radius:11px;
  background:rgba(255,255,255,.014)
}
.kml15-label{
  color:#7891a8;font-size:.47rem;font-weight:900;letter-spacing:.06em;
  text-transform:uppercase
}
.kml15-qb b{display:block;margin-top:2px;color:#eaf1f8;font-size:.68rem}
.kml15-qb small{display:block;margin-top:2px;color:#71879b;font-size:.48rem}
.kml15-primary{
  display:grid;grid-template-columns:1.2fr .8fr .8fr;gap:.52rem;
  padding:0 .76rem .72rem
}
.kml15-tile{
  min-width:0;padding:.66rem;border:1px solid rgba(88,201,255,.13);
  border-radius:12px;background:#07121d
}
.kml15-tile.hero{
  border-color:rgba(88,201,255,.34);
  background:linear-gradient(145deg,rgba(9,34,47,.98),rgba(7,24,32,.98))
}
.kml15-tile span{
  display:block;color:#70879d;font-size:.45rem;font-weight:900;
  letter-spacing:.055em
}
.kml15-tile b{
  display:block;margin-top:.3rem;color:#f4f8fc;font-size:.82rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml15-tile.hero b{color:#8fe3ff;font-size:1.15rem}
.kml15-secondary{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.45rem;
  padding:0 .76rem .76rem
}
.kml15-mini{
  min-width:0;padding:.52rem;border-top:1px solid rgba(88,201,255,.10)
}
.kml15-mini span{display:block;color:#6d849a;font-size:.42rem;font-weight:900}
.kml15-mini b{
  display:block;margin-top:.22rem;color:#dce8f2;font-size:.66rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml15-floor{
  display:flex;gap:9px;flex-wrap:wrap;padding:.58rem .76rem;
  border-top:1px solid rgba(88,201,255,.09);color:#72889d;font-size:.46rem
}
.kml15-floor b{color:#bed0de}
.kml15-verdict{
  display:grid;grid-template-columns:auto minmax(0,1fr);gap:.42rem 1rem;
  align-items:center;margin:.02rem .82rem .82rem;padding:.68rem .74rem;
  border:1px solid rgba(88,201,255,.16);border-radius:12px;background:#08131f
}
.kml15-verdict span{display:block;color:#718aa1;font-size:.44rem;font-weight:900}
.kml15-verdict b{display:block;margin-top:2px;color:#f5f9fc;font-size:.86rem}
.kml15-verdict p{margin:0;color:#b6c7d4;font-size:.58rem;line-height:1.4}
.kml15-verdict small{grid-column:1/-1;color:#6e8498;font-size:.44rem}
@media(max-width:900px){
  .kml15-grid{grid-template-columns:1fr}
}
@media(max-width:620px){
  .kml15-top{flex-direction:column;padding:.72rem}
  .kml15-health{justify-content:flex-start}
  .kml15-grid{padding:.65rem}
  .kml15-primary{grid-template-columns:1fr 1fr}
  .kml15-primary .hero{grid-column:1/-1}
  .kml15-secondary{grid-template-columns:1fr 1fr}
  .kml15-card{border-radius:15px}
  .kml15-verdict{grid-template-columns:1fr}
  .kml15-verdict small{grid-column:auto}
}
</style>
"""


def _safe(value: Any, fallback: str = "") -> str:
    return presentation._safe(value, fallback)


def _team_panel(*, game: dict, side: str, edge: dict, grade: dict, ctx: dict, gp: dict, mc: dict) -> str:
    team = _safe(game.get(f"{side}_team"), side.title())
    abbr = _safe(game.get(f"{side}_abbr"), "NFL")
    record = _safe(game.get(f"{side}_record"), "—")
    qb = presentation._qb_snapshot(ctx, gp, _safe(game.get("season_type")).lower() != "preseason")

    grade_name = _safe(grade.get("grade"), "NO PLAY")
    model_p = edge.get("model_p")
    market_p = edge.get("market_p")
    fair_ml = edge.get("fair_ml")
    best_price = edge.get("best_price")
    best_book = _safe(edge.get("best_book"), "—")

    if side == "away":
        p05 = mc.get("p05_probability")
        p95 = mc.get("p95_probability")
    else:
        away_p95 = presentation._num(mc.get("p95_probability"))
        away_p05 = presentation._num(mc.get("p05_probability"))
        p05 = 1.0 - away_p95 if math.isfinite(away_p95) else math.nan
        p95 = 1.0 - away_p05 if math.isfinite(away_p05) else math.nan

    interval = f"{presentation._pct(p05)}–{presentation._pct(p95)}"
    status = presentation._status_class(grade_name)

    return dedent(f"""
    <section class="kml15-team kml15-{escape(side)}">
      <div class="kml15-team-accent"></div>
      <div class="kml15-team-head">
        <div class="kml15-id">{presentation._team_logo(game, side)}<div>
          <b>{escape(team)}</b><span>{escape(abbr)} • {escape(record)}</span>
        </div></div>
        <span class="kml15-grade {status}">{escape(grade_name)}</span>
      </div>
      <div class="kml15-qb">
        <span class="kml15-label">QB / AVAILABILITY</span>
        <b>{escape(qb["starter"])}</b>
        <small>{escape(qb["injury"])} • {escape(qb["depth_state"])} • {escape(qb["plan_state"])}</small>
      </div>
      <div class="kml15-primary">
        <div class="kml15-tile hero"><span>MODEL P(WIN)</span><b>{presentation._pct(model_p)}</b></div>
        <div class="kml15-tile"><span>FAIR ML</span><b>{presentation._ml(fair_ml)}</b></div>
        <div class="kml15-tile"><span>BEST ML</span><b>{presentation._ml(best_price)}</b><span>{escape(best_book)}</span></div>
      </div>
      <div class="kml15-secondary">
        <div class="kml15-mini"><span>MARKET NO-VIG</span><b>{presentation._pct(market_p)}</b></div>
        <div class="kml15-mini"><span>EDGE</span><b>{presentation._pp(edge.get("edge"))}</b></div>
        <div class="kml15-mini"><span>EV / 1U</span><b>{presentation._ev(edge.get("ev"))}</b></div>
      </div>
      <div class="kml15-floor">
        <span>UNCERTAINTY <b>{interval}</b></span>
        <span>FLOOR EDGE <b>{presentation._pp(edge.get("conservative_edge"))}</b></span>
        <span>FLOOR EV <b>{presentation._ev(edge.get("conservative_ev"))}</b></span>
      </div>
    </section>
    """).strip()


def _command_center_matchup_html(
    game: dict,
    final: dict,
    edge_out: dict,
    mc_out: dict,
    snap: dict,
    contexts: dict,
    gameplans: dict,
) -> str:
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    away_abbr = _safe(game.get("away_abbr")).upper()
    home_abbr = _safe(game.get("home_abbr")).upper()

    state = _safe(final.get("state"), "GATED")
    leader_side = _safe(final.get("leader_side"), "away")
    leader = away if leader_side == "away" else home
    prereq = final.get("prerequisites") or {}

    tip = _safe(game.get("tip_et"), "TBD")
    venue = _safe(game.get("venue"), "Venue TBD")
    broadcast = _safe(game.get("broadcast"), "—")
    phase = _safe(game.get("season_type"), "NFL")

    mc_state = "CONVERGED" if (mc_out or {}).get("converged") else "CHECK"
    sims = int((mc_out or {}).get("simulations") or 0)
    market_quality = _safe((snap or {}).get("quality"), prereq.get("market_quality") or "CHECK")
    calibration = _safe(prereq.get("calibration_quality"), "CHECK")
    reason_text = " • ".join(_safe(x) for x in (prereq.get("reasons") or []) if _safe(x))

    verdict_copy = {
        "QUALIFIED": f"{leader} clears the frozen production thresholds.",
        "LEAN / WATCH": f"{leader} owns the stronger positive profile, but remains below full qualification.",
        "HIGH UNCERTAINTY": f"{leader} leads the headline profile, but the uncertainty floor weakens the case.",
        "NO PLAY": "Neither side clears the frozen production thresholds.",
        "GATED": reason_text or "Required production inputs are unresolved; downstream math stays diagnostic.",
    }.get(state, reason_text or "Frozen V8 final state.")

    return dedent(f"""
    <article class="kml15-card" data-game-id="{escape(presentation._gid(game))}">
      <header class="kml15-top">
        <div>
          <div class="kml15-kicker">{escape(phase)} • MONEYLINE MATCHUP COMMAND CENTER</div>
          <div class="kml15-matchup">{escape(away)} <span style="color:#70879d">@</span> {escape(home)}</div>
          <div class="kml15-meta">🕒 {escape(tip)} &nbsp; • &nbsp; 🏟️ {escape(venue)} &nbsp; • &nbsp; 📺 {escape(broadcast)}</div>
        </div>
        <div class="kml15-health">
          <span class="{presentation._status_class(calibration)}">CAL {escape(calibration)}</span>
          <span class="{presentation._status_class(market_quality)}">MARKET {escape(market_quality)}</span>
          <span class="{presentation._status_class(mc_state)}">MC {escape(mc_state)}</span>
        </div>
      </header>
      <div class="kml15-grid">
        {_team_panel(game=game, side="away", edge=(edge_out or {}).get("away") or {}, grade=final.get("away_grade") or {}, ctx=contexts.get(away_abbr) or {}, gp=gameplans.get(away_abbr) or {}, mc=mc_out or {})}
        {_team_panel(game=game, side="home", edge=(edge_out or {}).get("home") or {}, grade=final.get("home_grade") or {}, ctx=contexts.get(home_abbr) or {}, gp=gameplans.get(home_abbr) or {}, mc=mc_out or {})}
      </div>
      <div class="kml15-verdict {presentation._status_class(state)}">
        <div><span>FINAL MONEYLINE STATE</span><b>{escape(state)}</b></div>
        <p>{escape(verdict_copy)}</p>
        <small>{"5M" if sims >= 5_000_000 else (f"{sims:,}" if sims else "—")} simulations • market is comparison-only • sportsbook influence on model P(win): 0.0%</small>
      </div>
    </article>
    """).strip()


def _step2_css(base: str) -> str:
    return str(base or "") + _STEP2_CSS


def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V15 direct handler is Moneyline only.")

    original_step1_css = prior._step1_css
    original_matchup = presentation._matchup_html

    # Step 1 is frozen. Extend its final CSS layer rather than replacing it:
    # V13 universal theme -> V14 Step 1 -> V15 Step 2.
    prior._step1_css = lambda base: _step2_css(original_step1_css(base))
    presentation._matchup_html = _command_center_matchup_html

    try:
        return prior.render_nfl_hub(market)
    finally:
        presentation._matchup_html = original_matchup
        prior._step1_css = original_step1_css


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
    "_command_center_matchup_html",
    "_team_panel",
    "_step2_css",
    "render_nfl_hub",
]
