"""WNBA Rebounds V3.1 — visual Top-5 production card.

Preserves the complete V3.0 production-hardened Steps 1–20 chain and adds only
an app-facing visual card section for the production final card. The visual layer
uses already-verified session-state outputs; it does not change projection,
Monte Carlo, probability, EV, qualification, ranking, quote freshness or any
production-readiness rule.

Each card includes:
- player face from immutable ESPN Player ID when available;
- official WNBA team/opponent logos from verified slate team IDs;
- exact sportsbook / side / line / price;
- market-independent projected rebounds + Monte Carlo median/range;
- model probability, no-vig edge, EV and fair odds;
- projected minutes + H2H context when available;
- confidence, quote freshness, game status and tip time.

The layout is responsive: two columns on tablets/desktop and one column on
narrow mobile screens. No new network requests are made by Python; browser image
assets load from the existing ESPN/WNBA CDN URLs only.
"""
from __future__ import annotations

import html
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v30 as base
import wnba_schedule_v25 as schedule_v25

MODEL_VERSION = "WNBA REBOUNDS V3.1 • VISUAL TOP-5 PRODUCTION CARDS • V3.0 MODEL PRESERVED"
MAX_VISUAL_CARDS = 5


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


def _pct(value, digits=1):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    return f"{100.0 * x:.{digits}f}%"


def _dec(value, digits=2):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    return f"{x:.{digits}f}"


def _intish(value):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    if math.isclose(x, round(x), abs_tol=1e-9):
        return str(int(round(x)))
    return f"{x:.1f}"


def _american(value):
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    n = int(round(x))
    return f"+{n}" if n > 0 else str(n)


def _initials(name: str):
    parts = [p for p in str(name or "").replace("-", " ").split() if p]
    if not parts:
        return "WN"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _player_lookup():
    rows = pd.DataFrame(st.session_state.get("wnba_rebounds_step12_players") or [])
    out = {}
    if rows.empty:
        return out
    for _, r in rows.iterrows():
        key = (_norm(r.get("Player")), _norm(r.get("Team")))
        if key[0] and key[1] and key not in out:
            out[key] = r
    return out


def _model_lookup():
    rows = pd.DataFrame(st.session_state.get("wnba_rebounds_step17_players") or [])
    out = {}
    if rows.empty:
        return out
    for _, r in rows.iterrows():
        key = (_norm(r.get("Player")), _norm(r.get("Team")))
        if key[0] and key[1] and key not in out:
            out[key] = r
    return out


def _team_meta(day: str):
    try:
        slate = schedule_v25.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()
    out = {}
    if slate is None or slate.empty:
        return out
    for _, r in slate.iterrows():
        for side in ("away", "home"):
            name = str(r.get(f"{side}_team") or "")
            if not name:
                continue
            try:
                tid = int(float(r.get(f"{side}_team_id") or 0))
            except Exception:
                tid = 0
            out[_norm(name)] = {
                "team_id": tid,
                "name": name,
                "tricode": str(r.get(f"{side}_tricode") or ""),
                "logo": schedule_v25.logo_url(tid) if tid else "",
            }
    return out


def _headshot_url(player_id):
    try:
        pid = int(float(player_id))
    except Exception:
        pid = 0
    if not pid:
        return ""
    return f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png"


def _style_bg(url: str):
    if not url:
        return ""
    safe = str(url).replace("'", "%27").replace('"', "%22")
    return f"background-image:url('{safe}');"


