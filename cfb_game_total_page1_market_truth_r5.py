"""CFB Game Total Page 1 market-truth + compact-card successor R5.

R4 remains the presentation baseline.  R5 adds an actually-consulted public
multi-book transport (Action Network), preserves ESPN/Kyre observations, and
selects one complete named sportsbook quote for the card so spread, moneyline,
and total can never be silently mixed across books.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape, unescape
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import requests
import streamlit as st

import cfb_game_total_page1_polish_r4 as r4

MODEL_VERSION = "CFB GAME TOTAL PAGE1 MARKET TRUTH R5"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE1_MARKET_TRUTH_R5_ACTIVE"
ACTION_ODDS_URL = "https://www.actionnetwork.com/ncaaf/odds"
ACTION_TIMEOUT_SECONDS = 12.0
CACHE_TTL_SECONDS = 30
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False
PAGE_WIDE_SOURCE_AUTHORITY = False
FABRICATION = False

_BOOK_PRIORITY = (
    "FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics", "BetRivers"
)
_AGGREGATE_BOOKS = {"consensus", "open"}
_BOOK_ALIASES = {
    "fanduel nj": "FanDuel", "fanduel": "FanDuel",
    "dk nj": "DraftKings", "draftkings nj": "DraftKings", "draftkings": "DraftKings",
    "betmgm nj": "BetMGM", "betmgm": "BetMGM",
    "caesars nj": "Caesars", "caesars": "Caesars",
    "bet365 nj": "bet365", "bet365": "bet365",
    "fanatics nj": "Fanatics", "fanatics": "Fanatics",
    "betrivers nj": "BetRivers", "betrivers": "BetRivers",
}
_R5_CSS = "<style id=\"cfb-game-total-page1-market-truth-r5\">\n" + (
    Path(__file__).with_name("cfb_game_total_page1_market_truth_r5.css").read_text(encoding="utf-8")
) + "\n</style>"
_BASE_CARD_VIEW_MODEL = r4.card_view_model
_MISSING = object()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_ts(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        out = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if out.tzinfo is None:
        return None
    return out.astimezone(timezone.utc)


def _book_name(value: Any) -> str:
    raw = _clean(value)
    return _BOOK_ALIASES.get(raw.casefold(), raw)


def _norm_team(value: Any) -> str:
    text = _clean(value).casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def _team_aliases(team: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("name", "full_name", "display_name", "location", "abbr"):
        value = _norm_team(team.get(key))
        if value:
            aliases.add(value)
    return aliases


def _action_team_aliases(team: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("full_name", "display_name", "location", "abbr", "short_name"):
        value = _norm_team(team.get(key))
        if value:
            aliases.add(value)
    return aliases


def _normal_row(rows: Any, side: str) -> Mapping[str, Any] | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("side")).casefold() != side:
            continue
        if _clean(row.get("line_status") or "normal").casefold() != "normal":
            continue
        if row.get("is_live") is True:
            continue
        return row
    return None


def _action_observations(game: Mapping[str, Any], books: Mapping[str, Any], observed_at: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    action_game_id = _clean(game.get("id"))
    for book_id, raw_pack in (game.get("markets") or {}).items():
        if not isinstance(raw_pack, Mapping):
            continue
        book_meta = books.get(str(book_id)) if isinstance(books, Mapping) else None
        book_meta = book_meta if isinstance(book_meta, Mapping) else {}
        raw_name = _clean(book_meta.get("display_name") or book_meta.get("parent_name") or book_id)
        book = _book_name(raw_name)
        if book.casefold() in _AGGREGATE_BOOKS or not book:
            continue
        event_markets = raw_pack.get("event") if isinstance(raw_pack.get("event"), Mapping) else {}
        away_ml = _normal_row(event_markets.get("moneyline"), "away")
        home_ml = _normal_row(event_markets.get("moneyline"), "home")
        away_sp = _normal_row(event_markets.get("spread"), "away")
        home_sp = _normal_row(event_markets.get("spread"), "home")
        over = _normal_row(event_markets.get("total"), "over")
        if away_ml is not None and home_ml is not None:
            av, hv = _num(away_ml.get("odds")), _num(home_ml.get("odds"))
            if av is not None and hv is not None:
                output.append({
                    "sportsbook": book, "raw_sportsbook": raw_name, "provider_id": f"action_{book_id}",
                    "market_type": "moneyline", "phase": "pregame", "value": hv,
                    "away_value": av, "home_value": hv, "observed_at_utc": observed_at,
                    "identity_verified": True, "transport": "action_network",
                    "provenance": f"Action Network NCAAF board • {raw_name}", "fabrication": False,
                    "action_event_id": action_game_id,
                })
        if away_sp is not None and home_sp is not None:
            av, hv = _num(away_sp.get("value")), _num(home_sp.get("value"))
            if av is not None and hv is not None:
                output.append({
                    "sportsbook": book, "raw_sportsbook": raw_name, "provider_id": f"action_{book_id}",
                    "market_type": "spread", "phase": "pregame", "value": hv,
                    "away_value": av, "home_value": hv, "observed_at_utc": observed_at,
                    "identity_verified": True, "transport": "action_network",
                    "provenance": f"Action Network NCAAF board • {raw_name}", "fabrication": False,
                    "action_event_id": action_game_id,
                })
        if over is not None:
            total = _num(over.get("value"))
            if total is not None:
                output.append({
                    "sportsbook": book, "raw_sportsbook": raw_name, "provider_id": f"action_{book_id}",
                    "market_type": "game_total", "phase": "pregame", "value": total,
                    "observed_at_utc": observed_at, "identity_verified": True,
                    "transport": "action_network", "provenance": f"Action Network NCAAF board • {raw_name}",
                    "fabrication": False, "action_event_id": action_game_id,
                })
    return output


def parse_action_network_board(text: str, *, observed_at_utc: str | None = None) -> list[dict[str, Any]]:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', text or "", re.S)
    if not match:
        return []
    try:
        data = json.loads(unescape(match.group(1)))
        page_props = data["props"]["pageProps"]
        board = page_props["scoreboardResponse"]
        books = page_props.get("allBooks") or {}
        games = board.get("games") or []
    except (KeyError, TypeError, json.JSONDecodeError):
        return []
    observed_at = observed_at_utc or _iso_now()
    parsed: list[dict[str, Any]] = []
    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        teams = [t for t in raw.get("teams") or [] if isinstance(t, Mapping)]
        away_id, home_id = raw.get("away_team_id"), raw.get("home_team_id")
        away = next((t for t in teams if str(t.get("id")) == str(away_id)), None)
        home = next((t for t in teams if str(t.get("id")) == str(home_id)), None)
        if away is None or home is None:
            continue
        observations = _action_observations(raw, books, observed_at)
        if not observations:
            continue
        parsed.append({
            "action_event_id": _clean(raw.get("id")),
            "start_time_utc": _clean(raw.get("start_time")),
            "away_aliases": sorted(_action_team_aliases(away)),
            "home_aliases": sorted(_action_team_aliases(home)),
            "observations": observations,
        })
    return parsed


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_action_market_board() -> list[dict[str, Any]]:
    response = requests.get(
        ACTION_ODDS_URL,
        timeout=ACTION_TIMEOUT_SECONDS,
        headers={"User-Agent": "KyreSportsAI/CFB-Page1-R5", "Accept": "text/html,application/xhtml+xml"},
    )
    response.raise_for_status()
    return parse_action_network_board(response.text, observed_at_utc=_iso_now())


def _kickoff_close(game: Mapping[str, Any], action_game: Mapping[str, Any]) -> bool:
    left = _parse_ts(game.get("kickoff_utc"))
    right = _parse_ts(action_game.get("start_time_utc"))
    if left is None or right is None:
        return True
    return abs((left - right).total_seconds()) <= 20 * 60


def _exact_action_match(game: Mapping[str, Any], action_games: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    away = r4._team(game, "away")
    home = r4._team(game, "home")
    away_aliases, home_aliases = _team_aliases(away), _team_aliases(home)
    for candidate in action_games:
        if not isinstance(candidate, Mapping) or not _kickoff_close(game, candidate):
            continue
        if away_aliases.intersection(set(candidate.get("away_aliases") or [])) and home_aliases.intersection(set(candidate.get("home_aliases") or [])):
            return candidate
    return None


def _observation_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _book_name(row.get("sportsbook")).casefold(),
        _clean(row.get("market_type")).casefold(),
        _clean(row.get("phase") or "pregame").casefold(),
        _clean(row.get("transport")).casefold(),
    )


def enrich_games_with_market_truth(
    games: Sequence[Mapping[str, Any]], *, action_games: Sequence[Mapping[str, Any]] | None = None
) -> list[dict[str, Any]]:
    if action_games is None:
        try:
            action_games = fetch_action_market_board()
        except Exception:
            action_games = []
    result: list[dict[str, Any]] = []
    for raw_game in games:
        game = dict(raw_game)
        existing = [dict(row) for row in game.get("market_observations") or [] if isinstance(row, Mapping)]
        match = _exact_action_match(game, action_games)
        if match is not None:
            new_rows: list[dict[str, Any]] = []
            for row in match.get("observations") or []:
                if not isinstance(row, Mapping):
                    continue
                enriched = dict(row)
                enriched["game_id"] = _clean(game.get("event_id"))
                new_rows.append(enriched)
            by_key = {_observation_key(row): row for row in existing}
            for row in new_rows:
                by_key[_observation_key(row)] = row
            existing = list(by_key.values())
            game.setdefault("provenance", {})
            if isinstance(game["provenance"], dict):
                game["provenance"]["sportsbook_lines_r5"] = "Action Network multi-book board + existing ESPN/Kyre observations"
        game["market_observations"] = existing
        result.append(game)
    return result


def _latest(rows: Sequence[Mapping[str, Any]], market_type: str) -> Mapping[str, Any] | None:
    filtered = [r for r in rows if _clean(r.get("market_type")).casefold() == market_type and _clean(r.get("phase") or "pregame").casefold() == "pregame"]
    if not filtered:
        return None
    return sorted(filtered, key=lambda r: (_parse_ts(r.get("observed_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[0]


def _book_quotes(observations: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    raw_names: dict[str, str] = {}
    for row in observations:
        if not isinstance(row, Mapping) or row.get("identity_verified") is not True:
            continue
        book = _book_name(row.get("sportsbook"))
        if not book or book.casefold() in _AGGREGATE_BOOKS:
            continue
        groups.setdefault(book, []).append(row)
        raw_names.setdefault(book, _clean(row.get("raw_sportsbook") or row.get("sportsbook")))
    quotes: dict[str, dict[str, Any]] = {}
    for book, rows in groups.items():
        ml, sp, total = _latest(rows, "moneyline"), _latest(rows, "spread"), _latest(rows, "game_total")
        if ml is None or sp is None or total is None:
            continue
        away_ml, home_ml = _num(ml.get("away_value")), _num(ml.get("home_value"))
        away_sp, home_sp = _num(sp.get("away_value")), _num(sp.get("home_value"))
        total_value = _num(total.get("value"))
        if None in {away_ml, home_ml, away_sp, home_sp, total_value}:
            continue
        timestamps = [_parse_ts(x.get("observed_at_utc")) for x in (ml, sp, total)]
        latest_ts = max((ts for ts in timestamps if ts is not None), default=None)
        quotes[book] = {
            "book": book, "raw_book": raw_names.get(book) or book,
            "away_moneyline": away_ml, "home_moneyline": home_ml,
            "away_spread": away_sp, "home_spread": home_sp, "total": total_value,
            "observed_at_utc": latest_ts.isoformat() if latest_ts else None,
            "transports": sorted({_clean(x.get("transport")) for x in (ml, sp, total) if _clean(x.get("transport"))}),
        }
    return quotes


def select_featured_book_quote(observations: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    quotes = _book_quotes(observations)
    for book in _BOOK_PRIORITY:
        if book in quotes:
            return quotes[book], quotes
    if not quotes:
        return None, quotes
    selected = sorted(
        quotes.values(),
        key=lambda q: (_parse_ts(q.get("observed_at_utc")) or datetime.min.replace(tzinfo=timezone.utc), q["book"]),
        reverse=True,
    )[0]
    return selected, quotes


def _american(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    n = int(value) if float(value).is_integer() else value
    return f"+{n}" if value > 0 else str(n)


def _spread(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:+g}"


def card_view_model(game: Mapping[str, Any]) -> dict[str, Any]:
    card = dict(_BASE_CARD_VIEW_MODEL(game))
    observations = [row for row in game.get("market_observations") or [] if isinstance(row, Mapping)]
    quote, quotes = select_featured_book_quote(observations)
    named_books = sorted({_book_name(row.get("sportsbook")) for row in observations if _book_name(row.get("sportsbook")) and _book_name(row.get("sportsbook")).casefold() not in _AGGREGATE_BOOKS})
    transports = sorted({_clean(row.get("transport")) for row in observations if _clean(row.get("transport"))})
    card.update({
        "market_book": quote["book"] if quote else "Verified market snapshot",
        "market_raw_book": quote["raw_book"] if quote else "",
        "market_source_count": len(named_books),
        "market_transport_count": len(transports),
        "market_books": named_books,
        "market_transports": transports,
        "market_quote_count": len(quotes),
        "line_observed_at_utc": quote.get("observed_at_utc") if quote else None,
        "away_spread": "Unavailable",
        "home_spread": card.get("spread") or "Unavailable",
    })
    if quote:
        card.update({
            "away_moneyline": _american(quote["away_moneyline"]),
            "home_moneyline": _american(quote["home_moneyline"]),
            "away_spread": _spread(quote["away_spread"]),
            "home_spread": _spread(quote["home_spread"]),
            "spread": _spread(quote["home_spread"]),
            "total": f"O/U {quote['total']:g}",
            "market_confidence": f"{len(quotes)} complete book quote{'s' if len(quotes) != 1 else ''}",
        })
    return card


def market_more_html(game: Mapping[str, Any], card: Mapping[str, Any]) -> str:
    books = ", ".join(card.get("market_books") or []) or "No complete named book"
    observed = _clean(card.get("line_observed_at_utc")) or "Timestamp unavailable"
    return (
        '<div class="cfbgt-r5-more-grid">'
        f'<div><span>Identity</span><strong>Event ID {escape(_clean(card.get("event_id")) or "Unavailable")}</strong><small>Team IDs {escape(_clean(card.get("away_id")))} / {escape(_clean(card.get("home_id")))}</small></div>'
        f'<div><span>Location</span><strong>{escape(_clean(card.get("venue")) or "Unavailable")}</strong><small>{escape(_clean(card.get("city")) or "—")}</small></div>'
        f'<div><span>Featured book</span><strong>{escape(_clean(card.get("market_book")))}</strong><small>{escape(str(card.get("market_quote_count") or 0))} complete books • {escape(observed)}</small></div>'
        f'<div class="wide"><span>Market sources</span><strong>{escape(books)}</strong><small>Transports: {escape(", ".join(card.get("market_transports") or []) or "Unavailable")}</small></div>'
        '</div>'
    )


def _render_game_card(game: Mapping[str, Any], selected_day) -> None:
    away, home = r4._team(game, "away"), r4._team(game, "home")
    card = card_view_model(game)
    status = r4._status_state(game)
    score = ""
    if status in {"Live", "Halftime", "Final"}:
        score = f" • {escape(r4._clean(away.get('score')) or '—')}–{escape(r4._clean(home.get('score')) or '—')}"
    away_logo = f'<img class="cfbgt-team-logo" src="{escape(card["away_logo"], quote=True)}" alt="" loading="lazy">' if card["away_logo"] else '<span></span>'
    home_logo = f'<img class="cfbgt-team-logo" src="{escape(card["home_logo"], quote=True)}" alt="" loading="lazy">' if card["home_logo"] else '<span></span>'
    away_sub = " • ".join(x for x in (card["away_conference"], r4._clean(away.get("record"))) if x) or "College Football"
    home_sub = " • ".join(x for x in (card["home_conference"], r4._clean(home.get("record"))) if x) or "College Football"
    move_display = "No verified move" if card["total_move"] == "Unavailable" else f'{card["total_move"]} pts'
    with st.container(border=True):
        st.markdown(
            '<div class="cfbgt-r5-sourcebar"><span>Sportsbook quote</span>'
            f'<strong>{escape(card["market_book"])}</strong><small>{card["market_quote_count"]} complete books checked</small></div>'
            '<div class="cfbgt-matchup"><div class="cfbgt-team-row">'
            f'{away_logo}<div><div class="cfbgt-team-name">{escape(r4._team_title(away))}</div><div class="cfbgt-team-sub">{escape(away_sub)}</div></div><span class="cfbgt-team-id">ID {escape(card["away_id"])}</span></div>'
            '<div class="cfbgt-at">at</div><div class="cfbgt-team-row">'
            f'{home_logo}<div><div class="cfbgt-team-name">{escape(r4._team_title(home))}</div><div class="cfbgt-team-sub">{escape(home_sub)}</div></div><span class="cfbgt-team-id">ID {escape(card["home_id"])}</span></div></div>'
            f'<div class="cfbgt-card-meta"><strong>{escape(r4._status_line(game))}</strong>{score} &nbsp;•&nbsp; 📺 {escape(card["broadcast"])}</div>'
            f'<div class="cfbgt-detail-row"><span>🏟️ {escape(card["venue"])} • {escape(card["city"])}</span><span>🌤️ {escape(card["weather"])}</span></div>'
            f'<div class="cfbgt-total-focus"><div><div class="cfbgt-total-label">{escape(card["market_book"])} Total</div><div class="cfbgt-total-number">{escape(card["total"])}</div></div><div class="cfbgt-total-move">Open <strong>{escape(card["opening_total"])}</strong><br>Move <strong>{escape(move_display)}</strong></div></div>'
            '<div class="cfbgt-market-grid cfbgt-r5-market-grid">'
            f'<div class="cfbgt-market-cell"><span class="label">Away ML</span><span class="value">{escape(card["away_moneyline"])}</span></div>'
            f'<div class="cfbgt-market-cell"><span class="label">Home ML</span><span class="value">{escape(card["home_moneyline"])}</span></div>'
            f'<div class="cfbgt-market-cell"><span class="label">Away Spread</span><span class="value">{escape(card["away_spread"])}</span></div>'
            f'<div class="cfbgt-market-cell"><span class="label">Home Spread</span><span class="value">{escape(card["home_spread"])}</span></div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("More ↓", expanded=False):
            st.markdown(market_more_html(game, card), unsafe_allow_html=True)
        href = r4.view_game_href(game, selected_day)
        if href:
            st.markdown(f'<div class="cfbgt-view"><a href="{escape(href, quote=True)}" target="_self">View Game →</a></div>', unsafe_allow_html=True)
        else:
            st.caption("View Game unavailable — exact game identity is missing")


def _enriched_loader(delegate):
    def load(*args, **kwargs):
        payload = dict(delegate(*args, **kwargs))
        games = payload.get("games") or []
        if games:
            payload["games"] = enrich_games_with_market_truth(games)
            payload["market_truth_r5"] = True
        return payload
    load._cfbgt_r5_delegate = delegate  # type: ignore[attr-defined]
    return load


def install_into(target):
    """Layer R5 over an already-installed R4 Daily Slate module."""
    target_attrs = ("card_view_model", "_render_game_card", "enrich_games_with_market_truth", "market_more_html", "PAGE_CSS")
    target_originals = {name: getattr(target, name, _MISSING) for name in target_attrs}
    r4_attrs = ("_load_day", "_load_slate_cached_20", "card_view_model", "_render_game_card", "PAGE_CSS")
    r4_originals = {name: getattr(r4, name) for name in r4_attrs}

    r4._load_day = _enriched_loader(r4._load_day)
    r4._load_slate_cached_20 = _enriched_loader(r4._load_slate_cached_20)
    r4.card_view_model = card_view_model
    r4._render_game_card = _render_game_card
    r4.PAGE_CSS = r4.PAGE_CSS + _R5_CSS

    target.card_view_model = card_view_model
    target._render_game_card = _render_game_card
    target.enrich_games_with_market_truth = enrich_games_with_market_truth
    target.market_more_html = market_more_html
    target.PAGE_CSS = r4.PAGE_CSS
    return {"target": target_originals, "r4": r4_originals}


def restore_from(target, originals) -> None:
    for name, value in originals["target"].items():
        if value is _MISSING:
            if hasattr(target, name):
                delattr(target, name)
        else:
            setattr(target, name, value)
    for name, value in originals["r4"].items():
        setattr(r4, name, value)


__all__ = [
    "ACTIVE_MARKER", "ACTION_ODDS_URL", "FABRICATION", "MODEL_VERSION", "PAGE_WIDE_SOURCE_AUTHORITY",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "card_view_model", "enrich_games_with_market_truth", "fetch_action_market_board",
    "install_into", "market_more_html", "parse_action_network_board", "restore_from", "select_featured_book_quote",
]
