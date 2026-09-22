"""Readable presentation-only adapter for frozen CFB O/U Step 9 environment output.

Step 9 already runs in the certified runtime slate. This module only translates
that existing engine payload into a readable game-day environment panel. It
never fetches data, recomputes stress, changes projected points, or consumes
sportsbook values.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 9 V1 • GAME-DAY ENVIRONMENT"
PROJECTION_WEIGHT = 0.0
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


def _signed(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):+.{digits}f}"
    except Exception:
        return "—"


def _official_event_id(value: Any) -> str:
    event_id = _clean(value)
    return event_id if event_id.isdigit() else ""


def _ready(engine: Mapping[str, Any]) -> bool:
    if not isinstance(engine, Mapping):
        return False
    if engine.get("model_ready") is not True:
        return False
    event_id = _official_event_id(engine.get("event_id"))
    if not event_id:
        return False
    if engine.get("same_date_event_identity_verified") is False:
        return False
    return True


def _roster_card(label: str, roster: Mapping[str, Any]) -> str:
    if not isinstance(roster, Mapping) or roster.get("ready") is not True:
        return (
            f'<div class="env9-roster"><b>{escape(label)}</b>'
            "<span>Roster availability audit unavailable.</span>"
            "<strong>UNAVAILABLE</strong></div>"
        )

    timestamp = escape(_clean(roster.get("timestamp")) or "timestamp unavailable")
    return f"""
<div class="env9-roster">
  <b>{escape(label)}</b>
  <div class="env9-roster-grid">
    <div><strong>{_int(roster.get("roster_total"))}</strong><small>rostered</small></div>
    <div><strong>{_int(roster.get("active_count"))}</strong><small>active</small></div>
    <div><strong>{_int(roster.get("flagged_count"))}</strong><small>reported flags</small></div>
  </div>
  <span>ESPN roster snapshot: {timestamp}</span>
</div>
"""


def _verdict(venue: Mapping[str, Any], stress: Mapping[str, Any], sigma: Any) -> tuple[str, str]:
    if venue.get("indoor") is True or stress.get("indoor_weather_neutralized") is True:
        return (
            "INDOOR / WEATHER NEUTRAL",
            "The verified indoor venue neutralizes weather stress. No points adjustment is invented.",
        )
    try:
        value = float(sigma or 0.0)
    except Exception:
        value = 0.0
    if value > 0:
        return (
            "WEATHER INCREASES GAME UNCERTAINTY",
            "The verified game-time conditions widen structural uncertainty while leaving the frozen projected total unchanged.",
        )
    if value < 0:
        return (
            "WEATHER TIGHTENS GAME UNCERTAINTY",
            "The existing environment output is slightly less uncertain; no projected points are changed.",
        )
    return (
        "WEATHER IS NEUTRAL",
        "Verified game-time conditions do not widen structural uncertainty for this matchup.",
    )


def render_step9(engine: Mapping[str, Any]) -> str:
    """Render the existing Step 9 engine payload without recomputation."""
    if not isinstance(engine, Mapping):
        engine = {}

    event_id = _official_event_id(engine.get("event_id"))
    if not _ready(engine):
        reason = _clean(engine.get("reason"))
        if not reason:
            reason = (
                "Verified exact same-date ESPN event identity and game-time "
                "environment evidence are incomplete"
            )
        if not event_id:
            reason = (
                "Official ESPN event ID is unavailable; "
                + reason
            )
        return f"""