def _visual_rows():
    card = pd.DataFrame(st.session_state.get("wnba_rebounds_prod_guard_card") or [])
    if card.empty:
        return []
    if "Rank" in card.columns:
        card = card.sort_values("Rank", kind="mergesort")
    card = card.head(MAX_VISUAL_CARDS).copy()

    day = str(st.session_state.get("wnba_rebounds_step1_day") or "")
    players = _player_lookup()
    models = _model_lookup()
    teams = _team_meta(day)

    rows = []
    for idx, p in card.iterrows():
        player = str(p.get("Player") or "Player")
        team = str(p.get("Team") or "")
        opp = str(p.get("Opponent") or "")
        key = (_norm(player), _norm(team))
        pr = players.get(key)
        mr = models.get(key)
        team_meta = teams.get(_norm(team), {})
        opp_meta = teams.get(_norm(opp), {})

        rank = int(_num(p.get("Rank"), len(rows) + 1))
        player_id = pr.get("Player ID") if pr is not None else 0
        headshot = _headshot_url(player_id)
        proj_reb = _num(mr.get("Expected REB")) if mr is not None else np.nan
        mc_median = mr.get("MC median REB") if mr is not None else np.nan
        p10 = mr.get("MC P10 REB") if mr is not None else np.nan
        p90 = mr.get("MC P90 REB") if mr is not None else np.nan
        proj_min = _num(pr.get("Proj MIN")) if pr is not None else np.nan
        if not np.isfinite(proj_min) and pr is not None:
            proj_min = _num(pr.get("Projected MIN"))
        h2h_gp = _num(pr.get("H2H GP"), 0.0) if pr is not None else 0.0
        h2h_avg = _num(pr.get("H2H avg REB")) if pr is not None else np.nan

        rows.append({
            "rank": rank,
            "player": player,
            "team": team,
            "opponent": opp,
            "team_logo": str(team_meta.get("logo") or ""),
            "opp_logo": str(opp_meta.get("logo") or ""),
            "team_abbr": str(team_meta.get("tricode") or team[:3]).upper(),
            "opp_abbr": str(opp_meta.get("tricode") or opp[:3]).upper(),
            "headshot": headshot,
            "initials": _initials(player),
            "book": str(p.get("Book") or ""),
            "line": _num(p.get("Line")),
            "side": str(p.get("Side") or "").upper(),
            "posted_odds": str(p.get("Posted odds") or ""),
            "model_prob": _num(p.get("Model decision probability")),
            "edge": _num(p.get("No-vig edge")),
            "ev": _num(p.get("Expected ROI")),
            "fair": _num(p.get("Model fair American")),
            "confidence": str(p.get("Confidence grade") or "—"),
            "quote_freshness": str(p.get("Quote freshness") or "UNKNOWN"),
            "game_status": str(p.get("Game status") or "UNKNOWN"),
            "tip": str(p.get("Tip ET") or "TBD"),
            "prod_state": str(p.get("Production pick state") or "HOLD"),
            "hold_reason": str(p.get("Production hold reason") or ""),
            "proj_reb": proj_reb,
            "mc_median": mc_median,
            "p10": p10,
            "p90": p90,
            "proj_min": proj_min,
            "h2h_gp": h2h_gp,
            "h2h_avg": h2h_avg,
        })
    return rows


def _metric(label: str, value: str):
    return (
        '<div class="kr-reb-metric">'
        f'<div class="kr-reb-metric-label">{_esc(label)}</div>'
        f'<div class="kr-reb-metric-value">{_esc(value)}</div>'
        '</div>'
    )


def _logo_html(url: str, abbr: str):
    return (
        f'<span class="kr-reb-team-logo" style="{_style_bg(url)}">'
        f'<span>{_esc(abbr)}</span></span>'
    )


