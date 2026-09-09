"""CFB Over/Under Intelligence V2 — Upgrade Step 9 game-day environment engine.

Additive model layer above permanently frozen Upgrade Step 8.

Certified evidence
------------------
Step 9 resolves the exact same-date ESPN college-football event from the frozen
NCAA matchup identity, then reads:
- ESPN event summary venue,
- ESPN/AccuWeather game-time temperature,
- gust speed,
- precipitation probability,
- exact ESPN team IDs,
- timestamped ESPN roster snapshots.

Availability integrity
----------------------
ESPN's roster schema exposes per-athlete status and injury fields, but live
certification across the current slate showed those fields are not populated
consistently enough to certify a complete college-football injury report.
Therefore roster availability is surfaced as an AUDIT ONLY:
- reported flags are shown when present,
- "zero flags" is never interpreted as "no injuries",
- injury/availability model weight is exactly 0%.

Weather policy
--------------
The weather layer is intentionally conservative. It does NOT move the Step-8
projected points or projected total. Severe game-day conditions widen structural
total uncertainty using transparent stress thresholds:
- gust stress begins above 15 mph,
- precipitation stress begins above 50%,
- temperature stress begins below 35 F or above 95 F,
- total sigma widening is capped at +1.25 points.

These are structural stress thresholds, not claimed empirical calibration.
Indoor venues receive zero weather stress when the source explicitly marks them
indoor.

The analysis line has 0% environment weight. No sportsbook feed, market-implied
probability, EV, price, or Monte Carlo is introduced here.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import cfb_over_under_logo_resolver_v1 as logo_identity
import cfb_over_under_model_v1 as frozen_raw
import cfb_schedule_v3 as schedule

MODEL_VERSION = "CFB O/U GAME-DAY ENVIRONMENT ENGINE V1 • UPGRADE STEP 9"
FROZEN_STEP8_ENGINE = "cfb_over_under_turnover_engine_v1"
FROZEN_RAW_MODEL = "cfb_over_under_model_v1"

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)
ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary"
)
ESPN_TEAM_ROSTER_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/roster"
)

GUST_STRESS_START_MPH = 15.0
GUST_STRESS_FULL_MPH = 35.0
PRECIP_STRESS_START_PCT = 50.0
PRECIP_STRESS_FULL_PCT = 100.0
COLD_STRESS_START_F = 35.0
COLD_STRESS_FULL_F = 15.0
HEAT_STRESS_START_F = 95.0
HEAT_STRESS_FULL_F = 110.0

GUST_STRESS_WEIGHT = 0.55
PRECIP_STRESS_WEIGHT = 0.30
TEMPERATURE_STRESS_WEIGHT = 0.15

MAX_TOTAL_SIGMA_ADJUSTMENT = 1.25
ANALYSIS_LINE_ENVIRONMENT_WEIGHT = 0.0
PROJECTED_TOTAL_ENVIRONMENT_WEIGHT = 0.0
INJURY_MODEL_WEIGHT = 0.0
INJURY_REPORTING_COMPLETENESS_CERTIFIED = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _season_date_key(game: Mapping[str, Any]) -> str:
    day = _clean(game.get("game_date"))
    return day.replace("-", "")


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_scoreboard(
    game_date: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    key = _clean(game_date).replace("-", "")
    if len(key) != 8 or not key.isdigit():
        return {}, []
    return schedule.frozen.frozen._fetch_json_with_fallback(
        ESPN_SCOREBOARD_URL,
        {"dates": key, "limit": 1000},
        "ESPN CFB exact-date environment scoreboard",
    )


def _resolve_event(
    payload: Mapping[str, Any],
    game: Mapping[str, Any],
) -> Mapping[str, Any]:
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        if logo_identity._event_matches_game(event, game):
            return event
    return {}


def _side_meta(event: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sides = logo_identity._event_sides(event)
    out: dict[str, dict[str, Any]] = {}
    for side in ("away", "home"):
        competitor = sides.get(side) or {}
        team = competitor.get("team") or {}
        if not isinstance(team, Mapping):
            team = {}
        out[side] = {
            "team_id": _clean(team.get("id")),
            "display_name": _clean(
                team.get("displayName")
                or team.get("shortDisplayName")
                or team.get("location")
            ),
            "abbreviation": _clean(team.get("abbreviation")),
        }
    return out


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_summary(
    event_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not _clean(event_id):
        return {}, []
    return schedule.frozen.frozen._fetch_json_with_fallback(
        ESPN_SUMMARY_URL,
        {"event": _clean(event_id)},
        "ESPN CFB exact-event environment summary",
    )


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_roster(
    team_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return {}, []
    return schedule.frozen.frozen._fetch_json_with_fallback(
        ESPN_TEAM_ROSTER_URL.format(team_id=team_id),
        {},
        f"ESPN CFB team {team_id} roster availability audit",
    )


def _roster_audit(payload: Mapping[str, Any], team_id: str) -> dict[str, Any]:
    total = 0
    active = 0
    flagged: list[dict[str, Any]] = []
    group_counts: dict[str, int] = {}

    for group in payload.get("athletes") or []:
        if not isinstance(group, Mapping):
            continue
        group_name = _clean(group.get("position")) or "unknown"
        for athlete in group.get("items") or []:
            if not isinstance(athlete, Mapping):
                continue
            total += 1
            group_counts[group_name] = group_counts.get(group_name, 0) + 1
            status = athlete.get("status") or {}
            if not isinstance(status, Mapping):
                status = {}
            status_type = _clean(status.get("type")).lower()
            injuries = athlete.get("injuries") or []
            if status_type == "active":
                active += 1
            if injuries or (status_type and status_type != "active"):
                position = athlete.get("position") or {}
                if not isinstance(position, Mapping):
                    position = {}
                flagged.append({
                    "athlete_id": _clean(athlete.get("id")),
                    "name": _clean(
                        athlete.get("displayName")
                        or athlete.get("fullName")
                    ),
                    "position": _clean(
                        position.get("abbreviation")
                        or position.get("displayName")
                    ),
                    "group": group_name,
                    "status": _clean(
                        status.get("name")
                        or status.get("abbreviation")
                        or status.get("type")
                    ),
                    "injuries": list(injuries) if isinstance(injuries, list) else [],
                })

    return {
        "team_id": _clean(team_id),
        "ready": bool(
            _clean(payload.get("status")).lower() == "success"
            and total > 0
        ),
        "timestamp": _clean(payload.get("timestamp")),
        "roster_total": total,
        "active_count": active,
        "flagged_count": len(flagged),
        "flagged": flagged[:20],
        "group_counts": group_counts,
        "injury_reporting_completeness_certified": (
            INJURY_REPORTING_COMPLETENESS_CERTIFIED
        ),
        "model_weight": INJURY_MODEL_WEIGHT,
        "interpretation": (
            "audit only; zero reported flags does not certify a healthy roster"
        ),
    }


def _summary_competition(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    header = payload.get("header") or {}
    if not isinstance(header, Mapping):
        return {}
    comps = header.get("competitions") or []
    if comps and isinstance(comps[0], Mapping):
        return comps[0]
    return {}


def _summary_identity_matches(
    payload: Mapping[str, Any],
    event_id: str,
) -> bool:
    header = payload.get("header") or {}
    if not isinstance(header, Mapping):
        return False
    header_id = _clean(header.get("id"))
    comp = _summary_competition(payload)
    comp_id = _clean(comp.get("id")) if isinstance(comp, Mapping) else ""
    wanted = _clean(event_id)
    return bool(wanted and wanted in {header_id, comp_id})


def _weather(payload: Mapping[str, Any]) -> dict[str, Any]:
    game_info = payload.get("gameInfo") or {}
    if not isinstance(game_info, Mapping):
        game_info = {}
    item = game_info.get("weather") or {}
    if not isinstance(item, Mapping):
        item = {}

    temperature = _float(item.get("temperature"))
    gust = _float(item.get("gust"))
    precipitation = _float(item.get("precipitation"))

    ready_fields = sum(
        value is not None
        for value in (temperature, gust, precipitation)
    )

    link = item.get("link") or {}
    if not isinstance(link, Mapping):
        link = {}

    return {
        "ready": ready_fields >= 2,
        "temperature_f": temperature,
        "high_temperature_f": _float(item.get("highTemperature")),
        "low_temperature_f": _float(item.get("lowTemperature")),
        "gust_mph": gust,
        "precipitation_pct": precipitation,
        "condition_id": _clean(item.get("conditionId")),
        "source_link": _clean(link.get("href")),
        "source": "ESPN event summary weather / linked AccuWeather forecast",
        "fields_available": ready_fields,
    }


def _venue(payload: Mapping[str, Any]) -> dict[str, Any]:
    game_info = payload.get("gameInfo") or {}
    if not isinstance(game_info, Mapping):
        game_info = {}
    venue = game_info.get("venue") or {}
    if not isinstance(venue, Mapping):
        venue = {}

    address = venue.get("address") or {}
    if not isinstance(address, Mapping):
        address = {}

    full_name = _clean(
        venue.get("fullName")
        or venue.get("name")
    )
    return {
        "ready": bool(full_name),
        "id": _clean(venue.get("id")),
        "name": full_name,
        "city": _clean(address.get("city")),
        "state": _clean(address.get("state")),
        "zip": _clean(address.get("zipCode")),
        "country": _clean(address.get("country")),
        "indoor": venue.get("indoor") is True,
    }


def _ramp_up(value: float | None, start: float, full: float) -> float:
    if value is None:
        return 0.0
    if full <= start:
        return 0.0
    return _clamp((float(value) - start) / (full - start), 0.0, 1.0)


def _temperature_stress(value: float | None) -> float:
    if value is None:
        return 0.0
    temp = float(value)
    if temp < COLD_STRESS_START_F:
        return _clamp(
            (COLD_STRESS_START_F - temp)
            / (COLD_STRESS_START_F - COLD_STRESS_FULL_F),
            0.0,
            1.0,
        )
    if temp > HEAT_STRESS_START_F:
        return _clamp(
            (temp - HEAT_STRESS_START_F)
            / (HEAT_STRESS_FULL_F - HEAT_STRESS_START_F),
            0.0,
            1.0,
        )
    return 0.0


def _weather_stress(
    weather: Mapping[str, Any],
    venue: Mapping[str, Any],
) -> dict[str, Any]:
    if venue.get("indoor") is True:
        return {
            "gust_stress": 0.0,
            "precipitation_stress": 0.0,
            "temperature_stress": 0.0,
            "total_stress": 0.0,
            "sigma_adjustment": 0.0,
            "indoor_weather_neutralized": True,
        }

    gust_stress = _ramp_up(
        _float(weather.get("gust_mph")),
        GUST_STRESS_START_MPH,
        GUST_STRESS_FULL_MPH,
    )
    precip_stress = _ramp_up(
        _float(weather.get("precipitation_pct")),
        PRECIP_STRESS_START_PCT,
        PRECIP_STRESS_FULL_PCT,
    )
    temperature_stress = _temperature_stress(
        _float(weather.get("temperature_f"))
    )

    total = _clamp(
        GUST_STRESS_WEIGHT * gust_stress
        + PRECIP_STRESS_WEIGHT * precip_stress
        + TEMPERATURE_STRESS_WEIGHT * temperature_stress,
        0.0,
        1.0,
    )
    sigma_adjustment = _clamp(
        total * MAX_TOTAL_SIGMA_ADJUSTMENT,
        0.0,
        MAX_TOTAL_SIGMA_ADJUSTMENT,
    )
    return {
        "gust_stress": float(gust_stress),
        "precipitation_stress": float(precip_stress),
        "temperature_stress": float(temperature_stress),
        "total_stress": float(total),
        "sigma_adjustment": float(sigma_adjustment),
        "indoor_weather_neutralized": False,
    }


def build_environment_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    day = _clean(game.get("game_date"))
    scoreboard, scoreboard_attempts = _fetch_scoreboard(day)
    event = _resolve_event(scoreboard, game)

    if not event:
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "reason": "exact same-date ESPN event identity is unavailable",
            "event_id": "",
            "weather": {},
            "venue": {},
            "away_availability": {},
            "home_availability": {},
            "coverage": 0.0,
            "roster_audit_coverage": 0.0,
            "sigma_adjustment": 0.0,
            "analysis_line_environment_weight": ANALYSIS_LINE_ENVIRONMENT_WEIGHT,
            "projected_total_environment_weight": PROJECTED_TOTAL_ENVIRONMENT_WEIGHT,
            "injury_model_weight": INJURY_MODEL_WEIGHT,
            "injury_reporting_completeness_certified": False,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
            "diagnostics": {"scoreboard_attempts": scoreboard_attempts},
        }

    event_id = _clean(event.get("id"))
    sides = _side_meta(event)

    summary, summary_attempts = _fetch_summary(event_id)
    identity_ready = _summary_identity_matches(summary, event_id)
    weather = _weather(summary) if identity_ready else {}
    venue = _venue(summary) if identity_ready else {}
    stress = _weather_stress(weather, venue) if weather.get("ready") else {
        "gust_stress": 0.0,
        "precipitation_stress": 0.0,
        "temperature_stress": 0.0,
        "total_stress": 0.0,
        "sigma_adjustment": 0.0,
        "indoor_weather_neutralized": False,
    }

    away_id = _clean((sides.get("away") or {}).get("team_id"))
    home_id = _clean((sides.get("home") or {}).get("team_id"))
    away_roster, away_attempts = _fetch_roster(away_id)
    home_roster, home_attempts = _fetch_roster(home_id)
    away_availability = _roster_audit(away_roster, away_id)
    home_availability = _roster_audit(home_roster, home_id)

    roster_coverage = (
        float(bool(away_availability.get("ready")))
        + float(bool(home_availability.get("ready")))
    ) / 2.0

    model_ready = bool(
        identity_ready
        and weather.get("ready")
    )
    reason = ""
    if not model_ready:
        if not identity_ready:
            reason = "ESPN event summary identity did not verify"
        elif not weather.get("ready"):
            reason = "verified game-time weather fields are incomplete"

    coverage = (
        (
            float(identity_ready)
            + float(bool(weather.get("ready")))
            + float(bool(venue.get("ready")))
        )
        / 3.0
    )

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "model_ready": model_ready,
        "reason": reason,
        "event_id": event_id,
        "same_date_event_identity_verified": bool(event_id and identity_ready),
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "away_event_team": (sides.get("away") or {}).get("display_name"),
        "home_event_team": (sides.get("home") or {}).get("display_name"),
        "weather": weather,
        "venue": venue,
        "weather_stress": stress,
        "sigma_adjustment": float(stress.get("sigma_adjustment") or 0.0),
        "coverage": float(coverage),
        "away_availability": away_availability,
        "home_availability": home_availability,
        "roster_audit_coverage": float(roster_coverage),
        "analysis_line_environment_weight": ANALYSIS_LINE_ENVIRONMENT_WEIGHT,
        "projected_total_environment_weight": PROJECTED_TOTAL_ENVIRONMENT_WEIGHT,
        "injury_model_weight": INJURY_MODEL_WEIGHT,
        "injury_reporting_completeness_certified": (
            INJURY_REPORTING_COMPLETENESS_CERTIFIED
        ),
        "availability_zero_flags_means_healthy": False,
        "weather_thresholds_empirically_calibrated": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "diagnostics": {
            "scoreboard_attempts": scoreboard_attempts,
            "summary_attempts": summary_attempts,
            "away_roster_attempts": away_attempts,
            "home_roster_attempts": home_attempts,
        },
    }


def _lean(p_over: float, p_under: float, p_push: float) -> str:
    if p_push >= max(p_over, p_under):
        return "PASS"
    if p_over > p_under:
        return "OVER"
    if p_under > p_over:
        return "UNDER"
    return "PASS"


def apply_to_raw(
    base_raw: Mapping[str, Any],
    engine: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply Step-9 weather uncertainty without moving Step-8 projected points."""
    out = dict(base_raw)
    out["base_step8_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step9_environment_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step9_applied"] = False
    out["environment_engine_coverage"] = float(engine.get("coverage") or 0.0)
    out["roster_audit_coverage"] = float(engine.get("roster_audit_coverage") or 0.0)
    out["analysis_line_environment_weight"] = ANALYSIS_LINE_ENVIRONMENT_WEIGHT
    out["projected_total_environment_weight"] = PROJECTED_TOTAL_ENVIRONMENT_WEIGHT
    out["injury_model_weight"] = INJURY_MODEL_WEIGHT

    if not base_raw.get("ready") or not engine.get("model_ready"):
        out["environment_engine_reason"] = _clean(
            engine.get("reason")
            or "environment evidence below Step-9 minimum coverage"
        )
        return out

    base_away = float(base_raw.get("projected_away_points") or 0.0)
    base_home = float(base_raw.get("projected_home_points") or 0.0)
    base_total = float(base_raw.get("projected_total") or (base_away + base_home))
    base_sigma = float(
        base_raw.get("structural_total_sigma")
        or frozen_raw.BASE_TOTAL_SIGMA
    )
    sigma_adjustment = float(engine.get("sigma_adjustment") or 0.0)
    adjusted_sigma = max(1.0, base_sigma + sigma_adjustment)

    line = float(base_raw.get("analysis_line") or 0.0)
    p_over, p_under, p_push = frozen_raw._line_probabilities(
        base_total,
        adjusted_sigma,
        line,
    )
    interval_low = max(0.0, base_total - 1.645 * adjusted_sigma)
    interval_high = base_total + 1.645 * adjusted_sigma

    components = dict(base_raw.get("components") or {})
    components.update({
        "step9_environment_sigma_adjustment": float(sigma_adjustment),
        "step9_weather_stress": float(
            (engine.get("weather_stress") or {}).get("total_stress") or 0.0
        ),
        "step9_environment_coverage": float(engine.get("coverage") or 0.0),
        "step9_roster_audit_coverage": float(
            engine.get("roster_audit_coverage") or 0.0
        ),
        "step9_projected_total_adjustment": 0.0,
        "step9_injury_points_adjustment": 0.0,
    })

    out.update({
        "upgrade_step9_applied": True,
        "step9_base_projected_away_points": float(base_away),
        "step9_base_projected_home_points": float(base_home),
        "step9_base_projected_total": float(base_total),
        "step9_base_structural_total_sigma": float(base_sigma),
        "projected_away_points": float(base_away),
        "projected_home_points": float(base_home),
        "projected_total": float(base_total),
        "structural_total_sigma": float(adjusted_sigma),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": _lean(p_over, p_under, p_push),
        "total_uncertainty_90": {
            "low": float(interval_low),
            "high": float(interval_high),
        },
        "components": components,
        "injury_reporting_completeness_certified": False,
        "availability_zero_flags_means_healthy": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    })
    return out


def clear_environment_engine_cache() -> None:
    for fn in (_fetch_scoreboard, _fetch_summary, _fetch_roster):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ANALYSIS_LINE_ENVIRONMENT_WEIGHT",
    "FROZEN_RAW_MODEL",
    "FROZEN_STEP8_ENGINE",
    "GUST_STRESS_START_MPH",
    "INJURY_MODEL_WEIGHT",
    "INJURY_REPORTING_COMPLETENESS_CERTIFIED",
    "MAX_TOTAL_SIGMA_ADJUSTMENT",
    "MODEL_VERSION",
    "PRECIP_STRESS_START_PCT",
    "PROJECTED_TOTAL_ENVIRONMENT_WEIGHT",
    "_fetch_roster",
    "_fetch_scoreboard",
    "_fetch_summary",
    "_resolve_event",
    "_roster_audit",
    "_temperature_stress",
    "_venue",
    "_weather",
    "_weather_stress",
    "apply_to_raw",
    "build_environment_engine",
    "clear_environment_engine_cache",
]
