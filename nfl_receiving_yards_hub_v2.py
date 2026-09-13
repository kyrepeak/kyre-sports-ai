"""NFL Receiving Yards V2 — Page Build Step 2 receiver player cards.

Additive over frozen Receiving Yards V1. V2 connects the certified production
Receiving Yards context API and renders player-first receiver identity cards
for exact ESPN WR/TE/RB/FB athletes. Step 2 intentionally stops before summary
metrics, volume/efficiency analysis, opponent pass-defense presentation,
player-vs-team history, projection, sportsbook markets, probability, EV,
ranking, recommendation, staking, or wager actions.

Permanent safety:
- Receiving V1 remains unchanged;
- certified Passing and Rushing chains remain unchanged;
- exact ESPN event/team/athlete IDs only;
- names, headshots and team logos are display-only;
- no fuzzy matching or synthetic IDs;
- targets are display-status only here and never inferred;
- sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import re
from typing import Any

import pandas as pd
import streamlit as st

from nfl_hub_v1 import ET, load_nfl_slate
import nfl_receiving_yards_context_api_v1 as receiving_context_api
import nfl_receiving_yards_hub_v1 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V2 • PAGE BUILD STEP 2 • RECEIVER PLAYER CARDS"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v1"
PAGE_BUILD_STEP = 2
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_TEAM_ABBR_RE = re.compile(r"^[A-Z]{2,4}$")

_STEP2_CSS = r'''
<style>
.krecv-fill{width:20%!important}
.krecv2-banner{border:1px solid #315940;border-radius:14px;background:#0e1b14;padding:10px 12px;margin:12px 0 9px;color:#9ecfaf;font-size:.63rem;line-height:1.5}
.krecv2-match{border:1px solid #263d31;border-radius:14px;background:#0b1611;padding:10px 11px;margin:8px 0 11px}.krecv2-match b{color:#eef7f1;font-size:.70rem}.krecv2-match span{color:#71877a;font-size:.54rem;margin-left:6px}
.krecv2-teamhead{display:flex;align-items:center;gap:8px;margin:14px 0 7px}.krecv2-teamhead img{width:30px;height:30px;object-fit:contain;border:1px solid #294335;border-radius:9px;background:#09150f;padding:3px;box-sizing:border-box}.krecv2-teamhead b{color:#edf6f0;font-size:.83rem}.krecv2-teamhead span{display:block;color:#718679;font-size:.50rem;margin-top:2px}
.krecv2-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-bottom:12px}
.krecv2-card{position:relative;overflow:hidden;border:1px solid #2b4b39;border-radius:17px;background:linear-gradient(145deg,#0b1712 0%,#0a1411 70%,#0d1a14 100%);padding:10px 11px;min-width:0}
.krecv2-card:after{content:"";position:absolute;right:-28px;bottom:-55px;width:130px;height:130px;border:1px solid rgba(139,226,172,.055);border-radius:50%;box-shadow:0 0 0 18px rgba(139,226,172,.018)}
.krecv2-top{position:relative;z-index:1;display:flex;align-items:center;gap:9px;min-width:0}.krecv2-head{width:54px;height:54px;flex:0 0 54px;border:1px solid #355b45;border-radius:50%;overflow:hidden;background:#09140f;display:flex;align-items:flex-end;justify-content:center}.krecv2-head img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.krecv2-ident{min-width:0;flex:1}.krecv2-name{color:#f6faf7;font-size:.83rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv2-meta{color:#7d9285;font-size:.51rem;line-height:1.45;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv2-teamlogo{width:36px;height:36px;flex:0 0 36px;border:1px solid #284334;border-radius:10px;background:#09150f;padding:4px;box-sizing:border-box;object-fit:contain}
.krecv2-badges{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}.krecv2-badge{display:inline-flex;align-items:center;border:1px solid #3c6a4d;background:#0f2418;color:#8be2ac;border-radius:999px;padding:3px 6px;font-size:.43rem;font-weight:950;letter-spacing:.04em}.krecv2-badge.blue{border-color:#435e76;background:#111e29;color:#a9c5df}.krecv2-badge.gold{border-color:#6d613a;background:#241f12;color:#dcc06d}
.krecv2-body{position:relative;z-index:1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:9px}.krecv2-cell{border-top:1px solid #1e3528;padding-top:7px;min-width:0}.krecv2-cell b{display:block;color:#dfeae2;font-size:.66rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv2-cell span{display:block;color:#617568;font-size:.42rem;text-transform:uppercase;font-weight:900;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv2-foot{position:relative;z-index:1;border-top:1px solid #1a2d22;margin-top:7px;padding-top:6px;color:#6f8477;font-size:.46rem;line-height:1.45}.krecv2-foot strong{color:#91cda4}
.krecv2-guard{border-left:3px solid #6a88a7;background:#101922;border-radius:8px;padding:9px 11px;color:#92a7ba;font-size:.61rem;line-height:1.45;margin-top:12px}
@media(max-width:760px){.krecv2-grid{grid-template-columns:1fr}.krecv2-card{padding:9px 10px}.krecv2-head{width:48px;height:48px;flex-basis:48px}.krecv2-body{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _headshot_url(athlete_id: Any) -> str:
    athlete_id = _safe(athlete_id, "")
    if not athlete_id.isdigit():
        return ""
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png"


def _team_logo_url(abbr: Any) -> str:
    abbr = _safe(abbr, "").upper()
    if _TEAM_ABBR_RE.fullmatch(abbr) is None:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"


def _player_card(player: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any]) -> str:
    athlete_id = _safe(player.get("official_athlete_id"), "")
    team_id = _safe(player.get("official_team_id"), "")
    player_name = _safe(player.get("player_name"), "Unknown receiver")
    position = _safe(player.get("position"), "REC").upper()
    team_abbr = _safe(team.get("team_abbreviation"), "NFL").upper()
    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()
    baseline = _safe(player.get("baseline_season"), _safe(team.get("player_baseline_season")))
    sample_games = _safe(player.get("sample_games"), "0")
    targets_live = player.get("targets_data_available") is True
    target_badge = "ESPN TARGETS VERIFIED" if targets_live else "TARGETS NOT PUBLISHED"
    target_class = "blue" if targets_live else "gold"

    headshot = _headshot_url(athlete_id)
    logo = _team_logo_url(team_abbr)
    head_html = (
        f'<div class="krecv2-head"><img src="{escape(headshot, quote=True)}" alt="{escape(player_name, quote=True)} headshot" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"></div>'
        if headshot else '<div class="krecv2-head"></div>'
    )
    logo_html = (
        f'<img class="krecv2-teamlogo" src="{escape(logo, quote=True)}" alt="{escape(team_abbr, quote=True)} logo" loading="lazy" decoding="async" onerror="this.style.display=\'none\'">'
        if logo else ""
    )

    return f'''
    <article class="krecv2-card">
      <div class="krecv2-top">
        {head_html}
        <div class="krecv2-ident">
          <div class="krecv2-name">{escape(player_name)}</div>
          <div class="krecv2-meta">{escape(position)} • {escape(team_abbr)} vs {escape(opponent_abbr)}</div>
          <div class="krecv2-badges">
            <span class="krecv2-badge">EXACT-ID RECEIVER</span>
            <span class="krecv2-badge {target_class}">{escape(target_badge)}</span>
          </div>
        </div>
        {logo_html}
      </div>
      <div class="krecv2-body">
        <div class="krecv2-cell"><b>{escape(athlete_id)}</b><span>ESPN Athlete ID</span></div>
        <div class="krecv2-cell"><b>{escape(baseline)}</b><span>Baseline Season</span></div>
        <div class="krecv2-cell"><b>{escape(sample_games)}</b><span>Verified Games</span></div>
      </div>
      <div class="krecv2-foot">ESPN team <strong>{escape(team_id)}</strong> • name/headshot/logo display-only • no fuzzy matching • sportsbook projection influence <strong>0.0%</strong></div>
    </article>
    '''


def _team_map(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for team in context.get("teams") or []:
        if not isinstance(team, dict):
            continue
        team_id = _safe(team.get("official_team_id"), "")
        if team_id.isdigit():
            out[team_id] = team
    return out


@st.cache_data(ttl=60, show_spinner=False)
def _load_receiving_context(event_id: str) -> dict[str, Any]:
    return receiving_context_api.fetch_event_context(str(event_id))


def _render_player_board(games: pd.DataFrame) -> None:
    st.markdown(
        '<div class="krecv-section"><h3>🎯 Step 2 • Receiver Player Cards</h3><span>LIVE KYRE API • EXACT ESPN IDs</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="krecv2-banner">✅ The certified production Receiving Yards API is now connected to this page. Select a verified matchup to load current-roster WR/TE/RB/FB identities, ESPN headshots, team logos and baseline sample labels. Summary statistics stay reserved for Step 3.</div>',
        unsafe_allow_html=True,
    )

    verified = games.copy()
    if "game_id" not in verified.columns:
        st.warning("Verified slate did not expose an official ESPN event ID, so Step 2 is staying fail-closed.")
        return
    verified["game_id"] = verified["game_id"].astype(str).str.strip()
    verified = verified[verified["game_id"].str.fullmatch(r"\d+")].copy()
    if verified.empty:
        st.warning("No exact numeric ESPN event IDs survived the slate contract, so Step 2 is staying fail-closed.")
        return

    labels: dict[str, str] = {}
    rows_by_event: dict[str, dict[str, Any]] = {}
    for _, row in verified.iterrows():
        event_id = _safe(row.get("game_id"), "")
        labels[event_id] = (
            f"{_safe(row.get('away_abbr'), 'AWY')} @ {_safe(row.get('home_abbr'), 'HME')}"
            f" • {_safe(row.get('tip_et'), 'TBD')} • ESPN {event_id}"
        )
        rows_by_event[event_id] = row.to_dict()

    selected_event_id = st.selectbox(
        "🎯 Receiver research matchup",
        options=list(labels),
        format_func=lambda value: labels.get(value, value),
        key="nfl_receiving_yards_step2_event",
    )

    with st.spinner("🎯 Loading exact-ID receiver identities from the Kyre Sports API…"):
        context = _load_receiving_context(selected_event_id)

    if context.get("ready") is not True:
        st.warning(
            "Receiving Yards context failed closed. No player values were guessed. "
            f"Reason: {context.get('reason') or 'production API unavailable'}"
        )
        return
    if context.get("data_available") is not True:
        st.info(
            "The event identity and API contract are verified, but no current-roster receiver profiles are available yet. "
            "No synthetic fallback is shown."
        )
        return

    event_row = rows_by_event.get(selected_event_id, {})
    st.markdown(
        '<div class="krecv2-match">'
        f'<b>{escape(_safe(event_row.get("away_team"), "Away"))} @ {escape(_safe(event_row.get("home_team"), "Home"))}</b>'
        f'<span>ESPN event {escape(selected_event_id)} • {_safe(event_row.get("game_date"), "—")}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    teams = context.get("teams") or []
    teams = sorted(teams, key=lambda item: 0 if _safe(item.get("home_away"), "").lower() == "away" else 1)
    team_lookup = _team_map(context)
    for team in teams:
        team_id = _safe(team.get("official_team_id"), "")
        opponent_id = _safe(team.get("opponent_official_team_id"), "")
        opponent = team_lookup.get(opponent_id, {})
        abbr = _safe(team.get("team_abbreviation"), "NFL").upper()
        name = _safe(team.get("team_name"), abbr)
        logo = _team_logo_url(abbr)
        logo_html = (
            f'<img src="{escape(logo, quote=True)}" alt="{escape(abbr, quote=True)} logo" loading="lazy" decoding="async">'
            if logo else ""
        )
        players = team.get("players") or []
        st.markdown(
            '<div class="krecv2-teamhead">'
            f'{logo_html}<div><b>{escape(abbr)} • {escape(name)}</b>'
            f'<span>ESPN team {escape(team_id)} • {len(players)} verified receiver profile{"s" if len(players) != 1 else ""}</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if not players:
            st.info(f"No exact-ID receiver profile is available for {abbr} yet.")
            continue
        cards = "".join(_player_card(player, team, opponent) for player in players)
        st.markdown(f'<div class="krecv2-grid">{cards}</div>', unsafe_allow_html=True)

    stamp = _safe(context.get("captured_at_utc"), "—")
    attempts = _safe(context.get("request_attempts"), "—")
    st.caption(
        f"✅ Schema {receiving_context_api.SCHEMA_VERSION} • official ESPN event {selected_event_id} • "
        f"captured {stamp} • request attempts {attempts} • sportsbook influence 0.0%"
    )
    if context.get("source_note"):
        st.caption(f"Source note: {context.get('source_note')}")


def _render_hero_v2() -> None:
    st.markdown(
        prior._RECV_CSS
        + _STEP2_CSS
        + '<div class="krecv-hero">'
        + '<div class="krecv-kicker">NFL RECEIVING YARDS • MONSTER BUILD</div>'
        + '<div class="krecv-title">🎯 Receiving Yards <span>Receiver Lab</span></div>'
        + '<div class="krecv-sub">Step 2 connects the certified Kyre Sports API and adds exact-ID receiver cards with player headshots, team logos and verified baseline identity. Summary metrics, opponent defense, player-vs-team history, projections and FanDuel markets remain locked for their own steps.</div>'
        + '<div class="krecv-chiprow">'
        + '<span class="krecv-chip">✅ VERIFIED SLATE</span>'
        + '<span class="krecv-chip">✅ RECEIVER CARDS</span>'
        + '<span class="krecv-chip">🏈 EXACT ESPN IDs</span>'
        + '<span class="krecv-chip lock">🔒 SUMMARY METRICS NEXT</span>'
        + '<span class="krecv-chip lock">SPORTSBOOK INFLUENCE 0.0%</span>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="krecv-board">'
        '<div class="krecv-tool live"><div class="icon">🏈</div><b>Verified Slate ✅</b><span>Exact ESPN event/team schedule identity.</span></div>'
        '<div class="krecv-tool live"><div class="icon">👤</div><b>Receiver Cards ✅</b><span>Exact-ID WR/TE/RB/FB profiles and display visuals.</span></div>'
        '<div class="krecv-tool"><div class="icon">📊</div><b>Summary Metrics</b><span>Receptions, yards and efficiency arrive in Step 3.</span></div>'
        '<div class="krecv-tool"><div class="icon">🧠</div><b>Projection + Market</b><span>Still locked until later certified steps.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    stages = [
        (1, "SLATE", True),
        (2, "PLAYER CARDS", True),
        (3, "SUMMARY", False),
        (4, "VOLUME", False),
        (5, "DEFENSE + H2H", False),
        (6, "PROJECTION", False),
        (7, "SUPPORT", False),
        (8, "FANDUEL", False),
        (9, "TIERS", False),
        (10, "FINAL", False),
    ]
    stage_html = "".join(
        f'<span class="krecv-stage{" on" if live else ""}">{num} • {label}{" ✅" if live else ""}</span>'
        for num, label, live in stages
    )
    st.markdown(
        '<div class="krecv-progress">'
        '<div class="krecv-progress-top"><b>Receiving Yards page build</b><span>STEP 2 OF 10 • PLAYER CARDS LIVE</span></div>'
        '<div class="krecv-track"><div class="krecv-fill"></div></div>'
        f'<div class="krecv-stage-row">{stage_html}</div></div>',
        unsafe_allow_html=True,
    )


def render_nfl_receiving_yards_hub() -> None:
    _render_hero_v2()

    if "nfl_receiving_yards_v2_date" not in st.session_state:
        st.session_state["nfl_receiving_yards_v2_date"] = datetime.now(ET).date()
    day = st.date_input(
        "📅 NFL slate date",
        value=st.session_state["nfl_receiving_yards_v2_date"],
        key="nfl_receiving_yards_v2_date_input",
    )
    st.session_state["nfl_receiving_yards_v2_date"] = day
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    with st.spinner("🎯 Verifying Receiving Yards NFL slate…"):
        games, diag = load_nfl_slate(day_str)
    prior._render_schedule(games, day_str, diag)

    if diag.get("request_ok") and not games.empty:
        _render_player_board(games)

    st.markdown(
        '<div class="krecv2-guard"><strong>Step 2 safety lock:</strong> Receiving player cards are read-only exact-ID context. Summary metrics, volume/efficiency interpretation, opponent pass-defense presentation, player-vs-team history, projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.</div>',
        unsafe_allow_html=True,
    )


def render_nfl_hub(market: str = prior.RECEIVING_YARDS_MARKET) -> None:
    if str(market or prior.RECEIVING_YARDS_MARKET) != prior.RECEIVING_YARDS_MARKET:
        raise ValueError("NFL Receiving Yards V2 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_headshot_url",
    "_load_receiving_context",
    "_player_card",
    "_render_player_board",
    "_team_logo_url",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
