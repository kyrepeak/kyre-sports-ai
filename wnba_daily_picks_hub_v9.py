"""WNBA Daily Picks V9 — Step 9 Top-5 selection + visual cards.

Steps 1-8 remain frozen. Step 9 consumes only Step-8 ranked rows, preserves the
existing rank order, applies bounded diversity caps, and publishes up to five
visual cards. It never launches simulations, refreshes injuries/markets, requests
sportsbook data, alters source projections, or writes production-model state.

Player/team imagery is presentation-only. Team logo URLs are deterministic CDN
references; player IDs are resolved only from data already present in Streamlit
session state. No Python-side image/network request is made. Missing headshots use
a clean silhouette fallback with no initials over the face.

Step 10 owns the final production-ready guard/recheck.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v7 as prev
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_standardizer_v1 as standardizer
import wnba_daily_picks_safety_v1 as safety
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking
import wnba_daily_picks_selection_v1 as selection

MODEL_VERSION = "WNBA DAILY PICKS V9 • STEP 9 VISUAL TOP 5"
_ET = ZoneInfo("America/New_York")

_TEAM_META = {
    "atlantadream": ("ATL", "atl"),
    "chicagosky": ("CHI", "chi"),
    "connecticutsun": ("CON", "con"),
    "dallaswings": ("DAL", "dal"),
    "goldenstatevalkyries": ("GSV", "gs"),
    "indianafever": ("IND", "ind"),
    "lasvegasaces": ("LVA", "lv"),
    "losangelessparks": ("LAS", "la"),
    "minnesotalynx": ("MIN", "min"),
    "newyorkliberty": ("NYL", "ny"),
    "phoenixmercury": ("PHX", "phx"),
    "seattlestorm": ("SEA", "sea"),
    "washingtonmystics": ("WAS", "wsh"),
    "torontotempo": ("TOR", "tor"),
}


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in {"", "—", "NONE", "NAN", "NULL", "N/A", "NA"} else s


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _pct(value):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    if abs(x) > 1 and abs(x) <= 100:
        return f"{x:.1f}%"
    return f"{100*x:.1f}%"


def _pp(value):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    if abs(x) <= 1:
        x *= 100.0
    return f"{x:+.1f} pp"


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


def _dec(value, digits=1, signed=False):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"


def _sims(value):
    x = _num(value, 0)
    if x >= 1_000_000:
        return f"{x/1_000_000:.0f}M" if math.isclose(x/1_000_000, round(x/1_000_000)) else f"{x/1_000_000:.1f}M"
    return f"{int(round(x)):,}" if x > 0 else "—"


def _team_visual(team: str) -> tuple[str, str]:
    key = _norm(team)
    abbr, slug = _TEAM_META.get(key, ((team[:3] if team else "WNBA").upper(), ""))
    logo = f"https://a.espncdn.com/i/teamlogos/wnba/500/{slug}.png" if slug else ""
    return abbr, logo


def _frames_from_value(value):
    if isinstance(value, pd.DataFrame):
        yield value
    elif isinstance(value, (list, tuple)):
        try:
            frame = pd.DataFrame(list(value))
            if not frame.empty:
                yield frame
        except Exception:
            return
    elif isinstance(value, dict):
        for key in ("rows", "players", "data", "projections", "player_rows"):
            nested = value.get(key)
            if isinstance(nested, pd.DataFrame):
                yield nested
            elif isinstance(nested, (list, tuple)):
                try:
                    frame = pd.DataFrame(list(nested))
                    if not frame.empty:
                        yield frame
                except Exception:
                    pass


def _player_id_from_session(player: str, team: str = ""):
    """Resolve identity from already-loaded WNBA session payloads only."""
    target = _norm(player)
    target_team = _norm(team)
    if not target:
        return None
    name_cols = ("PLAYER_NAME", "Player", "player", "player_name", "name")
    id_cols = ("PLAYER_ID", "Player ID", "player_id", "athlete_id", "athleteId")
    team_cols = ("team_name", "Team", "team", "TEAM_NAME")

    # Prefer likely identity/projection keys, then inspect other WNBA frames.
    keys = [str(k) for k in st.session_state.keys() if str(k).lower().startswith("wnba")]
    keys.sort(key=lambda k: (0 if any(token in k.lower() for token in ("projection", "player", "roster", "points", "pra", "rebound")) else 1, k))
    for key in keys[:180]:
        try:
            value = st.session_state.get(key)
        except Exception:
            continue
        for frame in _frames_from_value(value):
            if frame is None or frame.empty or len(frame) > 1500:
                continue
            ncol = next((c for c in name_cols if c in frame.columns), None)
            icol = next((c for c in id_cols if c in frame.columns), None)
            if not ncol or not icol:
                continue
            try:
                names = frame[ncol].astype(str).map(_norm)
                match = frame[names.eq(target)]
            except Exception:
                continue
            if match.empty:
                continue
            tcol = next((c for c in team_cols if c in match.columns), None)
            if tcol and target_team:
                by_team = match[match[tcol].astype(str).map(_norm).eq(target_team)]
                if not by_team.empty:
                    match = by_team
            for raw in match[icol].tolist():
                try:
                    pid = int(float(raw))
                    if pid > 0:
                        return pid
                except Exception:
                    pass
    return None


def _headshot(player: str, team: str) -> str:
    pid = _player_id_from_session(player, team)
    return f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png" if pid else ""


def _style_bg(url: str) -> str:
    if not url:
        return ""
    safe = str(url).replace("'", "%27").replace('"', "%22")
    return f"background-image:url('{safe}');"


def _logo_html(team: str) -> str:
    abbr, url = _team_visual(team)
    return (
        f'<span class="ks9-logo" style="{_style_bg(url)}">'
        f'<span>{escape(abbr)}</span></span>'
    )


def _metric(label: str, value: str) -> str:
    return (
        '<div class="ks9-metric">'
        f'<div class="ks9-mlabel">{escape(label)}</div>'
        f'<div class="ks9-mvalue">{escape(value)}</div>'
        '</div>'
    )


def _ranking_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Rank", "Rank state", "Ranking score", "Market", "Player", "Team", "Opponent",
        "Side", "Line", "Book", "Posted odds", "Projection", "Projection edge",
        "Model probability", "No-vig ranked", "Edge ranked", "EV / $100 ranked",
        "Exposure penalty", "Qualification state", "Freshness", "Quote selection",
        "Protection flags",
    ]
    d = frame[[c for c in keep if c in frame.columns]].copy()
    for col in ("Model probability", "No-vig ranked", "Edge ranked"):
        if col in d.columns:
            vals = pd.to_numeric(d[col], errors="coerce")
            d[col] = vals.map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
    for col in ("Ranking score", "Projection edge", "EV / $100 ranked", "Exposure penalty"):
        if col in d.columns:
            vals = pd.to_numeric(d[col], errors="coerce")
            d[col] = vals.map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    return d


def _card_html(row: pd.Series) -> str:
    rank = int(_num(row.get("Daily rank"), 0) or 0)
    player = _text(row.get("Player")) or "WNBA Player"
    team = _text(row.get("Team")) or "Team"
    opponent = _text(row.get("Opponent")) or "Opponent"
    market = (_text(row.get("Market")) or "PROP").upper()
    side = (_text(row.get("Side")) or "—").upper()
    is_best = rank == 1
    best_class = " best" if is_best else ""
    side_class = " over" if side == "OVER" else (" under" if side == "UNDER" else "")
    label = f"⭐ BEST PICK • DAILY #{rank}" if is_best else f"🏆 DAILY PICK #{rank}"
    photo = _headshot(player, team)
    avatar = "" if photo else '<span class="ks9-silhouette">👤</span>'
    proj_edge = _num(row.get("Projection edge"))
    fair = row.get("Fair odds")
    if not np.isfinite(_num(fair)):
        # Ranking can derive comparable probabilities but never invent fair odds.
        fair_text = "—"
    else:
        fair_text = _odds(fair)
    confidence = _text(row.get("Confidence")) or "—"
    freshness = _text(row.get("Freshness")) or "—"
    qstate = _text(row.get("Qualification state")) or "—"
    book = _text(row.get("Book")) or "—"

    return f'''
    <article class="ks9-card{best_class}">
      <div class="ks9-top">
        <span class="ks9-rank">{escape(label)}</span>
        <span class="ks9-state">STEP-9 SELECTED</span>
      </div>
      <div class="ks9-hero">
        <div class="ks9-avatar" style="{_style_bg(photo)}">{avatar}</div>
        <div class="ks9-playerblock">
          <div class="ks9-player">{escape(player)}</div>
          <div class="ks9-market">{escape(market)}</div>
          <div class="ks9-matchup">
            {_logo_html(team)}<span>{escape(team)}</span><span class="ks9-vs">vs</span>
            {_logo_html(opponent)}<span>{escape(opponent)}</span>
          </div>
        </div>
      </div>
      <div class="ks9-pickline">
        <span class="ks9-side{side_class}">{escape(side)} {escape(_line(row.get('Line')))}</span>
        <span class="ks9-book">{escape(book)} • {escape(_odds(row.get('Posted odds')))}</span>
      </div>
      <div class="ks9-metrics">
        {_metric('PROJECTION', _dec(row.get('Projection'),1))}
        {_metric('MODEL WIN', _pct(row.get('Model probability')))}
        {_metric('NO-VIG', _pct(row.get('No-vig ranked')))}
        {_metric('EDGE', _pp(row.get('Edge ranked')))}
        {_metric('EV / $100', _dec(row.get('EV / $100 ranked'),1,signed=True))}
        {_metric('FAIR ODDS', fair_text)}
        {_metric('PROJ EDGE', _dec(proj_edge,2,signed=True))}
        {_metric('RANK SCORE', _dec(row.get('Ranking score'),1))}
        {_metric('SIMS', _sims(row.get('Simulation count')))}
      </div>
      <div class="ks9-foot">
        <span class="ks9-pill">CONF {escape(confidence)}</span>
        <span class="ks9-pill">{escape(freshness)}</span>
        <span class="ks9-pill">{escape(qstate)}</span>
        <span class="ks9-pill warn">STEP 10 GUARD PENDING</span>
      </div>
    </article>
    '''


def _render_cards(selected: pd.DataFrame):
    css = '''
    <style>
      .ks9-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:12px 0 20px}
      .ks9-card{background:linear-gradient(145deg,#071b2c,#081523);border:1px solid #1f5d7d;border-radius:24px;padding:20px;box-shadow:0 12px 30px rgba(0,0,0,.18);min-width:0}
      .ks9-card.best{border-color:#49cfff;box-shadow:0 0 0 1px rgba(73,207,255,.18),0 14px 34px rgba(0,0,0,.24)}
      .ks9-top{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
      .ks9-rank{font-size:.72rem;letter-spacing:.10em;font-weight:950;color:#59d8ff}
      .ks9-state{font-size:.62rem;font-weight:950;letter-spacing:.06em;padding:6px 9px;border-radius:999px;background:#0e3b2b;color:#70f0a5;border:1px solid #246b4c;white-space:nowrap}
      .ks9-hero{display:flex;align-items:center;gap:15px;margin-bottom:14px}.ks9-avatar{width:82px;height:82px;min-width:82px;border-radius:50%;background:#102a3d;background-size:cover;background-position:center top;border:1px solid #2c7598;display:flex;align-items:center;justify-content:center;overflow:hidden}.ks9-silhouette{font-size:1.9rem;opacity:.72}
      .ks9-playerblock{min-width:0;flex:1}.ks9-player{font-size:1.35rem;font-weight:950;color:#fff;line-height:1.15}.ks9-market{margin:5px 0 8px;color:#67e8f9;font-size:.67rem;font-weight:950;letter-spacing:.10em}
      .ks9-matchup{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#a9bbcd;font-size:.78rem}.ks9-vs{color:#72899f;font-weight:850}.ks9-logo{width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;background-size:contain;background-position:center;background-repeat:no-repeat;border-radius:50%;font-size:.43rem;font-weight:950;color:#8aa1b5}.ks9-logo span{opacity:.72}
      .ks9-pickline{border-top:1px solid #1b536f;border-bottom:1px solid #1b536f;padding:14px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}.ks9-side{border-radius:999px;padding:8px 13px;font-weight:950;font-size:1rem;background:#25364a;color:#e2e8f0;border:1px solid #476079}.ks9-side.over{background:#164b31;border-color:#277b4e;color:#78efa7}.ks9-side.under{background:#4b2633;border-color:#81435a;color:#ff9fbd}.ks9-book{font-size:.82rem;font-weight:850;color:#e2eaf2;text-align:right}
      .ks9-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.ks9-metric{border:1px solid #1f5875;border-radius:13px;padding:10px 11px;min-height:62px;background:rgba(5,24,39,.42)}.ks9-mlabel{font-size:.56rem;letter-spacing:.09em;font-weight:950;color:#7697ad;margin-bottom:5px}.ks9-mvalue{font-size:.96rem;font-weight:950;color:#eef5fa;line-height:1.25}
      .ks9-foot{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.ks9-pill{font-size:.58rem;font-weight:850;letter-spacing:.03em;border:1px solid #255a73;color:#a9c3d4;border-radius:999px;padding:6px 8px;background:#092133}.ks9-pill.warn{border-color:#756318;color:#ffe173;background:#312b12}
      @media(max-width:720px){.ks9-grid{grid-template-columns:1fr}.ks9-card{padding:17px}.ks9-avatar{width:72px;height:72px;min-width:72px}.ks9-player{font-size:1.18rem}.ks9-metrics{gap:8px}.ks9-metric{padding:9px}.ks9-top{align-items:flex-start;flex-direction:column}.ks9-state{align-self:flex-start}}
    </style>
    '''
    cards = "".join(_card_html(row) for _, row in selected.iterrows())
    st.markdown(css + f'<div class="ks9-grid">{cards}</div>', unsafe_allow_html=True)


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    pra = pra_feed.status(slate_day)
    points = points_feed.status(slate_day)
    rebounds = rebounds_feed.status(slate_day)
    common = standardizer.normalize_all(slate_day)
    diag = standardizer.diagnostics(slate_day)
    feeds = {"PRA": pra, "POINTS": points, "REBOUNDS": rebounds}
    audit = safety.evaluate(common, slate_day, feeds=feeds)
    sdiag = safety.diagnostics(audit)
    protected = protection.annotate(audit)
    pdiag = protection.diagnostics(protected)
    ranked = ranking.rank_candidates(protected)
    rdiag = ranking.diagnostics(ranked)
    selected, skipped = selection.select_top5(ranked)
    vdiag = selection.diagnostics(ranked, selected, skipped)

    st.markdown('''<style>.ks-dp-hero{padding:24px 26px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(10,24,46,.99));box-shadow:0 14px 38px rgba(0,0,0,.16)}.ks-dp-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}.ks-dp-title{margin-top:9px;color:#f8fafc;font-size:2.08rem;line-height:1.08;font-weight:950}.ks-dp-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.6;font-weight:650}.ks-dp-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900}</style>''', unsafe_allow_html=True)
    st.markdown(f'''<div class="ks-dp-hero"><div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 9</div><div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div><div class="ks-dp-sub">Steps 1–8 remain frozen. Step 9 publishes up to five visual selections from the existing Step-8 ranking only. Nothing is forced, and Step 10 still owns the final production-ready guard.</div><span class="ks-dp-chip">📅 ET slate {slate_day}</span><span class="ks-dp-chip">🔌 3 read-only connectors</span><span class="ks-dp-chip">🛡️ safety preserved</span><span class="ks-dp-chip">🧷 protection preserved</span><span class="ks-dp-chip">🏁 ranking preserved</span><span class="ks-dp-chip">🏆 Top 5 publishing ACTIVE</span></div>''', unsafe_allow_html=True)
    st.success("✅ STEP 9 ACTIVE • Visual Top-5 publishing reads Step-8 ranking only. Daily Picks still controls zero production models.")

    st.markdown("### 🧩 Market Feed Status")
    st.caption("PRA, Points and Rebounds remain independent read-only feeds. Assists and game markets remain future connectors.")
    row1 = st.columns(4, gap="small")
    cards1 = [
        ("PRA", str(pra.get("state") or "⏳ NOT RUN"), prev.base._feed_note(pra, "No same-day PRA payload loaded")),
        ("Points", str(points.get("state") or "⏳ NOT RUN"), prev.base._feed_note(points, "No same-day Points payload loaded")),
        ("Rebounds", str(rebounds.get("state") or "⏳ NOT RUN"), prev.base._feed_note(rebounds, "No same-day Rebounds payload loaded")),
        ("Assists", "NEXT", "Future independent feed"),
    ]
    for col, (label, state, note) in zip(row1, cards1):
        with col: st.markdown(prev.base._ui._status_card(label, state, note), unsafe_allow_html=True)
    row2 = st.columns(3, gap="small")
    for col, item in zip(row2, [("Spread","NEXT","Future independent feed"),("Moneyline","NEXT","Future independent feed"),("Game Total","NEXT","Future independent feed")]):
        with col: st.markdown(prev.base._ui._status_card(*item), unsafe_allow_html=True)

    prev.base.base._render_connector_panels(slate_day, pra, points, rebounds)

    st.markdown("### 🧬 Step 5 — Unified Daily Picks Data Contract")
    st.caption("Frozen. PRA / Points / Rebounds outputs share the same 22-field read-only contract.")
    c1,c2,c3,c4=st.columns(4); c1.metric("Common fields",int(diag.get("schema_columns",0))); c2.metric("Standardized rows",int(diag.get("rows",0))); c3.metric("Feeds with rows",f"{int(diag.get('feeds_with_rows',0))}/3"); c4.metric("Required-field gaps",int(diag.get("missing_required_cells",0)))
    counts=diag.get("market_counts",{}) or {}; c5,c6,c7,c8=st.columns(4); c5.metric("PRA rows",int(counts.get("PRA",0))); c6.metric("Points rows",int(counts.get("POINTS",0))); c7.metric("Rebounds rows",int(counts.get("REBOUNDS",0))); c8.metric("Model writes","0")
    if common.empty: st.info("⏳ STANDARDIZER READY • no same-day source payloads are loaded.")
    else:
        st.success(f"✅ STEP-5 CONTRACT PASS • {len(common)} row(s) normalized.")
        with st.expander("🧬 Unified source rows — read only", expanded=False): st.dataframe(prev.base.base._common_display(common).head(150), use_container_width=True, hide_index=True)

    st.markdown("### 🛡️ Step 6 — Production Safety Gates")
    st.caption("Frozen. Only SAFE rows can move forward; HOLD / REJECT remain blocked.")
    g1,g2,g3,g4=st.columns(4); g1.metric("Rows audited",int(sdiag.get("rows",0))); g2.metric("SAFE",int(sdiag.get("safe",0))); g3.metric("HOLD",int(sdiag.get("hold",0))); g4.metric("REJECT",int(sdiag.get("reject",0)))
    g5,g6,g7,g8=st.columns(4); g5.metric("Quote max age",f"{int(safety.MAX_QUOTE_AGE_MIN)}m"); g6.metric("Minimum sims",f"{int(safety.STANDARD_SIMS/1_000_000)}M"); g7.metric("Model writes","0"); g8.metric("Safety","ACTIVE")
    if audit.empty: st.info("⏳ SAFETY ENGINE ARMED • no standardized rows exist yet.")
    else:
        with st.expander("🛡️ Row-by-row safety audit — display only", expanded=False): st.dataframe(prev.base._safety_display(audit).head(150), use_container_width=True, hide_index=True)

    st.markdown("### 🧷 Step 7 — Duplicate + Correlation Protection")
    st.caption("Frozen. Equivalent quotes are one candidate family and correlated exposure remains tagged.")
    p1,p2,p3,p4=st.columns(4); p1.metric("SAFE source rows",int(pdiag.get("safe_rows",0))); p2.metric("Candidate groups",int(pdiag.get("candidate_groups",0))); p3.metric("Duplicate quote groups",int(pdiag.get("duplicate_quote_groups",0))); p4.metric("Extra quote rows",int(pdiag.get("extra_quote_rows",0)))
    p5,p6,p7,p8=st.columns(4); p5.metric("Alternate-line groups",int(pdiag.get("alternate_line_groups",0))); p6.metric("Player-correlation groups",int(pdiag.get("player_correlation_groups",0))); p7.metric("Same-game groups",int(pdiag.get("game_exposure_groups",0))); p8.metric("Protection","ACTIVE")
    if protected.empty: st.info("⏳ PROTECTION ENGINE ARMED • no Step-6 rows exist yet.")
    else:
        with st.expander("🧷 Candidate-group / exposure audit — display only", expanded=False): st.dataframe(prev._protection_display(protected).head(200), use_container_width=True, hide_index=True)

    st.markdown("### 🏁 Step 8 — Cross-Market Ranking Preview")
    st.caption("Frozen. Step 8 selects one best existing quote per SAFE candidate family and scores candidates across markets.")
    r1,r2,r3,r4=st.columns(4); r1.metric("Candidate families",int(rdiag.get("candidate_groups",0))); r2.metric("Ranked",int(rdiag.get("ranked",0))); r3.metric("Score holds",int(rdiag.get("score_holds",0))); r4.metric("Markets represented",int(rdiag.get("markets",0)))
    r5,r6,r7,r8=st.columns(4); r5.metric("Best quotes selected",int(rdiag.get("quotes_selected",0))); r6.metric("Ranking","ACTIVE"); r7.metric("New simulations","0"); r8.metric("Step-8 state","FROZEN")
    if ranked.empty: st.info("⏳ RANKING ENGINE ARMED • no SAFE candidate families exist yet.")
    else:
        with st.expander("🏁 Cross-market ranking audit", expanded=False): st.dataframe(_ranking_display(ranked).head(100), use_container_width=True, hide_index=True)

    st.markdown("### 🏆 Step 9 — Top 5 Selection + Visual Cards")
    st.caption("Selection preserves Step-8 rank order, never forces five, publishes at most one card per player and applies bounded game/team exposure caps. Step 10 production guard is still pending.")
    v1,v2,v3,v4=st.columns(4); v1.metric("Step-8 eligible",int(vdiag.get("eligible",0))); v2.metric("Published",f"{int(vdiag.get('published',0))}/5"); v3.metric("Markets on card",int(vdiag.get("markets",0))); v4.metric("Diversity holds",int(vdiag.get("skipped",0)))
    v5,v6,v7,v8=st.columns(4); v5.metric("New simulations","0"); v6.metric("Model writes","0"); v7.metric("Python network","0"); v8.metric("Production guard","STEP 10")

    if selected.empty:
        st.info("⏳ TOP-5 PUBLISHER ARMED • no Step-8 ranked candidates exist yet. Cards will appear automatically after a source model produces same-day output that clears Steps 5–8.")
    else:
        st.success(f"✅ STEP-9 VISUAL CARD PASS • {len(selected)} selection(s) published from the existing Step-8 ranking. These are selected for display; Step 10 production readiness is not applied yet.")
        _render_cards(selected)
        if not skipped.empty:
            with st.expander("🧷 Step-9 diversity holds — why a higher-ranked row was not duplicated", expanded=False):
                st.dataframe(skipped, use_container_width=True, hide_index=True)

    with st.expander("🧪 Step-9 selection / visual methodology", expanded=False):
        st.write("• Only Step-8 RANKED rows can publish")
        st.write("• Step-8 score/order is preserved; Step 9 does not rescore")
        st.write("• Maximum five cards; five is never forced")
        st.write("• Maximum one card per player")
        st.write(f"• Maximum {selection.MAX_PER_GAME} cards from one game")
        st.write(f"• Maximum {selection.MAX_PER_TEAM} cards from one player's team")
        st.write("• Player headshots are resolved only from already-loaded session identity; missing images use a silhouette, never initials")
        st.write("• Team/opponent logos are browser-display CDN references only")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Sportsbook/model refresh requests launched by Daily Picks: 0")
        st.write("• Production-model/session writes by Daily Picks: 0")
        st.write("• Step 10 final production-ready guard: PENDING")

    st.caption("⚡ WNBA Daily Picks V9 Step 9 • Steps 1–8 preserved • visual Top 5 ACTIVE • production-ready guard pending Step 10")


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
