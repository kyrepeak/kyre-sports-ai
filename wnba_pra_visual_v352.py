"""WNBA PRA V3.5.2 — presentation-only Preliminary PRA visual cards.

This module replaces only the Step-6 Preliminary PRA Over Board renderer. The
underlying market grader, projection math, injury/minutes/role logic, matchup
adjustments, Monte Carlo engine, SportsGameOdds pairing and finalization gates are
unchanged.

Visual cards reuse the already-verified Step-6 rows and add:
- ESPN player headshots resolved from the existing WNBA PLAYER_ID;
- team and opponent logos resolved from the verified slate team IDs;
- exact book / Over line / posted price;
- projection, delta, preliminary probability, fair odds, no-vig edge, EV,
  freshness, variance source, projected minutes and Step-6 grade;
- responsive two-column tablet/desktop and one-column phone layout.

Images load in the browser from the same public ESPN/WNBA CDN pattern already
used by the Rebounds visual-card layer. No new Python-side network request is
introduced and no player initials are drawn over faces.
"""
from __future__ import annotations

import html
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_market_v29 as base
import wnba_schedule_v25 as schedule_v25

MODEL_VERSION = "PRA V3.5.2 • VISUAL PRELIMINARY PRA CARDS • MODEL PRESERVED"
MAX_CARDS = 5


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _style_bg(url: str) -> str:
    if not url:
        return ""
    safe = str(url).replace("'", "%27").replace('"', "%22")
    return f"background-image:url('{safe}');"


def _pct(value, digits=1):
    x = _num(value)
    return "—" if not np.isfinite(x) else f"{100.0 * x:.{digits}f}%"


def _odds(value):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    n = int(round(x))
    return f"+{n}" if n > 0 else str(n)


def _line(value):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    return str(int(round(x))) if math.isclose(x, round(x), abs_tol=1e-9) else f"{x:.1f}"


def _dec(value, digits=1):
    x = _num(value)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _age(value):
    return base._age(value)


def _headshot_url(player_id):
    try:
        pid = int(float(player_id))
    except Exception:
        pid = 0
    if not pid:
        return ""
    return f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png"


def _team_meta(day):
    """Resolve logos only from the already-selected verified slate."""
    try:
        slate = base.role.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()
    out = {}
    if slate is None or slate.empty:
        return out
    for _, r in slate.iterrows():
        for side in ("away", "home"):
            name = str(r.get(f"{side}_team") or "").strip()
            if not name:
                continue
            try:
                tid = int(float(r.get(f"{side}_team_id") or 0))
            except Exception:
                tid = 0
            tri = str(r.get(f"{side}_tricode") or r.get(f"{side}_abbr") or name[:3]).upper()
            try:
                logo = schedule_v25.logo_url(tid) if tid else ""
            except Exception:
                logo = ""
            out[_norm(name)] = {
                "team_id": tid,
                "name": name,
                "tricode": tri,
                "logo": logo,
            }
    return out


def _player_id_lookup(day):
    """Join visual identity to the same projection frame used by Step 6."""
    try:
        projections, _schedule = base._projection_frame(day)
    except Exception:
        projections = pd.DataFrame()
    out = {}
    if projections is None or projections.empty:
        return out
    for _, r in projections.iterrows():
        gid = str(r.get("game_id") or "")
        player = str(r.get("PLAYER_NAME") or "")
        pkey = str(r.get("player_key") or base.sgo._norm(player))
        if gid and pkey:
            out[(gid, pkey)] = r.get("PLAYER_ID")
    return out


def _logo_html(url: str, abbr: str):
    return (
        f'<span class="kpra-logo" style="{_style_bg(url)}">'
        f'<span>{_esc(abbr)}</span></span>'
    )


def _metric(label: str, value: str):
    return (
        '<div class="kpra-metric">'
        f'<div class="kpra-metric-label">{_esc(label)}</div>'
        f'<div class="kpra-metric-value">{_esc(value)}</div>'
        '</div>'
    )


