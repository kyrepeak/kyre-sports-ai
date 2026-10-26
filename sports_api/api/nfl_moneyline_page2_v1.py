"""Kyre Sports API — NFL Moneyline Page 2 verified display context."""
from __future__ import annotations

import math
from typing import Any, Mapping
import pandas as pd
from sports_api import nfl_data_nflverse_v1 as nflverse

SCHEMA_VERSION = "nfl_moneyline_page2_v1"
MODEL_VERSION = "NFL MONEYLINE PAGE2 API V1 • VERIFIED DISPLAY CONTEXT"
DISPLAY_ONLY = True
MODEL_INFLUENCE = 0.0
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
HISTORY_SOURCE = "nflverse"


def _clean(value: Any, fallback: str = "") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or fallback


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _abbr(value: Any) -> str:
    return nflverse.canonical_team_abbr(value)


def _semantic(state: str, reason: str, **values: Any) -> dict[str, Any]:
    return {"status": "SEMANTIC_EMPTY", "semantic_state": state, "reason": reason, **values}


def _meeting(record: Mapping[str, Any]) -> dict[str, Any] | None:
    away = _abbr(record.get("away_team")); home = _abbr(record.get("home_team"))
    away_score = _num(record.get("away_score")); home_score = _num(record.get("home_score"))
    day = _clean(record.get("gameday"))[:10]
    if not away or not home or away_score is None or home_score is None or not day:
        return None
    winner = "TIE" if away_score == home_score else (away if away_score > home_score else home)
    return {
        "date": day, "away_abbr": away, "home_abbr": home,
        "away_score": int(away_score), "home_score": int(home_score),
        "score": f"{away} {int(away_score)} – {home} {int(home_score)}",
        "winner_abbr": winner, "margin": float(abs(away_score-home_score)),
        "combined_score": float(away_score+home_score), "site": home,
    }


def _history_empty(state: str, reason: str) -> dict[str, Any]:
    return _semantic(state, reason, source=HISTORY_SOURCE, display_only=True, model_influence=0.0,
        games=0, series_summary="No verified meetings", average_margin=None,
        average_combined_score=None, current_home_record=None, recent_meetings=[], full_meetings=[])


def normalize_matchup_history(frame: pd.DataFrame, away_abbr: str, home_abbr: str, *, limit: int = 5, full_limit: int = 50) -> dict[str, Any]:
    """Normalize exact completed head-to-head meetings, newest first."""
    away = _abbr(away_abbr); home = _abbr(home_abbr)
    if not away or not home or away == home:
        return _history_empty("MATCHUP_IDENTITY_UNAVAILABLE", "Exact team identity is unavailable.")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return _history_empty("HISTORY_SOURCE_UNAVAILABLE", "Verified matchup history is unavailable.")
    required = {"gameday", "away_team", "home_team", "away_score", "home_score"}
    if not required.issubset(frame.columns):
        return _history_empty("HISTORY_SCHEMA_UNAVAILABLE", "Verified history fields are incomplete.")
    rows = frame.copy()
    rows["_away"] = rows["away_team"].map(_abbr); rows["_home"] = rows["home_team"].map(_abbr)
    pair = rows[((rows["_away"] == away) & (rows["_home"] == home)) | ((rows["_away"] == home) & (rows["_home"] == away))].copy()
    pair = pair[pair["away_score"].notna() & pair["home_score"].notna()]
    if pair.empty:
        return _history_empty("NO_PREVIOUS_MEETINGS", "No previous verified meetings are available for these teams.")
    pair["_date"] = pd.to_datetime(pair["gameday"], errors="coerce")
    pair = pair[pair["_date"].notna()].sort_values("_date", ascending=False)
    meetings = []
    for raw in pair.head(min(max(int(full_limit), 1), 100)).to_dict("records"):
        item = _meeting(raw)
        if item: meetings.append(item)
    if not meetings:
        return _history_empty("NO_PREVIOUS_MEETINGS", "No previous verified completed meetings are available.")
    wins = {away: 0, home: 0}; ties = 0
    for row in meetings:
        if row["winner_abbr"] in wins: wins[row["winner_abbr"]] += 1
        elif row["winner_abbr"] == "TIE": ties += 1
    if wins[away] == wins[home]: series = f"Series tied {wins[away]}-{wins[home]}"
    else:
        leader = away if wins[away] > wins[home] else home; trailer = home if leader == away else away
        series = f"{leader} leads {wins[leader]}-{wins[trailer]}"
    if ties: series += f"-{ties}"
    at_home = [row for row in meetings if row["home_abbr"] == home]
    home_record = None
    if at_home:
        hw = sum(row["winner_abbr"] == home for row in at_home); hl = sum(row["winner_abbr"] == away for row in at_home); ht = sum(row["winner_abbr"] == "TIE" for row in at_home)
        home_record = f"{hw}-{hl}" + (f"-{ht}" if ht else "")
    margins = [row["margin"] for row in meetings]; totals = [row["combined_score"] for row in meetings]
    return {
        "status": "READY", "semantic_state": "", "reason": "", "source": HISTORY_SOURCE,
        "display_only": True, "model_influence": 0.0, "games": len(meetings), "series_summary": series,
        "average_margin": round(sum(margins)/len(margins),1), "average_combined_score": round(sum(totals)/len(totals),1),
        "current_home_record": home_record, "recent_meetings": meetings[:min(max(int(limit),1),10)], "full_meetings": meetings,
    }


