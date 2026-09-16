"""CFB Game Total Clean Page V3 — exact identity foundation.

Additive over V2. The certified frozen Game Total calculation path still runs
first on the original selected game. V3 then uses only the reconciled display
copy to resolve canonical team identity, exact ESPN IDs/logos, conference/rank,
and game metadata. Missing identity fails closed to IDENTITY CHECK.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v2 as prior
import cfb_game_total_hub_v3 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V3 • V152 EXACT IDENTITY"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_V152_IDENTITY_CSS = r"""
<style>
.gt152-identity{margin:9px 0 10px;padding:10px;border:1px solid rgba(88,150,205,.24);border-radius:16px;background:linear-gradient(145deg,#07131f,#0b1723)}
.gt152-idtop{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}.gt152-idtitle{font-size:.56rem;font-weight:950;letter-spacing:.08em;color:#9fb4c8}.gt152-idbadge{padding:4px 7px;border-radius:999px;font-size:.36rem;font-weight:950}.gt152-idbadge.ok{color:#9cf0c2;border:1px solid rgba(60,207,137,.40);background:rgba(20,91,61,.24)}.gt152-idbadge.check{color:#f2d582;border:1px solid rgba(244,191,77,.40);background:rgba(95,68,19,.24)}
.gt152-idgrid{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:10px;align-items:center}.gt152-teamhero{display:flex;gap:9px;align-items:center;min-width:0;padding:8px;border-radius:12px;background:#0a1824;border:1px solid rgba(110,140,168,.14)}.gt152-teamhero.home{flex-direction:row-reverse;text-align:right}.gt152-teamlogo{width:54px;height:54px;object-fit:contain;flex:0 0 54px}.gt152-monogram{width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#122435;color:#92a8bb;font-size:1rem;font-weight:950;flex:0 0 54px}.gt152-teamtext{min-width:0}.gt152-teamname{color:#f5f9fc;font-size:.86rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt152-teammeta{color:#8fa4b6;font-size:.34rem;line-height:1.45;margin-top:2px}.gt152-at{color:#8c9daf;font-size:.72rem;font-weight:950}.gt152-gamebar{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.gt152-gamecell{padding:6px 7px;border-radius:9px;background:#0a1824;border:1px solid rgba(110,140,168,.12);min-width:0}.gt152-gamecell b{display:block;color:#e7f0f7;font-size:.46rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt152-gamecell span{display:block;color:#6f8496;font-size:.25rem;font-weight:850;text-transform:uppercase;margin-top:2px}
@media(max-width:760px){.gt152-idgrid{grid-template-columns:1fr}.gt152-at{text-align:center}.gt152-teamhero.home{flex-direction:row;text-align:left}.gt152-gamebar{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _first(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean(mapping.get(key))
        if value:
            return value
    return ""


def _rank_label(profile: Mapping[str, Any]) -> str:
    raw: Any = None
    for key in ("ap_rank", "rank", "ranking"):
        if profile.get(key) not in (None, ""):
            raw = profile.get(key)
            break
    if raw in (None, "", 0, "0", "N/A", "n/a", "NR", "Unranked", "UNRANKED"):
        return "UNRANKED"
    text = _clean(raw)
    if not text:
        return "UNRANKED"
    if text.startswith("#"):
        return text
    try:
        number = int(float(text))
        return f"#{number}" if number > 0 else "UNRANKED"
    except (TypeError, ValueError):
        return text.upper()


def _team_identity(
    game: Mapping[str, Any],
    profile: Mapping[str, Any],
    visual: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    team_id = _clean(visual.get("team_id"))
    logo = _clean(visual.get("logo"))
    exact = bool(visual.get("exact_identity")) and team_id.isdigit() and bool(logo)
    team = _clean(profile.get("team")) or _clean(game.get(f"{side}_team")) or side.title()
    conference = (
        _clean(profile.get("conference"))
        or _clean(game.get(f"{side}_conference"))
        or "Conference unavailable"
    )
    return {
        "team": team,
        "team_id": team_id if exact else "",
        "logo": logo if exact else "",
        "exact_identity": exact,
        "conference": conference,
        "rank": _rank_label(profile),
    }


def _identity_state(
    display_game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    visuals: Mapping[str, Any],
) -> dict[str, Any]:
    away_state = _team_identity(
        display_game,
        away,
        visuals.get("away") if isinstance(visuals.get("away"), Mapping) else {},
        "away",
    )
    home_state = _team_identity(
        display_game,
        home,
        visuals.get("home") if isinstance(visuals.get("home"), Mapping) else {},
        "home",
    )
    verified = bool(away_state["exact_identity"] and home_state["exact_identity"])
    return {
        "verified": verified,
        "status_label": "IDENTITY VERIFIED" if verified else "IDENTITY CHECK",
        "away": away_state,
        "home": home_state,
        "kickoff": _first(
            display_game,
            "kickoff_display",
            "kickoff_et",
            "kickoff",
            "game_time",
            "time",
        ) or "Kickoff unavailable",
        "venue": _first(display_game, "venue", "venue_name", "stadium") or "Venue unavailable",
        "broadcast": _first(display_game, "broadcast", "network", "tv") or "Broadcast unavailable",
        "game_status": _first(display_game, "status", "game_status") or "Status unavailable",
    }


def _monogram(team: str) -> str:
    letters = "".join(part[:1] for part in team.split() if part)[:2].upper()
    return letters or "CF"


def _team_hero(team: Mapping[str, Any], side: str) -> str:
    logo = _clean(team.get("logo"))
    name = _clean(team.get("team")) or side.title()
    image = (
        f'<img class="gt152-teamlogo" data-testid="gt152-{side}-logo" src="{escape(logo)}" alt="{escape(name)} logo">'
        if logo
        else f'<div class="gt152-monogram" data-testid="gt152-{side}-logo-missing">{escape(_monogram(name))}</div>'
    )
    return f"""
<div class="gt152-teamhero {'home' if side == 'home' else ''}" data-testid="gt152-{side}-hero">
  {image}
  <div class="gt152-teamtext">
    <div class="gt152-teamname">{escape(name)}</div>
    <div class="gt152-teammeta">{escape(_clean(team.get('rank')))} • {escape(_clean(team.get('conference')))}</div>
    <div class="gt152-teammeta">ESPN ID: {escape(_clean(team.get('team_id')) or 'unavailable')}</div>
  </div>
</div>
"""


def _identity_panel(state: Mapping[str, Any]) -> str:
    verified = bool(state.get("verified"))
    badge_class = "ok" if verified else "check"
    return f"""
<div class="gt152-identity" data-testid="gt152-identity-panel">
  <div class="gt152-idtop">
    <div class="gt152-idtitle">TEAM IDENTITY FOUNDATION • EXACT ESPN IDs ONLY</div>
    <div class="gt152-idbadge {badge_class}" data-testid="gt152-identity-status">{escape(_clean(state.get('status_label')))}</div>
  </div>
  <div class="gt152-idgrid">
    {_team_hero(state.get('away') or {}, 'away')}
    <div class="gt152-at">@</div>
    {_team_hero(state.get('home') or {}, 'home')}
  </div>
  <div class="gt152-gamebar">
    <div class="gt152-gamecell"><b>{escape(_clean(state.get('kickoff')))}</b><span>Kickoff</span></div>
    <div class="gt152-gamecell"><b>{escape(_clean(state.get('venue')))}</b><span>Venue</span></div>
    <div class="gt152-gamecell"><b>{escape(_clean(state.get('broadcast')))}</b><span>Broadcast</span></div>
    <div class="gt152-gamecell"><b>{escape(_clean(state.get('game_status')))}</b><span>Status</span></div>
  </div>
</div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(prior.prior._CSS + prior._V151_CSS + _V152_IDENTITY_CSS, unsafe_allow_html=True)
    st.markdown(
        """
<div class="gt151-head">
  <div class="gt151-kicker">CFB GAME TOTAL • V152 PRODUCTION ACTIVE • EXACT IDENTITY</div>
  <div class="gt151-title">🏁 College Football Game Total • Monster Dashboard</div>
  <div class="gt151-sub">Exact team identity is verified before the display claims success. Frozen Step-11/12 Game Total math remains untouched.</div>
  <div class="gt151-chips"><span class="gt151-chip live">V152 PRODUCTION ACTIVE ✅</span><span class="gt151-chip purple">FROZEN MODEL ✅</span><span class="gt151-chip live">EXACT-ID LOGOS</span><span class="gt151-chip amber">SPORTSBOOK 0.0%</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(prior.prior._PHOENIX).date(),
        key="cfb_v152_game_total_date",
    )
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V152 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v152_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # CERTIFIED MODEL PATH: analyze the original selected game first.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY PATH: reconcile a copy only; it can never feed frozen calculations.
    display_game, display_away, display_home, display_diag = prior._display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = _identity_state(display_game, display_away, display_home, visuals)

    st.markdown(_identity_panel(identity), unsafe_allow_html=True)
    st.markdown(prior.prior._quick_read(raw, final), unsafe_allow_html=True)
    st.markdown(prior._live_evidence(display_game, display_away, display_home, display_diag), unsafe_allow_html=True)
    prior._evidence_locker(display_game, display_away, display_home, display_diag)
    st.markdown(prior.prior._status_cards(raw, final), unsafe_allow_html=True)

    with st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False):
        st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
        for panel in (
            frozen_page.frozen_v2._band_panel(raw),
            frozen_page.frozen_v2._around_projection_panel(raw),
            frozen_page.frozen_v2._exact_panel(raw),
            frozen_page.frozen_v2._components_panel(raw),
        ):
            if panel:
                st.markdown(panel, unsafe_allow_html=True)

    with st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False):
        st.markdown(frozen_page._final_card(game, final), unsafe_allow_html=True)

    with st.expander("🏆 Top-5 slate scanner", expanded=False):
        scan_key = f"cfb_v152_top5_{selected_day}"
        diag_key = f"cfb_v152_scan_diag_{selected_day}"
        if st.button(
            "Run final Game Total Top-5 scan",
            type="primary",
            key=f"cfb_v152_scan_button_{selected_day}",
        ):
            with st.spinner("Scanning the verified CFB slate through frozen Steps 11–12..."):
                rows, diag = frozen_page.slate.scan_slate(games, selected_day)
                st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5)
                st.session_state[diag_key] = diag

        top5 = st.session_state.get(scan_key) or []
        diag = st.session_state.get(diag_key) or {}
        if diag:
            st.caption(
                f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • "
                f"{int(diag.get('final_ready') or 0)} final-ready • "
                f"{int(diag.get('qualified_forecasts') or 0)} ranked-eligible • "
                f"{len(diag.get('errors') or [])} errors"
            )
        if top5:
            for row in top5:
                st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
        elif diag:
            st.warning("No game cleared the frozen Step-12 qualification thresholds. V152 will not force a Top-5.")
        else:
            st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V152 display identity only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V152 Game Total page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_identity_state",
    "render_cfb_hub",
    "render_game_total_hub",
]
