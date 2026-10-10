"""CFB Game Total Page 2 Step 7 — Line Lab + Best Bet.

Presentation-only rendering for caller-owned alternate total-line scenarios and
the caller-owned final recommendation. The component switches among supplied
scenario values without fetching, projecting, calculating probabilities, or
creating betting recommendations.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from math import isfinite
from typing import Any

STEP3_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
STEP4_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
STEP5_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_FROZEN"
STEP6_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP6_TRENDS_SCORING_BREAKDOWN_FROZEN"
STEP7_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP7_LINE_LAB_BEST_BET_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP7_LINE_LAB_BEST_BET_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
RECOMMENDATION_LOGIC_ADDED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

PAGE2_STEP7_CSS = r"""
<style>
.gtp2s7-wrap{max-width:1180px;margin:0 auto 20px;color:#f7fbff;scroll-margin-top:18px}
.gtp2s7-card{overflow:hidden;border:1px solid rgba(75,197,255,.34);border-radius:20px;background:radial-gradient(circle at 12% 0,rgba(36,184,243,.13),transparent 34%),linear-gradient(180deg,rgba(7,27,41,.98),rgba(4,15,24,.99));box-shadow:0 16px 38px rgba(0,0,0,.25),0 0 30px rgba(46,190,255,.06)}
.gtp2s7-head{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:17px 18px 13px;border-bottom:1px solid rgba(82,174,211,.18)}
.gtp2s7-kicker{display:block;margin-bottom:5px;color:#66d9ff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}
.gtp2s7-head h3{margin:0;color:#fff;font-size:20px;line-height:1.05;font-weight:1000;letter-spacing:-.02em}
.gtp2s7-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:750}
.gtp2s7-owned{padding:5px 9px;border:1px solid rgba(86,202,246,.24);border-radius:999px;background:rgba(11,67,94,.26);color:#83dfff;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.gtp2s7-body{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(320px,.92fr);gap:12px;padding:14px}
.gtp2s7-panel{border:1px solid rgba(82,163,197,.20);border-radius:16px;background:rgba(8,29,43,.73);padding:13px}
.gtp2s7-panel-title{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.gtp2s7-panel-title strong{color:#eaf9ff;font-size:10px;font-weight:1000}.gtp2s7-panel-title span{color:#6edfff;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}
.gtp2s7-line-radio{position:absolute;opacity:0;pointer-events:none}
.gtp2s7-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-bottom:10px}
.gtp2s7-option{min-width:0;padding:10px 8px;border:1px solid rgba(78,157,191,.18);border-radius:11px;background:rgba(6,24,36,.72);text-align:center;cursor:pointer;transition:border-color .15s ease,background .15s ease,transform .15s ease}.gtp2s7-option:hover{border-color:rgba(87,214,255,.42);transform:translateY(-1px)}.gtp2s7-option b{display:block;color:#eaf9ff;font-size:11px;font-weight:1000}.gtp2s7-option small{display:block;margin-top:4px;color:#7697aa;font-size:6px;font-weight:850;line-height:1.35}
.gtp2s7-scenario-stage{min-height:118px}.gtp2s7-scenario{display:none;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:12px;border:1px solid rgba(86,202,246,.20);border-radius:13px;background:linear-gradient(180deg,rgba(8,47,66,.58),rgba(6,25,38,.76))}
.gtp2s7-scenario article{padding:12px 10px;border:1px solid rgba(84,163,196,.18);border-radius:12px;background:rgba(7,28,42,.80);text-align:center}.gtp2s7-scenario span{display:block;color:#7899ac;font-size:6px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.gtp2s7-scenario strong{display:block;margin-top:5px;color:#f8fdff;font-size:15px;font-weight:1000;overflow-wrap:anywhere}.gtp2s7-scenario article:nth-child(2) strong{color:#72e0ff}.gtp2s7-scenario article:nth-child(3) strong{color:#7ce9c0}
.gtp2s7-empty{display:grid;place-items:center;min-height:105px;border:1px solid rgba(86,202,246,.16);border-radius:13px;color:#7899ac;font-size:16px;font-weight:1000}
.gtp2s7-best{position:relative;overflow:hidden;border-color:rgba(76,225,176,.30);background:radial-gradient(circle at 90% 0,rgba(54,223,164,.12),transparent 38%),rgba(8,31,42,.80)}.gtp2s7-best::before{content:"";position:absolute;left:0;top:0;right:0;height:2px;background:linear-gradient(90deg,#4fe1bb,rgba(94,218,255,.70),transparent)}
.gtp2s7-pick{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px;border:1px solid rgba(73,220,174,.24);border-radius:13px;background:rgba(9,55,50,.27)}.gtp2s7-pick span{color:#87b4aa;font-size:7px;font-weight:950;text-transform:uppercase;letter-spacing:.08em}.gtp2s7-pick strong{display:block;margin-top:4px;color:#7af0c2;font-size:23px;font-weight:1000;letter-spacing:-.03em}.gtp2s7-pick em{font-style:normal;color:#dffbf2;font-size:12px;font-weight:1000;text-align:right}
.gtp2s7-best-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:9px}.gtp2s7-best-grid article{padding:10px;border:1px solid rgba(78,171,192,.15);border-radius:11px;background:rgba(6,26,37,.67)}.gtp2s7-best-grid span{display:block;color:#7393a6;font-size:6px;font-weight:950;letter-spacing:.07em;text-transform:uppercase}.gtp2s7-best-grid strong{display:block;margin-top:5px;color:#f8fdff;font-size:13px;font-weight:1000;overflow-wrap:anywhere}
.gtp2s7-rationale{margin:9px 0 0;padding:10px 11px;border:1px solid rgba(89,187,210,.14);border-radius:11px;background:rgba(4,21,31,.58);color:#9db6c3;font-size:8px;font-weight:750;line-height:1.5;overflow-wrap:anywhere}
@media(max-width:760px){.gtp2s7-head{align-items:start;flex-direction:column;gap:9px}.gtp2s7-owned{align-self:flex-start}.gtp2s7-body{grid-template-columns:1fr}.gtp2s7-options{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:480px){.gtp2s7-card{border-radius:17px}.gtp2s7-head{padding:14px 13px 11px}.gtp2s7-head h3{font-size:18px}.gtp2s7-body{padding:10px;gap:8px}.gtp2s7-panel{padding:10px}.gtp2s7-options{display:flex;overflow-x:auto;gap:6px;scrollbar-width:none}.gtp2s7-options::-webkit-scrollbar{display:none}.gtp2s7-option{min-width:102px}.gtp2s7-scenario{gap:5px;padding:9px}.gtp2s7-scenario article{padding:10px 5px}.gtp2s7-scenario strong{font-size:12px}.gtp2s7-pick strong{font-size:20px}.gtp2s7-best-grid{gap:6px}}
</style>
"""


def _display(value: Any) -> str:
    """Escape display text and collapse any non-finite numeric scalar to an em dash."""
    if value is None:
        return "—"
    if not isinstance(value, (str, bytes, bool)):
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            pass
        else:
            if not isfinite(numeric):
                return "—"
    text = str(value).strip()
    return escape(text) if text else "—"


def _scenario_rows(values: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    return [row for row in (values or []) if isinstance(row, Mapping)]


def _selected_index(rows: Sequence[Mapping[str, Any]], selected_line: Any) -> int:
    if not rows:
        return 0
    selected = _display(selected_line)
    for index, row in enumerate(rows):
        if _display(row.get("line")) == selected:
            return index
    return 0


def _radio_html(index: int, selected_index: int) -> str:
    checked = " checked" if index == selected_index else ""
    return (
        f'<input id="gtp2s7-line-{index}" type="radio" name="gtp2s7-line-choice"{checked} '
        f'class="gtp2s7-line-radio" />'
    )


def _option_html(row: Mapping[str, Any], index: int) -> str:
    line = _display(row.get("line"))
    over = _display(row.get("over_probability"))
    under = _display(row.get("under_probability"))
    return (
        f'<label class="gtp2s7-option" for="gtp2s7-line-{index}" data-line-index="{index}" '
        f'data-line="{line}" data-over="{over}" data-under="{under}">'
        f'<b>{line}</b><small>Over {over} • Under {under}</small></label>'
    )


def _scenario_html(row: Mapping[str, Any], index: int) -> str:
    line = _display(row.get("line"))
    over = _display(row.get("over_probability"))
    under = _display(row.get("under_probability"))
    return (
        f'<div class="gtp2s7-scenario gtp2s7-scenario-{index}" data-scenario-line="{line}">'
        f'<article><span>Selected Line</span><strong>{line}</strong></article>'
        f'<article><span>Over Probability</span><strong>{over}</strong></article>'
        f'<article><span>Under Probability</span><strong>{under}</strong></article>'
        f'</div>'
    )


def _scenario_switch_css(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    selectors = "".join(
        f'#gtp2s7-line-{index}:checked~.gtp2s7-scenario-stage .gtp2s7-scenario-{index}'
        + '{display:grid}'
        for index, _ in enumerate(rows)
    )
    selected_labels = "".join(
        f'#gtp2s7-line-{index}:checked~.gtp2s7-options label[for="gtp2s7-line-{index}"]'
        + '{border-color:rgba(87,214,255,.58);background:linear-gradient(180deg,rgba(10,65,89,.62),rgba(6,28,42,.88));box-shadow:0 0 18px rgba(65,200,255,.08)}'
        for index, _ in enumerate(rows)
    )
    return f"<style>{selectors}{selected_labels}</style>"


def build_line_lab_best_bet_html(
    *,
    line_scenarios: Sequence[Mapping[str, Any]] | None,
    selected_line: Any,
    recommendation: Mapping[str, Any] | None,
) -> str:
    """Render Step 7 from already-owned scenarios and recommendation values."""
    rows = _scenario_rows(line_scenarios)
    selected_index = _selected_index(rows, selected_line)
    selected = rows[selected_index] if rows else {}
    selected_line_display = _display(selected.get("line") if rows else selected_line)
    selected_over = _display(selected.get("over_probability"))
    selected_under = _display(selected.get("under_probability"))
    option_count = len(rows)

    radios_html = "".join(_radio_html(index, selected_index) for index, _ in enumerate(rows))
    options_html = "".join(_option_html(row, index) for index, row in enumerate(rows))
    scenarios_html = "".join(_scenario_html(row, index) for index, row in enumerate(rows))
    if not rows:
        options_html = '<span class="gtp2s7-option"><b>—</b><small>Over — • Under —</small></span>'
        scenarios_html = '<div class="gtp2s7-empty">—</div>'
    switch_css = _scenario_switch_css(rows)

    rec = recommendation if isinstance(recommendation, Mapping) else {}
    side = _display(rec.get("side"))
    rec_line = _display(rec.get("line"))
    probability = _display(rec.get("probability"))
    expected_total = _display(rec.get("expected_total"))
    edge = _display(rec.get("edge"))
    confidence = _display(rec.get("confidence"))
    rationale = _display(rec.get("rationale"))

    return f"""
{PAGE2_STEP7_CSS}
{switch_css}
<section id="gtp2-line-lab" class="gtp2s7-wrap" data-step7="{STEP7_MARKER}" data-testid="gtp2s7-line-lab" data-value-ownership="precomputed-inputs">
  <div class="gtp2s7-card">
    <header class="gtp2s7-head">
      <div>
        <span class="gtp2s7-kicker">Stage 4 • Line Lab</span>
        <h3>Line Lab + Best Bet</h3>
        <p>Tap a supplied total line to inspect its precomputed probabilities without changing the underlying model.</p>
      </div>
      <span class="gtp2s7-owned">Display only • no probability recompute</span>
    </header>
    <div class="gtp2s7-body">
      <div class="gtp2s7-panel" data-line-option-count="{option_count}" data-selected-line="{selected_line_display}" data-selected-over="{selected_over}" data-selected-under="{selected_under}">
        <div class="gtp2s7-panel-title"><strong>Line Lab</strong><span>{option_count} owned scenarios</span></div>
        {radios_html}
        <div class="gtp2s7-options">{options_html}</div>
        <div class="gtp2s7-scenario-stage">{scenarios_html}</div>
      </div>
      <div id="gtp2-best-bet" class="gtp2s7-panel gtp2s7-best" data-testid="gtp2s7-best-bet">
        <div class="gtp2s7-panel-title"><strong>Best Bet</strong><span>Caller-owned recommendation</span></div>
        <div class="gtp2s7-pick">
          <div><span>Recommendation</span><strong>{side}</strong></div>
          <em>Line {rec_line}<br>{probability}</em>
        </div>
        <div class="gtp2s7-best-grid">
          <article><span>Expected Total</span><strong>{expected_total}</strong></article>
          <article><span>Edge</span><strong>{edge}</strong></article>
          <article><span>Confidence</span><strong>{confidence}</strong></article>
          <article><span>Probability</span><strong>{probability}</strong></article>
        </div>
        <p class="gtp2s7-rationale">{rationale}</p>
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
    "PAGE2_STEP7_CSS",
    "RECOMMENDATION_LOGIC_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_FREEZE_TOKEN",
    "STEP4_FREEZE_TOKEN",
    "STEP5_FREEZE_TOKEN",
    "STEP6_FREEZE_TOKEN",
    "STEP7_MARKER",
    "build_line_lab_best_bet_html",
]
