"""Readable presentation-only adapter for frozen CFB O/U Step 10 history output.

Step 10 history is already produced by the certified runtime slate. This module
only renders the existing recent-game and head-to-head evidence. It never
fetches data, recomputes history, changes a projection, or consumes sportsbook
values.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 10 V1 • HISTORICAL MATCHUP CONTEXT"
PROJECTION_WEIGHT = 0.0
ANALYSIS_LINE_WEIGHT = 0.0
SELECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _int(value: Any) -> str:
    try:
        return str(int(float(value)))
    except Exception:
        return "—"


def _pct(value: Any, digits: int = 1) -> str:
    try:
        return f"{100.0 * float(value):.{digits}f}%"
    except Exception:
        return "—"


def _official_id(value: Any) -> str:
    value = _clean(value)
    return value if value.isdigit() else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _team_label(engine: Mapping[str, Any], side: str) -> str:
    direct = (
        engine.get(f"{side}_team")
        or engine.get(f"{side}_name")
        or engine.get(f"{side}_event_team")
    )
    if direct:
        return _clean(direct)
    summary = _mapping(engine.get(f"{side}_recent"))
    sample = summary.get("sample")
    if isinstance(sample, list) and sample:
        first = _mapping(sample[0])
        name = _clean(first.get("team_name"))
        if name:
            return name
    return "Away team" if side == "away" else "Home team"


def _summary_card(label: str, summary: Mapping[str, Any]) -> str:
    games = int(float(summary.get("games") or 0))
    if games <= 0:
        return f"""
<div class="hist10-card">
 <b>📚 {escape(label)}</b>
 <div class="hist10-muted">No completed pre-kickoff recent-game sample is available.</div>
 <div class="hist10-gated">UNAVAILABLE</div>
</div>
"""
    return f"""
<div class="hist10-card">
 <b>📚 {escape(label)} • last {games} completed games</b>
 <div class="hist10-muted">Strict cutoff: completed games before the target kickoff only.</div>
 <div class="hist10-metrics">
  <div><strong>{_num(summary.get("avg_points_for"))}</strong><small>avg points for</small></div>
  <div><strong>{_num(summary.get("avg_points_against"))}</strong><small>avg points against</small></div>
  <div><strong>{_num(summary.get("avg_combined_total"))}</strong><small>avg combined total</small></div>
  <div><strong>{_int(summary.get("wins"))}–{_int(summary.get("losses"))}</strong><small>win-loss</small></div>
 </div>
</div>
"""


def _h2h_panel(engine: Mapping[str, Any], away_label: str, home_label: str) -> str:
    # The recovery layer may add an all-time Winsipedia series while preserving
    # the exact ESPN H2H payload. Prefer the exact-team-ID payload when present.
    h2h = _mapping(engine.get("head_to_head"))
    external = _mapping(engine.get("all_time_head_to_head"))
    selected = h2h if h2h.get("meetings") else external
    meetings = int(float(selected.get("meetings") or 0))
    if meetings <= 0:
        return """
<div class="hist10-h2h">
 <b>🤝 VERIFIED HEAD-TO-HEAD HISTORY</b>
 <span>No verified historical matchup evidence was found inside the certified lookback. Nothing is fabricated.</span>
</div>
"""
    latest = _mapping(selected.get("latest"))
    date = _clean(latest.get("date"))[:10] or "date unavailable"
    source = _clean(selected.get("source")) or "ESPN team-schedule history"
    avg = _num(selected.get("avg_combined_total"))
    record = ""
    if selected.get("away_wins") is not None or selected.get("home_wins") is not None:
        record = (
            f" • series record {away_label} {_int(selected.get('away_wins'))}–"
            f"{_int(selected.get('home_wins'))} {home_label}"
        )
    score = ""
    if latest.get("away_points") is not None or latest.get("home_points") is not None:
        score = (
            f" • latest score {_int(latest.get('away_points'))}–"
            f"{_int(latest.get('home_points'))}"
        )
    elif latest.get("points_for") is not None or latest.get("points_against") is not None:
        score = (
            f" • latest observed score {_int(latest.get('points_for'))}–"
            f"{_int(latest.get('points_against'))}"
        )
    return f"""
<div class="hist10-h2h">
 <b>🤝 VERIFIED HEAD-TO-HEAD HISTORY • {meetings} meeting(s)</b>
 <span>Latest completed meeting: {escape(date)} • average combined total {avg}{score}{record} • source: {escape(source)}.</span>
</div>
"""


def _status(engine: Mapping[str, Any]) -> str:
    if engine.get("model_ready") is True:
        return "READY"
    h2h = _mapping(engine.get("head_to_head"))
    external = _mapping(engine.get("all_time_head_to_head"))
    if engine.get("context_ready") is True or h2h.get("meetings") or external.get("ready"):
        return "LIMITED"
    return "GATED"


def _reason(engine: Mapping[str, Any]) -> str:
    reason = _clean(engine.get("reason"))
    if reason:
        return reason
    if _status(engine) == "GATED":
        return "Verified completed pre-kickoff historical evidence is incomplete"
    return "Recent history is descriptive context; the certified projection remains unchanged"


def render_step10(engine: Mapping[str, Any]) -> str:
    """Render the existing Step 10 history payload without recomputation."""
    if not isinstance(engine, Mapping):
        engine = {}
    status = _status(engine)
    away_label = _team_label(engine, "away")
    home_label = _team_label(engine, "home")
    away_id = _official_id(engine.get("away_espn_team_id"))
    home_id = _official_id(engine.get("home_espn_team_id"))
    ids = (
        f"ESPN team IDs {escape(away_id)} / {escape(home_id)}"
        if away_id and home_id
        else "exact ESPN team IDs are not attached to this display payload"
    )
    coverage = _pct(engine.get("coverage"))
    if status == "GATED":
        return f"""