def _card_html(r: dict):
    side = str(r.get("side") or "")
    side_class = "over" if side == "OVER" else "under"
    state = str(r.get("prod_state") or "HOLD")
    state_class = "ready" if state == "READY" else "hold"
    line_txt = _intish(r.get("line"))
    odds = str(r.get("posted_odds") or "—")
    range_txt = f"{_intish(r.get('p10'))}–{_intish(r.get('p90'))}"
    h2h_txt = "NO SAMPLE"
    if _num(r.get("h2h_gp"), 0) > 0:
        h2h_txt = f"{int(_num(r.get('h2h_gp'),0))} GP • {_dec(r.get('h2h_avg'),1)} AVG"

    return f'''
    <article class="kr-reb-card">
      <div class="kr-reb-card-top">
        <span class="kr-reb-rank">🏀 TOP REB #{int(r.get('rank') or 0)}</span>
        <span class="kr-reb-state {state_class}">{_esc(state)}</span>
      </div>
      <div class="kr-reb-hero">
        <div class="kr-reb-avatar" style="{_style_bg(str(r.get('headshot') or ''))}">
          <span>{_esc(r.get('initials'))}</span>
        </div>
        <div class="kr-reb-player-block">
          <div class="kr-reb-player">{_esc(r.get('player'))}</div>
          <div class="kr-reb-matchup">
            {_logo_html(str(r.get('team_logo') or ''), str(r.get('team_abbr') or ''))}
            <span>{_esc(r.get('team'))}</span>
            <span class="kr-reb-vs">vs</span>
            {_logo_html(str(r.get('opp_logo') or ''), str(r.get('opp_abbr') or ''))}
            <span>{_esc(r.get('opponent'))}</span>
          </div>
        </div>
      </div>
      <div class="kr-reb-pickline">
        <span class="kr-reb-side {side_class}">{_esc(side)} {line_txt}</span>
        <span class="kr-reb-book">{_esc(r.get('book'))} • {_esc(odds)}</span>
      </div>
      <div class="kr-reb-metrics">
        {_metric('PROJ REB', _dec(r.get('proj_reb'),2))}
        {_metric('MODEL WIN', _pct(r.get('model_prob'),1))}
        {_metric('NO-VIG EDGE', _pct(r.get('edge'),1))}
        {_metric('EXPECTED ROI', _pct(r.get('ev'),1))}
        {_metric('MC MEDIAN', _intish(r.get('mc_median')))}
        {_metric('P10–P90', range_txt)}
        {_metric('PROJ MIN', _dec(r.get('proj_min'),1))}
        {_metric('H2H REB', h2h_txt)}
        {_metric('FAIR ODDS', _american(r.get('fair')))}
      </div>
      <div class="kr-reb-card-foot">
        <span class="kr-reb-pill">CONF {_esc(r.get('confidence'))}</span>
        <span class="kr-reb-pill">{_esc(r.get('quote_freshness'))}</span>
        <span class="kr-reb-pill">{_esc(r.get('game_status'))} • {_esc(r.get('tip'))}</span>
      </div>
      {f'<div class="kr-reb-hold">{_esc(r.get("hold_reason"))}</div>' if state != 'READY' and r.get('hold_reason') else ''}
    </article>
    '''


