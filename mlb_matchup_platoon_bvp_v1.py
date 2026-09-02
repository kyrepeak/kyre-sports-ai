"""MLB Matchup Intelligence V2 Step 4 — platoon + batter-vs-pitcher context.

This module connects the certified Step 2 hitter profile to the certified Step 3
starter identity through handedness splits and BvP history. It is deliberately
context-only: it produces descriptive matchup evidence and sample reliability,
not a game-level hit probability or production-model adjustment.
"""
from __future__ import annotations

import math
from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui


BVP_PRIOR_AB = 30.0
BVP_MAX_RELIABILITY = 0.70
HITTER_SPLIT_FULL_AB = 150.0
PITCHER_SPLIT_FULL_BF = 200.0


def _float(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _int(value: Any) -> int:
    value = _float(value)
    return int(value) if value is not None else 0


def _rate(value: Any) -> float | None:
    value = _float(value)
    if value is None:
        return None
    if abs(value) > 1.0:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _hand(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if text.startswith("L"):
        return "L"
    if text.startswith("R"):
        return "R"
    if text.startswith("S"):
        return "S"
    return None


def resolve_handedness(starter_hand: Any, batter_hand: Any) -> dict[str, Any]:
    """Resolve the exact split codes used for the selected hitter/starter pairing.

    MLB hitting split `vl`/`vr` is selected from the starter's throwing hand.
    Pitcher split `vl`/`vr` is selected from the hitter's effective batting side.
    A switch hitter is treated as batting opposite the starter's throwing hand.
    """
    starter = _hand(starter_hand)
    batter = _hand(batter_hand)

    hitter_code = "vl" if starter == "L" else "vr" if starter == "R" else None
    hitter_label = "LHP" if starter == "L" else "RHP" if starter == "R" else "UNKNOWN"

    effective_batter = batter
    if batter == "S" and starter == "R":
        effective_batter = "L"
    elif batter == "S" and starter == "L":
        effective_batter = "R"

    pitcher_code = "vl" if effective_batter == "L" else "vr" if effective_batter == "R" else None
    pitcher_label = "LHB" if effective_batter == "L" else "RHB" if effective_batter == "R" else "UNKNOWN"

    return {
        "starter_hand": starter,
        "batter_hand": batter,
        "effective_batter_hand": effective_batter,
        "hitter_split_code": hitter_code,
        "hitter_split_label": hitter_label,
        "pitcher_split_code": pitcher_code,
        "pitcher_split_label": pitcher_label,
        "switch_adjusted": batter == "S" and effective_batter in {"L", "R"},
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_stat_split(player_id: int, season: int, group: str, sit_code: str) -> dict[str, Any]:
    if not player_id or not season or group not in {"hitting", "pitching"} or sit_code not in {"vl", "vr"}:
        return {"status": "PENDING", "stat": {}, "source": "MLB Stats API statSplits"}
    try:
        data = ui._json(
            f"{ui.MLB_API}/people/{int(player_id)}/stats",
            {
                "stats": "statSplits",
                "group": group,
                "season": int(season),
                "sitCodes": sit_code,
                "gameType": "R",
            },
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
        if not splits:
            return {"status": "VERIFIED_NO_SPLIT", "stat": {}, "source": "MLB Stats API statSplits"}
        return {
            "status": "VERIFIED",
            "stat": splits[0].get("stat") or {},
            "source": "MLB Stats API statSplits",
        }
    except Exception as exc:
        return {
            "status": "PENDING",
            "stat": {},
            "source": "MLB Stats API statSplits",
            "error": f"{type(exc).__name__}: {str(exc)[:120]}",
        }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_bvp(player_id: int, pitcher_id: int, season: int) -> dict[str, Any]:
    """Fetch current-season BvP. No history is a valid verified observation."""
    if not player_id or not pitcher_id or not season:
        return {"status": "PENDING", "stat": {}, "source": "MLB Stats API vsPlayer"}
    try:
        data = ui._json(
            f"{ui.MLB_API}/people/{int(player_id)}/stats",
            {
                "stats": "vsPlayer",
                "group": "hitting",
                "season": int(season),
                "opposingPlayerId": int(pitcher_id),
                "gameType": "R",
            },
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
        if not splits:
            return {"status": "VERIFIED_NO_HISTORY", "stat": {}, "source": "MLB Stats API vsPlayer"}
        return {
            "status": "VERIFIED",
            "stat": splits[0].get("stat") or {},
            "source": "MLB Stats API vsPlayer",
        }
    except Exception as exc:
        return {
            "status": "PENDING",
            "stat": {},
            "source": "MLB Stats API vsPlayer",
            "error": f"{type(exc).__name__}: {str(exc)[:120]}",
        }


def _hitter_split_payload(response: dict[str, Any] | None) -> dict[str, Any]:
    response = response or {}
    stat = response.get("stat") or {}
    ab = _int(stat.get("atBats"))
    pa = _int(stat.get("plateAppearances"))
    hits = _int(stat.get("hits"))
    strikeouts = _int(stat.get("strikeOuts"))
    walks = _int(stat.get("baseOnBalls"))
    avg = _rate(stat.get("avg"))
    if avg is None and ab > 0:
        avg = hits / ab
    ops = _float(stat.get("ops"))
    k_pct = strikeouts / pa if pa > 0 else None
    bb_pct = walks / pa if pa > 0 else None
    hit_per_pa = hits / pa if pa > 0 else None
    return {
        "status": response.get("status") or "PENDING",
        "source": response.get("source") or "UNAVAILABLE",
        "ab": ab,
        "pa": pa,
        "hits": hits,
        "avg": avg,
        "ops": ops,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "hit_per_pa": hit_per_pa,
    }


def _pitcher_split_payload(response: dict[str, Any] | None) -> dict[str, Any]:
    response = response or {}
    stat = response.get("stat") or {}
    bf = _int(stat.get("battersFaced"))
    hits = _int(stat.get("hits"))
    strikeouts = _int(stat.get("strikeOuts"))
    walks = _int(stat.get("baseOnBalls"))
    avg = _rate(stat.get("avg"))
    ops = _float(stat.get("ops"))
    k_pct = strikeouts / bf if bf > 0 else None
    bb_pct = walks / bf if bf > 0 else None
    hit_per_bf = hits / bf if bf > 0 else None
    return {
        "status": response.get("status") or "PENDING",
        "source": response.get("source") or "UNAVAILABLE",
        "bf": bf,
        "hits": hits,
        "avg": avg,
        "ops": ops,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "hit_per_bf": hit_per_bf,
    }


def _bvp_payload(response: dict[str, Any] | None) -> dict[str, Any]:
    response = response or {}
    stat = response.get("stat") or {}
    ab = _int(stat.get("atBats"))
    pa = _int(stat.get("plateAppearances"))
    hits = _int(stat.get("hits"))
    home_runs = _int(stat.get("homeRuns"))
    strikeouts = _int(stat.get("strikeOuts"))
    walks = _int(stat.get("baseOnBalls"))
    avg = _rate(stat.get("avg"))
    if avg is None and ab > 0:
        avg = hits / ab
    ops = _float(stat.get("ops"))
    return {
        "status": response.get("status") or "PENDING",
        "source": response.get("source") or "UNAVAILABLE",
        "ab": ab,
        "pa": pa,
        "hits": hits,
        "home_runs": home_runs,
        "strikeouts": strikeouts,
        "walks": walks,
        "avg": avg,
        "ops": ops,
    }


def bvp_reliability(at_bats: int, prior_ab: float = BVP_PRIOR_AB) -> float:
    ab = max(0.0, float(at_bats or 0))
    if ab <= 0:
        return 0.0
    reliability = ab / (ab + max(1.0, float(prior_ab)))
    return min(BVP_MAX_RELIABILITY, reliability)


def shrink_bvp_avg(raw_avg: float | None, at_bats: int, baseline_avg: float | None) -> dict[str, Any]:
    """Empirical-Bayes style shrinkage so tiny BvP samples cannot dominate."""
    raw = _rate(raw_avg)
    baseline = _rate(baseline_avg)
    reliability = bvp_reliability(at_bats)
    if raw is None or baseline is None or at_bats <= 0:
        return {
            "raw_avg": raw,
            "baseline_avg": baseline,
            "shrunk_avg": baseline,
            "reliability": 0.0,
        }
    shrunk = baseline * (1.0 - reliability) + raw * reliability
    return {
        "raw_avg": raw,
        "baseline_avg": baseline,
        "shrunk_avg": _clamp(shrunk, 0.0, 1.0),
        "reliability": reliability,
    }


def _baseline_avg(neutral_hit_skill: float | None, season_avg: Any, hitter_split_avg: float | None, pitcher_split_avg: float | None) -> float | None:
    candidates: list[tuple[float, float]] = []
    neutral = _rate(neutral_hit_skill)
    season = _rate(season_avg)
    if neutral is not None:
        candidates.append((neutral, 0.65))
    elif season is not None:
        candidates.append((season, 0.65))
    if hitter_split_avg is not None:
        candidates.append((hitter_split_avg, 0.20))
    if pitcher_split_avg is not None:
        candidates.append((pitcher_split_avg, 0.15))
    total = sum(weight for _, weight in candidates)
    if total <= 0:
        return None
    return sum(value * weight for value, weight in candidates) / total


def _edge_label(score: int) -> str:
    if score >= 64:
        return "STRONG HITTER EDGE"
    if score >= 56:
        return "HITTER EDGE"
    if score >= 45:
        return "NEUTRAL"
    if score >= 36:
        return "PITCHER EDGE"
    return "STRONG PITCHER EDGE"


def _context_index(
    neutral_avg: float | None,
    hitter_split_avg: float | None,
    hitter_ab: int,
    pitcher_split_avg: float | None,
    pitcher_bf: int,
    shrunk_bvp_avg: float | None,
    bvp_rel: float,
) -> dict[str, Any]:
    baseline = _rate(neutral_avg)
    if baseline is None:
        return {"score": None, "label": "PENDING", "coverage": 0.0, "components": {}}

    hitter_rel = _clamp(float(hitter_ab or 0) / HITTER_SPLIT_FULL_AB, 0.0, 1.0)
    pitcher_rel = _clamp(float(pitcher_bf or 0) / PITCHER_SPLIT_FULL_BF, 0.0, 1.0)
    bvp_rel = _clamp(float(bvp_rel or 0.0), 0.0, BVP_MAX_RELIABILITY)

    hitter_signal = 0.0
    if hitter_split_avg is not None:
        hitter_signal = _clamp((float(hitter_split_avg) - baseline) / 0.050, -1.0, 1.0)

    pitcher_signal = 0.0
    if pitcher_split_avg is not None:
        # Higher AVG allowed by the pitcher is favorable to the hitter.
        pitcher_signal = _clamp((float(pitcher_split_avg) - baseline) / 0.050, -1.0, 1.0)

    bvp_signal = 0.0
    if shrunk_bvp_avg is not None:
        bvp_signal = _clamp((float(shrunk_bvp_avg) - baseline) / 0.060, -1.0, 1.0)

    hitter_weight = 0.45 * hitter_rel
    pitcher_weight = 0.40 * pitcher_rel
    bvp_weight = 0.15 * bvp_rel
    weighted_signal = (
        hitter_signal * hitter_weight
        + pitcher_signal * pitcher_weight
        + bvp_signal * bvp_weight
    )
    coverage = hitter_weight + pitcher_weight + bvp_weight
    score = int(round(_clamp(50.0 + 24.0 * weighted_signal, 25.0, 75.0)))
    return {
        "score": score,
        "label": _edge_label(score),
        "coverage": _clamp(coverage, 0.0, 1.0),
        "components": {
            "hitter_split_signal": hitter_signal,
            "hitter_split_reliability": hitter_rel,
            "hitter_effective_weight": hitter_weight,
            "pitcher_split_signal": pitcher_signal,
            "pitcher_split_reliability": pitcher_rel,
            "pitcher_effective_weight": pitcher_weight,
            "bvp_signal": bvp_signal,
            "bvp_reliability": bvp_rel,
            "bvp_effective_weight": bvp_weight,
        },
    }


def _quality_score(data: dict[str, Any]) -> tuple[int, dict[str, tuple[int, int]]]:
    hand = 0
    hand += 8 if data.get("starter_hand") in {"L", "R"} else 0
    hand += 6 if data.get("batter_hand") in {"L", "R", "S"} else 0
    hand += 6 if data.get("effective_batter_hand") in {"L", "R"} else 0

    hitter = 0
    hitter += 10 if data.get("hitter_split_status") in {"VERIFIED", "VERIFIED_NO_SPLIT"} else 0
    hitter += 10 if (data.get("hitter_split_ab") or 0) > 0 else 0
    hitter += 10 if data.get("hitter_split_avg") is not None else 0

    pitcher = 0
    pitcher += 10 if data.get("pitcher_split_status") in {"VERIFIED", "VERIFIED_NO_SPLIT"} else 0
    pitcher += 10 if (data.get("pitcher_split_bf") or 0) > 0 else 0
    pitcher += 10 if data.get("pitcher_split_avg") is not None else 0

    bvp = 0
    if data.get("bvp_status") in {"VERIFIED", "VERIFIED_NO_HISTORY"}:
        bvp += 8
    if (data.get("bvp_ab") or 0) > 0:
        bvp += 2

    bridge = 0
    bridge += 5 if data.get("neutral_hit_skill") is not None else 0
    bridge += 5 if data.get("bvp_baseline_avg") is not None else 0

    components = {
        "Handedness bridge": (hand, 20),
        "Hitter platoon split": (hitter, 30),
        "Pitcher batter-side split": (pitcher, 30),
        "BvP evidence": (bvp, 10),
        "Prior-step baseline": (bridge, 10),
    }
    return sum(earned for earned, _ in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE MATCHUP DATA"
    if score >= 75:
        return "STRONG MATCHUP DATA"
    if score >= 60:
        return "USABLE MATCHUP DATA"
    if score >= 40:
        return "PARTIAL MATCHUP DATA"
    return "LOW MATCHUP DATA"


def build_platoon_bvp_profile(
    foundation: dict[str, Any],
    hitter_split_response: dict[str, Any] | None,
    pitcher_split_response: dict[str, Any] | None,
    bvp_response: dict[str, Any] | None,
    neutral_hit_skill: float | None,
) -> dict[str, Any]:
    """Build Step 4 descriptive matchup evidence without touching probabilities."""
    hand_info = resolve_handedness(foundation.get("starter_hand"), foundation.get("batter_hand"))
    hitter = _hitter_split_payload(hitter_split_response)
    pitcher = _pitcher_split_payload(pitcher_split_response)
    bvp = _bvp_payload(bvp_response)

    season_avg = foundation.get("season_avg")
    baseline = _baseline_avg(
        neutral_hit_skill,
        season_avg,
        hitter.get("avg"),
        pitcher.get("avg"),
    )
    shrink = shrink_bvp_avg(bvp.get("avg"), bvp.get("ab") or 0, baseline)
    index = _context_index(
        neutral_avg=baseline,
        hitter_split_avg=hitter.get("avg"),
        hitter_ab=hitter.get("ab") or 0,
        pitcher_split_avg=pitcher.get("avg"),
        pitcher_bf=pitcher.get("bf") or 0,
        shrunk_bvp_avg=shrink.get("shrunk_avg"),
        bvp_rel=shrink.get("reliability") or 0.0,
    )

    data = {
        **foundation,
        **hand_info,
        "neutral_hit_skill": _rate(neutral_hit_skill),
        "hitter_split_status": hitter.get("status"),
        "hitter_split_source": hitter.get("source"),
        "hitter_split_ab": hitter.get("ab"),
        "hitter_split_pa": hitter.get("pa"),
        "hitter_split_hits": hitter.get("hits"),
        "hitter_split_avg": hitter.get("avg"),
        "hitter_split_ops": hitter.get("ops"),
        "hitter_split_k_pct": hitter.get("k_pct"),
        "hitter_split_bb_pct": hitter.get("bb_pct"),
        "hitter_split_hit_per_pa": hitter.get("hit_per_pa"),
        "pitcher_split_status": pitcher.get("status"),
        "pitcher_split_source": pitcher.get("source"),
        "pitcher_split_bf": pitcher.get("bf"),
        "pitcher_split_hits": pitcher.get("hits"),
        "pitcher_split_avg": pitcher.get("avg"),
        "pitcher_split_ops": pitcher.get("ops"),
        "pitcher_split_k_pct": pitcher.get("k_pct"),
        "pitcher_split_bb_pct": pitcher.get("bb_pct"),
        "pitcher_split_hit_per_bf": pitcher.get("hit_per_bf"),
        "bvp_status": bvp.get("status"),
        "bvp_source": bvp.get("source"),
        "bvp_ab": bvp.get("ab"),
        "bvp_pa": bvp.get("pa"),
        "bvp_hits": bvp.get("hits"),
        "bvp_home_runs": bvp.get("home_runs"),
        "bvp_strikeouts": bvp.get("strikeouts"),
        "bvp_walks": bvp.get("walks"),
        "bvp_avg": bvp.get("avg"),
        "bvp_ops": bvp.get("ops"),
        "bvp_baseline_avg": shrink.get("baseline_avg"),
        "bvp_shrunk_avg": shrink.get("shrunk_avg"),
        "bvp_reliability": shrink.get("reliability"),
        "platoon_context_score": index.get("score"),
        "platoon_context_label": index.get("label"),
        "platoon_context_coverage": index.get("coverage"),
        "platoon_context_components": index.get("components") or {},
    }
    score, components = _quality_score(data)
    data["matchup_data_score"] = int(score)
    data["matchup_data_label"] = quality_label(int(score))
    data["matchup_data_components"] = components
    return data


__all__ = [
    "BVP_MAX_RELIABILITY",
    "BVP_PRIOR_AB",
    "build_platoon_bvp_profile",
    "bvp_reliability",
    "fetch_bvp",
    "fetch_stat_split",
    "quality_label",
    "resolve_handedness",
    "shrink_bvp_avg",
]
