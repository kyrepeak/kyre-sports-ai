"""CFB Player Props Page 1 V1 — professional game-first prop hub."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from html import escape
import math
import re
from typing import Any, Callable, Mapping, Sequence

import streamlit as st

import cfb_over_under_environment_engine_v1 as cfb_environment
import cfb_over_under_logo_resolver_v2 as logo_fallback
import cfb_over_under_logo_resolver_v3 as logo_exact
import cfb_player_props_fanduel_v1 as fanduel
import cfb_player_props_history_v1 as history_engine
import cfb_player_props_identity_v1 as player_identity
import cfb_player_props_market_v1 as prop_market
import cfb_player_props_model_v1 as signal_model
import cfb_player_props_page1_handoff_v1 as handoff
import cfb_player_props_page1_slate_v1 as slate_engine
import cfb_player_props_sportsgameodds_v1 as sgo
from sports_api.api import cfb_market_identity_v1 as game_identity

MODEL_VERSION = "CFB PLAYER PROPS PAGE 1 V1 • GAME-FIRST PROP HUB"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MARKET = "Player Props"
MARKET_LABELS = {
    "passing_yards": "Passing Yards",
    "rushing_yards": "Rushing Yards",
    "receiving_yards": "Receiving Yards",
    "receiving_receptions": "Receptions",
    "passing_touchdowns": "Passing TDs",
    "touchdowns": "Anytime TD",
}

_PAGE_CSS = """
<style data-cfb-player-props-page1-css="v1">
.cfbpp1-hero{border:1px solid rgba(125,211,252,.23);border-radius:22px;padding:20px;margin:8px 0 14px;background:radial-gradient(circle at 92% 0,rgba(56,189,248,.13),transparent 24rem),linear-gradient(145deg,rgba(5,12,22,.99),rgba(8,23,39,.97));overflow:hidden}
.cfbpp1-kicker{font-size:.7rem;font-weight:900;letter-spacing:.16em;color:#7dd3fc}.cfbpp1-title{font-size:clamp(1.65rem,5vw,2.7rem);font-weight:950;color:#f8fafc;letter-spacing:-.045em;margin:.3rem 0}.cfbpp1-sub{color:#9fb3ca;font-size:.88rem;line-height:1.45}.cfbpp1-status{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.cfbpp1-chip,.cfbpp1-badge{display:inline-flex;align-items:center;border:1px solid rgba(125,211,252,.19);border-radius:999px;padding:6px 9px;font-size:.68rem;font-weight:850;color:#dbeafe;background:rgba(14,165,233,.06)}
.cfbpp1-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:10px}.cfbpp1-card{min-width:0;border:1px solid rgba(125,211,252,.17);border-radius:18px;padding:14px;background:linear-gradient(160deg,rgba(7,16,28,.99),rgba(9,25,42,.97));box-shadow:0 10px 30px rgba(0,0,0,.16)}.cfbpp1-meta{display:flex;justify-content:space-between;gap:8px;color:#8197af;font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.cfbpp1-team{display:grid;grid-template-columns:42px minmax(0,1fr);gap:9px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(125,211,252,.09)}.cfbpp1-team img{width:40px;height:40px;object-fit:contain}.cfbpp1-monogram{width:40px;height:40px;border-radius:11px;border:1px solid rgba(125,211,252,.18);display:flex;align-items:center;justify-content:center;font-weight:950;color:#7dd3fc}.cfbpp1-team b{display:block;color:#f3f7fb;font-size:.91rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbpp1-team span{display:block;color:#71869c;font-size:.65rem;margin-top:2px}.cfbpp1-marketrow{display:flex;flex-wrap:wrap;gap:5px;margin:10px 0}.cfbpp1-badge{padding:5px 7px;font-size:.61rem}.cfbpp1-empty{border:1px dashed rgba(148,163,184,.22);border-radius:12px;padding:11px;color:#8294a8;font-size:.75rem;margin-top:9px}.cfbpp1-signal{border:1px solid rgba(52,211,153,.23);border-radius:13px;padding:11px;margin-top:9px;background:rgba(16,185,129,.05)}.cfbpp1-signal-k{font-size:.61rem;font-weight:950;letter-spacing:.12em;color:#6ee7b7;text-transform:uppercase}.cfbpp1-signal-main{font-size:.84rem;font-weight:900;color:#edfdf6;margin-top:4px}.cfbpp1-signal-meta{font-size:.68rem;color:#95b8aa;margin-top:4px}
@media(max-width:760px){.cfbpp1-grid{grid-template-columns:1fr}.cfbpp1-hero{padding:16px 14px;border-radius:17px}.cfbpp1-card{padding:12px}.cfbpp1-title{font-size:1.65rem}}
</style>
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _text(value).casefold()))


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _rank(value: Any) -> str:
    text = _text(value)
    return f"#{text} " if text and text not in {"0", "None"} else ""