def _render_visual_top5():
    rows = _visual_rows()
    prod_ready = bool(st.session_state.get("wnba_rebounds_prod_guard_ready"))

    st.markdown("## 🏆 Today’s Top 5 Rebound Picks")
    st.caption(
        "Visual card view of the exact V3.0 production final card. Faces/logos are presentation-only; "
        "all projections, probabilities, edges, prices and production gates come from the verified model chain."
    )

    if not rows:
        st.info("No qualified production-card selections are available right now. The model will not force five picks.")
        return

    if prod_ready:
        st.success(f"✅ VISUAL CARD READY • {len(rows)} production-qualified selection(s) displayed from the verified final card.")
    else:
        st.warning("⚠️ VISUAL CARD PREVIEW • the production guard is currently on HOLD; cards below retain their hold status.")

    css = '''
    <style>
      .kr-reb-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:10px 0 18px}
      .kr-reb-card{background:linear-gradient(145deg,#071b2c,#081523);border:1px solid #1f5d7d;border-radius:24px;padding:20px;box-shadow:0 12px 30px rgba(0,0,0,.18);min-width:0}
      .kr-reb-card-top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:15px}
      .kr-reb-rank{font-size:.72rem;letter-spacing:.12em;font-weight:900;color:#59d8ff}
      .kr-reb-state{font-size:.68rem;font-weight:900;letter-spacing:.08em;padding:6px 9px;border-radius:999px}
      .kr-reb-state.ready{background:#0e3b2b;color:#70f0a5;border:1px solid #246b4c}
      .kr-reb-state.hold{background:#43211f;color:#ff9b91;border:1px solid #7d3b34}
      .kr-reb-hero{display:flex;align-items:center;gap:15px;margin-bottom:14px}
      .kr-reb-avatar{width:76px;height:76px;flex:0 0 76px;border-radius:50%;border:1px solid #2a7398;background-color:#0d2a3c;background-size:cover;background-position:center top;display:flex;align-items:center;justify-content:center;overflow:hidden}
      .kr-reb-avatar span{font-weight:900;font-size:1.05rem;color:#b8d7e7;z-index:0}
      .kr-reb-player-block{min-width:0}
      .kr-reb-player{font-size:1.35rem;line-height:1.15;font-weight:900;color:#f7fbff;margin-bottom:9px}
      .kr-reb-matchup{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#9fb3c3;font-size:.83rem}
      .kr-reb-vs{color:#6f8798;font-weight:700}
      .kr-reb-team-logo{width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background-size:contain;background-repeat:no-repeat;background-position:center;background-color:#0a2030;flex:0 0 28px}
      .kr-reb-team-logo span{font-size:.49rem;font-weight:900;color:#b3cbd8}
      .kr-reb-pickline{display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px solid #183f56;border-bottom:1px solid #183f56;padding:12px 0;margin:4px 0 14px;flex-wrap:wrap}
      .kr-reb-side{font-size:1rem;font-weight:950;letter-spacing:.04em;border-radius:999px;padding:7px 11px}
      .kr-reb-side.over{background:#0f3c2a;color:#78f2a9;border:1px solid #266849}
      .kr-reb-side.under{background:#3a232d;color:#ff9bb9;border:1px solid #734052}
      .kr-reb-book{color:#d8e4eb;font-size:.86rem;font-weight:800}
      .kr-reb-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
      .kr-reb-metric{border:1px solid #214d67;border-radius:13px;padding:10px;background:rgba(8,28,43,.72);min-width:0}
      .kr-reb-metric-label{font-size:.61rem;letter-spacing:.08em;font-weight:900;color:#7793a7;margin-bottom:5px}
      .kr-reb-metric-value{font-size:.98rem;font-weight:850;color:#f0f6fa;white-space:normal;overflow-wrap:anywhere}
      .kr-reb-card-foot{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}
      .kr-reb-pill{font-size:.64rem;font-weight:850;letter-spacing:.04em;color:#a8c0cf;border:1px solid #244b61;background:#0a1d2a;border-radius:999px;padding:6px 8px}
      .kr-reb-hold{margin-top:10px;border-radius:10px;background:#351b1d;color:#ff9c9c;padding:9px 10px;font-size:.74rem;font-weight:750}
      @media(max-width:760px){.kr-reb-grid{grid-template-columns:1fr}.kr-reb-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kr-reb-card{padding:16px}.kr-reb-player{font-size:1.2rem}}
    </style>
    '''
    body = '<div class="kr-reb-grid">' + ''.join(_card_html(r) for r in rows) + '</div>'
    st.markdown(css + body, unsafe_allow_html=True)

    with st.expander("🎨 Visual-card diagnostics"):
        st.write({
            "visual_cards": len(rows),
            "source": "V3.0 production final card",
            "player_face_source": "ESPN headshot CDN via verified ESPN Player ID",
            "team_logo_source": "official WNBA logo CDN via verified WNBA team ID",
            "new_model_inputs": 0,
            "new_python_network_requests": 0,
            "projection_math_changed": False,
            "ranking_math_changed": False,
            "production_guard_changed": False,
            "responsive_layout": "2 columns tablet/desktop • 1 column mobile",
        })

    st.caption(
        "⚡ V3.1 visual Top-5 layer • V3.0 production guard + Steps 1–20 unchanged • "
        "player faces + team logos + exact pick/model context • presentation only."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step20_ready"):
        _render_visual_top5()
    else:
        st.info("Top-5 visual cards remain locked until the complete Steps 1–20 chain is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
