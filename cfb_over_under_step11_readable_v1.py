"""Readable presentation-only adapter for frozen CFB O/U Step 11 output.

Step 11 form and schedule-strength values are already produced by the
certified runtime slate. This module only renders those values. It never
fetches schedules, recomputes the bounded adjustment, changes a projection, or
consumes sportsbook values.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 11 V1 • CURRENT FORM + SCHEDULE STRENGTH"
# This is the new presentation/market influence contract; the certified
# Step-11 engine's bounded current-form blend remains separately visible.
PROJECTION_WEIGHT = 0.0
FORM_PROJECTION_BLEND = 0.18
ANALYSIS_LINE_WEIGHT = 0.0
SELECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _team_label(engine: Mapping[str, Any], side: str) -> str:
    direct = (
        engine.get(f"{side}_team")
        or engine.get(f"{side}_name")
        or engine.get(f"{side}_event_team")
    )
    if direct:
        return _clean(direct)
    form = _mapping(engine.get(f"{side}_form"))
    sample = form.get("sample")
    if isinstance(sample, list) and sample:
        first = _mapping(sample[0])
        name = _clean(first.get("team_name"))
        if name:
            return name
    return "Away team" if side == "away" else "Home team"


def _schedule_read(form: Mapping[str, Any]) -> str:
    value = form.get("avg_opponent_win_pct")
    try:
        pct = float(value)
    except Exception:
        return "OPPONENT QUALITY UNAVAILABLE"
    if pct >= 0.55:
        return "TOUGHER OPPONENT SET"
    if pct <= 0.45:
        return "LIGHTER OPPONENT SET"
    return "BALANCED OPPONENT SET"


def _form_card(label: str, form: Mapping[str, Any]) -> str:
    games = int(float(form.get("games") or 0))
    if games <= 0:
        return f"""
<div class="form11-card">
 <b>📈 {escape(label)}</b>
 <div class="form11-muted">No completed current-season sample is available before the target kickoff.</div>
 <div class="form11-gated">UNAVAILABLE</div>
</div>
"""
    return f"""
<div class="form11-card">
 <b>📈 {escape(label)} • current season • {games} game(s)</b>
 <div class="form11-badge">{escape(_schedule_read(form))}</div>
 <div class="form11-metrics">
  <div><strong>{_num(form.get("avg_points_for"))}</strong><small>avg points for</small></div>
  <div><strong>{_num(form.get("avg_points_against"))}</strong><small>avg points against</small></div>
  <div><strong>{_pct(form.get("avg_opponent_win_pct"))}</strong><small>avg opp win pct</small></div>
  <div><strong>{_pct(form.get("opponent_record_coverage"))}</strong><small>opp record coverage</small></div>
 </div>
 <div class="form11-submetrics">
  <span>SOS-adjusted PF <b>{_num(form.get("sos_adjusted_points_for"))}</b></span>
  <span>SOS-adjusted PA <b>{_num(form.get("sos_adjusted_points_against"))}</b></span>
  <span>quality factor <b>{_pct(form.get("quality_factor"))}</b></span>
  <span>sample factor <b>{_pct(form.get("sample_factor"))}</b></span>
 </div>
</div>
"""


def _status(engine: Mapping[str, Any]) -> str:
    if engine.get("model_ready") is True:
        return "READY"
    try:
        coverage = float(engine.get("coverage") or 0.0)
    except Exception:
        coverage = 0.0
    return "LIMITED" if coverage > 0.0 else "GATED"


def _reason(engine: Mapping[str, Any]) -> str:
    reason = _clean(engine.get("reason"))
    if reason:
        return reason
    if _status(engine) == "GATED":
        return "Verified current-season form and opponent-record evidence is below the Step-11 minimum"
    return "Partial current-season evidence is visible; the full Step-11 readiness gate is not cleared"


def render_step11(engine: Mapping[str, Any]) -> str:
    """Render the existing Step-11 form payload without recomputation."""
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
    season = _clean(engine.get("season")) or "current season"
    coverage = _pct(engine.get("coverage"))
    if status == "GATED":
        return f"""
<div class="form11-wrap">
<style>{_CSS}</style>
<div class="form11-title"><b>🟧 STEP 11 • CURRENT FORM + SCHEDULE STRENGTH</b><span>FORM GATED</span></div>
<div class="form11-gate"><b>FORM GATED</b><br>{escape(_reason(engine))}. The Step-11 adjustment is not applied; no projection is forced. Step 10 output remains available and unchanged.</div>
<div class="form11-foot">Projection mutation by this display layer: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b> • analysis-line form weight: <b>0.0%</b> • direct-selection form weight: <b>0.0%</b> • official ESPN event IDs only • no fuzzy matching • no synthetic IDs.</div>
</div>
"""
    limited_note = (
        f"<div class='form11-gate'><b>LIMITED EVIDENCE</b> • {escape(_reason(engine))}. "
        "The certified engine exposes context but does not claim full readiness.</div>"
        if status == "LIMITED"
        else ""
    )
    return f"""
