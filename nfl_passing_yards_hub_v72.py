"""NFL Passing Yards V72 — Matchup Intelligence Step 3.

Additive presentation-only wrapper over frozen V71. It consolidates already-
certified opponent pass-defense, pressure, pace, and projection-volume evidence
into one selected-QB matchup intelligence panel.

Unsupported coverage-shell and explosive-pass fields fail closed as
UNAVAILABLE — NOT SYNTHESIZED. No projection, probability, market math, data
provider, sportsbook, widget, navigation, or router behavior is changed here.
"""
from __future__ import annotations

from html import escape
import re

import nfl_passing_yards_hub_v69 as detail_owner
import nfl_passing_yards_hub_v71 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v71

MODEL_VERSION = "NFL PASSING YARDS V72 • MATCHUP INTELLIGENCE STEP 3"
FROZEN_PRIOR = "nfl_passing_yards_hub_v71"
MATCHUP_INTELLIGENCE_VERSION = "v72"
NEW_PHASE_STEP = 3
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_MATCHUP_CSS = r"""
<style data-passing-yards-matchup-intelligence-css="v72">
.ks-py72-matchup,.ks-py72-matchup *{box-sizing:border-box}
.ks-py72-matchup{
  margin:10px 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:14px;background:linear-gradient(145deg,var(--kyre-sem-surface-panel),var(--kyre-sem-surface-panel-alt));
}
.ks-py72-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}
.ks-py72-kicker{font-size:.54rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py72-title{margin-top:3px;font-size:.96rem;font-weight:950;color:var(--kyre-sem-text-primary)}
.ks-py72-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py72-hero{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:9px}
.ks-py72-card{min-width:0;padding:9px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;background:rgba(255,255,255,.014)}
.ks-py72-card b{display:block;font-size:.84rem;line-height:1.2;color:var(--kyre-sem-text-primary);overflow-wrap:anywhere}
.ks-py72-card span{display:block;margin-top:4px;font-size:.47rem;font-weight:900;text-transform:uppercase;color:var(--kyre-sem-text-muted)}
.ks-py72-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.ks-py72-row{min-width:0;padding:9px 10px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;background:rgba(255,255,255,.01)}
.ks-py72-row strong{display:block;font-size:.62rem;color:var(--kyre-sem-text-primary);line-height:1.3}
.ks-py72-row span{display:block;margin-top:4px;font-size:.55rem;color:var(--kyre-sem-text-muted);line-height:1.45;overflow-wrap:anywhere}
.ks-py72-script{margin-top:9px;padding:9px 10px;border-top:1px solid var(--kyre-sem-border-soft);font-size:.58rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
.ks-py72-script strong{color:var(--kyre-sem-text-primary)}
.ks-py72-gap{margin-top:7px;font-size:.53rem;line-height:1.45;color:var(--kyre-sem-text-muted)}
@media(max-width:760px){
  .ks-py72-head{flex-direction:column}.ks-py72-badge{align-self:flex-start}
  .ks-py72-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-py72-grid{grid-template-columns:1fr}
}
@media(max-width:420px){.ks-py72-matchup{padding:10px}.ks-py72-hero{grid-template-columns:1fr}}
</style>
"""

_UNAVAILABLE = "UNAVAILABLE — NOT SYNTHESIZED"


def _safe(value: str, fallback: str = "—") -> str:
    return detail_owner._safe_text(value, limit=180, fallback=fallback)


def _span(source: str, label: str, fallback: str = "—") -> str:
    value = detail_owner._extract_b_span(source, label)
    return _safe(value, fallback) if value != "—" else fallback


def _label(source: str, label: str, fallback: str = "—") -> str:
    value = detail_owner._extract_b_label(source, label)
    return _safe(value, fallback) if value != "—" else fallback


def _class_text(source: str, class_prefix: str, fallback: str = "—") -> str:
    pattern = rf'class="[^"]*{re.escape(class_prefix)}[^"]*"[^>]*>\s*([^<]+?)\s*</'
    match = re.search(pattern, str(source or ""), flags=re.S | re.I)
    return _safe(match.group(1), fallback) if match else fallback


def _recent3_pass_yards(source: str) -> str:
    match = re.search(
        r"Recent\s*3:\s*<b[^>]*>([^<]+)</b>\s*pass\s*yds\s*allowed/game",
        str(source or ""),
        flags=re.S | re.I,
    )
    return _safe(match.group(1), "—") if match else "—"


def _blitz_context(source: str) -> str:
    match = re.search(r"Blitz\s*context:\s*([^<]+)", str(source or ""), flags=re.S | re.I)
    return _safe(match.group(1), _UNAVAILABLE) if match else _UNAVAILABLE


def _offense_team(source: str) -> str:
    match = re.search(
        r'class="kpy-xsub"[^>]*>\s*([^<]+?)\s+protection\s+vs\s+',
        str(source or ""),
        flags=re.S | re.I,
    )
    return _safe(match.group(1), "") if match else ""


def _team_tendency(source: str, team: str) -> str:
    if not team:
        return "CHECK"
    match = re.search(
        rf"<h4>\s*{re.escape(team)}\s*•\s*([^<]+)</h4>",
        str(source or ""),
        flags=re.S | re.I,
    )
    return _safe(match.group(1), "CHECK") if match else "CHECK"


def _pace_context(source: str) -> str:
    match = re.search(
        r"Game\s*Environment\s*•\s*([^<]+?)\s*pace\s*context",
        str(source or ""),
        flags=re.S | re.I,
    )
    return _safe(match.group(1), "CHECK") if match else "CHECK"


