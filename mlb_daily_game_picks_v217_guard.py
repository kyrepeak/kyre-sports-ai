"""V2.1.7 confirmed-lineup guard + Steps 5.2/5.3/5.4/5.5/5.6/5.7/5.8/5.9 market presentation.

Extends the V2.1.7 decision layer so hitter props are not merely gated on whether
a team posted nine hitters; the selected hitter must actually appear in that
confirmed official MLB batting order. Step 5.2 adds the read-only exact-ID FanDuel
Moneyline/Run Line/Total board. Step 5.3 derives raw implied probability, hold,
and proportional two-way no-vig market probability from those exact prices only.
Step 5.4 compares the unchanged production model probability to that certified
market context for display-only edge, fair odds, and EV. Step 5.5 separates model
handicap edge from actual price edge after vig and exposes the model's zero-EV price
limit. Step 5.6 tracks only ephemeral exact-identity FanDuel observations to show
snapshot age and real line/price movement without durable persistence. Step 5.7
combines those certified facts into display-only price health, snapshot freshness,
and same-line edge-retention/zero-EV crossing context. Step 5.8 adds a SHADOW-ONLY
actionability policy. Step 5.9 adds an explicit feature-flagged price-aware Final
Card eligibility gate for certified full-game markets only. Its production default
is OFF; when explicitly enabled it filters eligibility only and never changes
model math, Pick Strength, ranking math, risk logic, persistence, wagering, or WNBA.
"""
from __future__ import annotations

import re
import unicodedata

import streamlit as st

import mlb_daily_game_picks_v217 as previous
import mlb_daily_game_picks_v212 as live
import mlb_daily_game_picks_v2123 as riskfix
import slate_lineup_v204 as lineup_data
from mlb_daily_game_picks_controlled_price_gate_v1 import install_controlled_price_gate_layer

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.7 • CONFIRMED-LINEUP GUARD + STEP 5.9 CONTROLLED PRICE GATE"

_BASE_OFFICIAL = live._official_snapshots
_BASE_V217_RISK = previous._risk_context_v217
HITTER_MARKETS = {"1+ Hit", "Home Run", "H+R+RBI"}


def _safe_int(v):
    try:
        return int(float(v))
    except Exception:
        return None


def _norm(v):
    text = unicodedata.normalize("NFKD", str(v or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


@st.cache_data(ttl=150, show_spinner=False)
def _lineup_members_bulk(game_pks):
    pks = tuple(sorted({_safe_int(x) for x in game_pks if _safe_int(x) is not None}))
    if not pks:
        return {}
    try:
        return lineup_data._fetch_lineups_bulk(pks) or {}
    except Exception:
        return {}


def _official_snapshots_v217(game_pks):
    snaps = dict(_BASE_OFFICIAL(game_pks) or {})
    lineups = _lineup_members_bulk(tuple(game_pks or ()))
    for raw_pk, lus in (lineups or {}).items():
        pk = _safe_int(raw_pk)
        if pk is None:
            continue
        snap = dict(snaps.get(pk) or {})
        for side in ("away", "home"):
            arr = list((lus or {}).get(side) or [])
            snap[f"{side}_lineup"] = arr
            snap[f"{side}_lineup_count"] = len(arr)
        snaps[pk] = snap
    return snaps


def _player_lineup_guard(c, games_df, snap):
    market = str(c.get("market") or "")
    if market not in HITTER_MARKETS:
        return None
    if not snap or not snap.get("ok"):
        return None

    row = live._game_row(games_df, c.get("game_pk"))
    if row is None:
        return None
    away_team = str(row.get("away_team") or "")
    home_team = str(row.get("home_team") or "")
    team = str(c.get("team") or "")
    side = "away" if team == away_team else "home" if team == home_team else None
    if side is None:
        return None

    lineup = list(snap.get(f"{side}_lineup") or [])
    if not lineup:
        return None

    wanted = _norm(c.get("name"))
    match = None
    for player in lineup:
        if _norm((player or {}).get("player_name")) == wanted:
            match = player
            break

    if len(lineup) >= 9 and match is None:
        return {
            "level": "critical",
            "text": f"{str(c.get('name') or 'Selected hitter')} is not in {team}'s confirmed official starting batting order. This hitter prop is automatically removed from the Final Card.",
            "lineup": (
                "⛔ Player not in confirmed lineup",
                "warn",
                f"{team} has a confirmed official batting order, but {str(c.get('name') or 'the selected hitter')} is not listed among the nine starters.",
            ),
            "spot": None,
        }

    if match is not None:
        spot = _safe_int(match.get("spot"))
        if len(lineup) >= 9:
            return {
                "level": "safe",
                "text": f"{str(c.get('name') or 'Selected hitter')} is confirmed in {team}'s official batting order" + (f" at spot #{spot}." if spot else "."),
                "lineup": (
                    f"✅ Player confirmed" + (f" • batting #{spot}" if spot else ""),
                    "safe",
                    f"{str(c.get('name') or 'Selected hitter')} is in {team}'s confirmed official starting batting order" + (f" at spot #{spot}." if spot else "."),
                ),
                "spot": spot,
            }
        return {
            "level": "warn",
            "text": f"{str(c.get('name') or 'Selected hitter')} appears in the partial official batting order" + (f" at spot #{spot}," if spot else ",") + " but the full nine-player lineup is not confirmed yet.",
            "lineup": (
                f"🟡 Player listed" + (f" • batting #{spot}" if spot else ""),
                "warn",
                f"{str(c.get('name') or 'Selected hitter')} appears in {team}'s partial official batting order, but the complete nine-player order is still pending.",
            ),
            "spot": spot,
        }
    return None


def _risk_context_v217_guard(c, games_df, snap, ts, baseline):
    out = dict(_BASE_V217_RISK(c, games_df, snap, ts, baseline) or {})
    warnings = list(out.get("warnings") or [])
    guard = _player_lineup_guard(c, games_df, snap)
    if guard:
        out["lineup"] = guard["lineup"]
        out["player_lineup_spot"] = guard.get("spot")
        if guard["level"] in {"warn", "critical"}:
            text = str(guard["text"])
            if not any(str(existing) == text for _level, existing in warnings):
                warnings.append((guard["level"], text))

    if any(level == "critical" for level, _ in warnings):
        out["badge"] = ("⛔ AVOID / REPLACE", "critical")
    elif warnings:
        out["badge"] = ("⚠️ MONITOR", "warn")
    else:
        out["badge"] = ("✅ PREGAME CHECKS OK", "safe")
    out["warnings"] = warnings
    return out


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Patch the callables V2.1.7 resolves at runtime. The wrapper filename also
    # provides a clean Streamlit module-cache break for this guard deployment.
    live._official_snapshots = _official_snapshots_v217
    previous._risk_context_v217 = _risk_context_v217_guard
    riskfix._risk_context = _risk_context_v217_guard
    live._risk_context = _risk_context_v217_guard

    # Step 5.9 runs strictly downstream of certified Step 5.8. Production default
    # is OFF. Only an explicit environment activation can allow the certified
    # full-game price gate to filter Final Card eligibility. Player props remain
    # unchanged until a certified exact prop-price feed exists. Even when active,
    # Step 5.9 does not mutate model probability, projections, Pick Strength,
    # ranking math, V2.1.7 risk logic, persistence, wagering, or WNBA.
    install_controlled_price_gate_layer(games_df)

    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
