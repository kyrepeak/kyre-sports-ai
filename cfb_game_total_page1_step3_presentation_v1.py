"""CFB Game Total Page 1 V2 Step 3 pure presentation helpers.

Phoenix-local display time, future-only day windows, and matchup-hero HTML only.
No model, projection, ranking, probability, qualification, or sportsbook math.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from html import escape
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

PHOENIX_TZ = "America/Phoenix"
EASTERN_TZ = "America/New_York"
DISPLAY_TIME_SUFFIX = "AZ"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _game_date(game: Mapping[str, Any]) -> date | None:
    for key in ("game_date", "start_date", "date"):
        raw = _clean(game.get(key))
        if not raw:
            continue
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            continue
    return None


def _parse_iso_kickoff(game: Mapping[str, Any]) -> datetime | None:
    for key in ("kickoff_iso", "start_time_utc", "kickoff_utc", "start_time", "start_date", "date"):
        raw = _clean(game.get(key))
        if not raw or ("T" not in raw and ":" not in raw):
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(EASTERN_TZ))
        return parsed
    return None


_ET_CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([AP]M)\s*(?:ET|EST|EDT)?\s*$", re.I)


def _parse_et_clock(game: Mapping[str, Any], identity: Mapping[str, Any] | None = None) -> datetime | None:
    candidates = []
    if identity:
        candidates.append(identity.get("kickoff"))
    candidates.extend(game.get(key) for key in ("kickoff_et", "kickoff"))
    game_day = _game_date(game)
    if game_day is None:
        return None
    for value in candidates:
        raw = _clean(value)
        match = _ET_CLOCK.match(raw)
        if not match:
            continue
        hour = int(match.group(1)) % 12
        if match.group(3).upper() == "PM":
            hour += 12
        clock = time(hour=hour, minute=int(match.group(2)))
        return datetime.combine(game_day, clock, tzinfo=ZoneInfo(EASTERN_TZ))
    return None


def phoenix_kickoff_datetime(
    game: Mapping[str, Any], identity: Mapping[str, Any] | None = None
) -> datetime | None:
    parsed = _parse_iso_kickoff(game) or _parse_et_clock(game, identity)
    return parsed.astimezone(ZoneInfo(PHOENIX_TZ)) if parsed is not None else None


def phoenix_kickoff_text(
    game: Mapping[str, Any], identity: Mapping[str, Any] | None = None
) -> str:
    parsed = phoenix_kickoff_datetime(game, identity)
    if parsed is not None:
        return parsed.strftime("%I:%M %p").lstrip("0") + f" {DISPLAY_TIME_SUFFIX}"
    return "TBD AZ"


def phoenix_day_text(
    game: Mapping[str, Any], identity: Mapping[str, Any] | None = None
) -> str:
    parsed = phoenix_kickoff_datetime(game, identity)
    if parsed is not None:
        return parsed.strftime("%a %b %d").upper().replace(" 0", " ")
    game_day = _game_date(game)
    return game_day.strftime("%a %b %d").upper().replace(" 0", " ") if game_day else "DATE TBD"


def normalized_future_selected_date(
    selected: date | str | None,
    *,
    now: datetime | None = None,
) -> date:
    reference = now or datetime.now(ZoneInfo(PHOENIX_TZ))
    if reference.tzinfo is None or reference.utcoffset() is None:
        reference = reference.replace(tzinfo=ZoneInfo(PHOENIX_TZ))
    else:
        reference = reference.astimezone(ZoneInfo(PHOENIX_TZ))
    floor = reference.date() + timedelta(days=1)
    parsed: date | None = None
    if isinstance(selected, date):
        parsed = selected
    elif selected:
        try:
            parsed = date.fromisoformat(str(selected)[:10])
        except ValueError:
            parsed = None
    return max(parsed or floor, floor)


def future_day_window(
    selected: date | str | None,
    *,
    now: datetime | None = None,
    count: int = 7,
) -> list[date]:
    anchor = normalized_future_selected_date(selected, now=now)
    return [anchor + timedelta(days=index) for index in range(max(1, int(count)))]


def _team_name(identity: Mapping[str, Any], stats: Mapping[str, Any], fallback: str) -> str:
    return _clean(identity.get("team")) or _clean(stats.get("team")) or fallback


def _conf(identity: Mapping[str, Any]) -> str:
    return _clean(identity.get("conference")) or "NCAAF"


def _record(stats: Mapping[str, Any]) -> str:
    return _clean(stats.get("record")) or "—"


def build_matchup_hero_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
    *,
    away_logo_html: str,
    home_logo_html: str,
) -> str:
    away_id = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
    home_id = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}
    away_name = _team_name(away_id, away, "Away")
    home_name = _team_name(home_id, home, "Home")
    kickoff = phoenix_kickoff_text(display_game, identity)
    day_text = phoenix_day_text(display_game, identity)
    venue = _clean(identity.get("venue")) or _clean(display_game.get("venue")) or "Venue pending"
    location = _clean(display_game.get("venue_location") or display_game.get("location") or display_game.get("city")) or "Location pending"
    temp = _clean(display_game.get("temperature"))
    temperature = (temp + "°") if temp else "—"
    precipitation = _clean(display_game.get("precipitation") or display_game.get("precipitation_pct") or display_game.get("precip"))
    weather = _clean(display_game.get("weather") or display_game.get("forecast")) or "Forecast pending"
    weather_sub = " • ".join(part for part in (f"{precip}% precipitation" if precipitation and "%" not in precipitation else precipitation, weather) if part)
    wind = _clean(display_game.get("wind") or display_game.get("wind_mph")) or "Wind pending"

    return f"""