def load_matchup_history(game: Mapping[str, Any], *, limit: int = 5, full_limit: int = 50) -> dict[str, Any]:
    try:
        frame = nflverse._load_games_csv()
    except Exception as exc:
        return _history_empty("HISTORY_SOURCE_UNAVAILABLE", f"Verified matchup history is temporarily unavailable ({type(exc).__name__}).")
    return normalize_matchup_history(frame, _abbr(game.get("away_abbr")), _abbr(game.get("home_abbr")), limit=limit, full_limit=full_limit)


def _profile_values(profile: Mapping[str, Any]) -> dict[str, Any]:
    blended = profile.get("blended") or {}; current = profile.get("current") or {}
    return {"ready": bool(profile.get("ready")), "quality": _clean(profile.get("quality"), "CHECK").upper(),
        "strength_index": _num(profile.get("strength_index")), "win_pct": _num(blended.get("win_pct")),
        "ppg": _num(blended.get("ppg")), "papg": _num(blended.get("papg")),
        "recent6_diff_pg": _num(blended.get("recent6_diff_pg")), "games": int(_num(current.get("games")) or 0)}


def _side_context(abbr: str, contexts: Mapping[str, Any], gameplans: Mapping[str, Any]) -> dict[str, Any]:
    context = dict(contexts.get(abbr) or {}); plan = dict(gameplans.get(abbr) or {})
    depth = context.get("depth_chart") or context.get("depth") or {}
    starter = context.get("starter_qb") or context.get("qb1") or (depth.get("QB") if isinstance(depth, Mapping) else None) or plan.get("starter_qb")
    if isinstance(starter, Mapping):
        starter_name = _clean(starter.get("name") or starter.get("player_name"), "QB verification pending")
        starter_status = _clean(starter.get("status") or starter.get("availability"), "CHECK").upper()
    else:
        starter_name = _clean(starter, "QB verification pending")
        starter_status = _clean(context.get("qb_status") or plan.get("status") or context.get("availability"), "CHECK").upper()
    injuries = context.get("injuries") or context.get("injury_report") or []
    if isinstance(injuries, Mapping): injuries = list(injuries.values())
    verified = []
    for raw in injuries if isinstance(injuries, (list, tuple)) else []:
        if not isinstance(raw, Mapping): continue
        name = _clean(raw.get("name") or raw.get("player") or raw.get("player_name"))
        if not name: continue
        verified.append({"name": name, "position": _clean(raw.get("position") or raw.get("pos"), "—"),
            "status": _clean(raw.get("status") or raw.get("designation"), "CHECK").upper(), "impact": _clean(raw.get("impact"), "")})
    return {"starter_qb": starter_name, "starter_status": starter_status, "injuries": verified[:8], "context_ready": bool(context), "gameplan_ready": bool(plan)}


