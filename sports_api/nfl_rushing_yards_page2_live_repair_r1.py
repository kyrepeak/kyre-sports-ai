"""Production-readback repair for NFL Rushing Yards Page 2 completeness.

This successor keeps Kyre Sports API as the only application-facing gateway and
repairs the two provider assumptions that failed after PR #1824 reached live
production:

* current game spread/total are read directly from the same FanDuel NFL landing
  and event-page JSON used by the existing sportsbook collectors, reconciled by
  exact nflverse team abbreviations + kickoff (no ESPN dependency);
* injury/personnel truth is read from NFL.com's static AMP injury-report surface,
  which is server-readable and contains the official weekly report.

The Odds API remains an optional historical player-prop fallback only when its
credential is actually configured. Missing historical archives are represented
as a closed semantic state and are never fabricated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import re
from typing import Any, Mapping

import requests

from sports_api import nfl_rushing_yards_page2_enrichment_v1 as base
from sports_api.collectors import nfl_fanduel_passing_yards as fanduel
from sports_api.collectors import nfl_fanduel_spread_v1 as spread_mod
from sports_api.collectors import nfl_fanduel_game_totals_v1 as totals_mod

VERSION = "NFL_RUSHING_PAGE2_LIVE_REPAIR_R1"
NFL_INJURY_URL = "https://amp.nfl.com/injuries/"
MAX_KICKOFF_DELTA_SECONDS = 60 * 60

TEAM_NAMES = base.TEAM_NAMES
build_injury_personnel_context = base.build_injury_personnel_context
build_line_history = base.build_line_history
collect_weather = base.collect_weather
normalize_weather = base.normalize_weather
parse_game_markets = base.parse_game_markets
repair_history_dates = base.repair_history_dates

_NICKNAME_TO_ABBR = {
    "Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR","Bears":"CHI",
    "Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN","Lions":"DET","Packers":"GB",
    "Texans":"HOU","Colts":"IND","Jaguars":"JAX","Chiefs":"KC","Raiders":"LV","Chargers":"LAC",
    "Rams":"LAR","Dolphins":"MIA","Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG",
    "Jets":"NYJ","Eagles":"PHI","Steelers":"PIT","49ers":"SF","Seahawks":"SEA","Buccaneers":"TB",
    "Titans":"TEN","Commanders":"WAS",
}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _canon_team(value: Any) -> str:
    raw = _text(value).upper()
    return {"WSH":"WAS","JAC":"JAX"}.get(raw, raw)


def _parse_dt(value: Any) -> datetime | None:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        return None
    try:
        out = datetime.fromisoformat(text)
    except ValueError:
        return None
    if out.tzinfo is None or out.utcoffset() is None:
        return None
    return out.astimezone(timezone.utc)


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        out: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                out.append(row)
        return out
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def parse_official_nfl_injury_html(html: str) -> dict[str, dict[str, Any]]:
    """Parse official NFL AMP report while preserving the frozen V1 table parser."""
    repaired = str(html or "")
    # NFL AMP uses short team headings ("Cowboys", "Eagles", ...), while the
    # original parser was written for full display names. Expand only standalone
    # HTML text nodes; player names/content are otherwise untouched.
    for nickname, abbr in _NICKNAME_TO_ABBR.items():
        full = TEAM_NAMES[abbr]
        repaired = re.sub(
            rf"(?<=>)\s*{re.escape(nickname)}\s*(?=<)",
            full,
            repaired,
            flags=re.IGNORECASE,
        )
    return base.parse_official_nfl_injury_html(repaired)


@lru_cache(maxsize=1)
def collect_official_nfl_injury_report() -> dict[str, dict[str, Any]]:
    response = requests.get(
        NFL_INJURY_URL,
        timeout=10,
        headers={
            "User-Agent":"Mozilla/5.0 (compatible; KyreSportsAPI-NFL/1.0; read-only)",
            "Accept":"text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    report = parse_official_nfl_injury_html(response.text)
    if not report:
        raise RuntimeError("NFL AMP injury report parsed no team sections")
    return report


def match_fanduel_event(
    landing: Mapping[str, Any],
    *,
    away: str,
    home: str,
    kickoff: str,
) -> dict[str, Any]:
    """Resolve one FanDuel event by exact team abbreviations + kickoff only."""
    away = _canon_team(away)
    home = _canon_team(home)
    kickoff_utc = _parse_dt(kickoff)
    if not away or not home or kickoff_utc is None:
        return {}
    attachments = landing.get("attachments") if isinstance(landing, Mapping) else {}
    events = _rows((attachments or {}).get("events") if isinstance(attachments, Mapping) else [])
    matches: list[dict[str, Any]] = []
    for event in events:
        try:
            identity = fanduel._fanduel_event_identity(event)
        except Exception:
            continue
        candidate_away = _canon_team(identity.get("away_abbr"))
        candidate_home = _canon_team(identity.get("home_abbr"))
        candidate_kickoff = identity.get("kickoff_utc")
        if candidate_away != away or candidate_home != home or not isinstance(candidate_kickoff, datetime):
            continue
        delta = abs((candidate_kickoff.astimezone(timezone.utc) - kickoff_utc).total_seconds())
        if delta <= MAX_KICKOFF_DELTA_SECONDS:
            matches.append({
                "provider_event_id": _text(identity.get("provider_event_id")),
                "away": away,
                "home": home,
                "kickoff_delta_seconds": int(delta),
            })
    unique = {row["provider_event_id"]: row for row in matches if row.get("provider_event_id")}
    return dict(next(iter(unique.values()))) if len(unique) == 1 else {}


def parse_direct_fanduel_game_markets(
    event_page: Mapping[str, Any],
    *,
    provider_event_id: str,
) -> dict[str, Any]:
    """Extract one canonical full-game spread and total from an exact FD event."""
    spread_market = spread_mod._spread_market(event_page, provider_event_id)
    away_runner = spread_mod._role_runner(spread_market, "AWAY")
    home_runner = spread_mod._role_runner(spread_market, "HOME")
    away_spread = spread_mod._spread(away_runner)
    home_spread = spread_mod._spread(home_runner)
    total_row = totals_mod._extract_game_total(dict(event_page), provider_event_id)
    if abs(away_spread + home_spread) > 1e-9:
        raise ValueError("FanDuel spread pair is inconsistent")
    return {
        "sportsbook":"FanDuel",
        "provider":"FanDuel direct via Kyre Sports API",
        "provider_event_id":provider_event_id,
        "away_spread":away_spread,
        "home_spread":home_spread,
        "away_price":spread_mod._american_odds(away_runner),
        "home_price":spread_mod._american_odds(home_runner),
        "total":float(total_row["total"]),
        "over_price":total_row.get("over_price"),
        "under_price":total_row.get("under_price"),
        "timestamp":_text(total_row.get("updated_at_utc")) or datetime.now(timezone.utc).isoformat(),
        "identity_resolution":"EXACT_NFLVERSE_TEAMS_PLUS_KICKOFF",
        "sportsbook_line_averaging":False,
        "projection_weight":0.0,
    }


def collect_direct_fanduel_game_market(
    *,
    away: str,
    home: str,
    kickoff: str,
) -> dict[str, Any]:
    landing = fanduel.fetch_fanduel_nfl_landing(timeout=8)
    identity = match_fanduel_event(landing, away=away, home=home, kickoff=kickoff)
    provider_event_id = _text(identity.get("provider_event_id"))
    if not provider_event_id:
        return {}
    page = fanduel.fetch_fanduel_event_page(provider_event_id, timeout=8)
    return parse_direct_fanduel_game_markets(page, provider_event_id=provider_event_id)


def _abbr_for_name(name: str) -> str:
    target = _text(name).casefold()
    for abbr, full in TEAM_NAMES.items():
        if full.casefold() == target:
            return abbr
    return ""


def collect_market_context(
    *,
    away_name: str,
    home_name: str,
    kickoff_iso: str,
    player_name: str,
    current_prop: Mapping[str, Any],
) -> dict[str, Any]:
    """Field-first game market + optional historical prop enrichment."""
    away = _abbr_for_name(away_name)
    home = _abbr_for_name(home_name)
    game_market: dict[str, Any] = {}
    diagnostic: list[str] = []
    try:
        game_market = collect_direct_fanduel_game_market(away=away, home=home, kickoff=kickoff_iso)
    except Exception as exc:
        diagnostic.append(f"FANDUEL_GAME_MARKET_{type(exc).__name__}")

    # Historical player-prop snapshots remain optional. The existing V1 path is
    # allowed to query The Odds API only when a credential is truly configured.
    # It must never block or replace the direct FanDuel current market.
    history = base.build_line_history(current_prop, [])
    if base._api_key():
        try:
            legacy = base.collect_market_context(
                away_name=away_name,
                home_name=home_name,
                kickoff_iso=kickoff_iso,
                player_name=player_name,
                current_prop=current_prop,
            )
            history = dict(legacy.get("prop_history") or history)
            if not game_market:
                game_market = dict(legacy.get("game_market") or {})
        except Exception as exc:
            diagnostic.append(f"HISTORICAL_MARKET_{type(exc).__name__}")
    else:
        diagnostic.append("HISTORICAL_ARCHIVE_NOT_CONFIGURED")

    return {
        "game_market":game_market,
        "prop_history":history,
        "provider_event_id":_text(game_market.get("provider_event_id")),
        "diagnostic":";".join(diagnostic),
    }


__all__ = [
    "VERSION",
    "TEAM_NAMES",
    "build_injury_personnel_context",
    "build_line_history",
    "collect_direct_fanduel_game_market",
    "collect_market_context",
    "collect_official_nfl_injury_report",
    "collect_weather",
    "match_fanduel_event",
    "normalize_weather",
    "parse_direct_fanduel_game_markets",
    "parse_game_markets",
    "parse_official_nfl_injury_html",
    "repair_history_dates",
]
