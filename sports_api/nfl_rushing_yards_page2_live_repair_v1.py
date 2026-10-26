"""Post-merge live-acceptance repair for NFL Rushing Yards Page 2.

Repairs only source paths that failed live after Data Completeness V1:
- explicit season/week NFL.com injury report with nickname-aware team headings;
- full-game FanDuel spread/total from the exact nflverse-reconciled FanDuel event;
- public Action Network rushing-prop Open/current context as independent history.

Kyre Sports API remains the only frontend gateway. No ESPN/ESPN BET/SGO.
Sportsbook evidence has 0.0 influence on Kyre projection math.
"""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
from typing import Any, Mapping

import requests

from sports_api import nfl_rushing_yards_page2_enrichment_v1 as v1
from sports_api.collectors import nfl_fanduel_rushing_yards_nflverse_v1 as rushing_book

VERSION = "NFL_RUSHING_PAGE2_LIVE_ACCEPTANCE_REPAIR_V1"
ACTION_RUSHING_URL = "https://www.actionnetwork.com/nfl/props/rushing"
ACTION_BASE = "https://www.actionnetwork.com"


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def official_injury_url(season: int, week: int) -> str:
    return f"https://www.nfl.com/injuries/league/{int(season)}/reg{int(week)}"


def _nickname_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for abbr, name in v1.TEAM_NAMES.items():
        nickname = name.split()[-1]
        out[nickname] = name
        if abbr == "SF":
            out["49ers"] = name
    return out


def parse_official_weekly_injuries(html: str) -> dict[str, dict[str, Any]]:
    # The NFL page labels report tables with nicknames ("Cowboys", "Eagles")
    # while the frozen parser intentionally recognizes full canonical names.
    # Expand exact heading text before delegating so row parsing stays unchanged.
    text = str(html or "")
    for nickname, full_name in sorted(_nickname_map().items(), key=lambda item: -len(item[0])):
        text = re.sub(
            rf"(?<=>)\s*{re.escape(nickname)}\s*(?=<)",
            full_name,
            text,
            flags=re.I,
        )
    return v1.parse_official_nfl_injury_html(text)


def collect_official_weekly_injuries(*, season: int, week: int) -> dict[str, dict[str, Any]]:
    response = requests.get(
        official_injury_url(season, week),
        timeout=10,
        headers={"Accept":"text/html","User-Agent":"Mozilla/5.0 (compatible; KyreSportsAPI-NFL/1.0)"},
    )
    response.raise_for_status()
    return parse_official_weekly_injuries(response.text)


def _market_key(market: Mapping[str, Any]) -> str:
    return _text(market.get("marketType") or market.get("marketTypeCode") or market.get("type")).upper()


def _market_name(market: Mapping[str, Any]) -> str:
    return _text(market.get("marketName") or market.get("name") or market.get("displayName")).casefold()


def _runner_name(runner: Mapping[str, Any]) -> str:
    return _text(runner.get("runnerName") or runner.get("name") or runner.get("selectionName"))


