"""NBA PRA Page 1 model: basketball history/role only, never sportsbook-shaped."""
from __future__ import annotations
from math import erf, sqrt
from statistics import mean, median, pstdev
from typing import Any, Mapping, Sequence

MODEL_VERSION = "NBA PRA PAGE1 MODEL V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MIN_SIGMA = 4.0


def _num(value: Any) -> float | None:
    if isinstance(value, bool): return None
    try: value = float(value)
    except (TypeError, ValueError): return None
    return value if value == value else None


def summarize_history(games: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows=[]
    for game in games:
        stats=[_num(game.get(k)) for k in ("points","rebounds","assists")]
        if all(v is not None for v in stats): rows.append((sum(stats), _num(game.get("minutes"))))
    pras=[r[0] for r in rows]; minutes=[r[1] for r in rows if r[1] is not None and r[1] > 0]
    if not pras:
        return {"sample":0,"average":None,"median":None,"l5":None,"l10":None,"sigma":None,"minutes":None}
    return {"sample":len(pras),"average":mean(pras),"median":median(pras),"l5":mean(pras[:5]),"l10":mean(pras[:10]),"sigma":max(MIN_SIGMA,pstdev(pras)) if len(pras)>1 else MIN_SIGMA,"minutes":mean(minutes) if minutes else None}


def _center(summary: Mapping[str, Any]) -> float | None:
    values=[summary.get("average"), summary.get("l10"), summary.get("l5")]
    values=[float(v) for v in values if v is not None]
    if not values: return None
    weights=(0.50,0.30,0.20)[:len(values)]
    return sum(v*w for v,w in zip(values,weights))/sum(weights)


def project_pra(current_games: Sequence[Mapping[str, Any]], prior_games: Sequence[Mapping[str, Any]], *, expected_minutes: float | None=None) -> dict[str, Any]:
    current=summarize_history(current_games); prior=summarize_history(prior_games)
    cc=_center(current); pc=_center(prior)
    if cc is None and pc is None:
        return {"projection":None,"sigma":None,"current":current,"prior":prior,"basis":"HISTORY_UNAVAILABLE"}
    if cc is None:
        raw=pc; basis="PRIOR-SEASON BASELINE"
    elif pc is None:
        raw=cc; basis="CURRENT SEASON"
    else:
        weight=min(0.70,0.20+0.025*current["sample"])
        raw=cc*weight+pc*(1-weight); basis="CURRENT + PRIOR BLEND"
    historical_minutes=current.get("minutes") or prior.get("minutes")
    if raw is not None and expected_minutes is not None and historical_minutes:
        raw*=max(0.80,min(1.20,float(expected_minutes)/float(historical_minutes)))
        basis += " • VERIFIED MINUTES SCALE"
    sigmas=[float(v) for v in (current.get("sigma"),prior.get("sigma")) if v is not None]
    return {"projection":round(raw,1) if raw is not None else None,"sigma":round(max(MIN_SIGMA,mean(sigmas) if sigmas else MIN_SIGMA),2),"current":current,"prior":prior,"basis":basis}


def probability_over(projection: float | None, line: float | None, sigma: float | None) -> float | None:
    if projection is None or line is None or sigma is None or sigma <= 0: return None
    z=(float(line)-float(projection))/float(sigma)
    return round(max(0.01,min(0.99,1-(0.5*(1+erf(z/sqrt(2)))))),4)


def grade_market(projection: float | None, line: float | None, sigma: float | None) -> dict[str, Any]:
    p=probability_over(projection,line,sigma)
    if p is None or projection is None or line is None:
        return {"edge":None,"over_probability":None,"lean":"PASS","confidence":"UNAVAILABLE"}
    edge=round(float(projection)-float(line),1); best=max(p,1-p)
    return {"edge":edge,"over_probability":p,"lean":"OVER" if p>=.55 else "UNDER" if p<=.45 else "PASS","confidence":"HIGH" if best>=.64 else "MEDIUM" if best>=.57 else "LOW"}
