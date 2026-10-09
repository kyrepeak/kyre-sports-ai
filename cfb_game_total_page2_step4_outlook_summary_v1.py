"""CFB Game Total Page 2 Step 4 — Outlook + Projection Summary.

Presentation-only Page-2 component. It renders already-owned probability,
projection, market-line, edge, and confidence values. It performs no network
calls and does not calculate or alter model, probability, projection, market
ownership, sportsbook influence, Page 1, or frozen Page-2 predecessors.
"""
from __future__ import annotations

from html import escape
from typing import Any

STEP2_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
STEP3_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
STEP4_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

PAGE2_STEP4_CSS = r"""
<style>
.gtp2s4-wrap{max-width:1180px;margin:0 auto 20px;color:#f7fbff;scroll-margin-top:18px}
.gtp2s4-card{position:relative;overflow:hidden;border:1px solid rgba(75,197,255,.34);border-radius:20px;background:radial-gradient(circle at 13% 0,rgba(31,179,245,.13),transparent 34%),linear-gradient(180deg,rgba(7,27,41,.98),rgba(4,15,24,.99));box-shadow:0 16px 38px rgba(0,0,0,.26),0 0 28px rgba(46,190,255,.05)}
.gtp2s4-head{display:flex;align-items:end;justify-content:space-between;gap:18px;padding:17px 18px 13px;border-bottom:1px solid rgba(82,174,211,.17)}
.gtp2s4-kicker{display:block;margin-bottom:5px;color:#66d9ff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}
.gtp2s4-head h3{margin:0;color:#fff;font-size:20px;line-height:1.05;font-weight:1000;letter-spacing:-.02em}
.gtp2s4-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:750}
.gtp2s4-owned{padding:5px 9px;border:1px solid rgba(86,202,246,.24);border-radius:999px;background:rgba(11,67,94,.26);color:#83dfff;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.gtp2s4-body{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr);gap:12px;padding:14px}
.gtp2s4-probs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.gtp2s4-prob{position:relative;min-width:0;padding:16px;border:1px solid rgba(88,166,198,.22);border-radius:16px;background:rgba(10,35,51,.76)}
.gtp2s4-prob.over{border-color:rgba(52,221,165,.34);background:linear-gradient(145deg,rgba(10,73,61,.36),rgba(8,31,45,.83))}
.gtp2s4-prob.under{border-color:rgba(83,166,255,.34);background:linear-gradient(145deg,rgba(11,58,102,.38),rgba(8,31,45,.83))}
.gtp2s4-prob span{display:block;color:#92acbd;font-size:8px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}
.gtp2s4-prob strong{display:block;margin-top:7px;color:#fff;font-size:30px;line-height:1;font-weight:1000;letter-spacing:-.035em}
.gtp2s4-prob.over strong{color:#68efba}.gtp2s4-prob.under strong{color:#79c2ff}
.gtp2s4-prob em{display:block;margin-top:7px;color:#7893a5;font-style:normal;font-size:8px;font-weight:800}
.gtp2s4-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.gtp2s4-metric{min-width:0;padding:13px;border:1px solid rgba(85,157,188,.18);border-radius:14px;background:rgba(8,28,42,.72)}
.gtp2s4-metric span{display:block;color:#7897aa;font-size:7px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}
.gtp2s4-metric strong{display:block;margin-top:7px;color:#f8fbff;font-size:19px;line-height:1.08;font-weight:1000;overflow-wrap:anywhere}
.gtp2s4-metric.edge strong{color:#62dfff}.gtp2s4-metric.confidence strong{color:#78efbd;font-size:14px;line-height:1.2}
@media(max-width:760px){.gtp2s4-head{align-items:start;flex-direction:column;gap:9px}.gtp2s4-body{grid-template-columns:1fr}.gtp2s4-prob strong{font-size:27px}.gtp2s4-owned{align-self:flex-start}}
@media(max-width:480px){.gtp2s4-card{border-radius:17px}.gtp2s4-head{padding:14px 13px 11px}.gtp2s4-head h3{font-size:18px}.gtp2s4-body{padding:10px}.gtp2s4-probs{gap:7px}.gtp2s4-prob{padding:13px 10px}.gtp2s4-prob strong{font-size:24px}.gtp2s4-metrics{gap:7px}.gtp2s4-metric{padding:11px 9px}.gtp2s4-metric strong{font-size:16px}.gtp2s4-metric.confidence strong{font-size:12px}}
</style>
"""


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _format_numeric(value: Any, *, percent: bool = False, signed: bool = False) -> str:
    text = _clean(value)
    if not text:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        if percent and not text.endswith("%"):
            try:
                text = f"{float(text):.1f}%"
            except ValueError:
                pass
        return escape(text)
    if percent:
        if 0.0 <= numeric <= 1.0:
            numeric *= 100.0
        return f"{numeric:.1f}%"
    if signed:
        return f"{numeric:+.1f}"
    return f"{numeric:.1f}"


def build_outlook_projection_summary_html(
    *,
    over_probability: Any,
    under_probability: Any,
    projected_total: Any,
    market_line: Any,
    edge: Any,
    confidence_label: Any,
) -> str:
    """Render Step 4 from already-owned values without recomputing them."""
    over_text = _format_numeric(over_probability, percent=True)
    under_text = _format_numeric(under_probability, percent=True)
    projected_text = _format_numeric(projected_total)
    market_text = _format_numeric(market_line)
    edge_text = _format_numeric(edge, signed=True)
    confidence_text = escape(_clean(confidence_label)) if _clean(confidence_label) else "—"

    return f"""
{PAGE2_STEP4_CSS}
<section id="gtp2-outlook" class="gtp2s4-wrap" data-step4="{STEP4_MARKER}" data-testid="gtp2s4-outlook" data-value-ownership="precomputed-inputs">
  <div class="gtp2s4-card">
    <header class="gtp2s4-head">
      <div>
        <span class="gtp2s4-kicker">Stage 1 • Outlook</span>
        <h3>Outlook + Projection Summary</h3>
        <p>Model outlook compared with the already-owned market total.</p>
      </div>
      <span class="gtp2s4-owned">Display only • no recompute</span>
    </header>
    <div class="gtp2s4-body">
      <div class="gtp2s4-probs" aria-label="Over and Under probabilities">
        <article class="gtp2s4-prob over"><span>Over Probability</span><strong>{over_text}</strong><em>Current model probability</em></article>
        <article class="gtp2s4-prob under"><span>Under Probability</span><strong>{under_text}</strong><em>Current model probability</em></article>
      </div>
      <div class="gtp2s4-metrics">
        <article class="gtp2s4-metric"><span>Projected Total</span><strong>{projected_text}</strong></article>
        <article class="gtp2s4-metric"><span>Market Line</span><strong>{market_text}</strong></article>
        <article class="gtp2s4-metric edge"><span>Edge</span><strong>{edge_text}</strong></article>
        <article class="gtp2s4-metric confidence"><span>Confidence</span><strong>{confidence_text}</strong></article>
      </div>
    </div>
  </div>
</section>
"""


__all__ = [
    "FREEZE_TOKEN",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STEP4_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_FREEZE_TOKEN",
    "STEP3_FREEZE_TOKEN",
    "STEP4_MARKER",
    "build_outlook_projection_summary_html",
]