def _visual_rows(day, ranked: pd.DataFrame):
    teams = _team_meta(day)
    pids = _player_id_lookup(day)
    rows = []
    for rank, (_, r) in enumerate(ranked.head(MAX_CARDS).iterrows(), 1):
        player = str(r.get("player") or "Player")
        team = str(r.get("team") or "")
        opponent = str(r.get("opponent") or "")
        gid = str(r.get("game_id") or "")
        pkey = base.sgo._norm(player)
        tm = teams.get(_norm(team), {})
        om = teams.get(_norm(opponent), {})
        ready = str(r.get("status") or "") == "READY"
        rows.append({
            "rank": rank,
            "player": player,
            "team": team,
            "opponent": opponent,
            "team_logo": str(tm.get("logo") or ""),
            "opp_logo": str(om.get("logo") or ""),
            "team_abbr": str(tm.get("tricode") or team[:3]).upper(),
            "opp_abbr": str(om.get("tricode") or opponent[:3]).upper(),
            "headshot": _headshot_url(pids.get((gid, pkey))),
            "book": str(r.get("book") or ""),
            "line": r.get("line"),
            "price": r.get("over_odds"),
            "projection": r.get("projection"),
            "delta": r.get("delta"),
            "p_over": r.get("model_over"),
            "fair": r.get("fair_over"),
            "no_vig": r.get("no_vig_over"),
            "edge": r.get("edge"),
            "ev100": r.get("ev100"),
            "freshness": str(r.get("freshness") or "UNKNOWN"),
            "market_age": r.get("market_age"),
            "variance": str(r.get("variance_source") or "—"),
            "hist_games": int(_num(r.get("hist_games"), 0) or 0),
            "proj_min": r.get("proj_min"),
            "grade": r.get("market_grade"),
            "state": "STEP-6 QUALIFIED" if ready else "MONITOR",
        })
    return rows


def _card_html(r: dict):
    is_best = int(r.get("rank") or 0) == 1
    best_class = " best" if is_best else ""
    top_label = f"⭐ BEST PRELIMINARY • PRA #{r['rank']}" if is_best else f"🏆 PRELIMINARY PRA #{r['rank']}"
    state = str(r.get("state") or "MONITOR")
    state_class = "ready" if state == "STEP-6 QUALIFIED" else "monitor"
    avatar_style = _style_bg(str(r.get("headshot") or ""))
    avatar_fallback = "" if r.get("headshot") else '<span class="kpra-silhouette">👤</span>'
    freshness = f"{r.get('freshness')} {_age(r.get('market_age'))}".strip()
    variance = f"{r.get('variance')} • {int(r.get('hist_games') or 0)} GP"

    return f'''
    <article class="kpra-card{best_class}">
      <div class="kpra-card-top">
        <span class="kpra-rank">{_esc(top_label)}</span>
        <span class="kpra-state {state_class}">{_esc(state)}</span>
      </div>
      <div class="kpra-hero">
        <div class="kpra-avatar" style="{avatar_style}">{avatar_fallback}</div>
        <div class="kpra-player-block">
          <div class="kpra-player">{_esc(r.get('player'))}</div>
          <div class="kpra-matchup">
            {_logo_html(str(r.get('team_logo') or ''), str(r.get('team_abbr') or ''))}
            <span>{_esc(r.get('team'))}</span>
            <span class="kpra-vs">vs</span>
            {_logo_html(str(r.get('opp_logo') or ''), str(r.get('opp_abbr') or ''))}
            <span>{_esc(r.get('opponent'))}</span>
          </div>
        </div>
      </div>
      <div class="kpra-pickline">
        <span class="kpra-side">OVER {_esc(_line(r.get('line')))}</span>
        <span class="kpra-book">{_esc(r.get('book'))} • {_esc(_odds(r.get('price')))}</span>
      </div>
      <div class="kpra-metrics">
        {_metric('PROJ PRA', _dec(r.get('projection'),1))}
        {_metric('DELTA', ('+' if _num(r.get('delta'),0) >= 0 else '') + _dec(r.get('delta'),1))}
        {_metric('PRELIM P(OVER)', _pct(r.get('p_over'),1))}
        {_metric('FAIR ODDS', _odds(r.get('fair')))}
        {_metric('NO-VIG OVER', _pct(r.get('no_vig'),1))}
        {_metric('EDGE', ('+' if _num(r.get('edge'),0) >= 0 else '') + _dec(100.0 * _num(r.get('edge'),0),1) + ' pp')}
        {_metric('EV / $100', ('+' if _num(r.get('ev100'),0) >= 0 else '') + _dec(r.get('ev100'),1))}
        {_metric('PROJ MIN', _dec(r.get('proj_min'),1))}
        {_metric('STEP-6 GRADE', _dec(r.get('grade'),1) + '/100')}
      </div>
      <div class="kpra-card-foot">
        <span class="kpra-pill">MARKET {_esc(freshness)}</span>
        <span class="kpra-pill">VAR {_esc(variance)}</span>
      </div>
    </article>
    '''


