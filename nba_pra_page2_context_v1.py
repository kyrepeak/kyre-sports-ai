'''NBA PRA Page 2 selected-player context derived from the Kyre Sports API Page-1 snapshot.'''
from __future__ import annotations

from typing import Any, Mapping

from nba_pra_team_identity_v1 import resolve_nba_team_logo

LINE_MOVED_LABEL = "LINE MOVED SINCE SELECTION"


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _find_key(rows: Mapping[str, Any], requested: str) -> str | None:
    if requested in rows:
        return requested
    target = _norm(requested)
    for key in rows:
        if _norm(key) == target:
            return str(key)
    return None


def _same_quote_values(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    fields = ("sportsbook", "line", "over_price", "under_price")
    for field in fields:
        left, right = a.get(field), b.get(field)
        if field == "sportsbook":
            if str(left or "").casefold() != str(right or "").casefold():
                return False
        elif left != right:
            return False
    return True


def _current_same_book(quotes: list[Mapping[str, Any]], selected: Mapping[str, Any]) -> Mapping[str, Any] | None:
    book = str(selected.get("sportsbook") or "").casefold()
    if not book:
        return None
    for quote in quotes:
        if str(quote.get("sportsbook") or "").casefold() == book:
            return quote
    return None


def build_page2_context(
    snapshot: Mapping[str, Any],
    selected_player_key: str,
    *,
    selected_quote: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    markets = snapshot.get("market") or {}
    profiles = snapshot.get("profiles") or {}
    market_key = _find_key(markets, selected_player_key)
    profile_key = _find_key(profiles, selected_player_key)
    if market_key is None or profile_key is None:
        return {"state": "player_unavailable", "selected_player_key": selected_player_key}

    market = dict(markets.get(market_key) or {})
    profile = dict(profiles.get(profile_key) or {})
    quotes = [dict(q) for q in (market.get("quotes") or []) if isinstance(q, Mapping)]
    featured = dict(market.get("featured_quote") or {})
    if not featured and quotes:
        featured = dict(quotes[0])
    if not featured:
        return {"state": "market_unavailable", "selected_player_key": selected_player_key, "player": profile}

    team = str(profile.get("team") or featured.get("team") or "").upper()
    game = None
    opponent = ""
    for candidate in snapshot.get("games") or []:
        away = str((candidate or {}).get("away_tricode") or "").upper()
        home = str((candidate or {}).get("home_tricode") or "").upper()
        if team and team in {away, home}:
            game = dict(candidate)
            opponent = home if team == away else away
            break
    if game is None:
        return {"state": "market_unavailable", "selected_player_key": selected_player_key, "player": profile}

    selected = dict(selected_quote) if isinstance(selected_quote, Mapping) else dict(featured)
    current = _current_same_book(quotes or [featured], selected) or dict(featured)
    moved = not _same_quote_values(selected, current)

    injuries = snapshot.get("injury_players") or {}
    injury = injuries.get(profile_key) or injuries.get(_norm(profile.get("player_name"))) or {}
    state = "line_moved" if moved else "ready"
    return {
        "state": state,
        "selected_player_key": profile_key,
        "slate_date": snapshot.get("slate_date"),
        "player": profile,
        "player_name": profile.get("player_name") or market.get("player_name"),
        "team": team,
        "team_logo": resolve_nba_team_logo(team),
        "opponent": opponent,
        "opponent_logo": resolve_nba_team_logo(opponent),
        "game": game,
        "market": market,
        "quotes": quotes,
        "selected_quote": selected,
        "current_quote": current,
        "line_moved": moved,
        "line_moved_label": LINE_MOVED_LABEL if moved else "",
        "availability": injury.get("status") or "UNVERIFIED",
    }