<div class="env9-wrap">
<style>{_CSS}</style>
<div class="env9-title"><b>🟦 STEP 9 • GAME-DAY ENVIRONMENT</b><span>GATED</span></div>
<div class="env9-gate">{escape(reason)}. Step 8 remains active; the page refuses to invent weather, venue, or availability context.</div>
<div class="env9-foot">Projection mutation: <b>OFF</b> • projected-total adjustment: <b>0.00 pts</b> • injury model weight: <b>0.0%</b> • sportsbook projection weight: <b>0.0%</b> • official ESPN event ID only • no fuzzy matching • no synthetic IDs.</div>
</div>
"""

    weather = engine.get("weather") if isinstance(engine.get("weather"), Mapping) else {}
    venue = engine.get("venue") if isinstance(engine.get("venue"), Mapping) else {}
    stress = engine.get("weather_stress") if isinstance(engine.get("weather_stress"), Mapping) else {}
    away_audit = engine.get("away_availability") if isinstance(engine.get("away_availability"), Mapping) else {}
    home_audit = engine.get("home_availability") if isinstance(engine.get("home_availability"), Mapping) else {}
    sigma = engine.get("sigma_adjustment") or 0.0

    city_state = ", ".join(
        item for item in (_clean(venue.get("city")), _clean(venue.get("state"))) if item
    ) or "location unavailable"
    indoor = venue.get("indoor") is True
    venue_mode = "Indoor • weather neutralized" if indoor else "Outdoor / not marked indoor"
    weather_ready = weather.get("ready") is True
    weather_state = "VERIFIED" if weather_ready else "PARTIAL"
    status = "ESPN EVENT " + event_id
    verdict, explanation = _verdict(venue, stress, sigma)

    away_name = _clean(engine.get("away_event_team")) or "Away team"
    home_name = _clean(engine.get("home_event_team")) or "Home team"
    away_id = _official_event_id(engine.get("away_espn_team_id")) or "—"
    home_id = _official_event_id(engine.get("home_espn_team_id")) or "—"

    recovery = _clean(engine.get("recovery_source"))
    recovery_note = (
        f" • identity recovery: {escape(recovery)}"
        if recovery
        else ""
    )

    return f"""
<div class="env9-wrap">
<style>{_CSS}</style>
<div class="env9-title"><b>🟦 STEP 9 • GAME-DAY ENVIRONMENT</b><span>{escape(status)}</span></div>
<div class="env9-why"><b>Why it matters:</b> game-time weather and venue conditions can make a total more or less predictable. This is the existing UPGRADE STEP 9 environment output: exact same-date ESPN identity unlocks the context, while the frozen Step 8 projected points and projected total remain untouched.</div>

<div class="env9-grid">
  <div class="env9-card">
    <b>🪪 Exact ESPN event identity</b>
    <span>Event ID <strong>{escape(event_id)}</strong> • same-date identity verified<br>{escape(away_name)} ESPN team {escape(away_id)} @ {escape(home_name)} ESPN team {escape(home_id)}{recovery_note}</span>
    <div class="env9-metrics">
      <div><strong>{_pct(engine.get("coverage"))}</strong><small>environment coverage</small></div>
      <div><strong>{_pct(engine.get("roster_audit_coverage"))}</strong><small>roster audit coverage</small></div>
      <div><strong>{weather_state}</strong><small>weather evidence</small></div>
      <div><strong>{_signed(sigma)}</strong><small>sigma adjustment</small></div>
    </div>
  </div>
  <div class="env9-card">
    <b>🌦️ {escape(_clean(venue.get("name")) or "Venue unavailable")}</b>
    <span>{escape(city_state)} • {escape(venue_mode)}</span>
    <div class="env9-metrics">
      <div><strong>{_num(weather.get("temperature_f"), 0)}°F</strong><small>temperature</small></div>
      <div><strong>{_num(weather.get("gust_mph"), 0)} mph</strong><small>gust</small></div>
      <div><strong>{_num(weather.get("precipitation_pct"), 0)}%</strong><small>precipitation chance</small></div>
      <div><strong>{_int(weather.get("fields_available"))}</strong><small>weather fields</small></div>
    </div>
  </div>
</div>

<div class="env9-stress">
  <div class="env9-stress-title"><b>Weather stress already produced by the frozen engine</b><span>{_pct(stress.get("total_stress"))} total stress</span></div>
  <div class="env9-stress-grid">
    <div><strong>{_pct(stress.get("gust_stress"))}</strong><small>gust stress</small></div>
    <div><strong>{_pct(stress.get("precipitation_stress"))}</strong><small>precipitation stress</small></div>
    <div><strong>{_pct(stress.get("temperature_stress"))}</strong><small>temperature stress</small></div>
    <div><strong>{_signed(sigma)} pts</strong><small>structural sigma widening</small></div>
  </div>
</div>

<div class="env9-card env9-audit">
  <b>🩺 Availability audit only</b>
  <span>ESPN roster status and injury fields are monitored, but college-football injury-report completeness is not certified. Injury model weight is <strong>0%</strong>; availability is never converted into invented points.</span>
  <div class="env9-rosters">{_roster_card(away_name, away_audit)}{_roster_card(home_name, home_audit)}</div>
  <div class="env9-warning">Zero reported flags ≠ confirmed healthy roster. An incomplete feed cannot certify that either team is healthy.</div>
</div>

