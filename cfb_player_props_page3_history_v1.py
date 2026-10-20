"""CFB Player Props Page 3 V1 — verified production, hit-rate and opportunity views."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import cfb_player_props_history_v1 as frozen_history
from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import canonical_market_key


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except (TypeError,ValueError):
        return None


def load_page3_history(player: CanonicalPlayerIdentity, market_key: str, *, season: int) -> list[dict[str, Any]]:
    market=canonical_market_key(market_key)
    if market is None:
        return []
    try:
        return [dict(row) for row in (frozen_history.load_verified_player_history(player, market, season=int(season)) or []) if isinstance(row, Mapping)]
    except Exception:
        return []


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