def _optional_verified_metric(source: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        value = _span(source, label, "")
        if value:
            return value
        value = _label(source, label, "")
        if value:
            return value
    return _UNAVAILABLE


def build_matchup_intelligence(source: str) -> str:
    """Consolidate existing verified matchup evidence; never manufacture gaps."""
    pass_rank = _span(source, "Pass Yds Rank", "Rank unavailable")
    pass_yds_allowed = _span(source, "Pass Yds Allowed/G")
    attempts_allowed = _span(source, "Attempts Allowed/G")
    completion_allowed = _span(source, "Completion Allowed")
    ypa_allowed = _span(source, "Yards/Att Allowed")
    recent3_allowed = _recent3_pass_yards(source)

    pressure_state = _class_text(source, "kpy-xgrade", "CHECK")
    defense_sack_rate = _span(source, "Defense Sack Rate")
    defense_sacks_game = _span(source, "Defense Sacks/G")
    blitz = _blitz_context(source)

    pace = _pace_context(source)
    expected_attempts = _span(source, "Expected Attempts")
    offense = _offense_team(source)
    tendency = _team_tendency(source, offense)

    coverage = _optional_verified_metric(
        source,
        ("Coverage Tendency", "Primary Coverage", "Coverage Shell"),
    )
    explosives = _optional_verified_metric(
        source,
        ("Explosive Passes Allowed", "Explosive Pass Allowed/G", "20+ Passes Allowed"),
    )

    matchup_grade = _class_text(source, "kpy-grade", "CHECK")
    game_script = (
        f"{tendency} passing tendency • {pace} pace • {expected_attempts} expected attempts"
    )

    rows = (
        ("Opponent attempts allowed", attempts_allowed, "Verified opponent passing volume allowed per game."),
        ("Opponent completion allowed", completion_allowed, "Verified completion percentage allowed."),
        ("Opponent Y/A allowed", ypa_allowed, "Verified passing efficiency allowed per attempt."),
        ("Recent 3 pass yards allowed", recent3_allowed, "Recent verified opponent pass-defense form."),
        ("Pressure state", pressure_state, f"Defense sack rate {defense_sack_rate} • sacks/game {defense_sacks_game}."),
        ("Blitz context", blitz, "Fails closed when the verified source does not expose stable blitz data."),
        ("Coverage tendency", coverage, "No coverage shell is inferred from sacks, completion rate, or opponent results."),
        ("Explosive passes allowed", explosives, "No explosive-play count is reverse-engineered from total passing yards."),
    )
    row_html = "".join(
        f'<div class="ks-py72-row" data-matchup-intelligence-field="{idx}">'
        f'<strong>{escape(title)}</strong><span><b>{escape(value)}</b> • {escape(note)}</span></div>'
        for idx, (title, value, note) in enumerate(rows, start=1)
    )

    source_gap = ""
    if coverage == _UNAVAILABLE or explosives == _UNAVAILABLE:
        source_gap = (
            '<div class="ks-py72-gap" data-matchup-intelligence-source-gap="true">'
            'Source-gap guardrail: unsupported coverage/explosive fields remain unavailable rather than being estimated.'
            '</div>'
        )

    return (
        '<section class="ks-py72-matchup" data-passing-yards-matchup-intelligence="v72" '
        'data-passing-yards-v223-runtime="matchup-intelligence-step3">'
        '<div class="ks-py72-head"><div>'
        '<div class="ks-py72-kicker">Matchup intelligence • verified evidence</div>'
        '<div class="ks-py72-title">How this defense can shape the passing path</div>'
        f'</div><div class="ks-py72-badge">{escape(matchup_grade)}</div></div>'
        '<div class="ks-py72-hero">'
        f'<div class="ks-py72-card" data-matchup-hero="rank"><b>{escape(pass_rank)}</b><span>Pass Defense Rank</span></div>'
        f'<div class="ks-py72-card" data-matchup-hero="yards"><b>{escape(pass_yds_allowed)}</b><span>Pass Yds Allowed/G</span></div>'
        f'<div class="ks-py72-card" data-matchup-hero="pressure"><b>{escape(defense_sack_rate)}</b><span>Defense Sack Rate</span></div>'
        f'<div class="ks-py72-card" data-matchup-hero="attempts"><b>{escape(expected_attempts)}</b><span>Expected Attempts</span></div>'
        '</div>'
        f'<div class="ks-py72-grid">{row_html}</div>'
        '<div class="ks-py72-script" data-matchup-game-script="v72">'
        f'<strong>Volume / game-script signal:</strong> {escape(game_script)}. '
        'This is descriptive matchup context, not a score prediction or a new projection adjustment.'
        '</div>'
        f'{source_gap}</section>'
    )


def _inject_matchup_intelligence(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-projection-explainability="v71"' not in text
        or 'data-passing-yards-matchup-intelligence="v72"' in text
    ):
        return text

    panel = build_matchup_intelligence(text)
    anchor = '<section class="ks-py69-clean-detail" data-passing-yards-clean-detail="projection"'
    pos = text.find(anchor)
    if pos < 0:
        return text
    text = text[:pos] + panel + text[pos:]

    ready = 'data-passing-yards-explainability-ready="v71"'
    if ready in text and 'data-passing-yards-matchup-intelligence-ready="v72"' not in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-matchup-intelligence-ready="v72"',
            1,
        )
    return _MATCHUP_CSS + text


def _selected_analysis_v72(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_matchup_intelligence(
        _FROZEN_SELECTED_ANALYSIS(captured, slot)
    )


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v71
    prior._selected_analysis_v71 = _selected_analysis_v72
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v71 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V72 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MATCHUP_INTELLIGENCE_VERSION",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_inject_matchup_intelligence",
    "_selected_analysis_v72",
    "build_matchup_intelligence",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