def _render_visual_board(day, ranked: pd.DataFrame):
    rows = _visual_rows(day, ranked)
    if not rows:
        st.warning("No PRA overs currently clear the preliminary Step-6 probability + no-vig + freshness gates. That is a valid result; nothing is forced.")
        return

    css = '''
    <style>
      .kpra-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:10px 0 18px}
      .kpra-card{background:linear-gradient(145deg,#071b2c,#081523);border:1px solid #1f5d7d;border-radius:24px;padding:20px;box-shadow:0 12px 30px rgba(0,0,0,.18);min-width:0}
      .kpra-card.best{border-color:#49cfff;box-shadow:0 0 0 1px rgba(73,207,255,.18),0 14px 34px rgba(0,0,0,.24)}
      .kpra-card-top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:15px}
      .kpra-rank{font-size:.72rem;letter-spacing:.10em;font-weight:900;color:#59d8ff}
      .kpra-state{font-size:.66rem;font-weight:900;letter-spacing:.07em;padding:6px 9px;border-radius:999px;white-space:nowrap}
      .kpra-state.ready{background:#0e3b2b;color:#70f0a5;border:1px solid #246b4c}
      .kpra-state.monitor{background:#443917;color:#ffe173;border:1px solid #7e681c}
      .kpra-hero{display:flex;align-items:center;gap:15px;margin-bottom:14px}
      .kpra-avatar{width:78px;height:78px;min-width:78px;border-radius:50%;background-color:#102a3d;background-size:cover;background-position:center top;border:1px solid #2c7598;display:flex;align-items:center;justify-content:center;overflow:hidden}
      .kpra-silhouette{font-size:1.8rem;opacity:.75}
      .kpra-player-block{min-width:0;flex:1}
      .kpra-player{font-size:1.35rem;font-weight:900;color:#fff;line-height:1.15;margin-bottom:8px}
      .kpra-matchup{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#a9bbcd;font-size:.79rem;line-height:1.35}
      .kpra-vs{color:#72899f;font-weight:800}
      .kpra-logo{width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;background-size:contain;background-position:center;background-repeat:no-repeat;border-radius:50%;font-size:.45rem;font-weight:900;color:#879db1}
      .kpra-logo span{opacity:.7}
      .kpra-pickline{border-top:1px solid #1b536f;border-bottom:1px solid #1b536f;padding:14px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}
      .kpra-side{background:#164b31;border:1px solid #277b4e;color:#78efa7;border-radius:999px;padding:8px 13px;font-weight:900;font-size:1rem}
      .kpra-book{font-size:.82rem;font-weight:800;color:#e2eaf2;text-align:right}
      .kpra-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
      .kpra-metric{border:1px solid #1f5875;border-radius:13px;padding:10px 11px;min-height:62px;background:rgba(5,24,39,.42)}
      .kpra-metric-label{font-size:.57rem;letter-spacing:.09em;font-weight:900;color:#7697ad;margin-bottom:5px}
      .kpra-metric-value{font-size:.96rem;font-weight:900;color:#eef5fa;line-height:1.25}
      .kpra-card-foot{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
      .kpra-pill{font-size:.59rem;font-weight:850;letter-spacing:.035em;border:1px solid #255a73;color:#a9c3d4;border-radius:999px;padding:6px 8px;background:#092133}
      @media(max-width:720px){.kpra-grid{grid-template-columns:1fr}.kpra-card{padding:17px}.kpra-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}}
      @media(max-width:470px){.kpra-avatar{width:68px;height:68px;min-width:68px}.kpra-player{font-size:1.18rem}.kpra-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>
    '''
    cards = "".join(_card_html(r) for r in rows)
    st.markdown(css + f'<div class="kpra-grid">{cards}</div>', unsafe_allow_html=True)


