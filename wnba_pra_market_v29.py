"""WNBA PRA V2.9 — Step 6 exact sportsbook market grading.

WNBA-only module. MLB remains frozen at V2.1.7.

Step 6 connects the independent Step-5 minutes/role projections to verified
SportsGameOdds PRA markets. Sportsbook data never feeds back into the projection.
This layer:
- matches player identity + game + PRA market;
- requires exact same-book, same-line Over/Under pairs for no-vig grading;
- estimates PRELIMINARY over/under probabilities from Step-5 projection plus
  empirical player variance/correlation;
- reports fair odds, edge, EV, freshness and data quality;
- excludes FINAL games and never fabricates missing markets.

Opponent-defense adjustments and the production 5M/10M Monte Carlo engine remain
future steps, so probabilities shown here are explicitly preliminary rather than
final production probabilities.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd
import streamlit as st

import wnba_role_v282 as role
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "PRA V2.9 STEP 6"
STALE_SECONDS = 15 * 60
AGING_SECONDS = 3 * 60


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _american_implied(odds):
    o = _num(odds, np.nan)
    if pd.isna(o) or o == 0:
        return np.nan
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def _fair_american(prob):
    p = float(np.clip(_num(prob, np.nan), 1e-6, 1 - 1e-6))
    if not np.isfinite(p):
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _fmt_odds(value):
    try:
        return f"{int(round(float(value))):+d}"
    except Exception:
        return "—"


def _profit_per_dollar(odds):
    o = _num(odds, np.nan)
    if pd.isna(o) or o == 0:
        return np.nan
    return (100.0 / abs(o)) if o < 0 else (o / 100.0)


def _no_vig(over_odds, under_odds):
    po = _american_implied(over_odds)
    pu = _american_implied(under_odds)
    if pd.isna(po) or pd.isna(pu) or po + pu <= 0:
        return np.nan, np.nan
    den = po + pu
    return po / den, pu / den


def _freshness(age):
    a = _num(age, np.nan)
    if pd.isna(a):
        return "UNKNOWN", 0.45
    if a <= AGING_SECONDS:
        return "FRESH", 1.0
    if a <= STALE_SECONDS:
        return "AGING", max(0.55, 1.0 - (a - AGING_SECONDS) / (STALE_SECONDS - AGING_SECONDS) * 0.35)
    return "STALE", 0.25


def _status_text(row):
    return str(row.get("status") or row.get("status_text") or "").upper()


def _projection_frame(day):
    schedule = role.schedule_for_date(day)
    stats = role.player_form_table()
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame(), schedule

    rows = []
    for _, game in schedule.iterrows():
        if "FINAL" in _status_text(game):
            continue
        result = role.role_projection_for_game(game, stats)
        for team_id, frame in (result.get("teams") or {}).items():
            if frame is None or frame.empty:
                continue
            opponent = game.get("home_team") if int(team_id) == int(game.get("away_team_id") or 0) else game.get("away_team")
            team_name = game.get("away_team") if int(team_id) == int(game.get("away_team_id") or 0) else game.get("home_team")
            for _, p in frame.iterrows():
                name = str(p.get("PLAYER_NAME") or "").strip()
                if not name:
                    continue
                rows.append({
                    **p.to_dict(),
                    "game_id": str(game.get("game_id") or ""),
                    "game_status": _status_text(game),
                    "team_name": str(team_name or ""),
                    "opponent": str(opponent or ""),
                    "player_key": sgo._norm(name),
                })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.drop_duplicates(subset=["game_id", "player_key"], keep="first")
    return out, schedule


@st.cache_data(ttl=900, show_spinner=False)
def _empirical_for_player(player_id):
    try:
        log = role.player_game_log(int(float(player_id)))
        return role.empirical_profile(log) or {}
    except Exception:
        return {}


def _pra_sd(proj_row):
    profile = _empirical_for_player(proj_row.get("PLAYER_ID"))
    proj_pts = max(0.0, _num(proj_row.get("PROJ_PTS"), 0.0))
    proj_reb = max(0.0, _num(proj_row.get("PROJ_REB"), 0.0))
    proj_ast = max(0.0, _num(proj_row.get("PROJ_AST"), 0.0))
    proj_pra = max(0.0, proj_pts + proj_reb + proj_ast)

    games = int(profile.get("games") or 0)
    if games >= 5:
        sp = max(1.0, _num(profile.get("sd_pts"), 1.0))
        sr = max(0.7, _num(profile.get("sd_reb"), 0.7))
        sa = max(0.7, _num(profile.get("sd_ast"), 0.7))
        cpr = float(np.clip(_num(profile.get("corr_pr"), 0.0), -0.75, 0.75))
        cpa = float(np.clip(_num(profile.get("corr_pa"), 0.0), -0.75, 0.75))
        cra = float(np.clip(_num(profile.get("corr_ra"), 0.0), -0.75, 0.75))
        var = sp * sp + sr * sr + sa * sa + 2 * cpr * sp * sr + 2 * cpa * sp * sa + 2 * cra * sr * sa
        hist_pra = max(1.0, _num(profile.get("pra"), proj_pra or 1.0))
        role_scale = float(np.clip((max(proj_pra, 1.0) / hist_pra) ** 0.25, 0.82, 1.20))
        sd = max(2.2, math.sqrt(max(var, 1.0)) * role_scale)
        quality = min(1.0, 0.55 + min(games, 30) / 30.0 * 0.35)
        return sd, games, quality, "EMPIRICAL"

    # Explicit fallback when a usable game log is unavailable. This is not
    # presented as empirical data.
    sp = max(2.4, math.sqrt(max(proj_pts, 1.0)) * 1.20)
    sr = max(1.5, math.sqrt(max(proj_reb, 1.0)) * 1.10)
    sa = max(1.3, math.sqrt(max(proj_ast, 1.0)) * 1.12)
    sd = max(2.8, math.sqrt(sp * sp + sr * sr + sa * sa))
    return sd, games, 0.48, "FALLBACK"


def _paired_pra_markets(day):
    snap = sgo.market_snapshot(day)
    props = snap.get("player_props")
    if props is None or props.empty:
        return pd.DataFrame(), snap
    p = props.copy()
    p = p.loc[p["market"].astype(str).str.upper().eq("PRA")].copy()
    if p.empty:
        return pd.DataFrame(), snap

    keys = ["game_id", "player_key", "player_name", "line", "book"]
    over = p.loc[p["side"].astype(str).str.lower().eq("over")].copy()
    under = p.loc[p["side"].astype(str).str.lower().eq("under")].copy()
    if over.empty or under.empty:
        return pd.DataFrame(), snap

    over = over.rename(columns={"odds":"over_odds", "age_seconds":"over_age", "updated_at":"over_updated"})
    under = under.rename(columns={"odds":"under_odds", "age_seconds":"under_age", "updated_at":"under_updated"})
    keep_over = keys + ["over_odds", "over_age", "over_updated"]
    keep_under = keys + ["under_odds", "under_age", "under_updated"]
    pairs = over[keep_over].merge(under[keep_under], on=keys, how="inner")
    if pairs.empty:
        return pairs, snap
    pairs["market_age"] = pairs[["over_age", "under_age"]].max(axis=1, skipna=True)
    return pairs, snap


def grade_pra_markets(day):
    projections, schedule = _projection_frame(day)
    pairs, snap = _paired_pra_markets(day)
    if projections.empty or pairs.empty:
        return pd.DataFrame(), {"snapshot": snap, "projections": len(projections), "pairs": len(pairs)}

    by_key = {}
    for _, p in projections.iterrows():
        key = (str(p.get("game_id") or ""), str(p.get("player_key") or ""))
        by_key[key] = p

    rows = []
    unmatched = set()
    for _, m in pairs.iterrows():
        key = (str(m.get("game_id") or ""), str(m.get("player_key") or ""))
        proj = by_key.get(key)
        if proj is None:
            unmatched.add(str(m.get("player_name") or "Player"))
            continue
        line = _num(m.get("line"), np.nan)
        mu = _num(proj.get("PROJ_PRA"), np.nan)
        if pd.isna(line) or pd.isna(mu) or mu <= 0:
            continue
        sd, hist_games, data_quality, variance_source = _pra_sd(proj)
        dist = NormalDist(mu=float(mu), sigma=max(float(sd), 0.5))
        p_over = float(np.clip(1.0 - dist.cdf(float(line)), 0.01, 0.99))
        p_under = 1.0 - p_over
        nv_over, nv_under = _no_vig(m.get("over_odds"), m.get("under_odds"))
        edge = p_over - nv_over if pd.notna(nv_over) else np.nan
        profit = _profit_per_dollar(m.get("over_odds"))
        ev100 = ((p_over * profit - (1.0 - p_over)) * 100.0) if pd.notna(profit) else np.nan
        fresh_label, fresh_score = _freshness(m.get("market_age"))
        role_label = str(proj.get("ROLE_LABEL") or "ACTIVE")
        status_risk = "MONITOR" if role_label == "STATUS UNCERTAIN" else "READY"
        if fresh_label == "STALE":
            status_risk = "STALE"

        rows.append({
            "player": str(proj.get("PLAYER_NAME") or m.get("player_name") or "Player"),
            "team": str(proj.get("team_name") or ""),
            "opponent": str(proj.get("opponent") or ""),
            "game_id": str(m.get("game_id") or ""),
            "book": str(m.get("book") or ""),
            "line": float(line),
            "projection": float(mu),
            "delta": float(mu - line),
            "sd_pra": float(sd),
            "model_over": p_over,
            "model_under": p_under,
            "no_vig_over": nv_over,
            "no_vig_under": nv_under,
            "edge": edge,
            "over_odds": m.get("over_odds"),
            "under_odds": m.get("under_odds"),
            "fair_over": _fair_american(p_over),
            "fair_under": _fair_american(p_under),
            "ev100": ev100,
            "market_age": _num(m.get("market_age"), np.nan),
            "freshness": fresh_label,
            "fresh_score": fresh_score,
            "data_quality": data_quality,
            "hist_games": hist_games,
            "variance_source": variance_source,
            "proj_min": _num(proj.get("PROJ_MIN"), np.nan),
            "role_label": role_label,
            "status": status_risk,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out, {"snapshot": snap, "projections": len(projections), "pairs": len(pairs), "unmatched_players": sorted(unmatched)}

    # One best same-line/book offer per player for the ranking. Positive American
    # price is better; for negative prices, the less negative price is better.
    out["_price_sort"] = pd.to_numeric(out["over_odds"], errors="coerce").fillna(-100000)
    out["eligible"] = (
        out["no_vig_over"].notna()
        & out["edge"].notna()
        & out["model_over"].ge(0.53)
        & out["edge"].ge(0.025)
        & out["proj_min"].fillna(0).ge(10.0)
        & out["freshness"].ne("STALE")
    )
    out["market_grade"] = 100.0 * (
        0.52 * out["model_over"]
        + 0.28 * (0.50 + out["edge"].fillna(0.0)).clip(0.0, 1.0)
        + 0.12 * out["data_quality"].clip(0.0, 1.0)
        + 0.08 * out["fresh_score"].clip(0.0, 1.0)
    )
    out = out.sort_values(["eligible", "market_grade", "edge", "_price_sort"], ascending=[False, False, False, False]).reset_index(drop=True)
    return out.drop(columns=["_price_sort"]), {
        "snapshot": snap,
        "projections": len(projections),
        "pairs": len(pairs),
        "unmatched_players": sorted(unmatched),
    }


def _pct(value):
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _age(value):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    return f"{int(x)}s" if x < 120 else f"{int(x // 60)}m"


def render_pra_market_grade(day):
    st.markdown("### 🎯 Step 6 — WNBA PRA Market Grading")
    st.caption(
        "Independent Step-5 projection → exact SportsGameOdds PRA line → same-book no-vig grading. "
        "Sportsbook prices never change the projection. Preliminary probability layer only; opponent-defense and final 5M/10M Monte Carlo are still off."
    )

    with st.spinner("🧮 Matching PRA projections to exact sportsbook lines…"):
        graded, meta = grade_pra_markets(day)

    snap = meta.get("snapshot") or {}
    pra_props = snap.get("player_props")
    pra_rows = 0
    pra_players = 0
    if pra_props is not None and not pra_props.empty:
        pf = pra_props.loc[pra_props["market"].astype(str).str.upper().eq("PRA")].copy()
        pra_rows = len(pf)
        pra_players = pf["player_key"].nunique() if not pf.empty else 0

    qualified = int(graded["eligible"].sum()) if graded is not None and not graded.empty and "eligible" in graded.columns else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PRA market players", int(pra_players))
    c2.metric("Two-sided exact pairs", int(meta.get("pairs") or 0))
    c3.metric("Projection matches", 0 if graded is None else len(graded))
    c4.metric("Qualified overs", qualified)

    st.info(
        "Step 6 is a verification/calibration checkpoint. A pick is not final just because it grades well here. "
        "Confirmed starters are still pending on this slate, and opponent-defense + production Monte Carlo come next."
    )

    if graded is None or graded.empty:
        st.warning("No exact two-sided PRA markets could be matched to the current Step-5 player projections. No lines were fabricated.")
        if meta.get("unmatched_players"):
            st.caption("Unmatched player identities: " + " • ".join(meta["unmatched_players"][:12]))
        return

    ranked = graded.loc[graded["eligible"]].copy()
    # One ranked over per player; keep the strongest exact book/line combination.
    ranked = ranked.sort_values(["market_grade", "edge", "over_odds"], ascending=[False, False, False]).drop_duplicates("player", keep="first").head(5)

    st.markdown("#### 🏆 Preliminary PRA Over Board")
    if ranked.empty:
        st.warning("No PRA overs currently clear the preliminary Step-6 probability + no-vig + freshness gates. That is a valid result; nothing is forced.")
    else:
        for i, (_, r) in enumerate(ranked.iterrows(), 1):
            risk = "⚠️ MONITOR" if str(r.get("status")) != "READY" else "✅ STEP-6 QUALIFIED"
            st.markdown(
                f"**#{i} {r['player']} — OVER {r['line']:g}**  \n"
                f"{r['team']} vs {r['opponent']} • **{r['book']} {_fmt_odds(r['over_odds'])}** • {risk}  \n"
                f"Projection **{r['projection']:.1f} PRA** • Delta **{r['delta']:+.1f}** • Preliminary P(Over) **{_pct(r['model_over'])}** • Fair **{_fmt_odds(r['fair_over'])}**  \n"
                f"Same-book no-vig **{_pct(r['no_vig_over'])}** • Edge **{100*r['edge']:+.1f} pp** • EV **{r['ev100']:+.1f}/$100** • Market **{r['freshness']} ({_age(r['market_age'])})**  \n"
                f"Variance: {r['variance_source']} ({int(r['hist_games'])} games) • Projected minutes {r['proj_min']:.1f} • Step-6 Grade {r['market_grade']:.1f}/100"
            )
            st.divider()

    with st.expander("📋 All exact PRA model-vs-market matches", expanded=False):
        show = graded.copy()
        show["Model Over"] = show["model_over"].map(_pct)
        show["No-vig Over"] = show["no_vig_over"].map(_pct)
        show["Edge"] = show["edge"].map(lambda x: "—" if pd.isna(x) else f"{100*x:+.1f} pp")
        show["Fair"] = show["fair_over"].map(_fmt_odds)
        show["Price"] = show["over_odds"].map(_fmt_odds)
        st.dataframe(
            show[["player", "book", "line", "projection", "delta", "Model Over", "No-vig Over", "Edge", "Price", "Fair", "freshness", "eligible"]].rename(
                columns={"player":"Player", "book":"Book", "line":"Line", "projection":"Proj PRA", "delta":"Delta", "freshness":"Freshness", "eligible":"Qualified"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    if meta.get("unmatched_players"):
        st.caption("Identity-check unmatched (not graded): " + " • ".join(meta["unmatched_players"][:12]))


__all__ = ["MODEL_VERSION", "grade_pra_markets", "render_pra_market_grade"]
