"""NFL Moneyline V17 — visual upgrade Step 4: market / odds control panel.

Presentation-only wrapper over frozen V16. It adds a compact sportsbook market
control panel beneath the certified Step 3 analysis/evidence surface using only
already-computed frozen V5/V7 market state. No probability, Monte Carlo,
sportsbook transport, no-vig math, edge/EV, grading, identity, availability,
or stake logic changes.
"""
from __future__ import annotations

from html import escape
import math
from textwrap import dedent
from typing import Any

import nfl_moneyline_hub_v9 as presentation
import nfl_moneyline_hub_v16 as prior

MODEL_VERSION = "NFL MONEYLINE V17 • VISUAL STEP 4 • MARKET / ODDS CONTROL PANEL"
FROZEN_PRIOR = "nfl_moneyline_hub_v16"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
VISUAL_UPGRADE_STEP = 4
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

_FROZEN_STEP3_CSS = prior._step3_css
_FROZEN_STEP3_MATCHUP = prior._analysis_matchup_html

_STEP4_CSS = r"""
<style data-nfl-moneyline-visual-step="4">
.kml17-market,.kml17-market *{box-sizing:border-box}
.kml17-market{
  margin:0 .82rem .86rem;padding-top:.14rem;
  border-top:1px solid rgba(88,201,255,.10)
}
.kml17-title{
  display:flex;align-items:flex-end;justify-content:space-between;gap:10px;
  margin:.72rem 0 .48rem
}
.kml17-title b{
  color:#eef8ff;font-size:.7rem;font-weight:950;letter-spacing:.055em;
  text-transform:uppercase
}
.kml17-title span{color:#668198;font-size:.45rem}
.kml17-health{
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.42rem;
  margin-bottom:.52rem
}
.kml17-health>div{
  min-width:0;border:1px solid rgba(88,201,255,.12);border-radius:10px;
  background:#07131e;padding:.54rem
}
.kml17-health span,.kml17-label{
  display:block;color:#698197;font-size:.39rem;font-weight:900;
  letter-spacing:.055em;text-transform:uppercase
}
.kml17-health b{
  display:block;margin-top:3px;color:#e8f2f9;font-size:.58rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml17-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:.62rem;margin-bottom:.52rem
}
.kml17-side{
  min-width:0;border:1px solid rgba(88,201,255,.15);border-radius:13px;
  background:linear-gradient(145deg,rgba(7,19,30,.98),rgba(6,15,24,.98));
  padding:.68rem
}
.kml17-side-head{display:flex;align-items:center;gap:8px;margin-bottom:.55rem}
.kml17-side-head img{width:30px!important;height:30px!important;object-fit:contain}
.kml17-side-head div{min-width:0}
.kml17-side-head b{
  display:block;color:#f0f7fc;font-size:.66rem;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis
}
.kml17-side-head span{display:block;color:#6c8499;font-size:.42rem;margin-top:1px}
.kml17-price-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:.42rem
}
.kml17-price{
  min-width:0;border:1px solid rgba(88,201,255,.10);border-radius:9px;
  background:#06111b;padding:.52rem
}
.kml17-price.hero{
  border-color:rgba(88,201,255,.28);
  background:linear-gradient(145deg,rgba(8,31,43,.98),rgba(6,22,31,.98))
}
.kml17-price b{
  display:block;margin-top:3px;color:#eff8fd;font-size:.78rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml17-price.hero b{color:#8fe3ff;font-size:.92rem}
.kml17-price small{
  display:block;margin-top:2px;color:#687f94;font-size:.39rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml17-board{
  border:1px solid rgba(88,201,255,.13);border-radius:13px;
  background:#07131e;padding:.62rem
}
.kml17-board-head{
  display:grid;grid-template-columns:1.15fr .8fr .8fr .75fr .9fr;gap:7px;
  padding:0 .42rem .34rem;color:#688096;font-size:.37rem;font-weight:900;
  letter-spacing:.05em;text-transform:uppercase
}
.kml17-book-row{
  display:grid;grid-template-columns:1.15fr .8fr .8fr .75fr .9fr;gap:7px;
  align-items:center;padding:.45rem .42rem;border-top:1px solid rgba(88,201,255,.07)
}
.kml17-book-row b,.kml17-book-row span{
  min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.kml17-book-row b{color:#e7f0f7;font-size:.5rem}
.kml17-book-row span{color:#758ba0;font-size:.43rem}
.kml17-book-empty{
  padding:.58rem;color:#71879b;font-size:.47rem;
  border-top:1px solid rgba(88,201,255,.07)
}
.kml17-foot{
  margin-top:.48rem;color:#687f94;font-size:.41rem;line-height:1.4
}
@media(max-width:760px){
  .kml17-health{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kml17-grid{grid-template-columns:1fr}
  .kml17-board-head{display:none}
  .kml17-book-row{grid-template-columns:1fr 1fr;gap:.28rem .5rem}
  .kml17-book-row>*:nth-child(4),.kml17-book-row>*:nth-child(5){display:none}
}
@media(max-width:520px){
  .kml17-market{margin:0 .65rem .68rem}
  .kml17-health{grid-template-columns:1fr 1fr}
  .kml17-price-grid{grid-template-columns:1fr 1fr}
}
</style>
"""


def _safe(value: Any, fallback: str = "") -> str:
    return presentation._safe(value, fallback)


def _num(value: Any) -> float:
    return presentation._num(value)


