"""CFB Player Props Page 2 V1 — professional selected-game player command board."""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping, Sequence

import streamlit as st
from streamlit_autorefresh import st_autorefresh

import cfb_over_under_logo_resolver_v2 as logo_fallback
import cfb_over_under_logo_resolver_v3 as logo_exact
import cfb_player_props_model_v1 as frozen_model
import cfb_player_props_page2_availability_v1 as availability_owner
import cfb_player_props_page2_context_v1 as context_owner
import cfb_player_props_page2_handoff_v1 as page3_handoff
import cfb_player_props_page2_market_v1 as market_owner
import cfb_player_props_page2_matchup_v1 as matchup_owner
import cfb_player_props_page2_roster_v1 as roster_owner

MODEL_VERSION = "CFB PLAYER PROPS PAGE 2 V1 • GAME COMMAND BOARD"
SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE
MARKET_LABELS = {
    "passing_yards": "Passing Yards",
    "rushing_yards": "Rushing Yards",
    "receiving_yards": "Receiving Yards",
    "receiving_receptions": "Receptions",
    "passing_touchdowns": "Passing TDs",
    "touchdowns": "Anytime TD",
}
MARKET_FILTERS = {
    "ALL": frozenset(MARKET_LABELS),
    "PASS": frozenset({"passing_yards", "passing_touchdowns"}),
    "RUSH": frozenset({"rushing_yards"}),
    "REC": frozenset({"receiving_yards"}),
    "RECEPTIONS": frozenset({"receiving_receptions"}),
    "TD": frozenset({"touchdowns"}),
}

