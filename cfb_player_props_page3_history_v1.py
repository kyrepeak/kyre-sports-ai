"""CFB Player Props Page 3 V1 — verified production, hit-rate and opportunity views."""
from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

import cfb_player_props_history_v1 as frozen_history
from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import canonical_market_key
import cfb_player_props_model_v1 as frozen_model
import cfb_player_props_page3_gamebook_recovery_v1 as gamebook_recovery


def _text(value: Any) -> str:
    return str(value or '').strip()


def _norm(value: Any) -> str:
    return re.sub(r'[^a-z0-9]+','',_text(value).lower())


def _finite(value: Any) -> float | None:
    try:
        out=float(str(value).replace(',','').strip())
        return out if math.isfinite(out) else None
    except (TypeError,ValueError):
        return None


def _event_rows(raw: Any) -> list[dict[str, Any]]:
    helper=getattr(frozen_history,'_event_rows',None)
    if callable(helper):
        try:
            return [dict(row) for row in helper(raw)]
        except Exception:
            pass
    if isinstance(raw,Mapping):
        items=raw.get('items')
        if isinstance(items,list):
            return [dict(row) for row in items if isinstance(row,Mapping)]
        out=[]
        for key,value in raw.items():
            if isinstance(value,Mapping):
                row=dict(value); row.setdefault('eventId',str(key)); out.append(row)
        return out
    return [dict(row) for row in raw if isinstance(row,Mapping)] if isinstance(raw,list) else []


