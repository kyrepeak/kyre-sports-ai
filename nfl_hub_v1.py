"""Kyre Sports AI — NFL V1 foundation command center.

NFL-only foundation page. Adds a verified ESPN NFL slate/date layer and a clean
market workspace without enabling any betting projection, sportsbook grading,
Monte Carlo, ranking or recommendation logic.

MLB and WNBA modules are not imported or modified here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

ET = ZoneInfo("America/New_York")
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
MODEL_VERSION = "NFL V1 • FOUNDATION / VERIFIED SLATE • NO BETTING MODEL"

NFL_MARKETS = [
    "Slate",
    "Moneyline",
    "Spread",
    "Game Total",
    "Passing Yards",
    "Rushing Yards",
    "Receiving Yards",
    "Receptions",
    "Passing TDs",
    "Anytime TD",
    "Daily Picks",
]


def _safe_text(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _logo(team: dict, abbr: str) -> str:
    direct = _safe_text((team or {}).get("logo"))
    if direct:
        return direct
    logos = (team or {}).get("logos") or []
    if logos and isinstance(logos[0], dict):
        href = _safe_text(logos[0].get("href"))
        if href:
            return href
    if abbr:
        return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"
    return ""


def _record(comp: dict) -> str:
    records = (comp or {}).get("records") or []
    for item in records:
        if not isinstance(item, dict):
            continue
        summary = _safe_text(item.get("summary"))
        if summary:
            return summary
    return "—"


def _tip_et(value) -> tuple[str, str]:
    if not value:
        return "TBD", ""
    try:
        ts = pd.to_datetime(value, utc=True).tz_convert(ET)
        return ts.strftime("%-I:%M %p ET"), ts.strftime("%Y-%m-%d")
    except Exception:
        return _safe_text(value, "TBD"), ""


def _season_label(value) -> str:
    try:
        n = int(value)
    except Exception:
        n = 0
    return {1: "Preseason", 2: "Regular Season", 3: "Postseason"}.get(n, "NFL")


@st.cache_data(ttl=180, show_spinner=False)
def load_nfl_slate(day_str: str):
    """Return one NFL calendar slate from ESPN plus lightweight diagnostics."""
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    params = {"dates": pd.to_datetime(day).strftime("%Y%m%d"), "limit": 100}
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
    }
    diag = {
        "provider": "ESPN NFL scoreboard",
        "selected_date": day,
        "http": None,
        "request_ok": False,
        "games": 0,
        "error": "",
    }
    try:
        response = requests.get(ESPN_SCOREBOARD, params=params, headers=headers, timeout=8)
        diag["http"] = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return pd.DataFrame(), diag

    rows = []
    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        competition = comps[0]
        sides = {}
        for competitor in competition.get("competitors", []) or []:
            sides[_safe_text(competitor.get("homeAway")).lower()] = competitor
        away = sides.get("away") or {}
        home = sides.get("home") or {}
        away_team = away.get("team") or {}
        home_team = home.get("team") or {}
        away_abbr = _safe_text(away_team.get("abbreviation"), "AWY").upper()
        home_abbr = _safe_text(home_team.get("abbreviation"), "HME").upper()
        status_type = (event.get("status") or {}).get("type") or {}
        state = _safe_text(status_type.get("state"), "pre").lower()
        detail = _safe_text(
            status_type.get("shortDetail")
            or status_type.get("detail")
            or status_type.get("description"),
            "Scheduled",
        )
        tip, event_day = _tip_et(event.get("date") or competition.get("date"))
        if event_day and event_day != day:
            # ESPN date requests can include boundary events. Keep the ET slate strict.
            continue
        venue = competition.get("venue") or {}
        address = venue.get("address") or {}
        broadcasts = []
        for block in competition.get("broadcasts", []) or []:
            for name in block.get("names", []) or []:
                if name and name not in broadcasts:
                    broadcasts.append(str(name))
        season = event.get("season") or {}
        rows.append(
            {
                "game_id": _safe_text(event.get("id")),
                "game_date": event_day or day,
                "tip_et": tip,
                "state": state,
                "status": detail,
                "season_type": _season_label(season.get("type")),
                "away_team": _safe_text(away_team.get("displayName") or away_team.get("shortDisplayName"), "Away"),
                "away_abbr": away_abbr,
                "away_logo": _logo(away_team, away_abbr),
                "away_record": _record(away),
                "away_score": _safe_text(away.get("score")),
                "home_team": _safe_text(home_team.get("displayName") or home_team.get("shortDisplayName"), "Home"),
                "home_abbr": home_abbr,
                "home_logo": _logo(home_team, home_abbr),
                "home_record": _record(home),
                "home_score": _safe_text(home.get("score")),
                "venue": _safe_text(venue.get("fullName"), "Venue TBD"),
                "location": ", ".join(x for x in (_safe_text(address.get("city")), _safe_text(address.get("state"))) if x),
                "broadcast": " / ".join(broadcasts) if broadcasts else "—",
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["game_id"], keep="first").reset_index(drop=True)
    diag["request_ok"] = True
    diag["games"] = int(len(frame))
    return frame, diag


def _team_logo(url: str, abbr: str, name: str) -> str:
    if url:
        return (
            f'<img src="{escape(url, quote=True)}" alt="{escape(name, quote=True)} logo" '
            'style="width:44px;height:44px;object-fit:contain;flex:0 0 44px">'
        )
    return (
        '<div class="knfl-logo-fallback">'
        f'{escape(abbr[:4])}'
        '</div>'
    )


def _score_text(row) -> tuple[str, str]:
    state = _safe_text(row.get("state")).lower()
    if state in {"in", "post"}:
        away = _safe_text(row.get("away_score"), "0")
        home = _safe_text(row.get("home_score"), "0")
        return away, home
    return "", ""


def _game_card(row) -> str:
    away_score, home_score = _score_text(row)
    status_class = "live" if _safe_text(row.get("state")).lower() == "in" else ""
    return f'''
    <article class="knfl-game">
      <div class="knfl-game-top">
        <span>{escape(_safe_text(row.get('season_type'), 'NFL'))}</span>
        <span class="knfl-status {status_class}">{escape(_safe_text(row.get('status'), 'Scheduled'))}</span>
      </div>
      <div class="knfl-team-row">
        {_team_logo(_safe_text(row.get('away_logo')), _safe_text(row.get('away_abbr')), _safe_text(row.get('away_team')))}
        <div class="knfl-team-copy">
          <b>{escape(_safe_text(row.get('away_team'), 'Away'))}</b>
          <span>{escape(_safe_text(row.get('away_record'), '—'))}</span>
        </div>
        <strong class="knfl-score">{escape(away_score)}</strong>
      </div>
      <div class="knfl-at">AT</div>
      <div class="knfl-team-row">
        {_team_logo(_safe_text(row.get('home_logo')), _safe_text(row.get('home_abbr')), _safe_text(row.get('home_team')))}
        <div class="knfl-team-copy">
          <b>{escape(_safe_text(row.get('home_team'), 'Home'))}</b>
          <span>{escape(_safe_text(row.get('home_record'), '—'))}</span>
        </div>
        <strong class="knfl-score">{escape(home_score)}</strong>
      </div>
      <div class="knfl-game-meta">
        <span>🕒 {escape(_safe_text(row.get('tip_et'), 'TBD'))}</span>
        <span>🏟️ {escape(_safe_text(row.get('venue'), 'Venue TBD'))}</span>
        <span>📺 {escape(_safe_text(row.get('broadcast'), '—'))}</span>
      </div>
    </article>
    '''


_NFL_CSS = r'''
<style>
.knfl-shell{border:1px solid #2b4b70;border-radius:20px;background:linear-gradient(180deg,#0d1727,#08111d);padding:18px 18px 20px;margin:8px 0 18px;box-shadow:0 15px 44px rgba(0,0,0,.16)}
.knfl-title{font-size:1.55rem;font-weight:950;color:#f8fafc;letter-spacing:-.02em}.knfl-title span{color:#7ff2c2}
.knfl-sub{color:#8fa4bd;font-size:.78rem;line-height:1.55;margin-top:5px}.knfl-chiprow{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
.knfl-chip{border:1px solid #2b516f;background:#0a1b2b;border-radius:999px;padding:5px 9px;color:#9bd9f5;font-size:.62rem;font-weight:900}
.knfl-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}.knfl-game{border:1px solid #284763;background:#081522;border-radius:16px;padding:12px;min-width:0}
.knfl-game-top{display:flex;justify-content:space-between;gap:8px;color:#7d96ae;font-size:.58rem;font-weight:900;text-transform:uppercase}.knfl-status{color:#a9bdd0}.knfl-status.live{color:#7ff2c2}
.knfl-team-row{display:flex;align-items:center;gap:9px;margin-top:10px}.knfl-team-copy{display:flex;flex-direction:column;min-width:0;flex:1}.knfl-team-copy b{color:#f4f8ff;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.knfl-team-copy span{color:#7890a8;font-size:.58rem;margin-top:2px}.knfl-score{color:#7ff2c2;font-size:1.35rem}.knfl-at{color:#587187;font-size:.48rem;font-weight:950;margin:3px 0 0 54px}.knfl-logo-fallback{width:44px;height:44px;border:1px solid #31516e;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#9eb6ca;font-size:.55rem;font-weight:950;flex:0 0 44px}.knfl-game-meta{display:grid;gap:3px;border-top:1px solid #193149;margin-top:10px;padding-top:8px;color:#728aa0;font-size:.55rem}.knfl-empty{border:1px dashed #35506c;border-radius:14px;padding:18px;color:#8fa4bd;background:#091523;margin-top:12px}
@media(max-width:700px){.knfl-grid{grid-template-columns:1fr}.knfl-shell{padding:14px}.knfl-title{font-size:1.3rem}}
</style>
'''


def render_nfl_hub(market: str = "Slate"):
    """Render isolated NFL foundation page. No MLB/WNBA model is called."""
    market = str(market or "Slate")
    st.markdown(_NFL_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="knfl-shell">'
        '<div class="knfl-title">🏈 NFL <span>Command Center</span></div>'
        '<div class="knfl-sub">NFL V1 foundation • verified date-controlled NFL slate • team identity and game status only • no projection, sportsbook grading, Monte Carlo or ranking is active yet.</div>'
        '<div class="knfl-chiprow">'
        '<span class="knfl-chip">NFL ONLY</span><span class="knfl-chip">ESPN SCHEDULE</span>'
        '<span class="knfl-chip">ET DATE GUARD</span><span class="knfl-chip">MODEL OFF</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(ET).date()

    day = st.date_input(
        "📅 NFL slate date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_v1_date_input",
    )
    st.session_state["nfl_v1_date"] = day
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    st.markdown(f"### 🎯 NFL {escape(market)}")
    if market != "Slate":
        st.info(
            f"NFL {market} is reserved and visible in navigation, but the betting model is intentionally OFF. "
            "We are building the NFL foundation first so the league/date/game identity layer is stable before any market math is added."
        )

    with st.spinner("🏈 Verifying NFL slate…"):
        games, diag = load_nfl_slate(day_str)

    c1, c2, c3, c4 = st.columns(4)
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    c1.metric("Games", len(games))
    c2.metric("Upcoming", upcoming)
    c3.metric("Live", live)
    c4.metric("Final", final)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. The NFL page stays isolated and no fake games are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        if diag.get("error"):
            st.caption(f"Provider detail: {diag.get('error')}")
        return

    st.caption(
        f"✅ Verified NFL schedule • {day_str} • {diag.get('provider')} • {len(games)} game(s) • slate date interpreted in America/New_York"
    )

    if games.empty:
        st.markdown(
            '<div class="knfl-empty">No NFL games were returned for this selected ET calendar date. Pick another date above; this is treated as an empty NFL slate, not a provider-made prediction.</div>',
            unsafe_allow_html=True,
        )
        return

    cards = "".join(_game_card(row) for _, row in games.iterrows())
    st.markdown(f'<div class="knfl-grid">{cards}</div>', unsafe_allow_html=True)

    st.markdown("### 🧱 NFL build status")
    st.markdown(
        "**Step 1 — League page + verified slate:** ✅ ACTIVE  \n"
        "**Player/roster layer:** ⏳ NEXT  \n"
        "**Injuries/depth chart:** ⏳ NEXT  \n"
        "**Sportsbook markets:** OFF  \n"
        "**Projection model:** OFF  \n"
        "**Monte Carlo:** OFF  \n"
        "**Rankings/recommendations:** OFF"
    )


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
