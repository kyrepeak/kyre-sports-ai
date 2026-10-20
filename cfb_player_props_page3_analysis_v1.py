"""CFB Player Props Page 3 V1 — compositional analysis packet over frozen owners."""
from __future__ import annotations

from typing import Any, Mapping

import cfb_player_props_model_v1 as frozen_model
import cfb_player_props_page2_availability_v1 as page2_availability
import cfb_player_props_page2_market_v1 as page2_market
import cfb_player_props_page2_matchup_v1 as page2_matchup
import cfb_player_props_page3_history_v1 as page3_history
import cfb_player_props_page3_line_lab_v1 as line_lab

SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE


def _text(value: Any) -> str:
    return str(value or '').strip()


def _cfb_season_from_date(value: Any) -> int:
    text=_text(value)
    try:
        year=int(text[:4]); month=int(text[5:7])
    except (TypeError,ValueError):
        return 0
    if month < 1 or month > 12:
        return 0
    return year if month >= 7 else year - 1


def _opponent_team_id(context: Mapping[str, Any], player: Any) -> str:
    team_id=_text(getattr(player,'official_team_id',''))
    away=_text(context.get('away_team_id')); home=_text(context.get('home_team_id'))
    if team_id == away:
        return home
    if team_id == home:
        return away
    return ''


def build_reasoning(line_result: Mapping[str, Any], history_view: Mapping[str, Any], matchup: Mapping[str, Any], availability: Mapping[str, Any], movement: Mapping[str, Any]) -> dict[str, Any]:
    why=[]; bull=[]; bear=[]
    margin=line_result.get('margin')
    if line_result.get('model_ready') and isinstance(margin,(int,float)):
        direction='above' if margin >= 0 else 'below'
        why.append(f"Frozen projection is {abs(float(margin)):.1f} {direction} the selected line.")
        (bull if margin >= 0 else bear).append(why[-1])
    last5=(history_view.get('last5') or {}) if isinstance(history_view,Mapping) else {}
    avg=last5.get('average')
    selected=line_result.get('line')
    if isinstance(avg,(int,float)) and isinstance(selected,(int,float)) and int(last5.get('sample_size') or 0) > 0:
        direction='above' if float(avg) >= float(selected) else 'below'
        statement=f"Last-5 verified average is {direction} the selected line ({float(avg):.1f} vs {float(selected):.1f})."
        why.append(statement); (bull if direction=='above' else bear).append(statement)
    label=_text(matchup.get('label')).upper()
    if label in {'FAVORABLE','NEUTRAL','TOUGH'}:
        statement=f"Opponent matchup context is {label.lower()}."
        why.append(statement)
        if label=='FAVORABLE': bull.append(statement)
        elif label=='TOUGH': bear.append(statement)
    state=_text(availability.get('state')).upper() or 'UNVERIFIED'
    if state != 'UNVERIFIED':
        statement=f"Player availability is verified as {state}."
        why.append(statement)
        if state in {'OUT','DOUBTFUL','QUESTIONABLE'}: bear.append(statement)
    if movement.get('available') is True:
        delta=movement.get('delta')
        if isinstance(delta,(int,float)):
            why.append(f"Verified market opening-to-current move is {float(delta):+.1f}.")
    if not why:
        why.append('Verified evidence is limited; no additional directional claim is made.')
    return {
        'why':why,
        'bull_case':' '.join(bull) if bull else 'No additional verified bull-case evidence.',
        'bear_case':' '.join(bear) if bear else 'No additional verified bear-case evidence.',
    }


def build_page3_analysis(context: Mapping[str, Any], *, selected_line: Any = None, season: int | None = None, opening_rows=()) -> dict[str, Any]:
    player=context.get('player')
    market_key=_text(context.get('market_key'))
    if player is None or not market_key:
        return {'state':'invalid','reason':'Exact player and market are required.','sportsbook_projection_influence':SPORTSBOOK_PROJECTION_INFLUENCE}
    if season is None:
        season=_cfb_season_from_date(context.get('slate_date'))

    observations=page2_market.load_game_prop_observations(context,[player])
    market=page2_market.build_player_market_view(player,market_key,observations,opening_rows=opening_rows)
    history=page3_history.load_page3_history(player.identity,market_key,season=int(season or 0))
    projection=frozen_model.build_prop_projection(history,market_key)
    line=selected_line if selected_line is not None else line_lab.default_line(
        market_key, consensus_line=market.get('consensus_line'), handoff_line=context.get('handoff_line')
    )
    evaluated=line_lab.evaluate_line(projection,line,market_key)
    curve=line_lab.build_probability_curve(projection,evaluated.get('line'),market_key)
    history_view=page3_history.build_history_view(history,evaluated.get('line'))
    opportunity=page3_history.build_opportunity_evidence(history,market_key)
    opponent_id=_opponent_team_id(context,player)
    prior=page3_history.build_prior_opponent_history(history,opponent_id)
    matchup_context=page2_matchup.load_game_matchup_context(context)
    matchup=page2_matchup.grade_player_matchup(player,market_key,matchup_context)
    availability_map=page2_availability.load_game_availability(context,[player])
    availability=dict(availability_map.get(player.official_player_id) or {'state':'UNVERIFIED','source':''})
    movement=dict(market.get('movement') or {'available':False})
    latest=''
    for row in market.get('observations') or []:
        stamp=_text(getattr(row,'observed_at_utc',''))
        if stamp > latest: latest=stamp
    reasoning=build_reasoning(evaluated,history_view,matchup,availability,movement)
    quality={
        'model_ready':bool(projection.get('model_ready')),
        'model_sample_count':int(projection.get('sample_count') or 0),
        'verified_book_count':int(market.get('book_count') or 0),
        'latest_market_timestamp':latest,
        'availability_state':_text(availability.get('state')) or 'UNVERIFIED',
        'opponent_data_available':_text(matchup.get('label')).upper() not in {'','CHECK'},
        'movement_available':movement.get('available') is True,
    }
    return {
        'state':'ready' if market.get('observations') else 'market_unavailable',
        'market_key':market_key,
        'player':player,
        'market':market,
        'available_markets':tuple(key for key in page2_market.MARKET_ORDER if any(row.canonical_player_id == player.official_player_id and row.market_key == key for row in observations)),
        'projection':projection,
        'history_rows':tuple(history),
        'line_lab':evaluated,
        'probability_curve':curve,
        'history':history_view,
        'opportunity':opportunity,
        'prior_opponent':prior,
        'opponent_team_id':opponent_id,
        'matchup':matchup,
        'availability':availability,
        'movement':movement,
        'reasoning':reasoning,
        'quality':quality,
        'sportsbook_projection_influence':SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def reline_page3_analysis(packet: Mapping[str, Any], selected_line: Any) -> dict[str, Any]:
    out=dict(packet)
    market_key=_text(out.get('market_key'))
    projection=out.get('projection') or {}
    evaluated=line_lab.evaluate_line(projection,selected_line,market_key)
    history_rows=list(out.get('history_rows') or [])
    history_view=page3_history.build_history_view(history_rows,evaluated.get('line'))
    out['line_lab']=evaluated
    out['probability_curve']=line_lab.build_probability_curve(projection,evaluated.get('line'),market_key)
    out['history']=history_view
    out['reasoning']=build_reasoning(evaluated,history_view,out.get('matchup') or {},out.get('availability') or {},out.get('movement') or {})
    return out


__all__=['SPORTSBOOK_PROJECTION_INFLUENCE','build_page3_analysis','build_reasoning','reline_page3_analysis']