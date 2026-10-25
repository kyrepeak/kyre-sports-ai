"""NFL Receiving Yards V22 — canonical Kyre Sports API presentation."""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import nfl_receiving_yards_gateway_v2 as gateway

MODEL_VERSION = "NFL RECEIVING YARDS V22 • CANONICAL SOURCE MIGRATION"
DATA_GATEWAY = "kyre_sports_api"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
DISPLAY_ONLY = True

_CSS = r'''
<style>
.krecv22{max-width:1120px;margin:0 auto;padding:2px 2px 28px}.krecv22-hero{border:1px solid #315940;border-radius:17px;background:linear-gradient(145deg,#0c1b14,#08130e);padding:13px 14px;margin:5px 0 10px}.krecv22-kicker{color:#8be2ac;font-size:.56rem;font-weight:950;letter-spacing:.11em}.krecv22-title{color:#f5faf7;font-size:1.35rem;font-weight:950;line-height:1.08;margin-top:3px}.krecv22-sub{color:#82988a;font-size:.61rem;line-height:1.4;margin-top:5px}
.krecv22-match{border:1px solid #2c4d39;border-radius:12px;background:#0b1711;padding:8px 9px;margin:6px 0 9px;color:#b8d7c3;font-size:.60rem;font-weight:850}.krecv22-team{border:1px solid #274333;border-radius:14px;background:#09150f;padding:10px;margin:8px 0}.krecv22-teamtop{display:flex;align-items:center;gap:8px}.krecv22-logo{width:31px;height:31px;object-fit:contain}.krecv22-teamname{color:#eef7f1;font-size:.78rem;font-weight:950}.krecv22-teammeta{color:#6e8576;font-size:.45rem;margin-top:2px}
.krecv22-defense{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin:7px 0}.krecv22-cell{border:1px solid #1e3428;border-radius:8px;background:#08120d;padding:6px;min-width:0}.krecv22-cell b{display:block;color:#e5efe8;font-size:.63rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv22-cell span{display:block;color:#5e7466;font-size:.34rem;font-weight:900;text-transform:uppercase;margin-top:2px}
.krecv22-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.krecv22-player{border:1px solid #294938;border-radius:13px;background:#0a1611;padding:8px;min-width:0}.krecv22-ident{display:grid;grid-template-columns:42px 1fr 28px;gap:7px;align-items:center}.krecv22-face{width:40px;height:40px;border-radius:50%;object-fit:cover;border:1px solid #355d45;background:#101a14}.krecv22-plogo{width:27px;height:27px;object-fit:contain}.krecv22-name{color:#f2f8f4;font-size:.68rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv22-meta{color:#6f8677;font-size:.42rem;margin-top:2px}.krecv22-badge{color:#86dca4;font-size:.40rem;font-weight:900;margin-top:2px}.krecv22-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:7px}.krecv22-stat{border-top:1px solid #1b3024;padding-top:5px}.krecv22-stat b{display:block;color:#e5efe8;font-size:.58rem}.krecv22-stat span{display:block;color:#5c7164;font-size:.32rem;text-transform:uppercase;font-weight:900}.krecv22-market,.krecv22-history{margin-top:6px;border-radius:8px;padding:6px 7px;font-size:.45rem;line-height:1.35}.krecv22-market{background:#0f1c17;border:1px solid #294838;color:#91aa9a}.krecv22-history{background:#0b151c;border:1px solid #2b4354;color:#8ca7b8}.krecv22-guard{border-left:3px solid #4c745b;background:#0c1912;border-radius:8px;padding:7px 8px;color:#829b8b;font-size:.47rem;line-height:1.4;margin-top:9px}
@media(max-width:760px){.krecv22-grid{grid-template-columns:1fr}.krecv22-defense{grid-template-columns:repeat(4,minmax(0,1fr));gap:4px}.krecv22-cell{padding:5px}.krecv22-stats{grid-template-columns:repeat(4,minmax(0,1fr))}.krecv22-hero{padding:11px}.krecv22-title{font-size:1.16rem}}
</style>
'''


