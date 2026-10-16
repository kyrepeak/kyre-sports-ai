"""CFB Game Total Page 2 — Stage 5 Best Bet presentation.

Display-only renderer for a caller-owned recommendation derived from already-owned
forecast/distribution evidence. This module does not fetch data, recompute the
model, calculate sportsbook prices, or alter market ownership.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
from math import isfinite
from typing import Any

STAGE5_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_STAGE5_BEST_BET_V1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_STAGE5_BEST_BET_V1_FROZEN"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

PAGE2_STAGE5_CSS = r"""
<style>
.gtp2s9-wrap{max-width:1180px;margin:0 auto 20px;color:#f7fbff;scroll-margin-top:18px}
.gtp2s9-card{overflow:hidden;border:1px solid rgba(76,225,176,.34);border-radius:20px;background:radial-gradient(circle at 90% 0,rgba(54,223,164,.12),transparent 38%),linear-gradient(180deg,rgba(7,31,39,.98),rgba(4,17,23,.99));box-shadow:0 16px 38px rgba(0,0,0,.25),0 0 30px rgba(70,224,180,.06)}
.gtp2s9-head{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:17px 18px 13px;border-bottom:1px solid rgba(92,211,178,.18)}
.gtp2s9-kicker{display:block;margin-bottom:5px;color:#72e7c2;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}.gtp2s9-head h3{margin:0;color:#fff;font-size:20px;line-height:1.05;font-weight:1000;letter-spacing:-.02em}.gtp2s9-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:750}.gtp2s9-owned{padding:5px 9px;border:1px solid rgba(86,224,190,.24);border-radius:999px;background:rgba(11,82,69,.25);color:#88f0ce;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.gtp2s9-body{padding:14px}.gtp2s9-pick{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px;border:1px solid rgba(73,220,174,.26);border-radius:14px;background:rgba(9,55,50,.28)}.gtp2s9-pick span{color:#87b4aa;font-size:7px;font-weight:950;text-transform:uppercase;letter-spacing:.08em}.gtp2s9-pick strong{display:block;margin-top:4px;color:#7af0c2;font-size:26px;font-weight:1000;letter-spacing:-.03em}.gtp2s9-pick em{font-style:normal;color:#dffbf2;font-size:12px;font-weight:1000;text-align:right}
.gtp2s9-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:9px}.gtp2s9-grid article{padding:11px;border:1px solid rgba(78,171,192,.16);border-radius:11px;background:rgba(6,26,37,.67)}.gtp2s9-grid span{display:block;color:#7393a6;font-size:6px;font-weight:950;letter-spacing:.07em;text-transform:uppercase}.gtp2s9-grid strong{display:block;margin-top:5px;color:#f8fdff;font-size:13px;font-weight:1000;overflow-wrap:anywhere}.gtp2s9-rationale{margin:9px 0 0;padding:11px 12px;border:1px solid rgba(89,187,210,.14);border-radius:11px;background:rgba(4,21,31,.58);color:#9db6c3;font-size:8px;font-weight:750;line-height:1.5;overflow-wrap:anywhere}
@media(max-width:760px){.gtp2s9-head{align-items:start;flex-direction:column;gap:9px}.gtp2s9-owned{align-self:flex-start}.gtp2s9-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.gtp2s9-card{border-radius:17px}.gtp2s9-head{padding:14px 13px 11px}.gtp2s9-head h3{font-size:18px}.gtp2s9-body{padding:10px}.gtp2s9-pick{padding:12px}.gtp2s9-pick strong{font-size:22px}.gtp2s9-grid{gap:6px}}
</style>
"""


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if not isinstance(value, (str, bytes, bool)):
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            pass
        else:
            if not isfinite(number):
                return "—"
    text = str(value).strip()
    return escape(text) if text else "—"


def build_best_bet_html(recommendation: Mapping[str, Any] | None) -> str:
    rec = recommendation if isinstance(recommendation, Mapping) else {}
    side = _display(rec.get("side"))
    line = _display(rec.get("line"))
    probability = _display(rec.get("probability"))
    expected_total = _display(rec.get("expected_total"))
    edge = _display(rec.get("edge"))
    confidence = _display(rec.get("confidence"))
    rationale = _display(rec.get("rationale"))
    return f"""
{PAGE2_STAGE5_CSS}
<section id="gtp2-stage5-best-bet" class="gtp2s9-wrap" data-stage5="{STAGE5_MARKER}" data-testid="gtp2s9-best-bet" data-value-ownership="frozen-forecast-distribution">
  <div class="gtp2s9-card">
    <header class="gtp2s9-head">
      <div>
        <span class="gtp2s9-kicker">Stage 5 • Best Bet</span>
        <h3>Best Bet</h3>
        <p>Qualified forecast direction against the verified market total using the already-owned frozen distribution.</p>
      </div>
      <span class="gtp2s9-owned">No odds • no EV • no model rerun</span>
    </header>
    <div class="gtp2s9-body">
      <div class="gtp2s9-pick">
        <div><span>Recommendation</span><strong>{side}</strong></div>
        <em>Line {line}<br>{probability}</em>
      </div>
      <div class="gtp2s9-grid">
        <article><span>Expected Total</span><strong>{expected_total}</strong></article>
        <article><span>Edge</span><strong>{edge}</strong></article>
        <article><span>Forecast Grade</span><strong>{confidence}</strong></article>
        <article><span>Probability</span><strong>{probability}</strong></article>
      </div>
      <p class="gtp2s9-rationale">{rationale}</p>
    </div>
  </div>
</section>
"""


__all__ = [
    "FREEZE_TOKEN",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STAGE5_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAGE5_MARKER",
    "build_best_bet_html",
]