def parse_fanduel_game_lines(payload: Mapping[str, Any], *, away_name: str, home_name: str) -> dict[str, Any]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else {}
    if not isinstance(attachments, Mapping):
        return {}
    spread: dict[str, Any] = {}
    total: float | None = None
    spread_prices: dict[str, int | None] = {}
    total_prices: dict[str, int | None] = {}
    for market in rushing_book.base._rows(attachments.get("markets")):
        if not rushing_book.base._market_open(market):
            continue
        key, name = _market_key(market), _market_name(market)
        # Fail closed on halves, quarters, alternates and team totals.
        blocked = ("1ST_HALF", "FIRST_HALF", "QUARTER", "ALTERNATE", "ALTERNATIVE", "TEAM_TOTAL")
        if any(token in key for token in blocked) or any(token.replace("_", " ").lower() in name for token in blocked):
            continue
        runners = rushing_book.base._rows(market.get("runners"))
        if key in {"MATCH_HANDICAP_(2-WAY)", "MATCH_HANDICAP_2_WAY"} or name in {"point spread", "spread"}:
            for runner in runners:
                rname = _runner_name(runner)
                handicap = _num(runner.get("handicap"))
                if handicap is None:
                    continue
                if _norm(rname).startswith(_norm(away_name)):
                    spread["away_spread"] = handicap
                    spread_prices["away_spread_odds"] = rushing_book.base._american_odds(runner)
                elif _norm(rname).startswith(_norm(home_name)):
                    spread["home_spread"] = handicap
                    spread_prices["home_spread_odds"] = rushing_book.base._american_odds(runner)
        elif key in {"TOTAL_POINTS_(OVER/UNDER)", "TOTAL_POINTS_OVER_UNDER"} or name in {"total points", "total"}:
            points: list[float] = []
            for runner in runners:
                handicap = _num(runner.get("handicap"))
                if handicap is None:
                    continue
                role = rushing_book.base._runner_role(runner)
                if role in {"OVER", "UNDER"}:
                    points.append(handicap)
                    total_prices[role.lower() + "_odds"] = rushing_book.base._american_odds(runner)
            if points and len(set(points)) == 1:
                total = points[0]
    if set(spread) != {"away_spread", "home_spread"} or total is None:
        return {}
    return {"sportsbook":"FanDuel", **spread, **spread_prices, "total":total, **total_prices, "source":"FanDuel direct exact event"}


def collect_fanduel_game_lines(*, away_abbr: str, home_abbr: str, away_name: str, home_name: str, timeout: int = 8) -> dict[str, Any]:
    game = {"away":away_abbr,"home":home_abbr,"away_name":away_name,"home_name":home_name}
    landing = rushing_book._get_json_reliable(
        f"{rushing_book.base.FANDUEL_BASE_URL}/sbapi/content-managed-page",
        {"_ak":rushing_book.base.FANDUEL_PUBLIC_WEB_KEY,"page":"CUSTOM","customPageId":"nfl","timezone":"America/New_York"},
        timeout=timeout,
    )
    event_id = rushing_book.base._match_event(landing, game)
    if not event_id:
        return {}
    page = rushing_book._get_json_reliable(
        f"{rushing_book.base.FANDUEL_BASE_URL}/sbapi/event-page",
        {"_ak":rushing_book.base.FANDUEL_PUBLIC_WEB_KEY,"eventId":event_id},
        timeout=timeout,
    )
    row = parse_fanduel_game_lines(page, away_name=away_name, home_name=home_name)
    if row:
        row["provider_event_id"] = event_id
    return row


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
    def handle_data(self, data: str) -> None:
        text = _text(unescape(data))
        if text:
            self.parts.append(text)


def _visible_text(html: str) -> str:
    parser = _VisibleText()
    parser.feed(str(html or ""))
    return " ".join(parser.parts)


def parse_action_rushing_open_current(text: str, *, player_name: str) -> dict[str, Any]:
    flat = _text(text)
    player_pos = flat.casefold().find(_text(player_name).casefold())
    segment = flat[player_pos:player_pos + 3000] if player_pos >= 0 else flat
    match = re.search(
        r"Rush\s+Yds\s+[ou]?\s*(\d+(?:\.\d+)?)\s+[ou]?\s*(\d+(?:\.\d+)?)\s*[-+]?\d*",
        segment,
        flags=re.I,
    )
    if not match:
        return {}
    opening, current = float(match.group(1)), float(match.group(2))
    movement = round(current - opening, 1)
    return {
        "opening_line": opening,
        "current_line": current,
        "movement": movement,
        "source": "Action Network public player props",
        "opening_line_status": f"{opening:.1f} · Action Network open",
        "movement_status": f"ACTION NETWORK {opening:.1f} → {current:.1f} ({movement:+.1f})",
    }


def _discover_action_player_url(board_html: str, *, player_name: str) -> str:
    text = str(board_html or "")
    name_positions = [m.start() for m in re.finditer(re.escape(player_name), text, flags=re.I)]
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(r'href=["\'](?P<href>/nfl/players/[^"\']+/)["\']', text, flags=re.I):
        href = match.group("href")
        distance = min((abs(match.start() - pos) for pos in name_positions), default=10**9)
        if distance <= 6000:
            candidates.append((distance, href))
    candidates.sort(key=lambda item: item[0])
    return ACTION_BASE + candidates[0][1] if candidates else ""


