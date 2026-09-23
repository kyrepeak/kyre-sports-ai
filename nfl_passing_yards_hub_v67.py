"""NFL Passing Yards V67 — New Phase Step 6 Deep Evidence.

Additive presentation-only wrapper over frozen V66. Step 6 exposes the existing
certified evidence payloads already captured for the selected quarterback:
recent/profile evidence, opponent pass-defense evidence, pressure/protection,
personnel/availability, and game environment. It does not fetch, recalculate,
or mutate model/data/market values.
"""
from __future__ import annotations

from html import escape

import nfl_passing_yards_hub_v66 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v66

MODEL_VERSION = "NFL PASSING YARDS V67 • NEW PHASE STEP 6 DEEP EVIDENCE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v66"
DEEP_EVIDENCE_VERSION = "v67"
NEW_PHASE_STEP = 6
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_DEEP_EVIDENCE_CSS = r"""
<style data-passing-yards-deep-evidence-css="v67">
.ks-py67-deep,.ks-py67-deep *{box-sizing:border-box}
.ks-py67-deep{
  margin:12px 0 0;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);
  background:
    radial-gradient(circle at 100% 0%,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
}
.ks-py67-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.ks-py67-kicker{font-size:.54rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py67-title{margin-top:3px;font-size:.92rem;font-weight:950;line-height:1.15;color:var(--kyre-sem-text-primary)}
.ks-py67-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py67-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.ks-py67-card{
  min-width:0;padding:10px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:11px;background:rgba(255,255,255,.018);overflow-wrap:anywhere
}
.ks-py67-card[data-evidence-kind="recent"]{grid-column:1/-1}
.ks-py67-label{display:block;margin-bottom:7px;color:var(--kyre-sem-text-accent-soft);font-size:.59rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.ks-py67-body{min-width:0;color:var(--kyre-sem-text-primary);font-size:.66rem;line-height:1.45}
.ks-py67-provenance{
  margin-top:9px;padding-top:9px;border-top:1px solid var(--kyre-sem-border-soft);
  color:var(--kyre-sem-text-muted);font-size:.62rem;line-height:1.5
}
.ks-py67-provenance strong{color:var(--kyre-sem-text-primary)}
.ks-py67-method{margin-top:8px}
.ks-py67-method summary{cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:900}
.ks-py67-method p{margin:7px 0 0;color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.55}
@media(max-width:760px){
  .ks-py67-grid{grid-template-columns:1fr}
  .ks-py67-card[data-evidence-kind="recent"]{grid-column:auto}
}
@media(max-width:560px){
  .ks-py67-head{flex-direction:column;gap:8px}
  .ks-py67-badge{align-self:flex-start}
}
</style>
"""


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _evidence_card(kind: str, label: str, content: str) -> str:
    return (
        f'<section class="ks-py67-card" data-deep-evidence-kind="{escape(kind, quote=True)}">'
        f'<strong class="ks-py67-label">{escape(label)}</strong>'
        f'<div class="ks-py67-body">{content or "<div>Unavailable</div>"}</div>'
        '</section>'
    )


def build_deep_evidence(captured: dict[str, list[str]], slot: int) -> str:
    index = slot - 1
    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)

    cards = "".join((
        _evidence_card("recent", "Recent QB Games + Profile", profile),
        _evidence_card("opponent", "Opponent Pass-Defense Evidence", defense),
        _evidence_card("pressure", "Protection + Pressure Evidence", pressure),
        _evidence_card("personnel", "Personnel + Availability Evidence", personnel),
        _evidence_card("environment", "Game Environment Evidence", environment),
    ))
    return (
        '<section class="ks-py67-deep" data-passing-yards-deep-evidence="v67">'
        '<div class="ks-py67-head"><div>'
        '<div class="ks-py67-kicker">Receipts behind the analysis</div>'
        '<div class="ks-py67-title">Deep Evidence</div>'
        '</div><div class="ks-py67-badge">FROZEN SOURCE PAYLOAD</div></div>'
        f'<div class="ks-py67-grid">{cards}</div>'
        '<div class="ks-py67-provenance" data-passing-yards-evidence-provenance="v67">'
        '<strong>Source / provenance:</strong> frozen certified Passing Yards captured payloads '
        '(profile, defense, pressure, personnel, environment) • no new network request • '
        'no recalculation • sportsbook influence 0.0%</div>'
        '<details class="ks-py67-method" data-passing-yards-deep-evidence-method="v67">'
        '<summary>What Step 6 changes</summary>'
        '<p>Presentation only. Step 6 makes the already-certified supporting evidence easier '
        'to inspect for the selected quarterback. The underlying recent-form, opponent, '
        'pressure, personnel, and environment payloads remain byte-for-byte owned by the '
        'frozen upstream analysis chain.</p></details>'
        '</section>'
    )


def _inject_deep_evidence(
    body: str,
    captured: dict[str, list[str]],
    slot: int,
) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-distribution-detail="v66"' not in text
        or 'data-passing-yards-deep-evidence="v67"' in text
    ):
        return text

    close_token = "</div></article></section>"
    if close_token not in text:
        return text

    panel = build_deep_evidence(captured, slot)
    text = text.replace(close_token, "</div>" + panel + "</article></section>", 1)

    ready = 'data-passing-yards-distribution-detail-ready="v66"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-deep-evidence-ready="v67"',
            1,
        )
    return _DEEP_EVIDENCE_CSS + text


def _selected_analysis_v67(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_deep_evidence(
        _FROZEN_SELECTED_ANALYSIS(captured, slot),
        captured,
        slot,
    )


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v66
    prior._selected_analysis_v66 = _selected_analysis_v67
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v66 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V67 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DEEP_EVIDENCE_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_deep_evidence",
    "_selected_analysis_v67",
    "build_deep_evidence",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
