"""CFB Game Total Page 2 Step 8 — final selected-game runtime.

This additive runtime composes the frozen Page-2 Steps 2-7 on the existing exact
CFB Game Total selected-event route. It reuses already-owned runtime/model values,
adds no data provider, and does not alter projection, probability, ranking,
selection, market ownership, or sportsbook influence.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from html import escape
from math import isfinite
from threading import RLock
from typing import Any

import streamlit as st

import cfb_game_total_clean_page_v21 as late_analysis_owner
import cfb_game_total_clean_page_v36 as hero_runtime_owner
import cfb_game_total_clean_page_v38 as frozen_page
import cfb_game_total_page2_step2_matchup_hero_phx_v1 as step2
import cfb_game_total_page2_step3_integrated_flow_v1 as step3
import cfb_game_total_page2_step4_outlook_summary_v1 as step4
import cfb_game_total_page2_step5_team_snapshot_key_drivers_v1 as step5
import cfb_game_total_page2_step6_trends_scoring_breakdown_v1 as step6
import cfb_game_total_page2_step7_line_lab_best_bet_v1 as step7

MODEL_VERSION = "CFB GAME TOTAL PAGE2 STEP8 • FINAL RESPONSIVE LIVE DATA V1"
MARKET = frozen_page.MARKET
STEP8_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_FROZEN"
FROZEN_STEP_TOKENS = (
    step2.FREEZE_TOKEN,
    step3.FREEZE_TOKEN,
    step4.FREEZE_TOKEN,
    step5.FREEZE_TOKEN,
    step6.FREEZE_TOKEN,
    step7.FREEZE_TOKEN,
)
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
GITHUB_ACTIONS_FALLBACK = 0
TIMEZONE = "America/Phoenix"

_LOCK = RLock()
_LIVE_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("cfb_gt_page2_step8_context", default={})

PAGE2_STEP8_CSS = r"""
<style>
.gtp2s8-final{max-width:1180px;margin:0 auto;color:#f7fbff;overflow-x:clip}
.gtp2s8-back{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px auto 10px;padding:8px 10px;border:1px solid rgba(79,190,232,.22);border-radius:12px;background:rgba(5,22,34,.82)}
.gtp2s8-back a{display:inline-flex;align-items:center;min-height:40px;padding:0 12px;border:1px solid rgba(83,207,250,.34);border-radius:10px;background:rgba(15,82,111,.25);color:#80ddff;text-decoration:none;font-size:9px;font-weight:1000;letter-spacing:.05em;text-transform:uppercase}
.gtp2s8-back span{min-width:0;color:#7f9eb0;font-size:8px;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gtp2s8-cert{margin:0 auto 18px;padding:9px 11px;border:1px solid rgba(71,224,174,.24);border-radius:12px;background:rgba(8,56,47,.22);color:#80efc3;font-size:8px;font-weight:900;letter-spacing:.04em;text-align:center}
/* Selected-event Page 2 replaces the old compact Page-1 lower sections only. */
.gt159-shell>.gtp2s8-live~.gt159-section,.gt159-shell>.gtp2s8-live~.gt159-final,.gt159-shell>.gtp2s8-live~.gt159-top5{display:none!important}
@media(max-width:760px){.gtp2s8-final{width:100%;max-width:100%;overflow-x:hidden}.gtp2s8-back{align-items:flex-start;flex-direction:column}.gtp2s8-back a{min-height:44px}.gtp2s8-back span{max-width:100%}}
@media(max-width:480px){.gtp2s8-back{margin-bottom:8px;padding:7px}.gtp2s8-cert{font-size:7px;padding:8px}.gtp2s8-final *{max-width:100%;box-sizing:border-box}}
</style>
"""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _percent(value: Any) -> str:
    number = _number(value)
    if number is None:
        text = str(value or "").strip()
        return text or "—"
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return f"{number:.1f}%"


def _projected(raw: Mapping[str, Any], final: Mapping[str, Any]) -> Any:
    if final.get("ready"):
        return _first(final, "projected_combined_total", "projected_total") or _first(raw, "projected_combined_total", "projected_total")
    return _first(raw, "projected_combined_total", "projected_total")


def _market_line(raw: Mapping[str, Any], display_game: Mapping[str, Any]) -> Any:
    return _first(display_game, "market_total", "verified_market_total") or _first(raw, "analysis_line", "market_total")


def _display_edge(projected: Any, market: Any) -> Any:
    left = _number(projected)
    right = _number(market)
    if left is None or right is None:
        return None
    return round(left - right, 1)


def _event_id(display_game: Mapping[str, Any]) -> str:
    value = _first(display_game, "espn_event_id", "event_id", "game_id", "id")
    return str(value or "").strip()


def _enrich_page2_market_context(display_game: Mapping[str, Any]) -> dict[str, Any]:
    """Restore frozen V38 verified total-market context before Step-8 composition."""
    incoming = dict(_mapping(display_game))
    current = _mapping((_LIVE_CONTEXT.get() or {}).get("display_game"))
    if _event_id(current) and _event_id(current) == _event_id(incoming):
        current_line = _market_line({}, current)
        current_weight = _number(current.get("market_projection_weight"))
        if current_line not in (None, "") and current.get("market_identity_verified") is True and current_weight == 0.0:
            return dict(current)
    enriched = frozen_page._enrich_verified_total_market(incoming)
    return dict(enriched) if isinstance(enriched, Mapping) else incoming


def _distribution_line_probabilities(raw: Mapping[str, Any], line: Any) -> tuple[float | None, float | None]:
    """Read Over/Under probability from the frozen model distribution at a supplied line."""
    threshold = _number(line)
    values = raw.get("distribution")
    if threshold is None or raw.get("distribution_ready") is not True:
        return None, None
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return None, None

    over = 0.0
    under = 0.0
    valid = False
    for row in values:
        if not isinstance(row, Mapping):
            continue
        total = _number(row.get("total"))
        probability = _number(row.get("probability"))
        if total is None or probability is None or probability < 0.0:
            continue
        valid = True
        if total > threshold:
            over += probability
        elif total < threshold:
            under += probability
    if not valid:
        return None, None
    return over, under


def _line_scenarios(raw: Mapping[str, Any], display_game: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    supplied = raw.get("line_scenarios")
    if isinstance(supplied, Sequence) and not isinstance(supplied, (str, bytes)):
        rows = [dict(row) for row in supplied if isinstance(row, Mapping)]
        if rows:
            return rows
    line = _market_line(raw, display_game)
    if line in (None, ""):
        return []
    over, under = _distribution_line_probabilities(raw, line)
    return [{
        "line": line,
        "over_probability": _percent(over),
        "under_probability": _percent(under),
    }]


def _team_profile_value(profile: Mapping[str, Any], *keys: str) -> Any:
    return _first(profile, *keys)


def _recommendation(raw: Mapping[str, Any], final: Mapping[str, Any], display_game: Mapping[str, Any]) -> dict[str, Any]:
    projected = _projected(raw, final)
    market = _market_line(raw, display_game)
    active = final.get("betting_pick_active") is True
    if not active:
        return {
            "side": "NO BET",
            "line": market,
            "probability": None,
            "expected_total": projected,
            "edge": _display_edge(projected, market),
            "confidence": _first(final, "grade", "confidence_label", "confidence"),
            "rationale": _first(final, "rationale", "reason", "summary", "explanation") or "Independent Game Total forecast",
        }
    return {
        "side": _first(final, "recommendation", "pick", "lean", "side"),
        "line": market,
        "probability": _first(final, "bet_probability", "probability", "win_probability"),
        "expected_total": projected,
        "edge": _display_edge(projected, market),
        "confidence": _first(final, "grade", "confidence_label", "confidence"),
        "rationale": _first(final, "rationale", "reason", "summary", "explanation") or "Independent Game Total forecast",
    }


def build_page2_header_html(payload: Mapping[str, Any]) -> str:
    identity = _mapping(payload.get("identity"))
    away = _mapping(payload.get("away"))
    home = _mapping(payload.get("home"))
    display_game = _mapping(payload.get("display_game"))
    raw = _mapping(payload.get("raw"))
    final = _mapping(payload.get("final"))
    event_id = _event_id(display_game)
    market = _market_line(raw, display_game)
    confidence = _percent(_first(final, "forecast_strength", "confidence"))
    hero = step2.build_page2_matchup_hero_html(
        identity=identity,
        away=away,
        home=home,
        display_game=display_game,
        away_logo_html=str(payload.get("away_logo_html") or ""),
        home_logo_html=str(payload.get("home_logo_html") or ""),
        total_line=market,
        confidence_label=confidence,
    )
    back_url = "?ks_jump_sport=CFB&amp;ks_jump_market=Game+Total"
    return f"""
{PAGE2_STEP8_CSS}
<div class="gtp2s8-final gtp2s8-live" data-testid="gtp2s8-final" data-step8="{STEP8_MARKER}" data-timezone="{TIMEZONE}" data-event-id="{escape(event_id)}">
  <div class="gtp2s8-back" data-testid="gtp2s8-back-to-slate"><a href="{back_url}" target="_self">← Back to Slate</a><span>Exact event {escape(event_id or '—')} • Phoenix time</span></div>
  {hero}
  {step3.build_integrated_game_total_flow_html(active_step=1)}
</div>
"""


def build_page2_body_html(payload: Mapping[str, Any]) -> str:
    identity = _mapping(payload.get("identity"))
    away = _mapping(payload.get("away"))
    home = _mapping(payload.get("home"))
    display_game = _mapping(payload.get("display_game"))
    raw = _mapping(payload.get("raw"))
    final = _mapping(payload.get("final"))
    projected = _projected(raw, final)
    market = _market_line(raw, display_game)
    over, under = _distribution_line_probabilities(raw, market)
    if over is None and under is None:
        over = raw.get("over_probability")
        under = raw.get("under_probability")
    edge = _display_edge(projected, market)
    confidence = _first(final, "grade", "confidence_label") or _percent(_first(final, "forecast_strength", "confidence"))

    outlook = step4.build_outlook_projection_summary_html(
        over_probability=over,
        under_probability=under,
        projected_total=projected,
        market_line=market,
        edge=edge,
        confidence_label=confidence,
    )

    away_name = _first(_mapping(identity.get("away")), "team", "name") or _first(away, "team", "name")
    home_name = _first(_mapping(identity.get("home")), "team", "name") or _first(home, "team", "name")
    favorable = raw.get("favorable_for") if isinstance(raw.get("favorable_for"), Mapping) else {}
    snapshot = step5.build_team_snapshot_key_drivers_html(
        away_team=away_name,
        home_team=home_name,
        away_pace=_team_profile_value(away, "plays_per_game", "expected_plays", "pace", "pace_label"),
        home_pace=_team_profile_value(home, "plays_per_game", "expected_plays", "pace", "pace_label"),
        away_explosive=_team_profile_value(away, "yards_per_play", "explosive_rate", "explosive_efficiency", "explosive"),
        home_explosive=_team_profile_value(home, "yards_per_play", "explosive_rate", "explosive_efficiency", "explosive"),
        away_red_zone=_percent(_team_profile_value(away, "red_zone_td_rate", "red_zone_rate", "red_zone")),
        home_red_zone=_percent(_team_profile_value(home, "red_zone_td_rate", "red_zone_rate", "red_zone")),
        away_defense=_team_profile_value(away, "points_allowed_pg", "points_allowed", "defensive_efficiency", "defense"),
        home_defense=_team_profile_value(home, "points_allowed_pg", "points_allowed", "defensive_efficiency", "defense"),
        favorable_for=favorable,
    )

    scoring = raw.get("scoring_breakdown") if isinstance(raw.get("scoring_breakdown"), Mapping) else {}
    trends = step6.build_trends_scoring_breakdown_html(
        recent_totals=raw.get("recent_totals") if isinstance(raw.get("recent_totals"), Sequence) and not isinstance(raw.get("recent_totals"), (str, bytes)) else [],
        market_line=market,
        scoring_breakdown=scoring,
        explosive_scoring=_first(raw, "explosive_scoring", "explosive_scoring_label"),
        scoring_opportunities=_first(raw, "scoring_opportunities", "scoring_opportunity_rate"),
        red_zone_finishing=_first(raw, "red_zone_finishing", "red_zone_finish_rate"),
    )

    scenarios = _line_scenarios(raw, display_game)
    selected_line = _first(raw, "analysis_line") or market
    line_lab = step7.build_line_lab_best_bet_html(
        line_scenarios=scenarios,
        selected_line=selected_line,
        recommendation=_recommendation(raw, final, display_game),
    )
    return f"""
<div class="gtp2s8-final gtp2s8-live" data-testid="gtp2s8-body">
  {outlook}
  {snapshot}
  {trends}
  {line_lab}
  <div class="gtp2s8-cert" data-testid="gtp2s8-live-cert-state" data-sportsbook-projection-influence="0.0">LIVE SELECTED-EVENT DATA • EXACT IDENTITY • RESPONSIVE CERT TARGET</div>
</div>
"""


def build_page2_final_html(payload: Mapping[str, Any]) -> str:
    """Pure composition used by tests and final responsive certification."""
    return build_page2_header_html(payload) + build_page2_body_html(payload)


def _live_payload(raw: Mapping[str, Any], final: Mapping[str, Any], display_game: Mapping[str, Any], statuses: Mapping[int, str], ready_count: int) -> dict[str, Any]:
    payload = dict(_LIVE_CONTEXT.get() or {})
    payload.update({"raw": raw, "final": final, "display_game": display_game, "statuses": statuses, "ready_count": ready_count})
    return payload


def _render_selected_page(callback, *args: Any, **kwargs: Any):
    with _LOCK:
        captured: dict[str, Any] = {}
        token = _LIVE_CONTEXT.set(captured)
        original_matchup = hero_runtime_owner._matchup_header_html_v36
        original_v38_analysis = frozen_page._step4_prediction_market_html_v38
        original_late_analysis = late_analysis_owner._game_total_hero_html_v21

        def page2_matchup(identity, away, home, display_game):
            enriched_display_game = _enrich_page2_market_context(display_game)
            captured.update({
                "identity": identity,
                "away": away,
                "home": home,
                "display_game": enriched_display_game,
                "away_logo_html": hero_runtime_owner.hero_owner._logo(_mapping(_mapping(identity).get("away"))),
                "home_logo_html": hero_runtime_owner.hero_owner._logo(_mapping(_mapping(identity).get("home"))),
            })
            _LIVE_CONTEXT.set(dict(captured))
            return build_page2_header_html(captured)

        def page2_analysis(raw, final, display_game, statuses, ready_count):
            enriched_display_game = _enrich_page2_market_context(display_game)
            return build_page2_body_html(_live_payload(raw, final, enriched_display_game, statuses, ready_count))

        hero_runtime_owner._matchup_header_html_v36 = page2_matchup
        frozen_page._step4_prediction_market_html_v38 = page2_analysis
        late_analysis_owner._game_total_hero_html_v21 = page2_analysis
        try:
            return callback(*args, **kwargs)
        finally:
            hero_runtime_owner._matchup_header_html_v36 = original_matchup
            frozen_page._step4_prediction_market_html_v38 = original_v38_analysis
            late_analysis_owner._game_total_hero_html_v21 = original_late_analysis
            _LIVE_CONTEXT.reset(token)


def render_step6_cert_surface() -> None:
    return frozen_page.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(PAGE2_STEP8_CSS, unsafe_allow_html=True)
    return _render_selected_page(
        frozen_page.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page2 Step8 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FREEZE_TOKEN",
    "FROZEN_STEP_TOKENS",
    "GITHUB_ACTIONS_FALLBACK",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STEP8_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP8_MARKER",
    "TIMEZONE",
    "build_page2_body_html",
    "build_page2_final_html",
    "build_page2_header_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