def render_pra_market_grade_visual(day):
    """Exact Step-6 renderer with only the ranked board presentation changed."""
    st.markdown("### 🎯 Step 6 — WNBA PRA Market Grading")
    st.caption(
        "Independent Step-5 projection → exact SportsGameOdds PRA line → same-book no-vig grading. "
        "Sportsbook prices never change the projection. Preliminary probability layer only; opponent-defense and final 5M/10M Monte Carlo are still off."
    )

    with st.spinner("🧮 Matching PRA projections to exact sportsbook lines…"):
        graded, meta = base.grade_pra_markets(day)

    snap = meta.get("snapshot") or {}
    pra_props = snap.get("player_props")
    pra_players = 0
    if pra_props is not None and not pra_props.empty:
        pf = pra_props.loc[pra_props["market"].astype(str).str.upper().eq("PRA")].copy()
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
    ranked = ranked.sort_values(["market_grade", "edge", "over_odds"], ascending=[False, False, False]).drop_duplicates("player", keep="first").head(MAX_CARDS)

    st.markdown("#### 🏆 Preliminary PRA Over Board")
    st.caption(
        "Visual presentation of the exact Step-6 qualified rows. Player faces and team logos are display-only; "
        "the underlying projection, line, probability, no-vig, EV and qualification math is unchanged."
    )
    _render_visual_board(day, ranked)

    with st.expander("📋 All exact PRA model-vs-market matches", expanded=False):
        show = graded.copy()
        show["Model Over"] = show["model_over"].map(base._pct)
        show["No-vig Over"] = show["no_vig_over"].map(base._pct)
        show["Edge"] = show["edge"].map(lambda x: "—" if pd.isna(x) else f"{100*x:+.1f} pp")
        show["Fair"] = show["fair_over"].map(base._fmt_odds)
        show["Price"] = show["over_odds"].map(base._fmt_odds)
        st.dataframe(
            show[["player", "book", "line", "projection", "delta", "Model Over", "No-vig Over", "Edge", "Price", "Fair", "freshness", "eligible"]].rename(
                columns={"player":"Player", "book":"Book", "line":"Line", "projection":"Proj PRA", "delta":"Delta", "freshness":"Freshness", "eligible":"Qualified"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    if meta.get("unmatched_players"):
        st.caption("Identity-check unmatched (not graded): " + " • ".join(meta["unmatched_players"][:12]))


def install():
    """Patch only the Step-6 presentation function used throughout the PRA stack."""
    if getattr(base, "_v352_visual_board_installed", False):
        return
    base.render_pra_market_grade = render_pra_market_grade_visual
    base._v352_visual_board_installed = True


__all__ = ["MODEL_VERSION", "install", "render_pra_market_grade_visual"]