def _age_text(value: Any) -> str:
    n = _num(value)
    if not math.isfinite(n) or n < 0:
        return "—"
    if n < 60:
        return f"{int(n)}s"
    if n < 3600:
        return f"{int(n // 60)}m"
    return f"{n / 3600.0:.1f}h"


def _side_market_html(game: dict, side: str, snap: dict) -> str:
    team = _safe(game.get(f"{side}_team"), side.title())
    abbr = _safe(game.get(f"{side}_abbr"), "NFL").upper()
    best = (snap or {}).get(f"best_{side}") or {}
    consensus = (snap or {}).get(f"consensus_{side}_no_vig")
    return dedent(f"""
    <section class="kml17-side kml17-{escape(side)}">
      <div class="kml17-side-head">
        {presentation._team_logo(game, side)}
        <div><b>{escape(team)}</b><span>{escape(abbr)} • frozen market snapshot</span></div>
      </div>
      <div class="kml17-price-grid">
        <div class="kml17-price hero">
          <span class="kml17-label">BEST AVAILABLE ML</span>
          <b>{escape(presentation._ml(best.get("price")))}</b>
          <small>{escape(_safe(best.get("book"), "—"))}</small>
        </div>
        <div class="kml17-price">
          <span class="kml17-label">NO-VIG CONSENSUS</span>
          <b>{escape(presentation._pct(consensus))}</b>
          <small>market comparison only</small>
        </div>
      </div>
    </section>
    """).strip().replace("\n", "")


def _book_board_html(snap: dict) -> str:
    rows = (snap or {}).get("rows") or []
    out = []
    for row in rows[:6]:
        book = _safe(row.get("book"), "—")
        away_ml = presentation._ml(row.get("away_ml"))
        home_ml = presentation._ml(row.get("home_ml"))
        freshness = _safe(row.get("freshness"), "UNKNOWN")
        provider = _safe(row.get("provider"), "—")
        out.append(
            '<div class="kml17-book-row">'
            f'<b>{escape(book)}</b>'
            f'<span>{escape(away_ml)}</span>'
            f'<span>{escape(home_ml)}</span>'
            f'<span>{escape(freshness)}</span>'
            f'<span>{escape(provider)}</span>'
            '</div>'
        )
    if not out:
        return '<div class="kml17-book-empty">No full-game Moneyline book rows are available in the frozen market snapshot.</div>'
    return "".join(out)


def _market_html(game: dict, snap: dict) -> str:
    quality = _safe((snap or {}).get("quality"), "CHECK")
    usable = int((snap or {}).get("usable_books") or 0)
    freshest = _age_text((snap or {}).get("freshest_age"))
    disagreement = presentation._pp((snap or {}).get("disagreement"))
    providers = " + ".join((snap or {}).get("providers") or []) or "—"

    return dedent(f"""
    <div class="kml17-market" data-step4-market="true">
      <div class="kml17-title">
        <b>MARKET / ODDS CONTROL PANEL</b>
        <span>Frozen sportsbook snapshot • display only</span>
      </div>

      <div class="kml17-health">
        <div><span>MARKET QUALITY</span><b>{escape(quality)}</b></div>
        <div><span>USABLE BOOKS</span><b>{usable}</b></div>
        <div><span>FRESHEST QUOTE</span><b>{escape(freshest)}</b></div>
        <div><span>DISAGREEMENT</span><b>{escape(disagreement)}</b></div>
      </div>

      <div class="kml17-grid">
        {_side_market_html(game, "away", snap)}
        {_side_market_html(game, "home", snap)}
      </div>

      <section class="kml17-board">
        <div class="kml17-title" style="margin:.05rem 0 .36rem">
          <b>LIVE PRICE BOARD</b><span>{escape(providers)}</span>
        </div>
        <div class="kml17-board-head">
          <span>BOOK</span><span>AWAY ML</span><span>HOME ML</span><span>FRESHNESS</span><span>PROVIDER</span>
        </div>
        {_book_board_html(snap)}
      </section>

      <div class="kml17-foot">MODEL / MARKET FIREWALL • these prices and no-vig values come from the already-computed frozen market layer and never alter model P(win) • sportsbook influence on model P(win): 0.0% • stake sizing OFF.</div>
    </div>
    """).strip().replace("\n", "")


def _market_matchup_html(
    game: dict,
    final: dict,
    edge_out: dict,
    mc_out: dict,
    snap: dict,
    contexts: dict,
    gameplans: dict,
) -> str:
    base = _FROZEN_STEP3_MATCHUP(
        game, final, edge_out, mc_out, snap, contexts, gameplans
    )
    extra = _market_html(game, snap)
    if "</article>" not in base:
        return base + extra
    head, tail = base.rsplit("</article>", 1)
    return head + extra + "</article>" + tail


def _step4_css(base: str) -> str:
    return str(base or "") + _STEP4_CSS


def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V17 direct handler is Moneyline only.")

    original_step3_css = prior._step3_css
    original_matchup = prior._analysis_matchup_html

    prior._step3_css = lambda base: _step4_css(original_step3_css(base))
    prior._analysis_matchup_html = _market_matchup_html
    try:
        return prior.render_nfl_hub(market)
    finally:
        prior._analysis_matchup_html = original_matchup
        prior._step3_css = original_step3_css


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRESENTATION",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "_market_html",
    "_market_matchup_html",
    "_step4_css",
    "render_nfl_hub",
]