def collect_action_prop_history(*, player_name: str, timeout: int = 8) -> dict[str, Any]:
    headers = {"Accept":"text/html","User-Agent":"Mozilla/5.0 (compatible; KyreSportsAPI-NFL/1.0)"}
    board = requests.get(ACTION_RUSHING_URL, timeout=timeout, headers=headers)
    board.raise_for_status()
    player_url = _discover_action_player_url(board.text, player_name=player_name)
    if not player_url:
        return {}
    page = requests.get(player_url, timeout=timeout, headers=headers)
    page.raise_for_status()
    row = parse_action_rushing_open_current(_visible_text(page.text), player_name=player_name)
    if row:
        row["url"] = player_url
    return row


def apply_live_acceptance_repair(
    detail: Mapping[str, Any], *, injury_report: Mapping[str, Any], game_lines: Mapping[str, Any], prop_history: Mapping[str, Any]
) -> dict[str, Any]:
    out = dict(detail or {})
    team, opponent = _text(out.get("team_abbr")).upper(), _text(out.get("opponent_abbr")).upper()
    context = v1.build_injury_personnel_context(injury_report, player_name=_text(out.get("player_name")), team=team, opponent=opponent)
    availability = dict(context.get("availability") or {})
    ol, front = dict(context.get("offensive_line") or {}), dict(context.get("defensive_front") or {})
    personnel_verified = ol.get("verification") == "VERIFIED" and front.get("verification") == "VERIFIED"
    out["availability"] = availability
    out["personnel"] = {
        "status":"VERIFIED" if personnel_verified else "DATA_UNAVAILABLE",
        "display":f"OL: {_text(ol.get('display'))} · Opp front: {_text(front.get('display'))}" if personnel_verified else "Official personnel report unavailable",
        "offensive_line":ol,"defensive_front":front,"source":"NFL.com Official Injury Report",
    }
    script = dict(out.get("game_script") or {})
    home_away = _text(out.get("home_away")).upper()
    if game_lines:
        sportsbook = _text(game_lines.get("sportsbook")) or "FanDuel"
        spread = game_lines.get("away_spread") if home_away == "AWAY" else game_lines.get("home_spread")
        if spread is not None:
            script["spread"] = float(spread)
            script["spread_status"] = f"{team} {float(spread):+.1f} · {sportsbook}"
            script["spread_verification"] = "VERIFIED"
        if game_lines.get("total") is not None:
            script["total"] = float(game_lines["total"])
            script["total_status"] = f"{float(game_lines['total']):.1f} · {sportsbook}"
            script["total_verification"] = "VERIFIED"
    out["game_script"] = script
    market = dict(out.get("market_intelligence") or {})
    if prop_history:
        market["opening_line"] = prop_history.get("opening_line")
        market["opening_line_status"] = prop_history.get("opening_line_status") or f"{float(prop_history['opening_line']):.1f} · Action Network open"
        market["movement"] = prop_history.get("movement")
        market["movement_status"] = prop_history.get("movement_status")
        market["history_source"] = prop_history.get("source")
    out["market_intelligence"] = market
    final = dict(out.get("final_read") or {})
    if availability.get("verification") == "VERIFIED" and personnel_verified:
        final["risk_factors"] = [str(x) for x in (final.get("risk_factors") or []) if "Personnel verification" not in str(x)]
    if prop_history:
        final["unresolved"] = [str(x) for x in (final.get("unresolved") or []) if "line-movement history" not in str(x)]
    out["final_read"] = final
    lineage = dict(out.get("source_lineage") or {})
    lineage.update({
        "page2_injury_personnel":"NFL.com explicit season/week injury report",
        "page2_game_market":"FanDuel direct exact nflverse-reconciled event",
        "page2_prop_history":"Action Network public rushing prop open/current",
    })
    out["source_lineage"] = lineage
    out["live_acceptance_repair_version"] = VERSION
    return out


__all__ = ["VERSION","apply_live_acceptance_repair","collect_action_prop_history","collect_fanduel_game_lines","collect_official_weekly_injuries","official_injury_url","parse_action_rushing_open_current","parse_fanduel_game_lines","parse_official_weekly_injuries"]