_PAGE_CSS = """
<style data-cfb-player-props-page2-css="v2">
.cfbpp2-hero{position:relative;overflow:hidden;border:1px solid rgba(125,211,252,.22);border-radius:22px;padding:20px;margin:8px 0 14px;background:radial-gradient(circle at 88% 0,rgba(14,165,233,.17),transparent 23rem),linear-gradient(145deg,rgba(4,11,21,.99),rgba(7,24,40,.98));box-shadow:0 18px 44px rgba(0,0,0,.22)}
.cfbpp2-kicker{font-size:.68rem;font-weight:950;letter-spacing:.16em;color:#7dd3fc}.cfbpp2-title{font-size:clamp(1.55rem,4vw,2.45rem);font-weight:950;letter-spacing:-.045em;color:#f8fafc;margin:.28rem 0 .8rem}.cfbpp2-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:10px}.cfbpp2-teamhero{display:flex;align-items:center;gap:10px;min-width:0}.cfbpp2-teamhero.right{justify-content:flex-end;text-align:right}.cfbpp2-logo{width:52px;height:52px;object-fit:contain}.cfbpp2-monogram{width:50px;height:50px;border-radius:15px;border:1px solid rgba(125,211,252,.22);display:flex;align-items:center;justify-content:center;font-weight:950;color:#7dd3fc;background:rgba(14,165,233,.05)}.cfbpp2-teamname{font-size:.96rem;font-weight:900;color:#eef6ff}.cfbpp2-teammeta{font-size:.67rem;color:#8196ab;margin-top:2px}.cfbpp2-vs{font-size:.7rem;font-weight:950;letter-spacing:.12em;color:#587189}.cfbpp2-game-meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.cfbpp2-chip{display:inline-flex;align-items:center;border:1px solid rgba(125,211,252,.17);border-radius:999px;padding:6px 9px;background:rgba(14,165,233,.05);font-size:.65rem;font-weight:800;color:#cfeafa}
.cfbpp2-team-section{border:1px solid rgba(125,211,252,.13);border-radius:18px;padding:12px;background:linear-gradient(160deg,rgba(6,15,27,.98),rgba(8,20,34,.97));margin-bottom:10px}.cfbpp2-team-title{font-size:.72rem;font-weight:950;letter-spacing:.12em;color:#7dd3fc;text-transform:uppercase;margin:2px 0 10px}.cfbpp2-player{border:1px solid rgba(148,163,184,.14);border-radius:16px;padding:12px;margin:9px 0;background:rgba(3,10,18,.7)}.cfbpp2-player.compact{padding:9px 10px;margin:7px 0;background:rgba(3,10,18,.46)}.cfbpp2-player.compact .cfbpp2-headshot,.cfbpp2-player.compact .cfbpp2-monogram{width:40px;height:40px;border-radius:12px}.cfbpp2-player.compact .cfbpp2-player-head{grid-template-columns:42px minmax(0,1fr) auto}.cfbpp2-player-head{display:grid;grid-template-columns:52px minmax(0,1fr) auto;align-items:center;gap:10px}.cfbpp2-headshot{width:50px;height:50px;border-radius:14px;object-fit:cover;background:rgba(15,23,42,.9)}.cfbpp2-player-name{font-size:.9rem;font-weight:950;color:#f5f9fd}.cfbpp2-player-meta{font-size:.64rem;color:#7f94a9;margin-top:2px}.cfbpp2-status{border:1px solid rgba(148,163,184,.18);border-radius:999px;padding:5px 8px;font-size:.58rem;font-weight:950;letter-spacing:.05em;color:#cbd5e1}.cfbpp2-status.muted{opacity:.54;font-weight:800}.cfbpp2-empty{margin-top:10px;border:1px dashed rgba(148,163,184,.22);border-radius:12px;padding:10px;color:#879aae;font-size:.72rem}.cfbpp2-player.compact .cfbpp2-empty{margin-top:7px;padding:7px 9px;border-style:solid;background:rgba(148,163,184,.025);font-size:.65rem}.cfbpp2-prop{margin-top:10px;border-top:1px solid rgba(125,211,252,.09);padding-top:10px}.cfbpp2-prop-top{display:flex;justify-content:space-between;gap:8px;align-items:start}.cfbpp2-prop-name{font-size:.76rem;font-weight:950;color:#eaf5ff}.cfbpp2-consensus{font-size:.64rem;color:#7dd3fc;font-weight:850}.cfbpp2-lines{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:7px}.cfbpp2-line{border:1px solid rgba(125,211,252,.11);border-radius:10px;padding:7px;background:rgba(14,165,233,.035);font-size:.63rem;color:#b9cadd}.cfbpp2-line b{display:block;color:#edf7ff;font-size:.7rem;margin-top:2px}.cfbpp2-context{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.cfbpp2-mini{border-radius:999px;padding:4px 7px;background:rgba(148,163,184,.07);font-size:.58rem;font-weight:800;color:#91a6bb}.cfbpp2-signal{margin-top:7px;border:1px solid rgba(52,211,153,.18);border-radius:10px;padding:8px;background:rgba(16,185,129,.045);font-size:.63rem;color:#9fd6bd}.cfbpp2-signal b{color:#dffcef}.cfbpp2-shell{border:1px solid rgba(148,163,184,.2);border-radius:16px;padding:16px;color:#a8bacb;background:rgba(8,18,30,.75)}
.cfbpp2-filter-label{font-size:.63rem;font-weight:900;letter-spacing:.08em;color:#7dd3fc;text-transform:uppercase;margin:.3rem 0 .15rem}.cfbpp2-active-label{font-size:.62rem;font-weight:900;color:#9ddcf8;margin:.35rem 0 .1rem}.cfbpp2-top-link{position:fixed;right:20px;bottom:88px;z-index:9999;text-decoration:none!important;border:1px solid rgba(125,211,252,.28);border-radius:999px;padding:9px 12px;background:rgba(3,10,18,.94);box-shadow:0 10px 28px rgba(0,0,0,.3);font-size:.68rem;font-weight:950;letter-spacing:.08em;color:#dff5ff!important;backdrop-filter:blur(12px)}
.cfbpp2-top-link:hover{border-color:rgba(125,211,252,.62);transform:translateY(-1px)}
@media(max-width:760px){.cfbpp2-hero{padding:15px 13px;border-radius:17px}.cfbpp2-title{font-size:1.5rem}.cfbpp2-matchup{grid-template-columns:1fr}.cfbpp2-vs{display:none}.cfbpp2-teamhero.right{justify-content:flex-start;text-align:left}.cfbpp2-player-head{grid-template-columns:46px minmax(0,1fr)}.cfbpp2-status{grid-column:1/-1;width:max-content}.cfbpp2-player.compact .cfbpp2-status{grid-column:auto}.cfbpp2-headshot,.cfbpp2-monogram{width:44px;height:44px}.cfbpp2-lines{grid-template-columns:1fr}.cfbpp2-top-link{right:14px;bottom:104px;padding:10px 13px}}
</style>
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _number(value: Any, digits: int = 1) -> str:
    number = _finite(value)
    return f"{number:.{digits}f}" if number is not None else "—"


def _pct(value: Any) -> str:
    number = _finite(value)
    return f"{100.0 * number:.1f}%" if number is not None else "—"


def _price(value: Any) -> str:
    if value in (None, ""):
        return "—"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:+d}" if number > 0 else str(number)


def _market_label(key: Any) -> str:
    value = _text(key)
    return MARKET_LABELS.get(value, value.replace("_", " ").title())


def market_matches_filter(market_key: Any, market_filter: Any) -> bool:
    selected = _text(market_filter).upper() or "ALL"
    allowed = MARKET_FILTERS.get(selected, MARKET_FILTERS["ALL"])
    return _text(market_key) in allowed


def filter_player_markets(
    markets: Sequence[Mapping[str, Any]],
    market_filter: str,
) -> list[Mapping[str, Any]]:
    return [
        market for market in markets
        if market_matches_filter(market.get("market_key"), market_filter)
    ]


def partition_players_by_markets(
    players: Sequence[roster_owner.Page2Player],
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    market_filter: str,
) -> tuple[list[roster_owner.Page2Player], list[roster_owner.Page2Player]]:
    active: list[roster_owner.Page2Player] = []
    inactive: list[roster_owner.Page2Player] = []
    for player in players:
        markets = grouped.get(player.official_player_id) or ()
        target = active if filter_player_markets(markets, market_filter) else inactive
        target.append(player)
    return active, inactive


def _rank(value: Any) -> str:
    text = _text(value)
    return f"#{text} " if text and text not in {"0", "None"} else ""


def _monogram(name: str) -> str:
    letters = "".join(part[:1] for part in name.split()[:2]).upper() or "CFB"
    return f'<div class="cfbpp2-monogram">{escape(letters)}</div>'


def _image_or_monogram(url: str, name: str, *, headshot: bool = False) -> str:
    if _text(url).startswith(("https://", "http://")):
        klass = "cfbpp2-headshot" if headshot else "cfbpp2-logo"
        return f'<img class="{klass}" src="{escape(url, quote=True)}" alt="{escape(name)}" loading="lazy" />'
    return _monogram(name)


def _visuals(context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    game = dict(context.get("game") or {})
    game["away_espn_team_id"] = _text(context.get("away_team_id"))
    game["home_espn_team_id"] = _text(context.get("home_team_id"))
    try:
        resolved = logo_exact.resolve_visuals(game)
    except Exception:
        resolved = {"away": {}, "home": {}}
    out = {"away": dict(resolved.get("away") or {}), "home": dict(resolved.get("home") or {})}
    for side in ("away", "home"):
        if _text(out[side].get("logo")):
            continue
        try:
            fallback = logo_fallback.resolve_team_logo(
                _text(context.get(f"{side}_team")),
                _text(context.get(f"{side}_team_slug")),
                _text((context.get("game") or {}).get(f"{side}_conference")),
            )
            if isinstance(fallback, Mapping):
                out[side] = dict(fallback)
        except Exception:
            pass
    return out


def _team_hero(side: str, context: Mapping[str, Any], visuals: Mapping[str, Mapping[str, Any]]) -> str:
    name = _text(context.get(f"{side}_team")) or side.title()
    record = _text(context.get(f"{side}_record")) or "Record unavailable"
    rank_name = _rank(context.get(f"{side}_rank")) + name
    logo = _image_or_monogram(_text((visuals.get(side) or {}).get("logo")), name)
    right = " right" if side == "home" else ""
    if side == "home":
        return f'<div class="cfbpp2-teamhero{right}"><div><div class="cfbpp2-teamname">{escape(rank_name)}</div><div class="cfbpp2-teammeta">{escape(record)} • Home</div></div>{logo}</div>'
    return f'<div class="cfbpp2-teamhero{right}">{logo}<div><div class="cfbpp2-teamname">{escape(rank_name)}</div><div class="cfbpp2-teammeta">{escape(record)} • Away</div></div></div>'


def render_hero_html(context: Mapping[str, Any], visuals: Mapping[str, Mapping[str, Any]]) -> str:
    chips = [
        _text(context.get("kickoff_phoenix")), _text(context.get("status")),
        _text(context.get("venue")), _text(context.get("broadcast")),
    ]
    chip_html = "".join(f'<span class="cfbpp2-chip">{escape(value)}</span>' for value in chips if value)
    return (
        '<section class="cfbpp2-hero" data-cfb-player-props-page2="v2">'
        '<div class="cfbpp2-kicker">CFB • PLAYER PROPS • GAME COMMAND</div>'
        '<div class="cfbpp2-title">Player Prop Intelligence</div>'
        '<div class="cfbpp2-matchup">'
        f'{_team_hero("away", context, visuals)}<div class="cfbpp2-vs">VS</div>{_team_hero("home", context, visuals)}'
        f'</div><div class="cfbpp2-game-meta">{chip_html}</div></section>'
    )


def render_prop_row_html(
    market: Mapping[str, Any],
    recent: Mapping[str, Any],
    defense: Mapping[str, Any],
    signal: Mapping[str, Any],
) -> str:
    best_over = market.get("best_over") if isinstance(market.get("best_over"), Mapping) else {}
    best_under = market.get("best_under") if isinstance(market.get("best_under"), Mapping) else {}
    movement = market.get("movement") if isinstance(market.get("movement"), Mapping) else {}
    if movement.get("available") is True:
        movement_text = (
            f'Move {_number(movement.get("opening_line"))} → {_number(movement.get("current_line"))} '
            f'({_finite(movement.get("delta")) or 0:+.1f})'
        )
    else:
        movement_text = "Opening move unavailable"
    last3 = ", ".join(_number(value) for value in recent.get("last3") or ()) or "—"
    defense_label = _text(defense.get("label")) or "CHECK"
    if signal.get("model_ready") is True and signal.get("model_probability") is not None:
        signal_text = (
            f'<b>Kyre {_text(signal.get("side")).upper()} {_pct(signal.get("model_probability"))}</b> • '
            f'Projection {_number(signal.get("projection"))} • Edge {_pct(signal.get("edge"))}'
        )
    else:
        signal_text = "Kyre probability unavailable — verified history below readiness threshold."
    return (
        '<div class="cfbpp2-prop">'
        f'<div class="cfbpp2-prop-top"><div class="cfbpp2-prop-name">{escape(_market_label(market.get("market_key")))}</div>'
        f'<div class="cfbpp2-consensus">Consensus {_number(market.get("consensus_line"))}</div></div>'
        '<div class="cfbpp2-lines">'
        f'<div class="cfbpp2-line">Best Over<b>{escape(_text(best_over.get("sportsbook")) or "—")} • {_number(best_over.get("line"))} ({_price(best_over.get("price"))})</b></div>'
        f'<div class="cfbpp2-line">Best Under<b>{escape(_text(best_under.get("sportsbook")) or "—")} • {_number(best_under.get("line"))} ({_price(best_under.get("price"))})</b></div>'
        '</div>'
        '<div class="cfbpp2-context">'
        f'<span class="cfbpp2-mini">{int(market.get("book_count") or 0)} books</span>'
        f'<span class="cfbpp2-mini">{escape(movement_text)}</span>'
        f'<span class="cfbpp2-mini">Recent {escape(last3)}</span>'
        f'<span class="cfbpp2-mini">Avg {_number(recent.get("season_average"))}</span>'
        f'<span class="cfbpp2-mini">{escape(defense_label)}</span>'
        '</div>'
        f'<div class="cfbpp2-signal">{signal_text}</div></div>'
    )


def render_player_card_html(
    player: roster_owner.Page2Player,
    market_views: Sequence[Mapping[str, Any]],
    availability: Mapping[str, Any],
    rendered_props: Sequence[str],
    *,
    compact: bool = False,
) -> str:
    meta = " • ".join(value for value in (
        player.position,
        f"#{player.jersey_number}" if player.jersey_number else "",
        player.class_year,
    ) if value)
    status = _text(availability.get("state")) or "UNVERIFIED"
    status_class = "cfbpp2-status muted" if status == "UNVERIFIED" else "cfbpp2-status"
    player_class = "cfbpp2-player compact" if compact else "cfbpp2-player"
    face = _image_or_monogram(player.headshot_url, player.canonical_name, headshot=True)
    body = "".join(rendered_props)
    if not market_views:
        empty_copy = "No active verified prop markets." if compact else "No verified props posted yet."
        body += f'<div class="cfbpp2-empty">{empty_copy}</div>'
    return (
        f'<article class="{player_class}" data-player-id="{escape(player.official_player_id, quote=True)}">'
        '<div class="cfbpp2-player-head">'
        f'{face}<div><div class="cfbpp2-player-name">{escape(player.canonical_name)}</div><div class="cfbpp2-player-meta">{escape(meta)}</div></div>'
        f'<div class="{status_class}">{escape(status)}</div></div>{body}</article>'
    )


def _runtime_generation(context: Mapping[str, Any]) -> int:
    raw = st.session_state.get("ks_v5_runtime_state")
    if isinstance(raw, Mapping):
        active = raw.get("active") if isinstance(raw.get("active"), Mapping) else {}
        try:
            value = int(active.get("generation") or raw.get("generation") or 0)
            if value:
                return value
        except (TypeError, ValueError):
            pass
    return int(context.get("generation") or 0)


def _segmented(label: str, options: Sequence[str], key: str) -> str:
    try:
        return st.segmented_control(
            label, options=list(options), default=options[0], key=key,
            label_visibility="collapsed",
        ) or options[0]
    except AttributeError:
        return st.radio(
            label, options=list(options), index=0, key=key,
            horizontal=True, label_visibility="collapsed",
        )


def _position_filter() -> str:
    return _segmented("Position", ["ALL", "QB", "RB", "WR", "TE"], "cfbpp2_position")


def _market_filter() -> str:
    return _segmented(
        "Market",
        ["ALL", "PASS", "RUSH", "REC", "RECEPTIONS", "TD"],
        "cfbpp2_market",
    )


def _back() -> bool:
    if st.button("← Back to Player Props", key="cfbpp2_back", use_container_width=False):
        context_owner.clear_page2_selection(st.session_state, st.query_params)
        st.rerun()
        return True
    return False


def _season(context: Mapping[str, Any]) -> int:
    text = _text(context.get("game_date") or context.get("slate_date"))
    try:
        return int(text[:4])
    except (TypeError, ValueError):
        return 0


def _render_active_player(
    player: roster_owner.Page2Player,
    markets: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    availability: Mapping[str, Mapping[str, Any]],
    matchup_context: Mapping[str, Any],
) -> None:
    season = _season(context)
    rendered: list[str] = []
    prepared: list[Mapping[str, Any]] = []
    for market in markets:
        recent = matchup_owner.build_recent_production(
            player, _text(market.get("market_key")), season=season
        )
        signal = matchup_owner.build_page2_signal(
            player,
            _text(market.get("market_key")),
            recent.get("history") or (),
            market.get("observations") or (),
        )
        defense = matchup_owner.grade_player_matchup(
            player, _text(market.get("market_key")), matchup_context
        )
        rendered.append(render_prop_row_html(market, recent, defense, signal))
        prepared.append(market)
    st.markdown(
        render_player_card_html(
            player,
            markets,
            availability.get(player.official_player_id)
            or {"state": "UNVERIFIED", "verified": False},
            rendered,
        ),
        unsafe_allow_html=True,
    )
    for market in prepared:
        market_key = _text(market.get("market_key"))
        if st.button(
            "Analyze",
            key=f"cfbpp2_analyze_{player.official_player_id}_{market_key}",
            use_container_width=True,
        ):
            payload = page3_handoff.build_selected_prop_handoff(
                context, player, market, generation=_runtime_generation(context)
            )
            page3_handoff.commit_selected_prop_handoff(
                st.session_state, st.query_params, payload
            )
            st.rerun()


def _team_section(
    side: str,
    context: Mapping[str, Any],
    players: Sequence[roster_owner.Page2Player],
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    availability: Mapping[str, Mapping[str, Any]],
    matchup_context: Mapping[str, Any],
    position_filter: str,
    market_filter: str,
) -> None:
    team_name = _text(context.get(f"{side}_team")) or side.title()
    st.markdown(
        f'<section class="cfbpp2-team-section"><div class="cfbpp2-team-title">{escape(team_name)} • {side.title()}</div></section>',
        unsafe_allow_html=True,
    )
    shown = [
        player for player in players
        if position_filter == "ALL" or player.position == position_filter
    ]
    if not shown:
        st.caption("No verified players match this position filter.")
        return

    active, inactive = partition_players_by_markets(shown, grouped, market_filter)
    if active:
        st.markdown(
            f'<div class="cfbpp2-active-label">{len(active)} player{"s" if len(active) != 1 else ""} with active {escape(market_filter)} markets</div>',
            unsafe_allow_html=True,
        )
        for player in active:
            markets = filter_player_markets(
                list(grouped.get(player.official_player_id) or []), market_filter
            )
            _render_active_player(
                player, markets, context, availability, matchup_context
            )
    else:
        st.caption("No verified sportsbook markets match these filters right now.")

    if inactive:
        with st.expander(
            f"Other {team_name} roster players — no active markets ({len(inactive)})",
            expanded=False,
        ):
            for player in inactive:
                st.markdown(
                    render_player_card_html(
                        player,
                        [],
                        availability.get(player.official_player_id)
                        or {"state": "UNVERIFIED", "verified": False},
                        [],
                        compact=True,
                    ),
                    unsafe_allow_html=True,
                )


def render_cfb_player_props_page2() -> None:
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div id="cfbpp2-top"></div><a class="cfbpp2-top-link" href="#cfbpp2-top">↑ TOP</a>',
        unsafe_allow_html=True,
    )
    if _back():
        return

    context = context_owner.resolve_page2_context(st.session_state, st.query_params)
    if context.get("state") != "ready":
        st.markdown(
            '<div class="cfbpp2-shell">Selected game is unavailable. Return to Player Props.</div>',
            unsafe_allow_html=True,
        )
        return

    st_autorefresh(interval=30_000, key="cfbpp2_live_market_refresh")

    visuals = _visuals(context)
    st.markdown(render_hero_html(context, visuals), unsafe_allow_html=True)

    st.markdown('<div class="cfbpp2-filter-label">Position</div>', unsafe_allow_html=True)
    position_filter = _position_filter()
    st.markdown('<div class="cfbpp2-filter-label">Market</div>', unsafe_allow_html=True)
    market_filter = _market_filter()

    roster = roster_owner.load_offensive_roster(context)
    away_players = list(roster.get("away") or [])
    home_players = list(roster.get("home") or [])
    all_players = [*away_players, *home_players]
    if not all_players:
        st.markdown(
            '<div class="cfbpp2-shell">Verified roster temporarily unavailable.</div>',
            unsafe_allow_html=True,
        )
        return

    availability = availability_owner.load_game_availability(context, all_players)
    observations = market_owner.load_game_prop_observations(context, all_players)
    grouped = market_owner.group_player_markets(all_players, observations)
    matchup_context = matchup_owner.load_game_matchup_context(context)

    columns = st.columns(2, gap="medium")
    with columns[0]:
        _team_section(
            "away", context, away_players, grouped, availability,
            matchup_context, position_filter, market_filter,
        )
    with columns[1]:
        _team_section(
            "home", context, home_players, grouped, availability,
            matchup_context, position_filter, market_filter,
        )

    st.caption(
        "Live sportsbook markets refresh every 30 seconds • "
        "Verified sportsbook lines are market context only • "
        f"Kyre projection sportsbook influence: {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}%"
    )


__all__ = [
    "MARKET_FILTERS",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "filter_player_markets",
    "market_matches_filter",
    "partition_players_by_markets",
    "render_cfb_player_props_page2",
    "render_player_card_html",
    "render_prop_row_html",
]