<div class="form11-wrap">
<style>{_CSS}</style>
<div class="form11-title"><b>🟧 STEP 11 • CURRENT FORM + SCHEDULE STRENGTH</b><span>{escape(status)}</span></div>
<div class="form11-intro"><b>CURRENT SEASON ONLY</b> • {escape(season)} completed games before the target kickoff are used. The certified engine applies a bounded <b>Projection blend 18%</b> only when both sides clear the minimum sample/coverage gate; this panel displays the result without recomputation.</div>
<div class="form11-grid">
 {_form_card(away_label, _mapping(engine.get("away_form")))}
 {_form_card(home_label, _mapping(engine.get("home_form")))}
</div>
{limited_note}
<div class="form11-audit">
 <b>🧾 STEP 11 AUDIT</b>
 <span>Form-strength coverage <strong>{escape(coverage)}</strong> • {ids} • minimum sample <strong>2 games per side</strong> • minimum opponent-record coverage <strong>60%</strong> • current-season-only <strong>{'YES' if engine.get('current_season_only') is not False else 'CHECK'}</strong> • future-event leakage <strong>BLOCKED</strong> • target event excluded <strong>{'YES' if engine.get('target_event_excluded') is not False else 'CHECK'}</strong>.</span>
 <span>Opponent records are sourced from exact ESPN schedule evidence where available. Empirical calibration claimed: <strong>{'YES' if engine.get('empirical_calibration_claimed') is True else 'NO'}</strong>.</span>
</div>
<div class="form11-warning">The frozen Step-11 engine may apply only its bounded current-form result shown elsewhere in the page. This display layer never changes it. Analysis-line form weight <b>0.0%</b> • selection form weight <b>0.0%</b> • sportsbook projection weight: <b>0.0%</b> • no EV, price, market probability, or Monte Carlo input.</div>
<div class="form11-foot">Official ESPN event IDs only for attached game identity • exact team IDs for form history • no fuzzy matching • no synthetic IDs • frozen Schedule V5 and Steps 3–12 projection contracts preserved.</div>
</div>
"""


_CSS = r"""
.form11-wrap{margin:10px 0;border:1px solid rgba(255,172,91,.30);border-radius:16px;background:#17120e;overflow:hidden;color:#fff6eb}
.form11-title{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(255,172,91,.15)}
.form11-title b{color:#ffd09b;font-size:.56rem;letter-spacing:.07em}.form11-title span{font-size:.42rem;color:#ffc27d;font-weight:950}
.form11-intro,.form11-muted,.form11-foot{padding:8px 12px;color:#b9a99b;font-size:.72rem;line-height:1.48}.form11-intro{border-bottom:1px solid rgba(255,172,91,.08)}
.form11-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.form11-card{border:1px solid rgba(255,172,91,.14);border-radius:12px;background:#211710;padding:9px}.form11-card>b{display:block;color:#fff8ef;font-size:.78rem}.form11-card .form11-muted{padding:4px 0 0;font-size:.68rem}
.form11-badge{display:inline-block;margin-top:6px;border:1px solid #8f653c;border-radius:999px;padding:3px 6px;color:#ffd19c;background:#2c1c10;font-size:.60rem;font-weight:950}
.form11-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}.form11-metrics div{border:1px solid rgba(255,172,91,.10);border-radius:8px;background:#1a110c;padding:7px}.form11-metrics strong{display:block;color:#ffd09b;font-size:.72rem}.form11-metrics small{display:block;color:#9c8876;font-size:.58rem;margin-top:3px}
.form11-submetrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:6px}.form11-submetrics span{display:block;color:#a99686;font-size:.60rem}.form11-submetrics b{color:#ffe0b7}
.form11-audit{margin:0 10px 10px;border:1px solid rgba(255,172,91,.14);border-radius:11px;background:#211710;padding:9px}.form11-audit>b{display:block;color:#ffd09b;font-size:.70rem}.form11-audit span{display:block;color:#aa998a;font-size:.66rem;line-height:1.48;margin-top:4px}
.form11-warning,.form11-gate{margin:0 10px 10px;border:1px solid #765323;border-radius:9px;background:#30230f;color:#ead08f;padding:8px;font-size:.68rem;line-height:1.48}.form11-gate{margin-top:10px}
.form11-foot{border-top:1px solid rgba(255,172,91,.09)}
.form11-gated{margin-top:7px;color:#e5c36e;font-size:.68rem;font-weight:950}
@media(max-width:760px){.form11-grid{grid-template-columns:1fr}.form11-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

__all__ = [
    "ANALYSIS_LINE_WEIGHT",
    "FORM_PROJECTION_BLEND",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "SELECTION_WEIGHT",
    "render_step11",
]