def _text(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt(value: Any, digits: int = 1) -> str:
    number = _num(value)
    if number is None:
        return "—"
    rendered = f"{number:.{digits}f}"
    return rendered.rstrip("0").rstrip(".") if digits else rendered


def _img(url: Any, cls: str, alt: str) -> str:
    src = _text(url, "")
    if not src.startswith("https://"):
        return f'<span class="{cls}" aria-hidden="true"></span>'
    return f'<img class="{cls}" src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}" loading="lazy">'


def _defense_html(defense: Mapping[str, Any]) -> str:
    if defense.get("data_available") is not True:
        return '<div class="krecv22-guard">Opponent receiving-defense sample is not verified yet. Projection stays fail-closed rather than inventing a value.</div>'
    rows = (
        ("Rec/G", _fmt(defense.get("receptions_allowed_per_game"), 1)),
        ("Rec Yds/G", _fmt(defense.get("receiving_yards_allowed_per_game"), 1)),
        ("YPR", _fmt(defense.get("yards_per_reception_allowed"), 2)),
        ("Rec TD/G", _fmt(defense.get("receiving_touchdowns_allowed_per_game"), 2)),
    )
    return '<div class="krecv22-defense">' + ''.join(
        f'<div class="krecv22-cell"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for label, value in rows
    ) + '</div>'


def _market_html(market: Mapping[str, Any]) -> str:
    if market.get("identity_verified") is True:
        return (
            '<div class="krecv22-market">'
            f'FanDuel • line <b>{escape(_fmt(market.get("line"), 1))}</b> • '
            f'Over {escape(_text(market.get("over_odds")))} / Under {escape(_text(market.get("under_odds")))} • '
            'display-only • projection influence 0.0%'
            '</div>'
        )
    state = _text(market.get("state"), "NO_VERIFIED_PLAYER_MARKET")
    return f'<div class="krecv22-market">Market state: {escape(state)} • no line or price is fabricated.</div>'


def _history_html(history: Mapping[str, Any], opponent: str) -> str:
    if history.get("available") is not True:
        return f'<div class="krecv22-history">Vs {escape(opponent)} history • no verified prior matchup sample.</div>'
    return (
        '<div class="krecv22-history">'
        f'Vs {escape(opponent)} • {int(history.get("games") or 0)} verified game(s) • '
        f'avg {escape(_fmt(history.get("avg_receiving_yards"), 1))} receiving yds'
        '</div>'
    )


def _player_html(player: Mapping[str, Any], team_logo: str, opponent: str) -> str:
    name = _text(player.get("player_name"), "Verified receiver")
    position = _text(player.get("position"), "REC")
    jersey = _text(player.get("jersey_number"), "")
    jersey_text = f" • #{jersey}" if jersey else ""
    player_id = _text(player.get("canonical_player_id"))
    projection = player.get("projection") or {}
    projection_text = _fmt(projection.get("projection_yards"), 1) if projection.get("ready") is True else "—"
    stats = (
        ("Proj", projection_text),
        ("Season/G", _fmt(player.get("receiving_yards_per_game"), 1)),
        ("Recent 5", _fmt(player.get("recent5_yards_avg"), 1)),
        ("Rec/G", _fmt(player.get("receptions_per_game"), 1)),
    )
    stat_html = ''.join(
        f'<div class="krecv22-stat"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for label, value in stats
    )
    return (
        '<article class="krecv22-player">'
        '<div class="krecv22-ident">'
        f'{_img(player.get("headshot_url"), "krecv22-face", name + " headshot")}'
        '<div>'
        f'<div class="krecv22-name">{escape(name)}</div>'
        f'<div class="krecv22-meta">{escape(position + jersey_text)} • {escape(player_id)}</div>'
        '<div class="krecv22-badge">VERIFIED GSIS + KYRE ID</div>'
        '</div>'
        f'{_img(team_logo, "krecv22-plogo", "team logo")}'
        '</div>'
        f'<div class="krecv22-stats">{stat_html}</div>'
        f'{_market_html(player.get("market") or {})}'
        f'{_history_html(player.get("matchup_history") or {}, opponent)}'
        '</article>'
    )


def _render_team(team: Mapping[str, Any]) -> None:
    abbr = _text(team.get("team_abbr"), "NFL")
    name = _text(team.get("team_name"), abbr)
    opponent = _text(team.get("opponent_abbr"), "OPP")
    logo = _text(team.get("team_logo_url"), "")
    st.markdown(
        '<section class="krecv22-team">'
        '<div class="krecv22-teamtop">'
        f'{_img(logo, "krecv22-logo", abbr + " logo")}'
        '<div>'
        f'<div class="krecv22-teamname">{escape(abbr)} • {escape(name)}</div>'
        f'<div class="krecv22-teammeta">Key receiving options • vs {escape(opponent)} • {int(team.get("player_count") or 0)} verified player(s)</div>'
        '</div></div>'
        f'{_defense_html(team.get("opponent_pass_defense") or {})}'
        '</section>',
        unsafe_allow_html=True,
    )
    players = [row for row in (team.get("players") or []) if isinstance(row, Mapping)]
    if not players:
        st.info(f"No verified receiving option is available for {abbr} yet.")
        return
    st.markdown(
        '<div class="krecv22-grid">' + ''.join(_player_html(player, logo, opponent) for player in players) + '</div>',
        unsafe_allow_html=True,
    )


def render_nfl_receiving_yards_hub() -> None:
    st.html(_CSS)
    payload = gateway.load_receiving_yards_slate()
    st.markdown(
        '<div class="krecv22"><div class="krecv22-hero">'
        '<div class="krecv22-kicker">KYRE SPORTS API • NFL • RECEIVING YARDS</div>'
        '<div class="krecv22-title">Receiving Yards <span>Matchup Lab</span></div>'
        '<div class="krecv22-sub">Upcoming games only • verified GSIS identity • matchup history when available • sportsbook observations never alter the projection.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    if payload.get("ready") is not True:
        st.warning(_text(payload.get("reason"), "Receiving Yards data unavailable"))
        return
    games = [row for row in (payload.get("games") or []) if isinstance(row, Mapping)]
    if not games:
        st.info("No upcoming NFL games are currently available in the verified slate.")
        return
    labels = {
        _text(game.get("canonical_game_id")): (
            f"{_text(game.get('away'), 'AWY')} @ {_text(game.get('home'), 'HME')} • "
            f"{_text(game.get('game_date'))} • {_text(game.get('kickoff_et'))[11:16]} ET"
        )
        for game in games
    }
    selected_id = st.selectbox(
        "🏈 Receiving matchup",
        options=list(labels),
        format_func=lambda value: labels[value],
        key="nfl_receiving_yards_v22_game",
    )
    game = next(row for row in games if _text(row.get("canonical_game_id")) == selected_id)
    market_state = game.get("market_state") or {}
    st.markdown(
        '<div class="krecv22-match">'
        f'{escape(labels[selected_id])} • market router {escape(_text(market_state.get("state"), "CHECK"))}'
        '</div>',
        unsafe_allow_html=True,
    )
    teams = [row for row in (game.get("teams") or []) if isinstance(row, Mapping)]
    for team in teams:
        _render_team(team)
    st.markdown(
        '<div class="krecv22-guard">Kyre Sports API owns schedule, identity, history, defense, market reconciliation, freshness and semantic empty states. FanDuel is display-only and sportsbook projection influence is 0.0%.</div>',
        unsafe_allow_html=True,
    )


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V22 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DATA_GATEWAY", "DISPLAY_ONLY", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_nfl_hub", "render_nfl_receiving_yards_hub",
]
