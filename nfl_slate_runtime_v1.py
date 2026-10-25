"""Dedicated API2 NFL Slate presentation runtime V1."""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from nfl_slate_gateway_v1 import load_nfl_slate


API2_NFL_SLATE_CANONICAL_ROUTER_V1_FROZEN = True
MODEL_VERSION = "API2 NFL SLATE CANONICAL RUNTIME V1"
DATA_GATEWAY = "kyre_sports_api"
DATA_TRUTH_GATE = "api2_step2d_data_truth_gate_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


CSS = """
<style>
.ks-slate{max-width:1080px;margin:0 auto;padding:4px 4px 28px}
.ks-slate-head{display:flex;justify-content:space-between;gap:12px;align-items:end;margin:4px 0 14px}
.ks-slate-kicker{font-size:.72rem;font-weight:900;letter-spacing:.13em;color:#73d6ff}
.ks-slate-title{font-size:1.55rem;font-weight:950;color:#f8fbff;line-height:1.05}
.ks-slate-sub{font-size:.75rem;color:#93a9b8;margin-top:4px}
.ks-slate-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.ks-game{border:1px solid #263b4b;background:linear-gradient(145deg,#0a1620,#071018);border-radius:16px;padding:14px;box-shadow:0 10px 28px rgba(0,0,0,.2)}
.ks-time{font-size:.62rem;font-weight:900;color:#79d8ff;letter-spacing:.06em;margin-bottom:9px}
.ks-team{display:flex;align-items:center;gap:9px;color:#f6fbff;font-size:.92rem;font-weight:900;padding:6px 0}
.ks-logo{width:27px;height:27px;object-fit:contain}
.ks-vs{font-size:.58rem;color:#7f96a7;font-weight:900;letter-spacing:.12em;margin:1px 0}
@media(max-width:760px){.ks-slate-grid{grid-template-columns:1fr}.ks-slate-title{font-size:1.3rem}}
</style>
"""


def _text(value: Any, default: str = "Not Available") -> str:
    text = str(value or "").strip()
    return text or default


def _team_row(name: str, abbr: str, logo: str) -> str:
    image = f'<img class="ks-logo" src="{escape(logo)}" alt="{escape(abbr)} logo">' if logo else '<div class="ks-logo"></div>'
    return f'<div class="ks-team">{image}<span>{escape(name)} <small>({escape(abbr)})</small></span></div>'


def _game_card(game: dict[str, Any]) -> str:
    away = _text(game.get("away"), "NFL")
    home = _text(game.get("home"), "NFL")
    away_name = _text(game.get("away_name"), away)
    home_name = _text(game.get("home_name"), home)
    away_logo = _text(game.get("away_logo_url"), "")
    home_logo = _text(game.get("home_logo_url"), "")
    date = _text(game.get("date"), "Date Not Available")
    kickoff = _text(game.get("kickoff"), "Time Not Available")
    return (
        '<article class="ks-game">'
        f'<div class="ks-time">{escape(date)} · {escape(kickoff)} ET</div>'
        f'{_team_row(away_name, away, away_logo)}'
        '<div class="ks-vs">AT</div>'
        f'{_team_row(home_name, home, home_logo)}'
        '</article>'
    )


def render_nfl_slate_runtime() -> None:
    """Render NFL Slate exclusively from the Kyre Sports API gateway contract."""
    st.markdown(CSS, unsafe_allow_html=True)
    target_date = st.query_params.get("ks_nfl_slate_date") or None
    payload = load_nfl_slate(str(target_date) if target_date else None)
    if not payload.get("ready"):
        st.warning(_text(payload.get("reason"), "Kyre Sports API NFL slate unavailable"))
        return

    games = list(payload.get("games") or [])
    season = payload.get("season")
    week = payload.get("week")
    resolved = _text(payload.get("resolved_date"), "Current slate")
    week_label = f"Week {week}" if week is not None else "NFL Slate"
    season_label = f"{season} · " if season is not None else ""
    header = (
        '<div class="ks-slate"><div class="ks-slate-head"><div>'
        '<div class="ks-slate-kicker">KYRE SPORTS API · NFL</div>'
        '<div class="ks-slate-title">League Slate</div>'
        f'<div class="ks-slate-sub">{escape(season_label + week_label)} · {escape(resolved)} · {len(games)} games</div>'
        '</div></div><div class="ks-slate-grid">'
    )
    st.markdown(header + "".join(_game_card(game) for game in games) + "</div></div>", unsafe_allow_html=True)


__all__ = [
    "API2_NFL_SLATE_CANONICAL_ROUTER_V1_FROZEN",
    "DATA_GATEWAY",
    "DATA_TRUTH_GATE",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_nfl_slate_runtime",
]
