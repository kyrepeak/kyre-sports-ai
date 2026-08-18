"""MLB Daily Game Picks V2.0.9 — polished mobile final-card experience.

UI/UX layer only. Preserves V2.0.8 one-tap orchestration, V2.0.7 market-neutral
normalization, all seven production models, sportsbook gates, simulation depths,
identity firewalls, Step 5 rankings, and Step 6 selection rules.

Adds:
- compact Final Card / Full Dashboard view switch
- official MLB team logos in slate-wide cards and market leaders
- last-built timestamp and live display status
- quota-safe UI auto-refresh (display rerun only; never rebuilds engines)
- clearer confidence badges and connector status pills
- compact market-leader cards and collapsed diagnostics-first workflow
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # graceful deploy fallback while dependency installs
    st_autorefresh = None

import mlb_daily_game_picks_v208 as previous
import mlb_daily_game_picks_v206 as master

VERSION = "MLB Daily Game Picks V2.0.9 • POLISHED MOBILE FINAL CARD"
ET = ZoneInfo("America/New_York")

# Stable MLB team IDs used by official MLB static logo assets.
TEAM_IDS = {
    "Arizona Diamondbacks": 109,
    "Atlanta Braves": 144,
    "Baltimore Orioles": 110,
    "Boston Red Sox": 111,
    "Chicago Cubs": 112,
    "Chicago White Sox": 145,
    "Cincinnati Reds": 113,
    "Cleveland Guardians": 114,
    "Colorado Rockies": 115,
    "Detroit Tigers": 116,
    "Houston Astros": 117,
    "Kansas City Royals": 118,
    "Los Angeles Angels": 108,
    "Los Angeles Dodgers": 119,
    "Miami Marlins": 146,
    "Milwaukee Brewers": 158,
    "Minnesota Twins": 142,
    "New York Mets": 121,
    "New York Yankees": 147,
    "Athletics": 133,
    "Oakland Athletics": 133,
    "Philadelphia Phillies": 143,
    "Pittsburgh Pirates": 134,
    "San Diego Padres": 135,
    "San Francisco Giants": 137,
    "Seattle Mariners": 136,
    "St. Louis Cardinals": 138,
    "Tampa Bay Rays": 139,
    "Texas Rangers": 140,
    "Toronto Blue Jays": 141,
    "Washington Nationals": 120,
}


def _day(games_df):
    return previous._day(games_df)


def _now_et():
    return datetime.now(ET)


def _fmt_ts(ts):
    if not ts:
        return "Not built in this session"
    try:
        return ts.astimezone(ET).strftime("%b %d • %I:%M:%S %p ET")
    except Exception:
        return str(ts)


def _logo_url(team):
    tid = TEAM_IDS.get(str(team or "").strip())
    return f"https://www.mlbstatic.com/team-logos/{tid}.svg" if tid else ""


def _img(team, size=26):
    url = _logo_url(team)
    if not url:
        return ""
    return (
        f'<img src="{escape(url)}" alt="{escape(str(team or "team"))}" '
        f'width="{int(size)}" height="{int(size)}" '
        'style="object-fit:contain;flex:0 0 auto" '
        'onerror="this.style.display=\'none\'">'
    )


def _split_matchup(matchup):
    text = str(matchup or "")
    if " @ " in text:
        a, h = text.split(" @ ", 1)
        return a.strip(), h.strip()
    return text.strip(), ""


def _tier(score):
    s = master._finite(score)
    if s >= 82.0:
        return "ELITE", "elite"
    if s >= 76.0:
        return "STRONG", "strong"
    return "QUALIFIED", "qualified"


def _inject_css():
    st.markdown(
        """