def _factor(label: str, away: float | None, home: float | None, *, lower_is_better: bool = False) -> dict[str, Any] | None:
    if away is None or home is None: return None
    if abs(home-away) < 1e-9: advantage = "even"
    elif ((home < away) if lower_is_better else (home > away)): advantage = "home"
    else: advantage = "away"
    return {"label": label, "away": away, "home": home, "advantage": advantage}


def build_page2_context(*, game: Mapping[str, Any], final: Mapping[str, Any], edge_out: Mapping[str, Any], mc_out: Mapping[str, Any], snap: Mapping[str, Any], profiles: Mapping[str, Any], contexts: Mapping[str, Any], gameplans: Mapping[str, Any], history: Mapping[str, Any]) -> dict[str, Any]:
    away_abbr = _abbr(game.get("away_abbr")); home_abbr = _abbr(game.get("home_abbr"))
    away_profile = _profile_values(dict(profiles.get(away_abbr) or {})); home_profile = _profile_values(dict(profiles.get(home_abbr) or {}))
    away_context = _side_context(away_abbr, contexts, gameplans); home_context = _side_context(home_abbr, contexts, gameplans)
    pick_side = _clean(final.get("leader_side"), "home").lower(); pick_side = pick_side if pick_side in {"away","home"} else "home"
    side_out = dict(edge_out.get(pick_side) or {}); best = dict(snap.get(f"best_{pick_side}") or {})
    verdict = {"pick_side": pick_side, "pick_team": _clean(game.get(f"{pick_side}_team"), pick_side.title()), "pick_abbr": _abbr(game.get(f"{pick_side}_abbr")),
        "state": _clean(final.get("state"), "GATED").upper(), "grade": _clean((final.get("leader_grade") or {}).get("grade"), _clean(final.get("state"), "GATED")).upper(),
        "model_probability": _num(side_out.get("model_p")), "market_probability": _num(side_out.get("market_p")), "edge": _num(side_out.get("edge")), "ev": _num(side_out.get("ev")),
        "conservative_edge": _num(side_out.get("conservative_edge")), "conservative_ev": _num(side_out.get("conservative_ev")),
        "best_price": _num(side_out.get("best_price") if side_out.get("best_price") is not None else best.get("price")), "best_book": _clean(best.get("book"), "—"),
        "eligible": bool(final.get("eligible")), "gate_reasons": list((final.get("prerequisites") or {}).get("reasons") or [])}
    advantages = [row for row in (_factor("Strength index", away_profile["strength_index"], home_profile["strength_index"]),
        _factor("Scoring offense", away_profile["ppg"], home_profile["ppg"]), _factor("Scoring defense", away_profile["papg"], home_profile["papg"], lower_is_better=True),
        _factor("Recent form", away_profile["recent6_diff_pg"], home_profile["recent6_diff_pg"])) if row]
    why = [f'{row["label"]} favors {verdict["pick_abbr"]} in the verified team profile.' for row in advantages if row["advantage"] == pick_side]
    pick_ctx = home_context if pick_side == "home" else away_context
    if pick_ctx["starter_status"] not in {"OUT","DOUBTFUL","UNAVAILABLE"}: why.append(f'{verdict["pick_abbr"]} quarterback context is {pick_ctx["starter_status"].lower()} entering this matchup.')
    if not why: why = ["The frozen Moneyline engine identifies this side as the current quantitative leader."]
    other_side = "away" if pick_side == "home" else "home"; other_team = _clean(game.get(f"{other_side}_team"), "Opponent")
    market_rows=[]
    for raw in snap.get("rows") or []:
        if isinstance(raw, Mapping): market_rows.append({"book": _clean(raw.get("book"),"—"), "away_ml": _num(raw.get("away_ml")), "home_ml": _num(raw.get("home_ml")), "freshness": _clean(raw.get("freshness"),"UNKNOWN"), "provider": _clean(raw.get("provider"),"—")})
    home_mc = _num(mc_out.get("home_win_rate")); away_mc = _num(mc_out.get("away_win_rate"))
    if home_mc is None: home_mc = _num(mc_out.get("home_probability"))
    if away_mc is None: away_mc = _num(mc_out.get("away_probability"))
    if home_mc is None and away_mc is not None: home_mc = 1.0-away_mc
    if away_mc is None and home_mc is not None: away_mc = 1.0-home_mc
    risks=[]
    if final.get("state") in {"GATED","HIGH UNCERTAINTY"}: risks.append({"label":"Model uncertainty","level":"HIGH"})
    elif verdict["conservative_edge"] is not None and verdict["conservative_edge"] <= 0: risks.append({"label":"Edge floor","level":"HIGH"})
    else: risks.append({"label":"Model uncertainty","level":"MEDIUM"})
    risks.append({"label":"Availability verification","level":"LOW" if away_context["context_ready"] and home_context["context_ready"] else "MEDIUM"})
    risks.append({"label":"Market quality","level":"HIGH" if _clean(snap.get("quality"),"LOW").upper()=="LOW" else "MEDIUM"})
    risks.append({"label":"Turnover / explosive-play variance","level":"MEDIUM"})
    return {"schema_version":SCHEMA_VERSION,"status":"READY","game":dict(game),"verdict":verdict,"profiles":{"away":away_profile,"home":home_profile},"advantages":advantages,
        "why":{"bullets":why[:5],"biggest_reason":why[0],"could_lose":f"{other_team} can flip the matchup if turnover and explosive-play variance overwhelms the current model edge."},
        "history":dict(history),"game_script":{"summary":f'{verdict["pick_team"]} projects as the stronger Moneyline side if it sustains its verified profile advantages, protects the football, and keeps the game in its preferred efficiency range.',
        "pick_path":[f'Convert the {verdict["pick_abbr"]} profile advantage into early-down efficiency.',"Protect possessions and avoid short-field turnovers.","Keep quarterback availability and offensive structure intact."],
        "upset_path":[f"{other_team} creates explosive plays or short fields.","The underdog wins turnover variance.","The current model edge compresses under game-state volatility."]},
        "availability":{"away":away_context,"home":home_context},"recent_form":{"away":away_profile,"home":home_profile},
        "market":{"quality":_clean(snap.get("quality"),"CHECK"),"providers":list(snap.get("providers") or []),"best_away":dict(snap.get("best_away") or {}),"best_home":dict(snap.get("best_home") or {}),"rows":market_rows},
        "simulation":{"simulations":int(_num(mc_out.get("simulations")) or 0),"converged":bool(mc_out.get("converged")),"away_win_rate":away_mc,"home_win_rate":home_mc,"p05_probability":_num(mc_out.get("p05_probability")),"p95_probability":_num(mc_out.get("p95_probability"))},
        "risks":risks,"guardrails":{"display_only":True,"model_influence":0.0,"sportsbook_model_influence":0.0,"sportsbook_projection_influence":0.0,"stake_sizing_enabled":False,"frozen_final_state":_clean(final.get("state"),"GATED")}}


__all__=["DISPLAY_ONLY","HISTORY_SOURCE","MODEL_INFLUENCE","MODEL_VERSION","SCHEMA_VERSION","SPORTSBOOK_MODEL_INFLUENCE","SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED","build_page2_context","load_matchup_history","normalize_matchup_history"]