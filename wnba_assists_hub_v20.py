"""WNBA Assists V20 — Step 20 risk-adjusted qualification + Top 5.

Preserves Assists Steps 1–19, including the V19 same-day ET tip parser hotfix,
and adds only final qualification / publishing logic.

Step 20 rules:
- current Step 19 must PASS on this render;
- projection, distribution, Monte Carlo probabilities, no-vig probabilities and
  exact posted-price EV are frozen inputs and are never changed here;
- every Step-19 row must reconcile to the exact current Step-16 player risk
  profile (minutes/status/projection confidence/distribution confidence);
- Over and Under are evaluated independently, but only candidates clearing
  positive EV, minimum no-vig edge, minimum model probability, confidence,
  freshness, convergence and risk-adjusted-edge gates may qualify;
- questionable/day-to-day/reported or otherwise status-risk players are held;
- exact player/side/line duplicates collapse to the best current price; only one
  final card per player is allowed;
- diversity protection allows at most three published cards from one game and
  at most three from one team;
- publish up to five only; NEVER force five;
- save a standardized production-ready payload for a future Daily Picks
  connector without importing or mutating Daily Picks itself;
- no new simulations, projection changes, market requests or probability math.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v19_tip_hotfix as v19hotfix

# Importing the hotfix patches this base module's final pregame parser in-place.
v19 = v19hotfix.v19

MODEL_VERSION = "WNBA ASSISTS V20 • STEP 20 RISK-ADJUSTED QUALIFICATION + TOP 5"
_ET = ZoneInfo("America/New_York")
STANDARD_SIMS = 5_000_000
MAX_QUOTE_AGE_SECONDS = 15 * 60
MIN_EV_PER_100 = 4.00
MIN_EDGE = 0.030
MIN_RISK_ADJ_EDGE = 0.020
MIN_MODEL_FAIR_PROB = 0.540
MIN_CONFIDENCE_SCORE = 67.0
MAX_PUBLISHED = 5
MAX_PER_GAME = 3
MAX_PER_TEAM = 3
RISK_STATUSES = {"QUESTIONABLE", "DAY-TO-DAY", "REPORTED", "DOUBTFUL", "OUT", "INACTIVE"}

_TEAM_LOGO_SLUG = {
    "ATL": "atl", "CHI": "chi", "CON": "con", "DAL": "dal", "IND": "ind",
    "LVA": "lv", "LAS": "la", "MIN": "min", "NYL": "ny", "PHX": "phx",
    "SEA": "sea", "WAS": "wsh", "GSV": "gs", "POR": "por", "TOR": "tor",
}


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _norm_name(value: Any) -> str:
    return v19.v18._norm_name(value)


def _team_key(value: Any) -> str:
    return v19.v18._team_key(value)


def _fmt_odds(value: Any) -> str:
    x = _num(value)
    return "—" if not np.isfinite(x) else f"{int(round(x)):+d}"


def _confidence_label(score: float) -> str:
    if score >= 82.0:
        return "HIGH"
    if score >= 67.0:
        return "MEDIUM"
    return "LOW"


def _source_timestamp(row: pd.Series) -> str:
    stamps = []
    for col in ("OVER_UPDATED", "UNDER_UPDATED"):
        raw = str(row.get(col) or "").strip()
        if not raw:
            continue
        try:
            stamps.append(pd.to_datetime(raw, utc=True, errors="raise"))
        except Exception:
            continue
    if not stamps:
        return ""
    # The older side controls freshness for an O/U pair.
    return min(stamps).isoformat()


def _profile_maps(day_str: str) -> tuple[dict[tuple[str, str], pd.Series], set[tuple[str, str]], pd.DataFrame]:
    dist = st.session_state.get(f"wnba_assists_v16_distribution::{day_str}")
    if not isinstance(dist, pd.DataFrame) or dist.empty:
        return {}, set(), pd.DataFrame()

    buckets: dict[tuple[str, str], list[pd.Series]] = {}
    for _, row in dist.iterrows():
        if str(row.get("DISTRIBUTION_STATE") or "").upper() != "PASS":
            continue
        team = row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME") or row.get("TEAM")
        key = (_norm_name(row.get("PLAYER_NAME")), _team_key(team))
        if key[0] and key[1]:
            buckets.setdefault(key, []).append(row)
    exact = {k: rows[0] for k, rows in buckets.items() if len(rows) == 1}
    ambiguous = {k for k, rows in buckets.items() if len(rows) != 1}
    return exact, ambiguous, dist


def _risk_buffer(row: pd.Series, profile: pd.Series, side: str, age: float) -> tuple[float, dict[str, float]]:
    mc_se = _num(row.get("MC_OVER_SE" if side == "OVER" else "MC_UNDER_SE"), 0.0)
    proj_conf = _num(profile.get("PROJECTION_CONFIDENCE_SCORE"), 0.0)
    dist_conf = _num(profile.get("DISTRIBUTION_CONFIDENCE_SCORE"), 0.0)
    minute_conf = str(profile.get("MINUTE_CONFIDENCE") or "").upper()
    dispersion = _num(profile.get("DISPERSION_RATIO"), 1.0)
    proj_min = max(0.0, _num(profile.get("PROJ_MIN"), 0.0))
    min_sd = max(0.0, _num(profile.get("MIN_SD10"), 0.0))
    minute_cv = min_sd / max(proj_min, 8.0) if proj_min > 0 else 1.0

    pieces = {
        "mc": min(0.010, max(0.0, 2.0 * mc_se)),
        "projection": 0.0 if proj_conf >= 82 else (0.006 if proj_conf >= 67 else 0.020),
        "distribution": 0.0 if dist_conf >= 82 else (0.006 if dist_conf >= 67 else 0.020),
        "minutes": 0.0 if minute_conf == "HIGH" else (0.004 if minute_conf == "MEDIUM" else 0.012),
        "dispersion": min(0.010, max(0.0, dispersion - 1.35) * 0.010),
        "minute_vol": 0.005 if minute_cv >= 0.25 else 0.0,
        "freshness": 0.004 if age > 600 else 0.0,
    }
    return min(0.060, float(sum(pieces.values()))), pieces


def _candidate_rows(step19_rows: pd.DataFrame, step19_ready: bool, day_str: str):
    if not step19_ready:
        return pd.DataFrame(), {
            "layer_ready": False,
            "state": "LOCKED",
            "reason": "current Step 19 has not passed",
            "rows_received": 0 if step19_rows is None else len(step19_rows),
        }
    if step19_rows is None or step19_rows.empty:
        return pd.DataFrame(), {
            "layer_ready": False,
            "state": "CHECK",
            "reason": "Step 19 passed but supplied no current rows",
            "rows_received": 0,
        }

    profiles, ambiguous, _ = _profile_maps(day_str)
    if not profiles:
        return pd.DataFrame(), {
            "layer_ready": False,
            "state": "CHECK",
            "reason": "current Step-16 risk profile is missing",
            "rows_received": len(step19_rows),
        }

    records: list[dict[str, Any]] = []
    missing_profile = 0
    stale = 0
    started = 0
    risk_status_holds = 0

    for _, row in step19_rows.iterrows():
        pkey = (_norm_name(row.get("PLAYER_NAME")), _team_key(row.get("TEAM")))
        if pkey in ambiguous or pkey not in profiles:
            missing_profile += 1
            continue
        profile = profiles[pkey]

        age = v19.v18._actual_quote_age_seconds(row)
        if not np.isfinite(age):
            age = _num(row.get("QUOTE_AGE_SECONDS_STEP19"))
        if not np.isfinite(age) or age > MAX_QUOTE_AGE_SECONDS:
            stale += 1
            continue
        if not v19._tip_is_upcoming(row.get("TIP_ET")):
            started += 1
            continue

        availability = str(profile.get("AVAILABILITY") or "UNKNOWN").upper().strip()
        status_risk = bool(
            availability in RISK_STATUSES
            or str(profile.get("STATUS_RISK") or "").upper().strip() == "YES"
        )
        if status_risk:
            risk_status_holds += 1

        proj_conf = _num(profile.get("PROJECTION_CONFIDENCE_SCORE"), 0.0)
        dist_conf = _num(profile.get("DISTRIBUTION_CONFIDENCE_SCORE"), 0.0)
        conservative_conf = min(proj_conf, dist_conf)
        conf_label = _confidence_label(conservative_conf)
        proj_min = _num(profile.get("PROJ_MIN"), 0.0)
        player_id = _safe_int(profile.get("PLAYER_ID"))
        expected = _num(row.get("EXPECTED_ASSISTS"))
        simulations = _safe_int(row.get("SIMULATIONS"))
        converged = bool(row.get("CONVERGED"))

        for side in ("OVER", "UNDER"):
            over = side == "OVER"
            posted = _num(row.get("OVER_ODDS" if over else "UNDER_ODDS"))
            model_prob = _num(row.get("MODEL_OVER_PROB" if over else "MODEL_UNDER_PROB"))
            model_fair = _num(row.get("MODEL_FAIR_OVER_PROB" if over else "MODEL_FAIR_UNDER_PROB"))
            fair_odds = _num(row.get("MODEL_FAIR_OVER_ODDS" if over else "MODEL_FAIR_UNDER_ODDS"))
            novig = _num(row.get("NOVIG_OVER_PROB" if over else "NOVIG_UNDER_PROB"))
            edge = _num(row.get("OVER_EDGE_VS_NOVIG" if over else "UNDER_EDGE_VS_NOVIG"))
            ev = _num(row.get("OVER_EV_PER_100" if over else "UNDER_EV_PER_100"))
            mc_se = _num(row.get("MC_OVER_SE" if over else "MC_UNDER_SE"))
            buffer, pieces = _risk_buffer(row, profile, side, float(age))
            risk_edge = edge - buffer if np.isfinite(edge) else np.nan

            reasons: list[str] = []
            if not converged or simulations < STANDARD_SIMS:
                reasons.append("5M convergence")
            if status_risk:
                reasons.append(f"status risk {availability or 'UNKNOWN'}")
            if not np.isfinite(proj_min) or proj_min < 10.0:
                reasons.append("projected minutes <10")
            if conservative_conf < MIN_CONFIDENCE_SCORE:
                reasons.append("confidence <67")
            if not np.isfinite(model_fair) or model_fair < MIN_MODEL_FAIR_PROB:
                reasons.append("model probability <54%")
            if not np.isfinite(edge) or edge < MIN_EDGE:
                reasons.append("no-vig edge <3.0pp")
            if not np.isfinite(ev) or ev < MIN_EV_PER_100:
                reasons.append("EV <+$4/$100")
            if not np.isfinite(risk_edge) or risk_edge < MIN_RISK_ADJ_EDGE:
                reasons.append("risk-adjusted edge <2.0pp")
            if not np.isfinite(posted) or abs(posted) < 100:
                reasons.append("invalid posted price")
            if not np.isfinite(mc_se):
                reasons.append("missing MC probability SE")

            qualified = len(reasons) == 0
            freshness = max(0.0, 1.0 - float(age) / MAX_QUOTE_AGE_SECONDS)
            score = (
                (100.0 * max(risk_edge, -0.10) if np.isfinite(risk_edge) else -10.0)
                + (0.22 * ev if np.isfinite(ev) else -10.0)
                + (8.0 * (model_fair - 0.50) if np.isfinite(model_fair) else -4.0)
                + 0.025 * (conservative_conf - 67.0)
                + 0.75 * freshness
            )

            records.append({
                "PLAYER_ID": player_id,
                "PLAYER_NAME": str(row.get("PLAYER_NAME") or ""),
                "TEAM": str(row.get("TEAM") or ""),
                "OPPONENT": str(row.get("OPPONENT") or ""),
                "GAME_ID": str(row.get("GAME_ID") or ""),
                "EVENT_ID": str(row.get("EVENT_ID") or ""),
                "BOOK": str(row.get("BOOK") or ""),
                "SIDE": side,
                "LINE": _num(row.get("LINE")),
                "POSTED_ODDS": int(round(posted)) if np.isfinite(posted) else np.nan,
                "EXPECTED_ASSISTS": expected,
                "MODEL_WIN_PROB": model_prob,
                "MODEL_FAIR_PROB": model_fair,
                "MODEL_FAIR_ODDS": fair_odds,
                "NOVIG_PROB": novig,
                "EDGE_VS_NOVIG": edge,
                "EV_PER_100": ev,
                "MODEL_PUSH_PROB": _num(row.get("MODEL_PUSH_PROB"), 0.0),
                "MC_PROB_SE": mc_se,
                "MC_SD": _num(row.get("MC_SD")),
                "SIMULATIONS": simulations,
                "CONVERGED": converged,
                "PROJ_MIN": proj_min,
                "AVAILABILITY": availability,
                "PROJECTION_CONFIDENCE_SCORE": proj_conf,
                "DISTRIBUTION_CONFIDENCE_SCORE": dist_conf,
                "CONFIDENCE_SCORE": conservative_conf,
                "CONFIDENCE": conf_label,
                "DISPERSION_RATIO": _num(profile.get("DISPERSION_RATIO")),
                "MINUTE_CONFIDENCE": str(profile.get("MINUTE_CONFIDENCE") or ""),
                "RISK_BUFFER": buffer,
                "RISK_ADJ_EDGE": risk_edge,
                "RANK_SCORE": score,
                "QUALIFIED": qualified,
                "QUALIFICATION_STATE": "QUALIFIED" if qualified else "HOLD",
                "QUALIFICATION_REASONS": "PASS" if qualified else "; ".join(reasons),
                "QUOTE_AGE_SECONDS": float(age),
                "SOURCE_TIMESTAMP": _source_timestamp(row),
                "TIP_ET": str(row.get("TIP_ET") or ""),
                "RISK_MC": pieces.get("mc", 0.0),
                "RISK_PROJECTION": pieces.get("projection", 0.0),
                "RISK_DISTRIBUTION": pieces.get("distribution", 0.0),
                "RISK_MINUTES": pieces.get("minutes", 0.0),
                "RISK_DISPERSION": pieces.get("dispersion", 0.0),
                "RISK_MINUTE_VOL": pieces.get("minute_vol", 0.0),
                "RISK_FRESHNESS": pieces.get("freshness", 0.0),
                "MODEL_VERSION_STEP20": MODEL_VERSION,
            })

    out = pd.DataFrame(records)
    all_profiles_mapped = missing_profile == 0
    layer_ready = bool(not out.empty and all_profiles_mapped)
    return out, {
        "layer_ready": layer_ready,
        "state": "VERIFIED" if layer_ready else "CHECK",
        "reason": "" if layer_ready else (
            "one or more current Step-19 rows could not reconcile to the exact Step-16 risk profile"
            if missing_profile else "no current candidate side survived Step-20 prechecks"
        ),
        "rows_received": len(step19_rows),
        "candidate_sides": len(out),
        "missing_profile": missing_profile,
        "stale_blocked": stale,
        "started_blocked": started,
        "status_risk_rows": risk_status_holds,
        "new_simulations": 0,
        "projection_changes": 0,
        "market_requests": 0,
    }


def _select_top5(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if candidates is None or candidates.empty:
        return pd.DataFrame(), pd.DataFrame(), {"qualified": 0, "published": 0, "diversity_holds": 0}

    q = candidates.loc[candidates["QUALIFIED"].astype(bool)].copy()
    if q.empty:
        return q, pd.DataFrame(), {"qualified": 0, "published": 0, "diversity_holds": 0}

    # Best current sportsbook quote for the exact player/side/line family.
    q = q.sort_values(
        ["RANK_SCORE", "EV_PER_100", "EDGE_VS_NOVIG", "QUOTE_AGE_SECONDS"],
        ascending=[False, False, False, True],
    )
    q = q.drop_duplicates(["PLAYER_NAME", "TEAM", "SIDE", "LINE"], keep="first")

    # One final Assists card per player, even when alternate lines also qualify.
    q = q.sort_values(
        ["RANK_SCORE", "EV_PER_100", "EDGE_VS_NOVIG", "QUOTE_AGE_SECONDS"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    q = q.drop_duplicates(["PLAYER_NAME", "TEAM"], keep="first").reset_index(drop=True)

    selected: list[pd.Series] = []
    game_counts: dict[str, int] = {}
    team_counts: dict[str, int] = {}
    diversity_holds = 0
    for _, row in q.iterrows():
        if len(selected) >= MAX_PUBLISHED:
            break
        game_key = str(row.get("GAME_ID") or "") or "|".join(sorted([str(row.get("TEAM")), str(row.get("OPPONENT"))]))
        team_key = str(row.get("TEAM") or "")
        if game_counts.get(game_key, 0) >= MAX_PER_GAME or team_counts.get(team_key, 0) >= MAX_PER_TEAM:
            diversity_holds += 1
            continue
        selected.append(row)
        game_counts[game_key] = game_counts.get(game_key, 0) + 1
        team_counts[team_key] = team_counts.get(team_key, 0) + 1

    top = pd.DataFrame(selected)
    if not top.empty:
        top = top.reset_index(drop=True)
        top["DAILY_RANK"] = np.arange(1, len(top) + 1)
        top["SELECTION_STATE"] = "PRODUCTION READY"
    return q, top, {
        "qualified": len(q),
        "published": len(top),
        "diversity_holds": diversity_holds,
        "qualified_players": int(q["PLAYER_NAME"].nunique()) if not q.empty else 0,
    }


def _standardize(top: pd.DataFrame, day_str: str) -> pd.DataFrame:
    cols = [
        "Slate day", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Posted odds", "Projection", "Model probability", "Fair odds", "No-vig probability",
        "Edge", "EV / $100", "Confidence", "Simulation count", "Converged",
        "Qualification state", "Freshness", "Source timestamp", "Source",
    ]
    if top is None or top.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for _, r in top.iterrows():
        age = _num(r.get("QUOTE_AGE_SECONDS"), 0.0)
        freshness = f"FRESH {int(age)}s" if age < 120 else f"FRESH {int(age // 60)}m"
        rows.append({
            "Slate day": day_str,
            "Market": "Assists",
            "Player": str(r.get("PLAYER_NAME") or ""),
            "Team": str(r.get("TEAM") or ""),
            "Opponent": str(r.get("OPPONENT") or ""),
            "Side": str(r.get("SIDE") or ""),
            "Line": _num(r.get("LINE")),
            "Book": str(r.get("BOOK") or ""),
            "Posted odds": _safe_int(r.get("POSTED_ODDS")),
            "Projection": _num(r.get("EXPECTED_ASSISTS")),
            "Model probability": _num(r.get("MODEL_WIN_PROB")),
            "Fair odds": _num(r.get("MODEL_FAIR_ODDS")),
            "No-vig probability": _num(r.get("NOVIG_PROB")),
            "Edge": _num(r.get("EDGE_VS_NOVIG")),
            "EV / $100": _num(r.get("EV_PER_100")),
            "Confidence": str(r.get("CONFIDENCE") or ""),
            "Simulation count": _safe_int(r.get("SIMULATIONS")),
            "Converged": bool(r.get("CONVERGED")),
            "Qualification state": "PRODUCTION READY",
            "Freshness": freshness,
            "Source timestamp": str(r.get("SOURCE_TIMESTAMP") or ""),
            "Source": "WNBA Assists V20",
        })
    return pd.DataFrame(rows, columns=cols)


def _card_html(row: pd.Series) -> str:
    rank = _safe_int(row.get("DAILY_RANK"))
    player = escape(str(row.get("PLAYER_NAME") or "Player"))
    team = escape(str(row.get("TEAM") or ""))
    opp = escape(str(row.get("OPPONENT") or ""))
    side = str(row.get("SIDE") or "").upper()
    side_class = "over" if side == "OVER" else "under"
    pid = _safe_int(row.get("PLAYER_ID"))
    photo = f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png" if pid else ""
    slug = _TEAM_LOGO_SLUG.get(str(row.get("TEAM") or "").upper(), "")
    logo = f"https://a.espncdn.com/i/teamlogos/wnba/500/{slug}.png" if slug else ""
    img = f'<img class="ast20-player" src="{photo}" onerror="this.style.visibility=\'hidden\'">' if photo else '<div class="ast20-sil">◯</div>'
    logo_html = f'<img class="ast20-logo" src="{logo}">' if logo else ""
    return f"""
    <div class="ast20-card">
      <div class="ast20-rank">{'⭐ BEST ASSISTS PICK' if rank == 1 else f'🏆 ASSISTS PICK #{rank}'}</div>
      <div class="ast20-main">
        <div class="ast20-photo">{img}</div>
        <div class="ast20-who">
          <div class="ast20-playername">{player}</div>
          <div class="ast20-match">{logo_html}{team} vs {opp}</div>
          <div><span class="ast20-side {side_class}">{side} {float(row.get('LINE')):g}</span> <span class="ast20-book">{escape(str(row.get('BOOK') or ''))} {_fmt_odds(row.get('POSTED_ODDS'))}</span></div>
        </div>
        <div class="ast20-ready">✅ PRODUCTION READY</div>
      </div>
      <div class="ast20-grid">
        <div><b>{_num(row.get('EXPECTED_ASSISTS')):.2f}</b><span>Expected AST</span></div>
        <div><b>{100*_num(row.get('MODEL_WIN_PROB')):.1f}%</b><span>Model win</span></div>
        <div><b>{100*_num(row.get('EDGE_VS_NOVIG')):+.1f}%</b><span>No-vig edge</span></div>
        <div><b>${_num(row.get('EV_PER_100')):+.2f}</b><span>EV / $100</span></div>
        <div><b>{100*_num(row.get('RISK_ADJ_EDGE')):+.1f}%</b><span>Risk-adj edge</span></div>
        <div><b>{escape(str(row.get('CONFIDENCE') or ''))}</b><span>Confidence</span></div>
      </div>
    </div>
    """


def _render_step20(step19_rows: pd.DataFrame, step19_ready: bool, day_str: str):
    st.markdown("### 🏆 Step 20 — Risk-Adjusted Qualification + Top 5")
    st.caption(
        "Final Assists publishing layer. Step 20 does not move the projection, distribution, 5M probability or posted-price EV. It applies conservative status/confidence/uncertainty/freshness gates, selects the best exact quote, enforces diversity, and publishes up to five — never forced."
    )

    candidates, diag = _candidate_rows(step19_rows, step19_ready, day_str)
    qualified, top, sdiag = _select_top5(candidates)
    diag.update(sdiag)
    ready = bool(diag.get("layer_ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Step-19 rows", int(diag.get("rows_received") or 0))
    c2.metric("Candidate sides", int(diag.get("candidate_sides") or 0))
    c3.metric("Qualified players", int(diag.get("qualified_players") or 0))
    c4.metric("Published", f"{int(diag.get('published') or 0)}/5")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Status-risk holds", int(diag.get("status_risk_rows") or 0))
    d2.metric("Diversity holds", int(diag.get("diversity_holds") or 0))
    d3.metric("New simulations", "0")
    d4.metric("Projection changes", "0")

    if ready:
        if top is not None and not top.empty:
            st.success(f"✅ STEP 20 PASSED • {len(top)} production-ready Assists pick(s) published. The card is risk-adjusted and no pick was forced.")
        else:
            st.success("✅ STEP 20 PASSED • every current Step-19 market was evaluated, but none cleared all final production thresholds. Published 0/5 — no forced picks.")
    else:
        st.warning(f"⚠️ STEP 20 CHECK • {diag.get('reason') or 'final qualification incomplete'}. No production Assists card is published.")

    if int(diag.get("missing_profile") or 0) or int(diag.get("stale_blocked") or 0) or int(diag.get("started_blocked") or 0):
        st.caption(
            f"Precheck holds • profile {int(diag.get('missing_profile') or 0)} • stale {int(diag.get('stale_blocked') or 0)} • started {int(diag.get('started_blocked') or 0)}"
        )

    if top is not None and not top.empty:
        st.markdown("""
        <style>
        .ast20-card{margin:13px 0;padding:18px;border:1px solid rgba(34,211,238,.32);border-radius:20px;background:linear-gradient(135deg,rgba(7,24,42,.98),rgba(8,34,50,.98));box-shadow:0 12px 28px rgba(0,0,0,.16)}
        .ast20-rank{font-size:.72rem;font-weight:950;letter-spacing:.10em;color:#67e8f9;margin-bottom:10px}.ast20-main{display:flex;align-items:center;gap:14px}.ast20-photo{width:74px;height:74px;display:flex;align-items:flex-end;justify-content:center;overflow:hidden}.ast20-player{max-width:72px;max-height:72px}.ast20-sil{font-size:48px;color:#64748b}.ast20-who{flex:1}.ast20-playername{font-size:1.25rem;font-weight:950;color:#f8fafc}.ast20-match{display:flex;align-items:center;gap:6px;margin:4px 0 8px;color:#94a3b8;font-weight:750}.ast20-logo{width:20px;height:20px;object-fit:contain}.ast20-side,.ast20-book,.ast20-ready{display:inline-block;border-radius:999px;padding:5px 9px;font-size:.72rem;font-weight:950}.ast20-side.over{background:rgba(34,197,94,.16);color:#86efac}.ast20-side.under{background:rgba(244,114,182,.16);color:#f9a8d4}.ast20-book{background:rgba(148,163,184,.12);color:#cbd5e1}.ast20-ready{background:rgba(16,185,129,.12);color:#6ee7b7;white-space:nowrap}.ast20-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:14px}.ast20-grid div{padding:9px 7px;border:1px solid rgba(148,163,184,.12);border-radius:11px;text-align:center;background:rgba(15,23,42,.36)}.ast20-grid b{display:block;color:#f8fafc;font-size:.94rem}.ast20-grid span{display:block;color:#7f91aa;font-size:.63rem;margin-top:2px}@media(max-width:760px){.ast20-grid{grid-template-columns:repeat(3,1fr)}.ast20-ready{display:none}}
        </style>
        """, unsafe_allow_html=True)
        for _, row in top.iterrows():
            st.markdown(_card_html(row), unsafe_allow_html=True)

    with st.expander("📋 Step-20 qualification audit", expanded=False):
        if candidates is None or candidates.empty:
            st.write("No candidate sides available.")
        else:
            audit = candidates.copy()
            audit["Player"] = audit["PLAYER_NAME"].astype(str)
            audit["Side"] = audit["SIDE"].astype(str)
            audit["Line"] = pd.to_numeric(audit["LINE"], errors="coerce")
            audit["Book"] = audit["BOOK"].astype(str)
            audit["Model fair"] = (100 * pd.to_numeric(audit["MODEL_FAIR_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
            audit["Edge"] = (100 * pd.to_numeric(audit["EDGE_VS_NOVIG"], errors="coerce")).map(lambda x: f"{x:+.2f}%")
            audit["Risk edge"] = (100 * pd.to_numeric(audit["RISK_ADJ_EDGE"], errors="coerce")).map(lambda x: f"{x:+.2f}%")
            audit["EV/$100"] = pd.to_numeric(audit["EV_PER_100"], errors="coerce").map(lambda x: f"${x:+.2f}")
            audit["Confidence"] = audit["CONFIDENCE"].astype(str)
            audit["State"] = audit["QUALIFICATION_STATE"].astype(str)
            audit["Reason"] = audit["QUALIFICATION_REASONS"].astype(str)
            st.dataframe(audit[["Player","Side","Line","Book","Model fair","Edge","Risk edge","EV/$100","Confidence","State","Reason"]], hide_index=True, use_container_width=True)

    with st.expander("🧪 Step-20 production methodology", expanded=False):
        st.write(f"• Minimum exact posted-price EV: +${MIN_EV_PER_100:.2f} per $100.")
        st.write(f"• Minimum model-vs-no-vig action edge: {100*MIN_EDGE:.1f} percentage points.")
        st.write(f"• Minimum risk-adjusted edge after uncertainty buffer: {100*MIN_RISK_ADJ_EDGE:.1f} percentage points.")
        st.write(f"• Minimum model fair action probability: {100*MIN_MODEL_FAIR_PROB:.1f}%.")
        st.write("• Status-risk players are held from the production card even if raw EV is positive.")
        st.write("• Risk buffer includes MC probability SE, projection/distribution confidence, minute confidence, dispersion, minute volatility and quote age.")
        st.write("• Exact player/side/line duplicates collapse to the best current price; only one final Assists card per player.")
        st.write(f"• Diversity cap: max {MAX_PER_GAME} from one game and max {MAX_PER_TEAM} from one team.")
        st.write("• New simulations: 0. Projection changes: 0. Market requests: 0.")
        st.write("• Top 5 is a maximum, never a quota.")

    if ready:
        standard = _standardize(top, day_str)
        st.session_state[f"wnba_assists_v20_candidates::{day_str}"] = candidates.copy()
        st.session_state[f"wnba_assists_v20_qualified::{day_str}"] = qualified.copy()
        st.session_state[f"wnba_assists_v20_top5::{day_str}"] = top.copy()
        st.session_state[f"wnba_assists_v20_standard::{day_str}"] = standard.copy()
        st.session_state[f"wnba_assists_v20_diag::{day_str}"] = dict(diag)

    return ready, top, candidates, diag


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day_str = datetime.now(_ET).strftime("%Y-%m-%d")
    runtime: dict[str, Any] = {
        "step20_rendered": False,
        "step20_ready": False,
        "step20_top": pd.DataFrame(),
        "step20_diag": {},
    }

    original_button = st.button
    original_card = v19.v18.v17.v16.v15.step3._layer_card
    original_caption = st.caption
    original_markdown = st.markdown
    original_step19 = v19._render_step19

    def capture_step19(*args, **kwargs):
        result = original_step19(*args, **kwargs)
        try:
            ready19, rows19, _diag19 = result
            ready20, top20, _candidates20, diag20 = _render_step20(
                rows19 if isinstance(rows19, pd.DataFrame) else pd.DataFrame(),
                bool(ready19),
                day_str,
            )
            runtime.update({
                "step20_rendered": True,
                "step20_ready": bool(ready20),
                "step20_top": top20.copy() if isinstance(top20, pd.DataFrame) else pd.DataFrame(),
                "step20_diag": dict(diag20 or {}),
            })
        except Exception as exc:
            runtime.update({
                "step20_rendered": True,
                "step20_ready": False,
                "step20_top": pd.DataFrame(),
                "step20_diag": {"state": "CHECK", "reason": f"Step-20 render error: {type(exc).__name__}: {exc}"},
            })
            st.error(f"⛔ STEP 20 ERROR • {type(exc).__name__}: {exc}")
        return result

    def fixed_button(label, *args, **kwargs):
        text = str(label)
        if text == "🔄 RECHECK ASSISTS STEPS 2–19":
            text = "🔄 RECHECK ASSISTS STEPS 2–20"
            clicked = original_button(text, *args, **kwargs)
            if clicked:
                for key in (
                    f"wnba_assists_v20_candidates::{day_str}",
                    f"wnba_assists_v20_qualified::{day_str}",
                    f"wnba_assists_v20_top5::{day_str}",
                    f"wnba_assists_v20_standard::{day_str}",
                    f"wnba_assists_v20_diag::{day_str}",
                ):
                    st.session_state.pop(key, None)
            return clicked
        return original_button(label, *args, **kwargs)

    def fixed_card(step, label, card_state, note=""):
        if int(step) == 20:
            if runtime["step20_ready"]:
                card_state = "✅ LIVE"
                published = int(runtime.get("step20_diag", {}).get("published") or 0)
                note = f"Risk-adjusted production card • {published}/5 published • never forced"
            elif runtime["step20_rendered"]:
                card_state = "⚠️ CHECK"
                note = "Final risk-adjusted qualification incomplete"
        return original_card(step, label, card_state, note)

    def fixed_caption(body, *args, **kwargs):
        text = str(body)
        if text.startswith("⚡ WNBA Assists V19 Step 19"):
            text = text.replace("WNBA Assists V19 Step 19", "WNBA Assists V20 Step 20", 1)
            if "Step 19 PASS" in text:
                text += (
                    f" • Step 20 {'PASS' if runtime['step20_ready'] else 'CHECK'}"
                    f" • production picks {int(runtime.get('step20_diag', {}).get('published') or 0)}/5"
                    " • no forced picks"
                )
        return original_caption(text, *args, **kwargs)

    def fixed_markdown(body, *args, **kwargs):
        text = body
        if isinstance(text, str) and "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 19" in text:
            text = text.replace(
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 19",
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 20",
            )
            text = text.replace(
                "Steps 1–18 remain intact. Step 19 grades the frozen push-aware model probability against the same-book no-vig market and exact current posted price. Projection/simulation math is unchanged; ranking and qualification remain locked for Step 20.",
                "Steps 1–19 remain intact. Step 20 is the final risk-adjusted production gate: current status, confidence, Monte Carlo uncertainty, freshness, exact price, edge and EV are screened before publishing up to five. No pick is forced.",
            )
        return original_markdown(text, *args, **kwargs)

    st.button = fixed_button
    v19.v18.v17.v16.v15.step3._layer_card = fixed_card
    st.caption = fixed_caption
    st.markdown = fixed_markdown
    v19._render_step19 = capture_step19
    try:
        v19hotfix.render_wnba_assists_hub(section_header, status_info, team_logo, h)
    finally:
        st.button = original_button
        v19.v18.v17.v16.v15.step3._layer_card = original_card
        st.caption = original_caption
        st.markdown = original_markdown
        v19._render_step19 = original_step19


__all__ = ["MODEL_VERSION", "_candidate_rows", "_select_top5", "_render_step20", "render_wnba_assists_hub"]
