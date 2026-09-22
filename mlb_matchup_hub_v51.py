"""MLB Matchup Explorer V5.5 — cleanup Step 11 stable game/player selectors.

Presentation-only wrapper over certified Cleanup Step 10. Replaces the stateful
multi-card browsing controls with a deterministic two-step selector scoped to the
currently selected game, shows every selected matchup in Phoenix local time with
MLB team logos, and hardens the Player Spotlight HTML so bench players cannot
spill raw markup into Streamlit. All projection, probability, calibration,
ranking, Monte Carlo, router and Moneyline logic remains delegated unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
import html
import re
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v45 as step4
import mlb_matchup_hub_v46 as step5
import mlb_matchup_hub_v49 as step9
import mlb_matchup_hub_v50 as step10
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.5 • Cleanup Step 11"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP9_PRESENTATION = "mlb_matchup_hub_v49"
FROZEN_STEP10_PRESENTATION = "mlb_matchup_hub_v50"

_EASTERN = ZoneInfo("America/New_York")
_PHOENIX = ZoneInfo("America/Phoenix")

_STEP11_CSS = r"""
<style>
.mx51-finder{border:1px solid #284d70;background:linear-gradient(145deg,#0b1726,#08111c);border-radius:18px;padding:12px 13px;margin:4px 0 8px}
.mx51-finder-title{font-size:.92rem;font-weight:950;color:#f5f9fd;letter-spacing:-.015em}
.mx51-finder-sub{font-size:.55rem;color:#7896af;margin-top:2px;line-height:1.4}
.mx51-game{border:1px solid #2b5277;background:radial-gradient(circle at 50% 0%,rgba(47,120,190,.12),transparent 42%),#091521;border-radius:18px;padding:11px 12px;margin:7px 0 9px}
.mx51-teams{display:grid;grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr);align-items:center;gap:6px}
.mx51-team{min-width:0;text-align:center;color:#eef6fc;font-size:.67rem;font-weight:900;line-height:1.25}
.mx51-logo{width:42px;height:42px;object-fit:contain;display:block;margin:0 auto 4px}
.mx51-at{text-align:center;color:#688aa7;font-size:.60rem;font-weight:950}
.mx51-game-meta{text-align:center;margin-top:8px;color:#8ba4ba;font-size:.55rem;line-height:1.5}
.mx51-phx{color:#69d9ff;font-weight:900}.mx51-starters{color:#bdcad6}
.mx51-status{display:inline-block;margin-top:5px;border:1px solid #2d4b65;border-radius:999px;padding:2px 6px;color:#8fa9bf;font-size:.47rem;font-weight:850}
.mx51-player-note{font-size:.50rem;color:#7690a6;margin:-2px 0 5px}

/* Step 11 owns game/player finding. Never show stale Step 6/Step 3 browse controls. */
div[data-testid="stElementContainer"]:has(.mx47-summary),
div[data-testid="stElementContainer"]:has(.mx44-head),
div[data-testid="stElementContainer"]:has(.mx43-head){display:none!important}

/* The result should follow the two selectors immediately. */
.mx49-section{margin:4px 0 5px!important}.mx49-card{margin-bottom:6px!important}

@media(max-width:640px){
  .mx51-finder{padding:10px 11px;margin:2px 0 6px;border-radius:16px}
  .mx51-finder-title{font-size:.84rem}.mx51-finder-sub{font-size:.50rem}
  .mx51-game{padding:9px 10px;margin:5px 0 7px;border-radius:16px}
  .mx51-logo{width:38px;height:38px}.mx51-team{font-size:.61rem}
  .mx51-game-meta{font-size:.50rem;margin-top:6px}.mx51-player-note{font-size:.47rem}
}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    return step1._safe_int(value, default)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _game_day(row: Any) -> date | None:
    raw = str(row.get("game_date") or "")[:10]
    try:
        return date.fromisoformat(raw)
    except Exception:
        return None


def _phoenix_time_text(row: Any) -> str:
    """Convert the existing Eastern first-pitch label to Phoenix local time.

    America/Phoenix is used rather than subtracting a fixed number of hours so
    Eastern daylight-saving changes are handled correctly while Phoenix remains
    on Mountain Standard Time.
    """
    raw = str(row.get("first_pitch_et") or "").strip()
    if not raw or raw.upper() == "TBD":
        return "TBD"
    game_day = _game_day(row)
    if game_day is None:
        return raw

    cleaned = re.sub(r"\s+(?:ET|EDT|EST)\s*$", "", raw, flags=re.IGNORECASE).strip()
    parsed_time = None
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            parsed_time = datetime.strptime(cleaned, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        return raw

    eastern = datetime.combine(game_day, parsed_time, tzinfo=_EASTERN)
    phoenix = eastern.astimezone(_PHOENIX)
    clock = phoenix.strftime("%I:%M %p").lstrip("0")
    return f"{clock} MST"


def _team_logo_url(team_id: Any) -> str:
    team_id = _safe_int(team_id, 0)
    return f"https://www.mlbstatic.com/team-logos/{team_id}.svg" if team_id > 0 else ""


def _logo_html(team_id: Any, team_name: Any) -> str:
    url = _team_logo_url(team_id)
    if not url:
        return '<div class="mx51-logo" aria-hidden="true">⚾</div>'
    return f'<img class="mx51-logo" src="{_esc(url)}" alt="{_esc(team_name)} logo">'


def _game_picker_label(row: Any) -> str:
    away = str(row.get("away_team") or "Away")
    home = str(row.get("home_team") or "Home")
    return f"{away} @ {home} • {_phoenix_time_text(row)}"


def _selected_game_html(row: Any) -> str:
    away = row.get("away_team") or "Away"
    home = row.get("home_team") or "Home"
    away_logo = _logo_html(row.get("away_team_id"), away)
    home_logo = _logo_html(row.get("home_team_id"), home)
    venue = row.get("venue_name") or "Venue TBD"
    away_pitcher = row.get("away_pitcher") or "TBD"
    home_pitcher = row.get("home_pitcher") or "TBD"
    status = row.get("status") or "Scheduled"
    return (
        '<div class="mx51-game">'
        '<div class="mx51-teams">'
        f'<div class="mx51-team">{away_logo}<div>{_esc(away)}</div></div>'
        '<div class="mx51-at">@</div>'
        f'<div class="mx51-team">{home_logo}<div>{_esc(home)}</div></div>'
        '</div>'
        '<div class="mx51-game-meta">'
        f'<div class="mx51-phx">🌵 {_esc(_phoenix_time_text(row))} • Phoenix time</div>'
        f'<div>{_esc(venue)}</div>'
        f'<div class="mx51-starters">{_esc(away_pitcher)} vs {_esc(home_pitcher)}</div>'
        f'<span class="mx51-status">{_esc(status)}</span>'
        '</div></div>'
    )


def _player_picker_label(player: dict[str, Any]) -> str:
    role_label, _ = step1._role(player)
    slot = _safe_int(player.get("slot"), 99)
    slot_text = f"#{slot} • " if role_label != "Bench" and 1 <= slot <= 9 else ""
    name = str(player.get("name") or "Player")
    team = str(player.get("team") or "")
    position = str(player.get("position") or "").strip()
    details = " • ".join(x for x in (team, position, role_label) if x)
    return f"{slot_text}{name} • {details}" if details else f"{slot_text}{name}"


def _render_stable_selectors(games_df) -> int:
    options = list(range(len(games_df)))
    prior_game = _safe_int(st.session_state.get("mh12_game", 0), 0)
    if prior_game not in options:
        prior_game = 0
    if st.session_state.get("mx51_game") not in options:
        st.session_state["mx51_game"] = prior_game

    st.markdown(
        '<div class="mx51-finder"><div class="mx51-finder-title">⚾ Find your matchup + hitter</div>'
        '<div class="mx51-finder-sub">1. Pick the game. 2. Pick a player from that game only. All first-pitch times below are Phoenix local time.</div></div>',
        unsafe_allow_html=True,
    )

    game_index = st.selectbox(
        "1️⃣ Game",
        options,
        format_func=lambda i: _game_picker_label(games_df.iloc[int(i)]),
        key="mx51_game",
    )
    game_index = _safe_int(game_index, prior_game)
    st.session_state["mh12_game"] = game_index

    row = games_df.iloc[game_index]
    st.markdown(_selected_game_html(row), unsafe_allow_html=True)

    players = roster._all_hitters_v14(row)
    if not players:
        st.warning("No active hitters are available for this matchup yet.")
        return game_index

    ordered = step1._ordered_player_indices(players)
    game_pk = _safe_int(row.get("game_pk"), game_index)
    player_key = f"mx51_player_{game_pk}"
    active_pk = _safe_int(st.session_state.get("mx51_active_game_pk"), -1)

    if st.session_state.get(player_key) not in ordered:
        prior_player = _safe_int(st.session_state.get("mh12_player", ordered[0]), ordered[0])
        # Only reuse the global player index when it belongs to this same game.
        st.session_state[player_key] = prior_player if active_pk == game_pk and prior_player in ordered else ordered[0]

    player_index = st.selectbox(
        "2️⃣ Player",
        ordered,
        format_func=lambda i: _player_picker_label(players[int(i)]),
        key=player_key,
        help="Start typing a player name or open the list. Confirmed and projected lineup hitters appear before the bench.",
    )
    player_index = _safe_int(player_index, ordered[0])
    st.session_state["mh12_player"] = player_index
    st.session_state["mx51_active_game_pk"] = game_pk
    st.markdown(
        '<div class="mx51-player-note">Player choices are locked to the selected matchup, so switching games cannot carry a hitter over from the previous teams.</div>',
        unsafe_allow_html=True,
    )
    return game_index


def _stable_spotlight_html(context: dict[str, Any], final: dict[str, Any] | None = None) -> str:
    """Render Step 10's certified spotlight without Markdown blank-line hazards.

    A bench player has no batting-slot badge. In the previous multiline HTML that
    could leave an indented blank line, allowing Markdown to terminate the HTML
    block and display the remaining tags as literal code. Compacting the markup
    keeps the exact presentation data while removing that parser edge case.
    """
    source = step10._clean_loading_spotlight_html(context, final)
    return "".join(line.strip() for line in source.splitlines() if line.strip())


def _render_spotlight(slot, context: dict[str, Any] | None, final: dict[str, Any] | None = None) -> None:
    if not context:
        slot.info("Player spotlight is waiting for a verified selection.")
        return
    slot.markdown(_stable_spotlight_html(context, final), unsafe_allow_html=True)


def _step12_profile_with_spotlight(original, slot, context):
    def wrapped(profile: dict[str, Any] | None) -> None:
        _render_spotlight(slot, context, profile)
        return original(profile)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    st.markdown(step9._STEP9_CSS + step10._STEP10_CSS + _STEP11_CSS, unsafe_allow_html=True)
    _render_stable_selectors(games_df)

    # Context is built only after both selectors write the exact original game/player
    # indices expected by the frozen Step 12 model chain.
    context = step4._selected_context(games_df)
    hero_slot = st.empty()
    _render_spotlight(hero_slot, context, None)

    original_selectbox = st.selectbox
    original_text_input = st.text_input
    original_markdown = st.markdown
    original_expander = st.expander
    original_caption = st.caption
    original_step12_profile = final_layer._render_step12_profile

    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    st.text_input = step10._legacy_text_input_passthrough(original_text_input)
    st.markdown = step10._legacy_markdown_passthrough(original_markdown)
    st.expander = step5._collapsed_expander(original_expander)
    st.caption = step9._clean_engine_caption(original_caption)
    final_layer._render_step12_profile = _step12_profile_with_spotlight(
        original_step12_profile,
        hero_slot,
        context,
    )
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_step12_profile
        st.caption = original_caption
        st.expander = original_expander
        st.markdown = original_markdown
        st.text_input = original_text_input
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP9_PRESENTATION",
    "FROZEN_STEP10_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_game_picker_label",
    "_phoenix_time_text",
    "_player_picker_label",
    "_selected_game_html",
    "_stable_spotlight_html",
    "_team_logo_url",
    "render_matchup_hub",
]