<style>
/* V2.0.9 — mobile-first visual polish */
.kui-top{border:1px solid #294c69;background:linear-gradient(145deg,#0a1c2f,#071522);border-radius:18px;padding:13px 15px;margin:8px 0 13px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.kui-title{font-size:14px;font-weight:950;color:#fff}.kui-sub{font-size:10px;color:#91a8bd;margin-top:3px}.kui-live{display:inline-flex;align-items:center;gap:6px;border:1px solid #225b49;background:#0b3028;color:#65e3a9;border-radius:999px;padding:5px 9px;font-size:9px;font-weight:950;white-space:nowrap}
.kui-stagegrid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;margin:8px 0 13px}.kui-stage{border:1px solid #29465e;background:#081725;border-radius:11px;padding:7px 6px;text-align:center;color:#91a7ba;font-size:8px;font-weight:850}.kui-stage.ready{border-color:#27644e;background:#0a2b24;color:#65e3a9}.kui-stage.partial{border-color:#756427;background:#302b0b;color:#f1d665}.kui-stage.blocked{border-color:#6a3434;background:#2c1317;color:#ff9090}
.kui-master{border:1px solid #326386;background:linear-gradient(145deg,#0a1e33,#071522);border-radius:21px;padding:15px;margin:11px 0 18px}.kui-kicker{font-size:9px;color:#5ddcff;font-weight:950;letter-spacing:1.4px}.kui-master-title{font-size:27px;color:#fff;font-weight:1000;margin:4px 0}.kui-master-sub{font-size:10px;color:#91a8bd;line-height:1.5}.kui-stats{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 12px}.kui-stat{border:1px solid #294c67;border-radius:999px;padding:5px 8px;color:#8fa8bb;font-size:8px}.kui-stat b{color:#fff}
.kui-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.kui-card{border:1px solid #294967;background:#09192a;border-radius:17px;padding:13px;min-height:205px}.kui-card.first{border-color:#c5a72c;box-shadow:0 0 0 1px rgba(197,167,44,.08) inset}.kui-rank{color:#62dcff;font-size:9px;font-weight:950;letter-spacing:.7px}.kui-market{color:#9bb2c5;font-size:9px;font-weight:850;margin-top:8px}.kui-name-row{display:flex;align-items:center;gap:8px;margin-top:4px}.kui-name{font-size:18px;font-weight:1000;color:#fff;line-height:1.12}.kui-side{color:#d6e2ec;font-size:10px;margin-top:5px}.kui-score{font-size:31px;font-weight:1000;color:#fff;margin-top:11px}.kui-score small{font-size:7px;color:#83a0b8}.kui-badge{display:inline-block;margin-top:4px;border-radius:999px;padding:3px 7px;font-size:7px;font-weight:950}.kui-badge.elite{border:1px solid #8a7828;background:#2a260b;color:#ffe37a}.kui-badge.strong{border:1px solid #315f7c;background:#0a2639;color:#74dbff}.kui-badge.qualified{border:1px solid #486173;background:#17222c;color:#c7d4df}.kui-matchup{display:flex;align-items:center;gap:5px;flex-wrap:wrap;color:#91a7bb;font-size:9px;line-height:1.35;margin-top:10px}.kui-meta{color:#7892a8;font-size:8px;line-height:1.45;margin-top:7px}
.kui-market-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.kui-market-card{border:1px solid #29465f;background:#081725;border-radius:14px;padding:10px}.kui-market-head{display:flex;justify-content:space-between;gap:8px;color:#68dcff;font-size:8px;font-weight:950}.kui-market-pick{display:flex;align-items:center;gap:6px;color:#fff;font-size:13px;font-weight:950;margin-top:6px}.kui-market-side{font-size:9px;color:#c9d8e4;margin-top:4px}.kui-market-match{display:flex;align-items:center;gap:4px;flex-wrap:wrap;color:#8099ad;font-size:8px;margin-top:7px}.kui-score-pill{border:1px solid #315b78;border-radius:999px;color:#7fe0ff;padding:2px 6px;font-size:7px;font-weight:950;white-space:nowrap}
.kui-empty{border:1px dashed #31506b;border-radius:14px;padding:13px;color:#9fb0c0;font-size:10px}
@media(max-width:850px){.kui-stagegrid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:650px){.kui-grid,.kui-market-grid{grid-template-columns:1fr}.kui-master-title{font-size:23px}.kui-card{min-height:0}.kui-stagegrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
""",
        unsafe_allow_html=True,
    )


def _stage_class(games_df, stage):
    pack = previous._pack(games_df, stage)
    if previous._complete(pack):
        return "ready", "✅"
    if pack and previous._metric(stage, pack) > 0:
        return "partial", "🟡"
    if pack and previous._last_error(pack):
        return "blocked", "⛔"
    return "", "⚪"


def _render_stage_pills(games_df):
    cells = []
    for stage, label, _icon in previous.STAGES:
        cls, symbol = _stage_class(games_df, stage)
        cells.append(
            f'<div class="kui-stage {cls}">{symbol}<br>{escape(label)}</div>'
        )
    st.markdown(
        f'<div class="kui-stagegrid">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def _timestamp_key(day):
    return f"dgp_ui_last_ready_v209::{day}"


def _record_ready_timestamp(games_df):
    day = _day(games_df)
    if not day or not previous._all_complete(games_df):
        return None
    state = st.session_state.get(previous._state_key(day)) or {}
    run_id = int(state.get("runs", 0) or 0)
    key = _timestamp_key(day)
    saved = st.session_state.get(key)
    if not isinstance(saved, dict) or int(saved.get("run_id", -1)) != run_id:
        saved = {"ts": _now_et(), "run_id": run_id}
        st.session_state[key] = saved
    return saved.get("ts")


def _render_top_status(games_df):
    day = _day(games_df)
    done = previous._completed_count(games_df)
    ts = _record_ready_timestamp(games_df)
    auto = bool(st.session_state.get(f"dgp_ui_autorefresh_v209::{day}", True))
    refresh_secs = int(st.session_state.get(f"dgp_ui_refreshsecs_v209::{day}", 300) or 300)
    state = st.session_state.get(previous._state_key(day)) or {}
    live_label = "BUILDING" if state.get("active") else ("CARD READY" if done == 7 else f"{done}/7 READY")
    st.markdown(
        f'''<div class="kui-top">
          <div><div class="kui-title">Kyre Sports AI • MLB Daily Card</div>
          <div class="kui-sub">Slate {escape(day)} • Last full build: {escape(_fmt_ts(ts))} • Display refresh: {'ON' if auto else 'OFF'} ({refresh_secs//60}m)</div></div>
          <div class="kui-live">● {escape(live_label)}</div>
        </div>''',
        unsafe_allow_html=True,
    )
    _render_stage_pills(games_df)


def _render_refresh_controls(games_df):
    day = _day(games_df)
    state = st.session_state.get(previous._state_key(day)) or {}
    with st.expander("⚙️ Display & refresh settings", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.toggle(
                "Auto-refresh display",
                value=bool(st.session_state.get(f"dgp_ui_autorefresh_v209::{day}", True)),
                key=f"dgp_ui_autorefresh_v209::{day}",
                help="Reruns the screen only. It never rebuilds a production connector.",
            )
        with c2:
            st.selectbox(
                "Display refresh interval",
                options=[120, 300, 600],
                index={120: 0, 300: 1, 600: 2}.get(int(st.session_state.get(f"dgp_ui_refreshsecs_v209::{day}", 300) or 300), 1),
                format_func=lambda x: f"{x // 60} minutes",
                key=f"dgp_ui_refreshsecs_v209::{day}",
            )
        st.caption(
            "Quota-safe behavior: auto-refresh only rerenders cached UI/state. It does not call Run Line, Total, Moneyline, Pitcher K, H+R+RBI, Home Run, or 1+ Hit builders."
        )

    if (
        st_autorefresh is not None
        and bool(st.session_state.get(f"dgp_ui_autorefresh_v209::{day}", True))
        and not bool(state.get("active"))
    ):
        secs = int(st.session_state.get(f"dgp_ui_refreshsecs_v209::{day}", 300) or 300)
        st_autorefresh(interval=max(120, secs) * 1000, key=f"dgp_ui_tick_v209::{day}")


def _candidate_logo(c):
    market = str(c.get("market") or "")
    name = str(c.get("name") or "")
    team = str(c.get("team") or "")
    if market in {"Moneyline", "Run Line"}:
        team = name
    if team:
        return _img(team, 29)
    return ""


def _matchup_html(matchup):
    away, home = _split_matchup(matchup)
    if not home:
        return escape(away)
    return (
        f'{_img(away, 19)}<span>{escape(away)}</span><span>@</span>'
        f'{_img(home, 19)}<span>{escape(home)}</span>'
    )


def _master_card(c, rank):
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    score = master._finite(c.get("score"))
    tier, tier_cls = _tier(score)
    logo = _candidate_logo(c)
    name = escape(str(c.get("name") or "Candidate"))
    return f'''<div class="kui-card {'first' if rank == 1 else ''}">
      <div class="kui-rank">{medals.get(rank, '•')} DAILY #{rank}</div>
      <div class="kui-market">{escape(str(c.get('market') or ''))}</div>
      <div class="kui-name-row">{logo}<div class="kui-name">{name}</div></div>
      <div class="kui-side">{escape(str(c.get('side') or ''))}</div>
      <div class="kui-score">{score:.1f}<small> /100 PICK STRENGTH</small></div>
      <div class="kui-badge {tier_cls}">{tier}</div>
      <div class="kui-matchup">{_matchup_html(c.get('matchup'))}</div>
      <div class="kui-meta">{escape(str(c.get('first_pitch') or 'TBD'))} ET<br>Model {master._finite(c.get('probability'))*100:.1f}% • Reliability {master._finite(c.get('reliability'))*100:.0f}% • Data {master._finite(c.get('data_quality'))*100:.0f}%</div>
    </div>'''


def _market_leader_cards(candidates):
    parts = []
    for row in master._market_rows(candidates):
        matchup = str(row.get("Matchup") or "")
        pick = str(row.get("Pick") or "")
        market = str(row.get("Market") or "")
        team_for_logo = pick if market in {"Moneyline", "Run Line"} else ""
        logo = _img(team_for_logo, 22) if team_for_logo else ""
        score = master._finite(row.get("Pick Strength"))
        parts.append(
            f'''<div class="kui-market-card">
              <div class="kui-market-head"><span>{escape(market)} • #{int(row.get('Rank') or 0)}</span><span class="kui-score-pill">{score:.1f}</span></div>
              <div class="kui-market-pick">{logo}<span>{escape(pick)}</span></div>
              <div class="kui-market-side">{escape(str(row.get('Side') or ''))} • Model {escape(str(row.get('Model') or '—'))}</div>
              <div class="kui-market-match">{_matchup_html(matchup)}</div>
            </div>'''
        )
    return "".join(parts)


def _render_master_polished(games_df):
    candidates = master._collect_candidates(games_df)
    selected = master._select_master(candidates)
    qualified = [c for c in candidates if master._finite(c.get("score")) >= master.MASTER_MIN_SCORE]
    connected = len({(c.get("game_pk"), c.get("market")) for c in candidates})
    cards = "".join(_master_card(c, i) for i, c in enumerate(selected, 1))
    if not cards:
        cards = '<div class="kui-empty">Build the production connectors above. This view only displays real scored production outputs; it never fabricates a pick.</div>'

    st.markdown(
        f'''<div class="kui-master">
          <div class="kui-kicker">KYRE SPORTS AI • STEP 6 • FINAL CARD</div>
          <div class="kui-master-title">🏆 Daily Master Card — Top 5 MLB Picks</div>
          <div class="kui-master-sub">Market-neutral Pick Strength • minimum 70/100 • maximum one final pick per game • no repeated player across prop families • no forced fifth pick.</div>
          <div class="kui-stats">
            <div class="kui-stat"><b>{len(candidates)}</b> scored candidates</div>
            <div class="kui-stat"><b>{len(qualified)}</b> at 70+</div>
            <div class="kui-stat"><b>{connected}</b> connected game-markets</div>
            <div class="kui-stat"><b>{len(selected)}/{master.MASTER_LIMIT}</b> final picks</div>
          </div>
          <div class="kui-grid">{cards}</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if candidates:
        with st.expander("🎯 Best qualified picks by market", expanded=False):
            leader_html = _market_leader_cards(candidates)
            if leader_html:
                st.markdown(f'<div class="kui-market-grid">{leader_html}</div>', unsafe_allow_html=True)
                st.caption("Up to three qualified candidates per market. Missing or incompatible sportsbook markets stay absent/unscored.")
            else:
                st.info("No market candidate currently clears the 70/100 qualification floor.")
        with st.expander("🧠 Daily Master Card rules", expanded=False):
            st.caption(
                "Presentation-only V2.0.9. Production probabilities, simulation depths, sportsbook lines, market-neutral normalization, per-game Step 5 rankings, and identity firewalls are unchanged."
            )


# Replace Step 6's renderer only; selection/ranking functions stay untouched.
master._render_master = _render_master_polished


def _render_compact_final(games_df):
    if previous._all_complete(games_df):
        _render_master_polished(games_df)
    else:
        st.info("🚀 Build or resume the Full MLB Card above. The compact Final Card will populate automatically from completed production outputs.")
        _render_master_polished(games_df)


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    _inject_css()
    day = _day(games_df)

    # Keep V2.0.7 market-neutral scoring installed before any card is rendered.
    previous.previous.step3.normalize_candidate = previous.previous.normalize_candidate

    _render_top_status(games_df)
    _render_refresh_controls(games_df)

    # Render V2.0.8's production controller once. It handles active one-stage-per-rerun builds.
    previous._render_full_builder(games_df)

    view = st.radio(
        "View",
        options=["🏆 Final Card", "📊 Full Dashboard"],
        horizontal=True,
        key=f"dgp_ui_view_v209::{day}",
        help="Final Card is the clean phone view. Full Dashboard keeps all connector, per-game, audit, and diagnostic detail.",
    )

    if view == "🏆 Final Card":
        _render_compact_final(games_df)
        return None

    st.caption(
        "📊 Full Dashboard • all seven connectors, Step 5 per-game Top 3, audits, diagnostics, and the polished Step 6 Master Card."
    )
    # Bypass V2.0.8's wrapper here so the one-tap controller is not rendered twice.
    return previous.previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