<div class="hist10-wrap">
<style>{_CSS}</style>
<div class="hist10-title"><b>🟪 STEP 10 • HISTORICAL MATCHUP CONTEXT</b><span>GATED</span></div>
<div class="hist10-gate"><b>HISTORICAL CONTEXT GATED</b><br>{escape(_reason(engine))}. Step 9 projection math remains active and unchanged; no verified historical matchup evidence is displayed.</div>
<div class="hist10-foot">Projection mutation: <b>OFF</b> • projected-total adjustment: <b>0.00 pts</b> • sportsbook projection weight: <b>0.0%</b> • history weight: <b>0.0%</b> • official ESPN event IDs only • no fuzzy matching • no synthetic IDs.</div>
</div>
"""
    external = _mapping(engine.get("all_time_head_to_head"))
    external_source = _clean(external.get("source")) or "not used"
    source_note = (
        f"All-time H2H fallback: {escape(external_source)} • context/audit only"
        if external.get("ready")
        else "All-time H2H fallback: unavailable"
    )
    continuity = "CERTIFIED" if engine.get("historical_roster_continuity_certified") is True else "NOT CERTIFIED"
    strength = "ADJUSTED" if engine.get("opponent_strength_adjusted_history") is True else "NOT ADJUSTED"
    return f"""
<div class="hist10-wrap">
<style>{_CSS}</style>
<div class="hist10-title"><b>🟪 STEP 10 • HISTORICAL MATCHUP CONTEXT</b><span>{escape(status)}</span></div>
<div class="hist10-intro"><b>Why it matters:</b> prior scoring shape and true team-vs-team meetings add transparent context. They are descriptive only because roster continuity and opponent-strength normalization are not certified.</div>
<div class="hist10-grid">
 {_summary_card(away_label, _mapping(engine.get("away_recent")))}
 {_summary_card(home_label, _mapping(engine.get("home_recent")))}
</div>
{_h2h_panel(engine, away_label, home_label)}
<div class="hist10-audit">
 <b>🧾 STEP 10 AUDIT</b>
 <span>History coverage <strong>{escape(coverage)}</strong> • {ids} • future-event leakage <strong>BLOCKED</strong> • target event excluded <strong>{'YES' if engine.get('target_event_excluded') is not False else 'CHECK'}</strong> • roster continuity <strong>{continuity}</strong> • opponent-strength normalization <strong>{strength}</strong>.</span>
 <span>{escape(source_note)}.</span>
</div>
<div class="hist10-warning">Projected total remains unchanged by Step 10. Analysis-line history weight <b>0.0%</b> • selection history weight <b>0.0%</b> • sportsbook input <b>0.0%</b>. This panel cannot create a pick, edge, EV, price, probability, or Monte Carlo result.</div>
<div class="hist10-foot">Official ESPN event IDs only for attached game identity • exact team IDs for ESPN history • no fuzzy matching • no synthetic IDs • frozen Steps 3–12 projection math preserved.</div>
</div>
"""


_CSS = r"""
.hist10-wrap{margin:10px 0;border:1px solid rgba(193,151,255,.30);border-radius:16px;background:#11101b;overflow:hidden;color:#f5f1fb}
.hist10-title{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(193,151,255,.14)}
.hist10-title b{color:#d9c0ff;font-size:.56rem;letter-spacing:.07em}.hist10-title span{font-size:.42rem;color:#c6a8ef;font-weight:950}
.hist10-intro,.hist10-muted,.hist10-foot{padding:8px 12px;color:#a49cad;font-size:.72rem;line-height:1.48}.hist10-intro{border-bottom:1px solid rgba(193,151,255,.08)}
.hist10-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.hist10-card{border:1px solid rgba(193,151,255,.14);border-radius:12px;background:#15131f;padding:9px}.hist10-card>b{display:block;color:#f9f6ff;font-size:.78rem}.hist10-card .hist10-muted{padding:4px 0 0;font-size:.68rem}
.hist10-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}.hist10-metrics div{border:1px solid rgba(193,151,255,.10);border-radius:8px;background:#100e18;padding:7px}.hist10-metrics strong{display:block;color:#ddc9ff;font-size:.72rem}.hist10-metrics small{display:block;color:#81798b;font-size:.58rem;margin-top:3px}.hist10-gated{margin-top:7px;color:#e6c96f;font-size:.68rem;font-weight:950}
.hist10-h2h{margin:0 10px 10px;border:1px solid rgba(193,151,255,.14);border-radius:11px;background:#15131f;padding:9px}.hist10-h2h b{display:block;color:#f8f4ff;font-size:.72rem}.hist10-h2h span{display:block;color:#aaa1b4;font-size:.68rem;line-height:1.48;margin-top:4px}
.hist10-audit{margin:0 10px 10px;border:1px solid rgba(193,151,255,.14);border-radius:11px;background:#15131f;padding:9px}.hist10-audit b{display:block;color:#d9c0ff;font-size:.70rem}.hist10-audit span{display:block;color:#9e96a8;font-size:.66rem;line-height:1.48;margin-top:4px}
.hist10-warning,.hist10-gate{margin:0 10px 10px;border:1px solid #65521e;border-radius:9px;background:#2a230d;color:#dfcd82;padding:8px;font-size:.68rem;line-height:1.48}.hist10-gate{margin-top:10px}
.hist10-foot{border-top:1px solid rgba(193,151,255,.09)}
@media(max-width:760px){.hist10-grid{grid-template-columns:1fr}.hist10-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

__all__ = [
    "ANALYSIS_LINE_WEIGHT",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "SELECTION_WEIGHT",
    "render_step10",
]