def _pct(value: Any) -> str:
    number = _finite(value)
    return f"{100*number:.1f}%" if number is not None else "—"


def _signed_pct(value: Any) -> str:
    number = _finite(value)
    return f"{100*number:+.1f}%" if number is not None else "—"


def _market_label(value: Any) -> str:
    key = _text(value)
    return MARKET_LABELS.get(key, key.replace("_", " ").title())


def rank_top_signal(signals: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    ready = []
    for raw in signals:
        row = dict(raw)
        probability = _finite(row.get("model_probability"))
        if row.get("model_ready") is not True or probability is None:
            continue
        edge = _finite(row.get("edge"))
        positive = edge is not None and edge > 0
        ready.append((
            0 if positive else 1,
            -(edge if positive else -1.0),
            -probability,
            -int(row.get("book_count") or 0),
            _text(row.get("player_name")).casefold(),
            _text(row.get("market_key")),
            row,
        ))
    return dict(sorted(ready, key=lambda item: item[:-1])[0][-1]) if ready else None


def build_game_card_view(
    game: Mapping[str, Any],
    observations: Sequence[prop_market.PropObservation],
    signals: Sequence[Mapping[str, Any]],
    visuals: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    markets = tuple(sorted({_market_label(row.market_key) for row in observations}))
    books = {row.sportsbook for row in observations if row.sportsbook}
    return {
        **dict(game),
        "has_props": bool(observations),
        "observation_count": len(observations),
        "book_count": len(books),
        "market_badges": markets,
        "empty_message": "" if observations else "No verified player props posted yet",
        "top_signal": rank_top_signal(signals),
        "away_logo": _text((visuals.get("away") or {}).get("logo")),
        "home_logo": _text((visuals.get("home") or {}).get("logo")),
    }


def _logo_or_monogram(url: str, team: str) -> str:
    if url.startswith(("https://", "http://")):
        return f'<img src="{escape(url, quote=True)}" alt="{escape(team)} logo" loading="lazy" />'
    letters = "".join(part[:1] for part in team.split()[:2]).upper() or "CFB"
    return f'<div class="cfbpp1-monogram">{escape(letters)}</div>'


def render_game_card_html(card: Mapping[str, Any]) -> str:
    game_id = escape(_text(card.get("official_game_id")), quote=True)
    away = _text(card.get("away_team")) or "Away"
    home = _text(card.get("home_team")) or "Home"
    badges = "".join(f'<span class="cfbpp1-badge">{escape(label)}</span>' for label in card.get("market_badges") or ())
    signal = card.get("top_signal") if isinstance(card.get("top_signal"), Mapping) else None
    if signal:
        side = _text(signal.get("side")).upper()
        signal_html = (
            '<div class="cfbpp1-signal">'
            '<div class="cfbpp1-signal-k">Top Kyre Signal</div>'
            f'<div class="cfbpp1-signal-main">{escape(_text(signal.get("player_name")))} • {escape(_market_label(signal.get("market_key")))} • {escape(side)} {escape(_text(signal.get("consensus_line")))}</div>'
            f'<div class="cfbpp1-signal-meta">Model {_pct(signal.get("model_probability"))} • Edge {_signed_pct(signal.get("edge"))} • {int(signal.get("book_count") or 0)} verified books</div>'
            '</div>'
        )
    else:
        signal_html = ""
    coverage = (
        f'<div class="cfbpp1-marketrow"><span class="cfbpp1-chip">{int(card.get("book_count") or 0)} books</span>{badges}</div>'
        if card.get("has_props")
        else f'<div class="cfbpp1-empty">{escape(_text(card.get("empty_message")))}</div>'
    )
    return (
        f'<article class="cfbpp1-card" data-cfb-player-props-game="{game_id}">'
        f'<div class="cfbpp1-meta"><span>{escape(_text(card.get("kickoff_phoenix")))}</span><span>{escape(_text(card.get("status")))}</span></div>'
        f'<div class="cfbpp1-team">{_logo_or_monogram(_text(card.get("away_logo")), away)}<div><b>{escape(_rank(card.get("away_rank")) + away)}</b><span>Away</span></div></div>'
        f'<div class="cfbpp1-team">{_logo_or_monogram(_text(card.get("home_logo")), home)}<div><b>{escape(_rank(card.get("home_rank")) + home)}</b><span>Home</span></div></div>'
        f'{coverage}{signal_html}</article>'
    )


def _enrich_game_identity(game: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(game)
    if _text(out.get("away_team_id")) and _text(out.get("home_team_id")):
        return out
    try:
        payload, _ = cfb_environment._fetch_scoreboard(_text(out.get("game_date")))
        event = cfb_environment._resolve_event(payload, out)
        sides = cfb_environment._side_meta(event) if event else {}
        for side in ("away", "home"):
            meta = sides.get(side) or {}
            if not _text(out.get(f"{side}_team_id")):
                out[f"{side}_team_id"] = _text(meta.get("team_id"))
            out[f"{side}_abbr"] = _text(meta.get("abbreviation"))
        if event:
            out["espn_event_id"] = _text(event.get("id"))
    except Exception:
        pass
    return out


def _visuals_for_game(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    exact_game = dict(game)
    exact_game["away_espn_team_id"] = _text(game.get("away_team_id"))
    exact_game["home_espn_team_id"] = _text(game.get("home_team_id"))
    try:
        visuals = logo_exact.resolve_visuals(exact_game)
    except Exception:
        visuals = {"away": {}, "home": {}}
    out = {"away": dict(visuals.get("away") or {}), "home": dict(visuals.get("home") or {})}
    for side in ("away", "home"):
        if _text(out[side].get("logo")):
            continue
        try:
            fallback = logo_fallback.resolve_team_logo(
                _text(game.get(f"{side}_team")),
                _text(game.get(f"{side}_team_slug")),
                _text(game.get(f"{side}_conference")),
            )
            if isinstance(fallback, Mapping):
                out[side] = dict(fallback)
        except Exception:
            pass
    return out


def _walk_athletes(node: Any):
    if isinstance(node, Mapping):
        name = _text(node.get("fullName") or node.get("displayName") or node.get("name"))
        athlete_id = _text(node.get("id") or node.get("athleteId"))
        if athlete_id and name and node.get("position") is not None:
            yield node
        for value in node.values():
            yield from _walk_athletes(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_athletes(value)


def _game_players(game: Mapping[str, Any]) -> list[player_identity.CanonicalPlayerIdentity]:
    players: dict[str, player_identity.CanonicalPlayerIdentity] = {}
    for side in ("away", "home"):
        team_id = _text(game.get(f"{side}_team_id"))
        if not team_id:
            continue
        try:
            payload, _ = cfb_environment._fetch_roster(team_id)
        except Exception:
            payload = {}
        for row in _walk_athletes(payload):
            player = player_identity.player_identity_from_roster_row(
                row,
                official_team_id=team_id,
                team_name=_text(game.get(f"{side}_team")),
                team_abbr=_text(game.get(f"{side}_abbr")),
            )
            if player is not None:
                players[player.official_player_id] = player
    return list(players.values())


def _verified_identity_rows(games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": _text(game.get("official_game_id")),
            "game_date": _text(game.get("game_date")),
            "away_team": _text(game.get("away_team")),
            "home_team": _text(game.get("home_team")),
            "away_team_id": _text(game.get("away_team_id")),
            "home_team_id": _text(game.get("home_team_id")),
        }
        for game in games if _text(game.get("official_game_id"))
    ]


def _bind_raw_observations(
    raws: Sequence[Mapping[str, Any]],
    games: Sequence[Mapping[str, Any]],
    players_by_game: Mapping[str, Sequence[player_identity.CanonicalPlayerIdentity]],
) -> list[prop_market.PropObservation]:
    verified = _verified_identity_rows(games)
    normalized: list[prop_market.PropObservation] = []
    for raw in raws:
        provider_game = {
            "start_time_utc": raw.get("event_start"),
            "away_team": raw.get("away_team"),
            "home_team": raw.get("home_team"),
        }
        if not all(_text(provider_game.get(k)) for k in ("start_time_utc", "away_team", "home_team")):
            continue
        try:
            _, candidates = game_identity._qualified_candidates(provider_game, verified)
        except Exception:
            continue
        if len(candidates) != 1:
            continue
        official = candidates[0]["verified"]
        game_id = _text(official.get("event_id"))
        player_name = _norm(raw.get("player_name"))
        roster = list(players_by_game.get(game_id) or [])
        matches = [p for p in roster if _norm(p.canonical_name) == player_name and player_name]
        if len(matches) != 1:
            continue
        player = matches[0]
        enriched = dict(raw)
        enriched.update({
            "official_game_id": game_id,
            "official_player_id": player.official_player_id,
            "official_team_id": player.official_team_id,
        })
        obs = prop_market.normalize_prop_observation(
            enriched,
            player_identity.build_identity_index([player]),
        )
        if obs is not None:
            normalized.append(obs)
    return prop_market.merge_prop_observations(normalized)


def _signals_for_game(
    game: Mapping[str, Any],
    observations: Sequence[prop_market.PropObservation],
    players: Sequence[player_identity.CanonicalPlayerIdentity],
    *,
    history_loader: Callable[..., list[dict[str, Any]]] = history_engine.load_verified_player_history,
) -> list[dict[str, Any]]:
    by_player = {p.official_player_id: p for p in players}
    grouped: dict[tuple[str, str], list[prop_market.PropObservation]] = defaultdict(list)
    for obs in observations:
        grouped[(obs.canonical_player_id, obs.market_key)].append(obs)
    try:
        season = int(_text(game.get("game_date"))[:4])
    except ValueError:
        season = date.today().year
    signals = []
    for (player_id, market_key), rows in grouped.items():
        player = by_player.get(player_id)
        if player is None:
            continue
        history = history_loader(player, market_key, season=season)
        signal = signal_model.build_page1_signal(player, market_key, history, rows)
        if signal.get("model_ready") is True and signal.get("model_probability") is not None:
            signals.append(signal)
    return signals


def _runtime_generation() -> int:
    raw = st.session_state.get("ks_v5_runtime_state")
    if isinstance(raw, Mapping):
        active = raw.get("active") if isinstance(raw.get("active"), Mapping) else {}
        return int(active.get("generation") or raw.get("generation") or 0)
    return 0


def _segmented(label: str, options: list[str], default: str, key: str) -> str:
    try:
        return st.segmented_control(label, options=options, default=default, key=key, label_visibility="collapsed") or default
    except AttributeError:
        return st.radio(label, options=options, index=options.index(default), key=key, horizontal=True, label_visibility="collapsed")


def render_cfb_player_props_page1() -> None:
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    slate = slate_engine.load_next_player_prop_slate()
    games = [_enrich_game_identity(game) for game in slate.get("games") or []]
    slate_date = slate.get("slate_date")
    date_label = slate_date.strftime("%a %b %d, %Y") if isinstance(slate_date, date) else "Unavailable"

    sgo_raw = sgo.fetch_sgo_cfb_player_props(slate_date) if isinstance(slate_date, date) else []
    fd_raw = fanduel.fetch_fanduel_cfb_player_props(games) if games else []
    players_by_game = {game["official_game_id"]: _game_players(game) for game in games}
    observations = _bind_raw_observations([*sgo_raw, *fd_raw], games, players_by_game)
    by_game: dict[str, list[prop_market.PropObservation]] = defaultdict(list)
    for obs in observations:
        by_game[obs.official_game_id].append(obs)

    covered = len({obs.official_game_id for obs in observations})
    sources = sorted({obs.provider for obs in observations if obs.provider})
    source_label = " + ".join(sources) if sources else "Market feeds pending"
    st.markdown(
        '<section class="cfbpp1-hero" data-cfb-player-props-page1="v1">'
        '<div class="cfbpp1-kicker">CFB • PLAYER PROPS</div>'
        '<div class="cfbpp1-title">College Football Player Props</div>'
        f'<div class="cfbpp1-sub">Next active slate • {escape(date_label)} • Game-first prop intelligence with verified identities and sportsbook-independent Kyre projections.</div>'
        '<div class="cfbpp1-status">'
        f'<span class="cfbpp1-chip">{len(games)} games</span><span class="cfbpp1-chip">{covered} with verified props</span><span class="cfbpp1-chip">{escape(source_label)}</span>'
        '</div></section>',
        unsafe_allow_html=True,
    )
    if slate.get("state") != "live" or not games:
        st.info("Next active CFB slate is temporarily unavailable. No games were synthesized.")
        return

    coverage = _segmented("Coverage", ["All Games", "Live Props"], "All Games", "cfbpp1_coverage")
    sort_mode = _segmented("Sort", ["Kickoff", "Strongest Edge"], "Kickoff", "cfbpp1_sort")

    cards = []
    for game in games:
        rows = by_game.get(game["official_game_id"], [])
        signals = _signals_for_game(game, rows, players_by_game.get(game["official_game_id"], [])) if rows else []
        cards.append(build_game_card_view(game, rows, signals, _visuals_for_game(game)))
    if coverage == "Live Props":
        cards = [card for card in cards if card["has_props"]]
    if sort_mode == "Strongest Edge":
        cards.sort(key=lambda card: (-(_finite((card.get("top_signal") or {}).get("edge")) or -1.0), card.get("kickoff_iso") or ""))

    if not cards:
        st.info("No games match this Page 1 filter yet.")
        return
    st.markdown('<div class="cfbpp1-grid">', unsafe_allow_html=True)
    for card in cards:
        st.markdown(render_game_card_html(card), unsafe_allow_html=True)
        if st.button("View Game Props", key=f"cfbpp1_view_{card['official_game_id']}", use_container_width=True):
            payload = handoff.build_selected_game_handoff(
                card,
                slate_date=slate_date,
                generation=_runtime_generation(),
            )
            handoff.commit_selected_game_handoff(st.session_state, st.query_params, payload)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("Verified sportsbook lines are threshold/context only • Kyre projection sportsbook influence: 0.0%")


__all__ = [
    "MARKET", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "build_game_card_view",
    "rank_top_signal", "render_cfb_player_props_page1", "render_game_card_html",
]
