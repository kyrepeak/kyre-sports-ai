"""MLB Moneyline V17.3 — Step 7 park + weather run environment.

Additive presentation/evidence wrapper over permanently frozen V17.2 Step 6.
Pregame cards gain park and weather run-environment context. Frozen Step 5L live
mode remains untouched.

Evidence:
- Official MLB game feed weather
- Official MLB venue / roof metadata
- Current-season home club home-vs-road hitting splits, used only as a
  descriptive park run-environment proxy (not labeled an official park factor)

Step 8 defense/baserunning is intentionally excluded here.

No Moneyline probability, simulation, fair-odds, ranking, candidate selection,
or market math changes. Fail-closed when required park/weather evidence is not
available.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_moneyline_hub_v172 as prior
import mlb_moneyline_hub_v170 as pregame
import mlb_matchup_environment_v1 as environment

MODEL_VERSION = "V17.3 • MONEYLINE STEP 7 • PARK + WEATHER RUN ENVIRONMENT"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v172"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

PARK_MIN_AB = 600
PARK_FULL_AB = 2600
MIN_ENV_DATA_SCORE = 65

_STEP7_CSS = r"""
<style>
.ml173-step7{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(255,171,73,.28);border-radius:13px;background:linear-gradient(145deg,rgba(40,24,7,.96),rgba(9,17,27,.97));box-shadow:inset 3px 0 #ffad49}
.ml173-step7-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml173-step7-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#ffd08f}
.ml173-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #6a5b46;background:#2d2418;color:#efd7b4}
.ml173-grade.hitter{border-color:#8a5f27;background:#38240c;color:#ffd69b}.ml173-grade.pitcher{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml173-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml173-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml173-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:7px}.ml173-side{border:1px solid rgba(255,171,73,.18);border-radius:10px;background:rgba(10,18,25,.82);padding:8px}.ml173-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml173-side small{color:#788a95;font-size:.44rem}
.ml173-score{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #755b38;background:#261c10;color:#efd3a8;font-size:.45rem;font-weight:900}
.ml173-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml173-stat{border:1px solid rgba(122,112,88,.18);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml173-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml173-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml173-note{margin-top:7px;border:1px solid rgba(255,171,73,.15);border-radius:8px;padding:6px 7px;background:#17150f;color:#b9b4aa;font-size:.45rem;line-height:1.42}.ml173-note b{color:#eee2cf}
.ml173-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml173-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(255,171,73,.22);background:#261b0d;color:#edcf9c;font-size:.46rem;font-weight:850}.ml173-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml173-grid{grid-template-columns:1fr}.ml173-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml173-step7{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _rate(value: Any) -> float | None:
    val = _f(value)
    if val is None:
        return None
    if val > 2.0:
        val /= 1000.0
    return max(0.0, val)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _split_metrics(stat: Mapping[str, Any] | None) -> dict[str, Any]:
    stat = stat or {}
    ab = _i(stat.get("atBats"))
    games = _i(stat.get("gamesPlayed"))
    runs = _i(stat.get("runs"))
    hits = _i(stat.get("hits"))
    avg = _rate(stat.get("avg"))
    ops = _rate(stat.get("ops"))
    if avg is None and ab > 0:
        avg = hits / ab
    return {
        "ab": ab,
        "games": games,
        "runs": runs,
        "rpg": runs / games if games > 0 else None,
        "avg": avg,
        "ops": ops,
    }


def _park_run_proxy(home_stat: Mapping[str, Any] | None, road_stat: Mapping[str, Any] | None) -> dict[str, Any]:
    home = _split_metrics(home_stat)
    road = _split_metrics(road_stat)
    sample = min(int(home.get("ab") or 0), int(road.get("ab") or 0))
    if (
        sample < PARK_MIN_AB
        or home.get("ops") is None
        or road.get("ops") is None
        or float(road.get("ops") or 0) <= 0
        or home.get("rpg") is None
        or road.get("rpg") is None
        or float(road.get("rpg") or 0) <= 0
    ):
        return {
            "factor": None,
            "raw": None,
            "reliability": 0.0,
            "home": home,
            "road": road,
            "label": "PARK SAMPLE PENDING",
        }

    ops_ratio = _clamp(float(home["ops"]) / float(road["ops"]), 0.75, 1.25)
    run_ratio = _clamp(float(home["rpg"]) / float(road["rpg"]), 0.70, 1.30)
    raw = 0.60 * ops_ratio + 0.40 * run_ratio
    reliability = _clamp(
        (sample - PARK_MIN_AB) / float(PARK_FULL_AB - PARK_MIN_AB),
        0.0,
        1.0,
    )
    factor = 1.0 + (raw - 1.0) * reliability

    if factor >= 1.035:
        label = "RUN-BOOSTING PARK PROXY"
    elif factor <= 0.965:
        label = "RUN-SUPPRESSING PARK PROXY"
    else:
        label = "NEUTRAL PARK PROXY"

    return {
        "factor": factor,
        "raw": raw,
        "reliability": reliability,
        "home": home,
        "road": road,
        "label": label,
    }


def _weather_profile(feed: Mapping[str, Any], venue_detail: Mapping[str, Any] | None) -> dict[str, Any]:
    game_data = (feed or {}).get("gameData") or {}
    venue = game_data.get("venue") or {}
    detail = venue_detail or {}
    field_info = venue.get("fieldInfo") or detail.get("fieldInfo") or {}
    roof_type = str(field_info.get("roofType") or "—")
    turf_type = str(field_info.get("turfType") or "—")
    raw = game_data.get("weather") or {}
    weather = environment.weather_context(raw, roof_type)

    condition = str(weather.get("condition") or "—")
    lower = condition.lower()
    delay_risk = any(token in lower for token in ("rain", "storm", "thunder", "showers"))

    return {
        "roof_type": roof_type,
        "turf_type": turf_type,
        "temperature": weather.get("temperature"),
        "condition": condition,
        "wind_text": (weather.get("wind") or {}).get("text") or "—",
        "wind_mph": (weather.get("wind") or {}).get("mph"),
        "wind_direction": (weather.get("wind") or {}).get("direction") or "UNKNOWN",
        "indoor": bool(weather.get("indoor")),
        "signal": weather.get("signal"),
        "reliability": float(weather.get("reliability") or 0.0),
        "label": weather.get("label") or "WEATHER PENDING",
        "delay_risk": delay_risk,
    }


def _run_environment_score(park: Mapping[str, Any], weather: Mapping[str, Any]) -> dict[str, Any]:
    factor = _f(park.get("factor"))
    weather_signal = _f(weather.get("signal"))
    park_rel = float(park.get("reliability") or 0.0)
    weather_rel = float(weather.get("reliability") or 0.0)

    if factor is None or weather_signal is None:
        return {
            "score": None,
            "label": "DATA LIMITED / PENDING",
            "label_cls": "limited",
            "coverage": 0.0,
        }

    park_signal = _clamp((factor - 1.0) / 0.08, -1.0, 1.0)
    weighted = park_signal * 0.55 * park_rel + weather_signal * 0.45 * weather_rel
    coverage = 0.55 * park_rel + 0.45 * weather_rel
    if coverage <= 0:
        return {
            "score": None,
            "label": "DATA LIMITED / PENDING",
            "label_cls": "limited",
            "coverage": 0.0,
        }

    signal = weighted / coverage
    score = int(round(_clamp(50.0 + 20.0 * signal, 30.0, 70.0)))
    if score >= 58:
        label, cls = "HITTER-FRIENDLY RUN ENVIRONMENT", "hitter"
    elif score <= 42:
        label, cls = "RUN-SUPPRESSING ENVIRONMENT", "pitcher"
    else:
        label, cls = "NEUTRAL RUN ENVIRONMENT", "neutral"
    return {
        "score": score,
        "label": label,
        "label_cls": cls,
        "coverage": _clamp(coverage, 0.0, 1.0),
    }


def _data_score(feed_ok: bool, venue_ok: bool, park: Mapping[str, Any], weather: Mapping[str, Any]) -> int:
    score = 0
    score += 20 if feed_ok else 0
    score += 10 if venue_ok else 0
    score += int(round(35 * float(park.get("reliability") or 0.0))) if park.get("factor") is not None else 0

    weather_points = 0
    weather_points += 12 if weather.get("temperature") is not None or weather.get("indoor") else 0
    weather_points += 13 if weather.get("wind_direction") != "UNKNOWN" or weather.get("indoor") else 0
    weather_points += 10 if str(weather.get("condition") or "—") != "—" else 0
    score += int(round(weather_points * min(1.0, max(0.0, float(weather.get("reliability") or 0.0)))))

    return int(_clamp(score, 0, 100))


def _game_context(game_pk: Any) -> dict[str, Any]:
    pk = _i(game_pk)
    if not pk:
        return {
            "status": "PENDING",
            "score": None,
            "label": "DATA LIMITED / PENDING",
            "label_cls": "limited",
            "reason": "Official MLB game PK unavailable.",
        }

    feed = environment.fetch_game_context(pk) or {}
    game_data = feed.get("gameData") or {}
    venue = game_data.get("venue") or {}
    teams = game_data.get("teams") or {}
    home_team_id = _i((teams.get("home") or {}).get("id"))
    venue_id = _i(venue.get("id"))

    venue_detail = environment.fetch_venue_context(venue_id) if venue_id else None
    home_split = environment.fetch_team_split(home_team_id, SEASON, "home") if home_team_id else None
    road_split = environment.fetch_team_split(home_team_id, SEASON, "away") if home_team_id else None

    park = _park_run_proxy(home_split, road_split)
    weather = _weather_profile(feed, venue_detail)
    graded = _run_environment_score(park, weather)
    data_score = _data_score(bool(feed), bool(venue or venue_detail), park, weather)

    sufficient = graded.get("score") is not None and data_score >= MIN_ENV_DATA_SCORE
    if sufficient:
        score = graded.get("score")
        label = graded.get("label")
        label_cls = graded.get("label_cls")
        status = "VERIFIED"
        reason = ""
    else:
        score = None
        label = "DATA LIMITED / PENDING"
        label_cls = "limited"
        status = "PENDING"
        if not feed:
            reason = "Official MLB game/weather feed unavailable."
        elif park.get("factor") is None:
            reason = "Home-club home/road park sample is below the fail-closed threshold."
        elif weather.get("signal") is None:
            reason = "Weather/roof evidence is incomplete."
        else:
            reason = "Park/weather evidence did not clear the data-quality threshold."

    return {
        "status": status,
        "score": score,
        "label": label,
        "label_cls": label_cls,
        "venue_id": venue_id or None,
        "venue_name": venue.get("name") or (venue_detail or {}).get("name") or "—",
        "park": park,
        "weather": weather,
        "data_score": data_score,
        "coverage": graded.get("coverage"),
        "reason": reason,
    }


def _build_context(rows: Mapping[int, Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    out = {}
    for pk in rows or {}:
        ipk = _i(pk)
        if ipk:
            out[ipk] = _game_context(ipk)
    return out


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def _html(context: Mapping[str, Any]) -> str:
    park = context.get("park") or {}
    weather = context.get("weather") or {}
    home = park.get("home") or {}
    road = park.get("road") or {}
    score = context.get("score")
    score_text = "N/A" if score is None else f"{int(score)}/100"
    delay_text = "WEATHER DELAY RISK" if weather.get("delay_risk") else "NO RAIN SIGNAL IN FEED"

    return (
        '<div class="ml173-step7">'
        '<div class="ml173-step7-head">'
        '<span class="ml173-step7-title">STEP 7 • PARK + WEATHER RUN ENVIRONMENT</span>'
        f'<span class="ml173-grade {escape(str(context.get("label_cls") or "limited"))}">{escape(str(context.get("label") or "DATA LIMITED / PENDING"))}</span>'
        '</div>'
        '<div class="ml173-grid">'
        '<div class="ml173-side">'
        f'<h4>{escape(str(context.get("venue_name") or "Venue"))}</h4>'
        f'<small>{escape(str(park.get("label") or "PARK SAMPLE PENDING"))}</small>'
        f'<div class="ml173-score">RUN ENVIRONMENT • {escape(score_text)}</div>'
        '<div class="ml173-stats">'
        f'<div class="ml173-stat"><b>{_fmt(park.get("factor"),3)}</b><span>Park proxy</span></div>'
        f'<div class="ml173-stat"><b>{_fmt(home.get("rpg"),2)}</b><span>Home R/G</span></div>'
        f'<div class="ml173-stat"><b>{_fmt(road.get("rpg"),2)}</b><span>Road R/G</span></div>'
        f'<div class="ml173-stat"><b>{_fmt(float(park.get("reliability") or 0)*100,0,"%")}</b><span>Park reliability</span></div>'
        '</div>'
        '<div class="ml173-note">'
        '<b>Park method:</b> current-season home club home-vs-road OPS/RG split, shrunk toward neutral. '
        'This is explicitly a descriptive proxy, not an official park factor.'
        '</div>'
        '</div>'
        '<div class="ml173-side">'
        '<h4>Weather + roof</h4>'
        f'<small>{escape(str(weather.get("label") or "WEATHER PENDING"))}</small>'
        '<div class="ml173-stats">'
        f'<div class="ml173-stat"><b>{_fmt(weather.get("temperature"),0,"°F")}</b><span>Temp</span></div>'
        f'<div class="ml173-stat"><b>{escape(str(weather.get("wind_text") or "—"))}</b><span>Wind</span></div>'
        f'<div class="ml173-stat"><b>{escape(str(weather.get("roof_type") or "—"))}</b><span>Roof</span></div>'
        f'<div class="ml173-stat"><b>{escape(str(weather.get("condition") or "—"))}</b><span>Condition</span></div>'
        '</div>'
        f'<div class="ml173-note"><b>{escape(delay_text)}</b> • Indoor/closed-roof settings neutralize outdoor weather in the run-environment score.</div>'
        '</div>'
        '</div>'
        '<div class="ml173-pills">'
        f'<span class="ml173-pill">DATA QUALITY • {int(context.get("data_score") or 0)}/100</span>'
        '<span class="ml173-pill">DEFENSE RESERVED FOR STEP 8</span>'
        '<span class="ml173-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        f'<div class="ml173-source">Official MLB game feed + official venue metadata + official team home/road splits. {escape(str(context.get("reason") or ""))}</div>'
        '</div>'
    )


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml173-step7" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


_FROZEN_STEP6_RENDERER = prior._renderer


def _renderer(original, rows, lineups):
    step6 = _FROZEN_STEP6_RENDERER(original, rows, lineups)
    contexts = _build_context(rows)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        cursor = {"i": 0}
        original_markdown = st.markdown

        def capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(ordered):
                result = ordered[cursor["i"]]
                cursor["i"] += 1
                pk = _i(result.get("game_pk"))
                text = _inject(text, _html(contexts.get(pk) or {}))
            return original_markdown(text, *args, **kwargs)

        st.markdown = capture
        try:
            return step6(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def _render_pregame_with_step7(games_df, section_header, status_info, team_logo, h):
    original_renderer = pregame._renderer
    pregame._renderer = _renderer
    try:
        return pregame.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        pregame._renderer = original_renderer


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Preserve frozen Step 5L live mode while extending only the pregame chain."""
    st.markdown(_STEP7_CSS, unsafe_allow_html=True)
    original_step6_pregame = prior._render_pregame_with_step6
    prior._render_pregame_with_step6 = _render_pregame_with_step7
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._render_pregame_with_step6 = original_step6_pregame


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MIN_ENV_DATA_SCORE",
    "MODEL_VERSION",
    "PARK_FULL_AB",
    "PARK_MIN_AB",
    "_build_context",
    "_data_score",
    "_game_context",
    "_park_run_proxy",
    "_run_environment_score",
    "_weather_profile",
    "render_moneyline_hub",
]
