"""CFB Game Total Page 2 Step 8 — final selected-game runtime.

This additive runtime composes the frozen Page-2 surfaces on the existing exact
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
import cfb_game_total_page2_data_quality_step8_v1 as data_quality
import cfb_game_total_page2_step2_matchup_hero_phx_v1 as step2
import cfb_game_total_page2_step3_integrated_flow_v1 as step3
import cfb_game_total_page2_step4_outlook_summary_v1 as step4
import cfb_game_total_page2_step5_team_snapshot_key_drivers_v1 as step5
import cfb_game_total_page2_step6_trends_scoring_breakdown_v1 as step6
import cfb_game_total_page2_step7_line_lab_best_bet_v1 as step7
import cfb_game_total_page2_stage5_best_bet_v1 as stage5
import cfb_game_total_page2_stage6_tough_favorable_v1 as stage6
import cfb_game_total_step4_matchup_v2 as matchup_read_owner

MODEL_VERSION = "CFB GAME TOTAL PAGE2 STEP8 • FINAL RESPONSIVE LIVE DATA V1"
MARKET = frozen_page.MARKET
STEP8_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_FROZEN"
FROZEN_STEP_TOKENS = (step2.FREEZE_TOKEN, step3.FREEZE_TOKEN, step4.FREEZE_TOKEN, step5.FREEZE_TOKEN, step6.FREEZE_TOKEN, step7.FREEZE_TOKEN)
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
PAGE2_STEP8_CSS = '<style>.gtp2s8-final{max-width:1180px;margin:0 auto;color:#f7fbff;overflow-x:clip}.gtp2s8-back{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px auto 10px;padding:8px 10px;border:1px solid rgba(79,190,232,.22);border-radius:12px;background:rgba(5,22,34,.82)}.gtp2s8-back a{display:inline-flex;align-items:center;min-height:40px;padding:0 12px;border:1px solid rgba(83,207,250,.34);border-radius:10px;background:rgba(15,82,111,.25);color:#80ddff;text-decoration:none;font-size:9px;font-weight:1000;letter-spacing:.05em;text-transform:uppercase}.gtp2s8-back span{min-width:0;color:#7f9eb0;font-size:8px;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtp2s8-cert{margin:0 auto 18px;padding:9px 11px;border:1px solid rgba(71,224,174,.24);border-radius:12px;background:rgba(8,56,47,.22);color:#80efc3;font-size:8px;font-weight:900;letter-spacing:.04em;text-align:center}.gt159-shell>.gtp2s8-live~.gt159-section,.gt159-shell>.gtp2s8-live~.gt159-final,.gt159-shell>.gtp2s8-live~.gt159-top5{display:none!important}@media(max-width:760px){.gtp2s8-final{width:100%;max-width:100%;overflow-x:hidden}.gtp2s8-back{align-items:flex-start;flex-direction:column}.gtp2s8-back a{min-height:44px}.gtp2s8-back span{max-width:100%}}@media(max-width:480px){.gtp2s8-back{margin-bottom:8px;padding:7px}.gtp2s8-cert{font-size:7px;padding:8px}.gtp2s8-final *{max-width:100%;box-sizing:border-box}}</style>'

def _mapping(value: Any) -> Mapping[str, Any]: return value if isinstance(value, Mapping) else {}
def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value=mapping.get(key)
        if value not in (None, ""): return value
    return None
def _number(value: Any) -> float | None:
    try: number=float(value)
    except (TypeError, ValueError): return None
    return number if isfinite(number) else None
def _percent(value: Any) -> str:
    formatted=data_quality.format_optional_percent(value)
    return formatted if formatted is not None else str(value or "").strip() or "—"
def _projected(raw, final): return (_first(final,"projected_combined_total","projected_total") if final.get("ready") else None) or _first(raw,"projected_combined_total","projected_total")
def _market_line(raw, display_game): return _first(display_game,"market_total","verified_market_total") or _first(raw,"analysis_line","market_total")
def _display_edge(projected, market):
    left,right=_number(projected),_number(market)
    return round(left-right,1) if left is not None and right is not None else None
def _event_id(display_game): return str(_first(display_game,"espn_event_id","event_id","game_id","id") or "").strip()
def _selected_day(identity, display_game):
    value=_first(display_game,"date","game_date","kickoff_date","kickoff_iso") or _first(identity,"date","game_date","kickoff_date","kickoff_iso") or _first(_mapping(identity.get("game")),"date","game_date","kickoff_date","kickoff_iso")
    return str(value or "").strip()[:10]
def _enrich_page2_market_context(display_game):
    incoming=dict(_mapping(display_game)); current=_mapping((_LIVE_CONTEXT.get() or {}).get("display_game"))
    if _event_id(current) and _event_id(current)==_event_id(incoming) and _market_line({},current) not in (None,"") and current.get("market_identity_verified") is True and _number(current.get("market_projection_weight"))==0.0: return dict(current)
    enriched=frozen_page._enrich_verified_total_market(incoming); return dict(enriched) if isinstance(enriched,Mapping) else incoming
def _distribution_line_probabilities(raw,line):
    threshold=_number(line); values=raw.get("distribution")
    if threshold is None or raw.get("distribution_ready") is not True or not isinstance(values,Sequence) or isinstance(values,(str,bytes)): return None,None
    over=under=0.0; valid=False
    for row in values:
        if not isinstance(row,Mapping): continue
        total,probability=_number(row.get("total")),_number(row.get("probability"))
        if total is None or probability is None or probability<0: continue
        valid=True
        if total>threshold: over+=probability
        elif total<threshold: under+=probability
    return (over,under) if valid else (None,None)
def _line_scenarios(raw,display_game):
    supplied=raw.get("line_scenarios")
    if isinstance(supplied,Sequence) and not isinstance(supplied,(str,bytes)):
        rows=[dict(row) for row in supplied if isinstance(row,Mapping)]
        if rows:return rows
    market=_number(_market_line(raw,display_game))
    if market is None:return []
    result=[]
    for line in (round(market-3,1),round(market,1),round(market+3,1)):
        over,under=_distribution_line_probabilities(raw,line); result.append({"line":line,"over_probability":_percent(over),"under_probability":_percent(under)})
    return result
def _team_profile_value(profile,*keys): return _first(profile,*keys)
def _display_profile_number(value):
    formatted=data_quality.format_optional_number(value)
    return formatted if formatted is not None else value
def _display_explosive(value):
    number=_number(value)
    if number is None:return value
    if 0.0 <= number <= 1.0:return data_quality.format_optional_percent(number)
    return data_quality.format_optional_number(number)
def _owned_lean(raw,final):
    value=_first(final,"side","lean","pick","recommendation") or _first(raw,"side","lean","pick","recommendation")
    text=str(value or "").strip().upper()
    return text if text in {"OVER","UNDER"} else None
def _recommendation(raw,final,display_game):
    projected=_projected(raw,final); market=_market_line(raw,display_game); pn,mn=_number(projected),_number(market); edge=_display_edge(projected,market); confidence=_first(final,"grade","confidence_label","confidence")
    def no_bet(reason): return {"side":"NO BET","line":market,"probability":None,"expected_total":projected,"edge":edge,"confidence":confidence,"rationale":reason}
    if final.get("ready") is not True or final.get("forecast_ready") is not True:return no_bet("No bet: the independent Game Total forecast is not qualified.")
    if mn is None or display_game.get("market_identity_verified") is not True or _number(display_game.get("market_projection_weight"))!=0.0:return no_bet(data_quality.market_unavailable_rationale(_owned_lean(raw,final)))
    if pn is None:return no_bet("No bet: the qualified forecast has no verified expected total.")
    over,under=_distribution_line_probabilities(raw,mn)
    if over is None or under is None:return no_bet("No bet: the frozen total distribution is unavailable at the verified line.")
    if over==under:return no_bet("No bet: the frozen distribution is tied at the verified market total.")
    if over>under:
        if pn<=mn:return no_bet("No bet: distribution direction and projected-total direction disagree.")
        side,probability="OVER",over
    else:
        if pn>=mn:return no_bet("No bet: distribution direction and projected-total direction disagree.")
        side,probability="UNDER",under
    return {"side":side,"line":mn,"probability":_percent(probability),"expected_total":projected,"edge":edge,"confidence":confidence,"rationale":f"Qualified frozen forecast and distribution favor {side} at the verified market total."}

def _matchup_contract(identity,away,home,display_game):
    """Reuse the existing verified CFB matchup owner; Step 7 adds no provider or model."""
    return matchup_read_owner.build_step4_contract(identity,away,home,display_game,load_engine=True,load_fallback=True)

def build_page2_header_html(payload):
    identity,away,home,display_game,raw,final=map(_mapping,(payload.get("identity"),payload.get("away"),payload.get("home"),payload.get("display_game"),payload.get("raw"),payload.get("final")))
    event_id=_event_id(display_game); market=_market_line(raw,display_game); confidence=_percent(_first(final,"forecast_strength","confidence"))
    hero=step2.build_page2_matchup_hero_html(identity=identity,away=away,home=home,display_game=display_game,away_logo_html=str(payload.get("away_logo_html") or ""),home_logo_html=str(payload.get("home_logo_html") or ""),total_line=market,confidence_label=confidence)
    return f'{PAGE2_STEP8_CSS}<div class="gtp2s8-final gtp2s8-live" data-testid="gtp2s8-final" data-step8="{STEP8_MARKER}" data-timezone="{TIMEZONE}" data-event-id="{escape(event_id)}"><div class="gtp2s8-back" data-testid="gtp2s8-back-to-slate"><a href="?ks_jump_sport=CFB&amp;ks_jump_market=Game+Total" target="_self">← Back to Slate</a><span>Exact event {escape(event_id or "—")} • Phoenix time</span></div>{hero}{step3.build_integrated_game_total_flow_html(active_step=1)}</div>'
def build_page2_body_html(payload):
    identity,away,home,display_game,raw,final=map(_mapping,(payload.get("identity"),payload.get("away"),payload.get("home"),payload.get("display_game"),payload.get("raw"),payload.get("final")))
    projected=_projected(raw,final); market=_market_line(raw,display_game); edge=_display_edge(projected,market); over,under=_distribution_line_probabilities(raw,market)
    if over is None and under is None: over,under=raw.get("over_probability"),raw.get("under_probability")
    over_display=data_quality.format_optional_percent(over) or "No verified Over probability available"
    under_display=data_quality.format_optional_percent(under) or "No verified Under probability available"
    projected_display=data_quality.display_number(projected,missing="No verified projected total available")
    market_display=data_quality.display_number(market,missing="No verified market total available")
    edge_display=data_quality.display_number(edge,missing="No verified edge available")
    outlook=step4.build_outlook_projection_summary_html(over_probability=over_display,under_probability=under_display,projected_total=projected_display,market_line=market_display,edge=edge_display,confidence_label=_first(final,"grade","confidence_label") or _percent(_first(final,"forecast_strength","confidence")))
    away_name=_first(_mapping(identity.get("away")),"team","name") or _first(away,"team","name"); home_name=_first(_mapping(identity.get("home")),"team","name") or _first(home,"team","name"); favorable=raw.get("favorable_for") if isinstance(raw.get("favorable_for"),Mapping) else {}
    away_pace=_team_profile_value(away,"plays_per_game","expected_plays","pace","pace_label"); home_pace=_team_profile_value(home,"plays_per_game","expected_plays","pace","pace_label")
    away_explosive=_team_profile_value(away,"yards_per_play","explosive_rate","explosive_efficiency","explosive"); home_explosive=_team_profile_value(home,"yards_per_play","explosive_rate","explosive_efficiency","explosive")
    away_red_zone=_team_profile_value(away,"red_zone_td_rate","red_zone_rate","red_zone"); home_red_zone=_team_profile_value(home,"red_zone_td_rate","red_zone_rate","red_zone")
    away_defense=_team_profile_value(away,"points_allowed_pg","points_allowed","defensive_efficiency","defense"); home_defense=_team_profile_value(home,"points_allowed_pg","points_allowed","defensive_efficiency","defense")
    snapshot=step5.build_team_snapshot_key_drivers_html(away_team=away_name,home_team=home_name,away_pace=_display_profile_number(away_pace),home_pace=_display_profile_number(home_pace),away_explosive=_display_explosive(away_explosive),home_explosive=_display_explosive(home_explosive),away_red_zone=_percent(away_red_zone),home_red_zone=_percent(home_red_zone),away_defense=_display_profile_number(away_defense),home_defense=_display_profile_number(home_defense),favorable_for=favorable)
    scoring_map=raw.get("scoring_breakdown") if isinstance(raw.get("scoring_breakdown"),Mapping) else {}
    recent_totals=raw.get("recent_totals") if isinstance(raw.get("recent_totals"),Sequence) and not isinstance(raw.get("recent_totals"),(str,bytes)) else []
    trends=step6.build_trends_scoring_breakdown_html(recent_totals=recent_totals,market_line=market,scoring_breakdown=scoring_map,explosive_scoring=_first(raw,"explosive_scoring","explosive_scoring_label"),scoring_opportunities=_first(raw,"scoring_opportunities","scoring_opportunity_rate"),red_zone_finishing=_first(raw,"red_zone_finishing","red_zone_finish_rate"),away_team=away_name,home_team=home_name,away_profile=away,home_profile=home,as_of_day=_selected_day(identity,display_game))
    quality=data_quality.build_data_quality_strip_html(market=data_quality.market_quality(market,identity_verified=display_game.get("market_identity_verified") is True,projection_weight=display_game.get("market_projection_weight")),pace=data_quality.pair_quality(away_pace,home_pace),explosives=data_quality.pair_quality(away_explosive,home_explosive),red_zone=data_quality.pair_quality(away_red_zone,home_red_zone),trends=data_quality.trends_quality(recent_available=bool(recent_totals),splits_available=bool(scoring_map)))
    scenarios=_line_scenarios(raw,display_game); line_lab=step7.build_line_lab_html(line_scenarios=scenarios,selected_line=_first(raw,"analysis_line") or market); best_bet=stage5.build_best_bet_html(_recommendation(raw,final,display_game))
    matchup_contract=_matchup_contract(identity,away,home,display_game); tough_favorable=stage6.build_tough_favorable_html(matchup_contract)
    return f'<div class="gtp2s8-final gtp2s8-live" data-testid="gtp2s8-body">{quality}{outlook}{snapshot}{trends}{line_lab}{best_bet}{tough_favorable}<div class="gtp2s8-cert" data-testid="gtp2s8-live-cert-state" data-sportsbook-projection-influence="0.0">LIVE SELECTED-EVENT DATA • EXACT IDENTITY • RESPONSIVE CERT TARGET</div></div>'
def build_page2_final_html(payload): return build_page2_header_html(payload)+build_page2_body_html(payload)
def _live_payload(raw,final,display_game,statuses,ready_count):
    payload=dict(_LIVE_CONTEXT.get() or {}); payload.update({"raw":raw,"final":final,"display_game":display_game,"statuses":statuses,"ready_count":ready_count}); return payload
def _render_selected_page(callback,*args,**kwargs):
    with _LOCK:
        captured={}; token=_LIVE_CONTEXT.set(captured); original_matchup=hero_runtime_owner._matchup_header_html_v36; original_v38=frozen_page._step4_prediction_market_html_v38; original_late=late_analysis_owner._game_total_hero_html_v21
        def page2_matchup(identity,away,home,display_game):
            enriched_display_game = _enrich_page2_market_context(display_game)
            captured.update({"identity":identity,"away":away,"home":home,"display_game":enriched_display_game,"away_logo_html":hero_runtime_owner.hero_owner._logo(_mapping(_mapping(identity).get("away"))),"home_logo_html":hero_runtime_owner.hero_owner._logo(_mapping(_mapping(identity).get("home")))}); _LIVE_CONTEXT.set(dict(captured)); return build_page2_header_html(captured)
        def page2_analysis(raw,final,display_game,statuses,ready_count):
            enriched_display_game = _enrich_page2_market_context(display_game)
            return build_page2_body_html(_live_payload(raw, final, enriched_display_game, statuses, ready_count))
        hero_runtime_owner._matchup_header_html_v36=page2_matchup; frozen_page._step4_prediction_market_html_v38=page2_analysis; late_analysis_owner._game_total_hero_html_v21=page2_analysis
        try:return callback(*args,**kwargs)
        finally:
            hero_runtime_owner._matchup_header_html_v36=original_matchup; frozen_page._step4_prediction_market_html_v38=original_v38; late_analysis_owner._game_total_hero_html_v21=original_late; _LIVE_CONTEXT.reset(token)
def render_step6_cert_surface(): return frozen_page.render_step6_cert_surface()
def render_game_total_hub(section_header=None,status_info=None,team_logo=None,h=None):
    st.markdown(PAGE2_STEP8_CSS,unsafe_allow_html=True); return _render_selected_page(frozen_page.render_game_total_hub,section_header,status_info,team_logo,h)

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