<div class="env9-verdict"><small>ENVIRONMENT VERDICT</small><strong>{escape(verdict)}</strong><span>{escape(explanation)}</span><b>Frozen structural sigma adjustment: {_signed(sigma)} pts</b><em>Projected total remains unchanged by Step 9.</em></div>
<div class="env9-note">Weather stress thresholds are conservative structural thresholds, not empirical calibration: gust stress begins above 15 mph, precipitation above 50%, and temperature below 35°F or above 95°F. Indoor venues receive zero weather stress only when ESPN explicitly marks them indoor. Official ESPN event IDs only • no fuzzy matching • no synthetic IDs.</div>
<div class="env9-foot">Projection mutation: <b>OFF</b> • projected-total adjustment: <b>0.00 pts</b> • injury adjustment: <b>0.00 pts</b> • sportsbook projection weight: <b>0.0%</b> • uncertainty-only adjustment.</div>
</div>
"""


_CSS = """
.env9-wrap{margin:10px 0;border:1px solid rgba(93,200,255,.30);border-radius:16px;background:#101820;overflow:hidden;color:#eef6f8}
.env9-title{display:flex;justify-content:space-between;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(93,200,255,.16)}
.env9-title b{color:#9bdcff}.env9-title span{font-size:.72rem;color:#b8e6ff}.env9-why,.env9-note,.env9-foot{padding:9px 12px;color:#a6b2b8;font-size:.82rem;line-height:1.45}
.env9-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.env9-card{border:1px solid rgba(93,200,255,.14);border-radius:12px;background:#09151d;padding:9px}.env9-card>b{display:block;color:#eef7fa}.env9-card>span{display:block;color:#8ca0a9;font-size:.78rem;line-height:1.48;margin-top:4px}.env9-card strong{color:#f5fbfd}
.env9-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.env9-metrics div{border:1px solid rgba(93,200,255,.10);border-radius:8px;background:#071119;padding:7px}.env9-metrics strong{display:block;color:#b8e6ff}.env9-metrics small{display:block;color:#718893;font-size:.70rem;margin-top:3px}
.env9-stress{margin:0 10px 10px;border:1px solid rgba(93,200,255,.16);border-radius:11px;background:#07131b;padding:9px}.env9-stress-title{display:flex;justify-content:space-between;gap:8px}.env9-stress-title b{color:#d9f2ff}.env9-stress-title span{color:#a8d9ee}.env9-stress-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}.env9-stress-grid div{padding:7px;border:1px solid rgba(93,200,255,.08);border-radius:8px}.env9-stress-grid strong{display:block;color:#d8f2ff}.env9-stress-grid small{display:block;color:#718893;margin-top:3px}
.env9-audit{margin:0 10px 10px}.env9-rosters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:8px}.env9-roster{border:1px solid rgba(93,200,255,.10);border-radius:9px;background:#071119;padding:8px}.env9-roster>b{display:block;color:#eef7fa}.env9-roster>span{display:block;color:#718893;font-size:.72rem;line-height:1.4;margin-top:4px}.env9-roster>strong{display:block;color:#e3c875;margin-top:4px}
.env9-roster-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.env9-roster-grid div{padding:6px;border-radius:7px;background:#081820}.env9-roster-grid strong{display:block;color:#d8f2ff}.env9-roster-grid small{display:block;color:#718893;font-size:.68rem;margin-top:2px}
.env9-warning,.env9-gate{margin-top:8px;border:1px solid #6c5720;border-radius:9px;background:#2b240d;color:#d9c477;padding:8px;font-size:.78rem;line-height:1.45}.env9-gate{margin:10px}
.env9-verdict{margin:0 10px 10px;padding:10px;border:1px solid rgba(93,200,255,.18);border-radius:10px;background:#0d1b24}.env9-verdict small,.env9-verdict span,.env9-verdict em{display:block;color:#9ca9af}.env9-verdict strong{display:block;color:#b8e6ff;font-size:1rem;margin:3px 0}.env9-verdict b{display:block;margin-top:5px}.env9-verdict em{margin-top:5px;font-style:normal;color:#c9e8f5}
.env9-foot{border-top:1px solid rgba(93,200,255,.10)}
@media(max-width:760px){.env9-grid,.env9-rosters{grid-template-columns:1fr}.env9-metrics,.env9-stress-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

__all__ = ["MAY_MODIFY_PROJECTION", "MODEL_VERSION", "PROJECTION_WEIGHT", "render_step9"]