<div class="gt236-hero" data-testid="gt236-matchup-hero" data-timezone="{PHOENIX_TZ}">
  <div class="gt236-glow"></div>
  <div class="gt236-topline">NCAA FBS • {escape(day_text)} • {escape(kickoff)}</div>
  <div class="gt236-stage">
    <div class="gt236-team away">
      <div class="gt236-logo">{away_logo_html}</div>
      <div class="gt236-copy"><strong>{escape(away_name)}</strong><span>{escape(_record(away))} ({escape(_conf(away_id))})</span><em>{escape(_conf(away_id))}</em></div>
    </div>
    <div class="gt236-vs">VS</div>
    <div class="gt236-team home">
      <div class="gt236-copy"><strong>{escape(home_name)}</strong><span>{escape(_record(home))} ({escape(_conf(home_id))})</span><em>{escape(_conf(home_id))}</em></div>
      <div class="gt236-logo">{home_logo_html}</div>
    </div>
  </div>
  <div class="gt236-facts">
    <div><i>▣</i><b>{escape(venue)}</b><span>{escape(location)}</span></div>
    <div><i>☀</i><b>{escape(temperature)}</b><span>{escape(weather_sub)}</span></div>
    <div><i>≋</i><b>{escape(wind)}</b><span>Wind</span></div>
    <div><i>◷</i><b>{escape(kickoff)}</b><span>{escape(day_text)} • PHX</span></div>
  </div>
</div>
<div class="gt236-tabs" data-testid="gt236-view-tabs" aria-label="Game Total page views">
  <span class="gt236-tab active" aria-current="page">Overview</span>
  <span class="gt236-tab disabled" aria-disabled="true" title="Full Analysis becomes active with Page 2">Full Analysis</span>
</div>
"""


__all__ = [
    "DISPLAY_TIME_SUFFIX",
    "EASTERN_TZ",
    "MAY_MODIFY_PROJECTION",
    "PHOENIX_TZ",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_matchup_hero_html",
    "future_day_window",
    "normalized_future_selected_date",
    "phoenix_day_text",
    "phoenix_kickoff_datetime",
    "phoenix_kickoff_text",
]
