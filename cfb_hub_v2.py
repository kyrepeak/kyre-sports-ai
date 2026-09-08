"""College Football hub V2 — Step 2 official schedule + game identity.

Builds additively on permanently frozen CFB Hub V1. This step adds only:
- date-scoped FBS schedule loading,
- NCAA contest/team identity,
- home/away + conference + kickoff + venue/status display,
- duplicate/off-date protection and provider diagnostics.

No CFB projection/model output is produced in Step 2.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_hub_v1 as frozen_v1
import cfb_schedule_v1 as schedule

MODEL_VERSION = "CFB HUB V2 • STEP 2 OFFICIAL SCHEDULE + GAME IDENTITY"
FROZEN_CFB_HUB = "cfb_hub_v1"
CFB_MARKETS = list(frozen_v1.CFB_MARKETS)

_ET = ZoneInfo("America/New_York")

_PAGE_META = {
    "Moneyline": ("🏆", "College Football Moneyline", "Winner probability and team-vs-team analysis."),
    "Over/Under": ("↕️", "College Football Over/Under", "Sportsbook total-line analysis and scoring environment."),
    "Game Total": ("🧮", "College Football Game Total", "Independent combined-score distribution and total projection."),
}

_CSS = r"""
<style>
.cfb2-shell{border:1px solid rgba(56,189,248,.24);border-radius:16px;padding:15px;
background:linear-gradient(145deg,#0b1724,#09111a);margin-top:8px}
.cfb2-kicker{color:#65d7ff;font-size:.64rem;font-weight:950;letter-spacing:.10em}
.cfb2-title{color:#f8fbff;font-size:1.35rem;font-weight:950;margin-top:4px}
.cfb2-sub{color:#98aabd;font-size:.78rem;margin-top:4px}
.cfb2-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:11px}
.cfb2-badge{border:1px solid #2b465a;border-radius:999px;background:#0a1a27;
padding:5px 8px;color:#a9c4d6;font-size:.57rem;font-weight:900}
.cfb2-badge.good{border-color:#277353;background:#0a3024;color:#83e7b6}
.cfb2-badge.warn{border-color:#77611c;background:#342b0d;color:#f5db73}
.cfb2-game{margin-top:10px;border:1px solid rgba(56,189,248,.24);border-radius:16px;
background:linear-gradient(145deg,#071522,#08101a);overflow:hidden}
.cfb2-head{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap;
padding:10px 12px;border-bottom:1px solid rgba(91,140,166,.22)}
.cfb2-head b{color:#79dcff;font-size:.58rem;letter-spacing:.08em}
.cfb2-verified{border:1px solid #277353;border-radius:999px;background:#0a3024;color:#83e7b6;
padding:5px 8px;font-size:.50rem;font-weight:950}
.cfb2-match{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;
align-items:center;padding:14px 12px}
.cfb2-team{min-width:0}.cfb2-team.home{text-align:right}
.cfb2-team .conf{color:#7892a4;font-size:.54rem;font-weight:850;text-transform:uppercase}
.cfb2-team .name{color:#f3f8fb;font-size:.90rem;font-weight:950;line-height:1.15;margin-top:2px}
.cfb2-at{color:#6d8595;font-size:.70rem;font-weight:950}
.cfb2-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:0 12px 12px}
.cfb2-item{border:1px solid rgba(91,140,166,.20);border-radius:10px;background:#081722;
padding:8px;color:#a7bac7;font-size:.57rem;line-height:1.4}
.cfb2-item strong{display:block;color:#e0ebf2;font-size:.48rem;letter-spacing:.06em;
text-transform:uppercase;margin-bottom:2px}
.cfb2-source{padding:8px 12px;border-top:1px solid rgba(91,140,166,.18);
color:#6f8797;font-size:.47rem;line-height:1.4}
@media(max-width:700px){
  .cfb2-shell{padding:13px}.cfb2-title{font-size:1.18rem}
  .cfb2-match{gap:5px}.cfb2-team .name{font-size:.74rem}.cfb2-grid{grid-template-columns:1fr}
}
</style>
"""


def _rank_prefix(rank: Any) -> str:
    try:
        value = int(rank)
        if value > 0:
            return f"#{value} "
    except Exception:
        pass
    return ""


def _matchup_label(game: Mapping[str, Any]) -> str:
    return (
        f"{_rank_prefix(game.get('away_rank'))}{game.get('away_team', 'Away')} "
        f"@ {_rank_prefix(game.get('home_rank'))}{game.get('home_team', 'Home')} "
        f"• {game.get('kickoff_et', 'TBD')}"
    )


def _game_card(game: Mapping[str, Any]) -> str:
    verified = bool(game.get("identity_verified") and game.get("date_matches_query"))
    grade = "IDENTITY VERIFIED" if verified else "CHECK IDENTITY"
    away = escape(str(game.get("away_team") or "Away"))
    home = escape(str(game.get("home_team") or "Home"))
    away_conf = escape(str(game.get("away_conference") or "Conference unavailable"))
    home_conf = escape(str(game.get("home_conference") or "Conference unavailable"))
    gid = escape(str(game.get("game_id") or "—"))
    kickoff = escape(str(game.get("kickoff_et") or "TBD"))
    venue = escape(str(game.get("venue") or "Venue unavailable"))
    status = escape(str(game.get("status") or "Status unavailable"))
    broadcast = escape(str(game.get("broadcast") or "Broadcast unavailable"))
    identity = escape(str(game.get("identity_key") or "—"))
    espn_id = escape(str(game.get("espn_event_id") or "not matched"))
    source = escape(str(game.get("schedule_source") or "source unavailable"))
    enrich = escape(str(game.get("enrichment_source") or "none"))
    neutral = "YES" if bool(game.get("neutral_site")) else "NO"

    return f"""
<div class="cfb2-game">
  <div class="cfb2-head">
    <b>STEP 2 • OFFICIAL SCHEDULE + GAME IDENTITY</b>
    <span class="cfb2-verified">{grade}</span>
  </div>
  <div class="cfb2-match">
    <div class="cfb2-team">
      <div class="conf">{away_conf}</div>
      <div class="name">{escape(_rank_prefix(game.get('away_rank')))}{away}</div>
    </div>
    <div class="cfb2-at">@</div>
    <div class="cfb2-team home">
      <div class="conf">{home_conf}</div>
      <div class="name">{escape(_rank_prefix(game.get('home_rank')))}{home}</div>
    </div>
  </div>
  <div class="cfb2-grid">
    <div class="cfb2-item"><strong>Kickoff</strong>{kickoff}</div>
    <div class="cfb2-item"><strong>Venue</strong>{venue}</div>
    <div class="cfb2-item"><strong>Game status</strong>{status}</div>
    <div class="cfb2-item"><strong>Broadcast</strong>{broadcast}</div>
    <div class="cfb2-item"><strong>NCAA contest ID</strong>{gid}</div>
    <div class="cfb2-item"><strong>Stable identity key</strong>{identity}</div>
    <div class="cfb2-item"><strong>Neutral site</strong>{neutral}</div>
    <div class="cfb2-item"><strong>ESPN enrichment ID</strong>{espn_id}</div>
  </div>
  <div class="cfb2-source">
    Primary: {source} • enrichment: {enrich} • current schedule snapshot guards against
    duplicate/off-date rows • Step 2 makes no betting projection adjustment.
  </div>
</div>
"""


def _diagnostic_badges(diag: Mapping[str, Any]) -> str:
    games = int(diag.get("games") or 0)
    dup = int(diag.get("duplicate_event_ids_dropped") or 0) + int(
        diag.get("duplicate_identity_rows_dropped") or 0
    )
    enriched = int(diag.get("espn_matches") or 0)
    ready = bool(diag.get("identity_ready"))
    return f"""
<div class="cfb2-badges">
  <span class="cfb2-badge {'good' if ready else 'warn'}">IDENTITY {'READY' if ready else 'CHECK'}</span>
  <span class="cfb2-badge">{games} GAMES</span>
  <span class="cfb2-badge">{enriched} VENUE/STATUS MATCHES</span>
  <span class="cfb2-badge {'good' if dup == 0 else 'warn'}">{dup} DUPLICATES DROPPED</span>
  <span class="cfb2-badge good">OFF-DATE GUARD ACTIVE</span>
</div>
"""


def _attempt_summary(diag: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for attempt in diag.get("attempts") or []:
        rows.append(
            {
                "Provider": attempt.get("provider"),
                "Transport": attempt.get("transport"),
                "HTTP": attempt.get("http"),
                "Bytes": attempt.get("bytes"),
                "Error": attempt.get("error"),
            }
        )
    return rows


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render CFB Step 2 schedule + identity for the selected market."""
    if market not in CFB_MARKETS:
        st.error(f"Unknown College Football market: {market}")
        return

    icon, title, subtitle = _PAGE_META[market]
    st.caption("🏈 COLLEGE FOOTBALL • Step 2 official schedule + game identity ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="cfb2-shell">
  <div class="cfb2-kicker">CFB STEP 2 • VERIFIED DATA FOUNDATION</div>
  <div class="cfb2-title">{icon} {title}</div>
  <div class="cfb2-sub">{subtitle}</div>
  <div class="cfb2-badges">
    <span class="cfb2-badge good">ROUTE ✅</span>
    <span class="cfb2-badge good">PAGE ✅</span>
    <span class="cfb2-badge good">SCHEDULE + ID ✅</span>
    <span class="cfb2-badge">MODEL ⏳</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_et = datetime.now(_ET).date()
    selected = st.date_input(
        "📅 CFB slate date",
        value=today_et,
        key=f"cfb_step2_date_{market.lower().replace('/', '_').replace(' ', '_')}",
        help="Loads the latest NCAA FBS schedule snapshot for this date.",
    )
    selected_day = selected.isoformat()

    games, diag = schedule.load_with_diagnostics(selected_day)
    st.markdown(_diagnostic_badges(diag), unsafe_allow_html=True)

    if not games:
        st.warning(
            "No verified FBS games were returned for this date. Step 2 fails closed here—"
            "no matchup IDs, projections, picks, or totals will be invented."
        )
        attempts = _attempt_summary(diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Matchup",
        options=list(range(len(games))),
        format_func=lambda i: _matchup_label(games[int(i)]),
        key=f"cfb_step2_matchup_{market.lower().replace('/', '_').replace(' ', '_')}_{selected_day}",
    )
    game = games[int(index)]
    st.markdown(_game_card(game), unsafe_allow_html=True)

    with st.expander(f"Full verified slate • {selected_day}"):
        rows = [
            {
                "Matchup": f"{g.get('away_team')} @ {g.get('home_team')}",
                "Kickoff ET": g.get("kickoff_et"),
                "Away conf": g.get("away_conference"),
                "Home conf": g.get("home_conference"),
                "Venue": g.get("venue"),
                "Status": g.get("status"),
                "NCAA ID": g.get("game_id"),
            }
            for g in games
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    st.info(
        "Step 2 is data/identity only. College Football win probabilities, projected scores, "
        "Over/Under probabilities, fair odds, rankings, and Monte Carlo simulations are still OFF."
    )


__all__ = [
    "CFB_MARKETS",
    "FROZEN_CFB_HUB",
    "MODEL_VERSION",
    "_diagnostic_badges",
    "_game_card",
    "_matchup_label",
    "render_cfb_hub",
]