def _categories(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    helper=getattr(frozen_history,'_categories',None)
    if callable(helper):
        try:
            return list(helper(payload))
        except Exception:
            pass
    cats=payload.get('categories')
    if isinstance(cats,list):
        return [row for row in cats if isinstance(row,Mapping)]
    stats=payload.get('statistics')
    if isinstance(stats,Mapping) and isinstance(stats.get('categories'),list):
        return [row for row in stats['categories'] if isinstance(row,Mapping)]
    return []


def _event_meta(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    helper=getattr(frozen_history,'_event_meta',None)
    if callable(helper):
        try:
            return dict(helper(payload))
        except Exception:
            pass
    rows=_event_rows(payload.get('events') or payload.get('eventMetadata') or {})
    return {_text(row.get('eventId') or row.get('id')):row for row in rows if _text(row.get('eventId') or row.get('id'))}


def _raw_stat_map(category: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    raw=item.get('stats') or item.get('statistics') or []
    if isinstance(raw,Mapping):
        return {_norm(key):value for key,value in raw.items() if _norm(key)}
    labels=[_norm(value) for value in (category.get('labels') or category.get('names') or [])]
    values=list(raw) if isinstance(raw,list) else []
    return {labels[idx]:values[idx] for idx in range(min(len(labels),len(values))) if labels[idx]}


def _first(stats: Mapping[str, Any], *aliases: str) -> Any:
    for alias in aliases:
        key=_norm(alias)
        if key in stats:
            return stats[key]
    return None


def _pair(value: Any) -> tuple[float,float] | None:
    text=_text(value)
    if '/' not in text:
        return None
    left,right=text.split('/',1)
    first=_finite(left); second=_finite(right)
    if first is None or second is None or first < 0 or second < 0:
        return None
    return first,second


def _team_id(value: Any) -> str:
    if not isinstance(value,Mapping):
        return ''
    direct=_text(value.get('id') or value.get('teamId') or value.get('team_id'))
    if direct:
        return direct
    nested=value.get('team')
    if isinstance(nested,Mapping):
        return _text(nested.get('id') or nested.get('teamId') or nested.get('team_id'))
    return ''


def _opponent_team_id(meta: Mapping[str, Any], own_team_id: str) -> str:
    own=_text(own_team_id)
    for key in ('opponent','opponentTeam','opponent_team'):
        candidate=_team_id(meta.get(key))
        if candidate and candidate != own:
            return candidate

    competitor_groups=[]
    if isinstance(meta.get('competitors'),list):
        competitor_groups.append(meta.get('competitors'))
    competition=meta.get('competition')
    if isinstance(competition,Mapping) and isinstance(competition.get('competitors'),list):
        competitor_groups.append(competition.get('competitors'))
    competitions=meta.get('competitions')
    if isinstance(competitions,list):
        for raw in competitions:
            if isinstance(raw,Mapping) and isinstance(raw.get('competitors'),list):
                competitor_groups.append(raw.get('competitors'))
    for group in competitor_groups:
        for competitor in group:
            candidate=_team_id(competitor)
            if candidate and candidate != own:
                return candidate
    return ''


def _auxiliary_by_event(payload: Mapping[str, Any], own_team_id: str) -> dict[str,dict[str,Any]]:
    if not isinstance(payload,Mapping):
        return {}
    out: dict[str,dict[str,Any]]={}
    for event_id,meta in _event_meta(payload).items():
        opponent=_opponent_team_id(meta,own_team_id)
        if opponent:
            out.setdefault(event_id,{})['opponent_team_id']=opponent

    for category in _categories(payload):
        kind=_norm(category.get('name') or category.get('displayName') or category.get('abbreviation'))
        for item in _event_rows(category.get('events')):
            event_id=_text(item.get('eventId') or item.get('id'))
            if not event_id:
                continue
            target=out.setdefault(event_id,{})
            stats=_raw_stat_map(category,item)
            if 'pass' in kind:
                pair=_pair(_first(stats,'C/ATT','CMP/ATT','completions/attempts'))
                if pair is not None:
                    target['completions'],target['pass_attempts']=pair
                else:
                    completions=_finite(_first(stats,'CMP','COMP','completions'))
                    attempts=_finite(_first(stats,'ATT','passingAttempts','passAttempts'))
                    if completions is not None and completions >= 0: target['completions']=completions
                    if attempts is not None and attempts >= 0: target['pass_attempts']=attempts
            if 'rush' in kind:
                carries=_finite(_first(stats,'CAR','ATT','carries','rushingAttempts','rushAttempts'))
                if carries is not None and carries >= 0: target['carries']=carries
            if 'receiv' in kind:
                receptions=_finite(_first(stats,'REC','receptions','receivingReceptions'))
                targets=_finite(_first(stats,'TGT','TGTS','TAR','targets','receivingTargets'))
                if receptions is not None and receptions >= 0: target['receptions']=receptions
                if targets is not None and targets >= 0: target['targets']=targets
    return out


def _merge_primary_and_recovery(
    primary: Sequence[Mapping[str, Any]], recovery: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]]=[]
    seen: set[str]=set()
    for source_rows in (primary,recovery):
        for raw in source_rows or ():
            if not isinstance(raw,Mapping):
                continue
            row=dict(raw)
            event_id=_text(row.get('event_id'))
            if event_id and event_id in seen:
                continue
            if event_id:
                seen.add(event_id)
            merged.append(row)
    merged.sort(key=lambda row: (_text(row.get('game_date')),_text(row.get('event_id'))),reverse=True)
    return merged


def load_page3_history(player: CanonicalPlayerIdentity, market_key: str, *, season: int) -> list[dict[str, Any]]:
    market=canonical_market_key(market_key)
    if market is None:
        return []
    try:
        rows=[dict(row) for row in (frozen_history.load_verified_player_history(player, market, season=int(season)) or []) if isinstance(row, Mapping)]
    except Exception:
        rows=[]

    if len(rows) < int(frozen_model.MIN_SAMPLE):
        try:
            recovered=gamebook_recovery.load_completed_gamebook_history(player,market,season=int(season))
        except Exception:
            recovered=[]
        rows=_merge_primary_and_recovery(rows,recovered)

    try:
        raw_fetch=getattr(frozen_history,'_fetch_gamelog',None)
        payload=raw_fetch(player.official_player_id,int(season)) if callable(raw_fetch) else {}
        auxiliary=_auxiliary_by_event(payload,player.official_team_id)
    except Exception:
        auxiliary={}
    for row in rows:
        extra=auxiliary.get(_text(row.get('event_id'))) or {}
        for key,value in extra.items():
            if value not in (None,''):
                row[key]=value
    return rows


def _summary(rows: Sequence[Mapping[str, Any]], line: float | None) -> dict[str, Any]:
    values=[]
    for row in rows:
        value=_finite(row.get('value'))
        if value is not None and value >= 0:
            values.append(value)
    hits=sum(1 for value in values if line is not None and value > line) if line is not None else None
    return {
        'sample_size':len(values),
        'values':tuple(values),
        'average':(sum(values)/len(values)) if values else None,
        'hits':hits,
        'hit_rate':(hits/len(values)) if hits is not None and values else None,
    }


def build_history_view(history: Sequence[Mapping[str, Any]], selected_line: Any) -> dict[str, Any]:
    line=_finite(selected_line)
    verified=[]
    for raw in history:
        if not isinstance(raw, Mapping):
            continue
        value=_finite(raw.get('value'))
        if value is None or value < 0:
            continue
        row=dict(raw); row['value']=value
        verified.append(row)
    chart=[{**row,'comparison_line':line} for row in verified]
    return {
        'selected_line':line,
        'last5':_summary(verified[:5],line),
        'last8':_summary(verified[:8],line),
        'season':_summary(verified,line),
        'chart':chart,
    }


_OPPORTUNITY_FIELDS={
    'passing_yards':('pass_attempts','completions'),
    'passing_touchdowns':('pass_attempts','completions'),
    'rushing_yards':('carries',),
    'receiving_yards':('receptions','targets'),
    'receiving_receptions':('receptions','targets'),
    'touchdowns':('carries','receptions','targets'),
}


def build_opportunity_evidence(history: Sequence[Mapping[str, Any]], market_key: str) -> dict[str, Any]:
    market=canonical_market_key(market_key)
    metrics={}
    for field in _OPPORTUNITY_FIELDS.get(market,()):
        values=[]
        for row in history:
            value=_finite(row.get(field)) if isinstance(row, Mapping) else None
            if value is not None and value >= 0:
                values.append(value)
        if values:
            metrics[field]={'sample_size':len(values),'values':tuple(values),'average':sum(values)/len(values)}
    return {'available':bool(metrics),'market_key':market,'metrics':metrics}


def build_prior_opponent_history(history: Sequence[Mapping[str, Any]], opponent_team_id: str) -> dict[str, Any]:
    opponent=str(opponent_team_id or '').strip()
    if not opponent:
        return {'available':False,'sample_size':0,'rows':()}
    rows=[]
    for raw in history:
        if not isinstance(raw, Mapping) or str(raw.get('opponent_team_id') or '').strip() != opponent:
            continue
        value=_finite(raw.get('value'))
        if value is None:
            continue
        row=dict(raw); row['value']=value; rows.append(row)
    return {'available':bool(rows),'sample_size':len(rows),'rows':tuple(rows)}


__all__=['build_history_view','build_opportunity_evidence','build_prior_opponent_history','load_page3_history']
