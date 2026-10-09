"""CFB Game Total Page 2 Step 2 — matchup hero + Phoenix time.

Presentation-only Page-2 component. It consumes the already-selected verified
matchup and already-owned market values. It performs no network calls, changes
no projection/model/market ownership, and does not modify frozen Page 1.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

PHOENIX_TZ = "America/Phoenix"
STEP2_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_PAGE1 = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

PAGE2_STEP2_CSS = r"""
<style>
.gtp2s2-wrap{max-width:1180px;margin:0 auto 18px;color:#f7fbff}
.gtp2s2-heading{text-align:center;margin:0 0 11px}.gtp2s2-heading h2{margin:0;color:#fff;font-size:32px;line-height:1;font-weight:1000;letter-spacing:-.025em}.gtp2s2-heading p{margin:7px 0 0;color:#9cb6c9;font-size:11px;font-weight:800;letter-spacing:.035em}
.gtp2s2-hero{position:relative;overflow:hidden;border:1px solid rgba(75,197,255,.46);border-radius:22px;background:radial-gradient(circle at 50% 10%,rgba(43,177,255,.20),transparent 34%),radial-gradient(circle at 8% 20%,rgba(255,124,42,.10),transparent 30%),radial-gradient(circle at 92% 20%,rgba(201,48,71,.10),transparent 30%),linear-gradient(180deg,#071622,#051019 100%);box-shadow:0 18px 46px rgba(0,0,0,.32),0 0 30px rgba(65,192,255,.08)}
.gtp2s2-field{position:absolute;inset:0;pointer-events:none;opacity:.20;background:linear-gradient(90deg,transparent 49.8%,rgba(118,211,244,.18) 50%,transparent 50.2%),repeating-linear-gradient(90deg,transparent 0 12.35%,rgba(88,181,216,.055) 12.45% 12.6%);mask-image:linear-gradient(to bottom,transparent 0,black 17%,black 78%,transparent 96%)}
.gtp2s2-meta{position:relative;z-index:1;padding:14px 18px 4px;text-align:center;color:#9cb5c7;font-size:10px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}
.gtp2s2-stage{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,240px) minmax(0,1fr);align-items:center;gap:18px;padding:12px 28px 22px}
.gtp2s2-team{display:flex;align-items:center;gap:16px;min-width:0}.gtp2s2-team.away{justify-content:flex-end;text-align:right}.gtp2s2-team.home{text-align:left}.gtp2s2-logo{width:84px;height:84px;flex:0 0 84px;display:grid;place-items:center;border-radius:22px;background:radial-gradient(circle,rgba(255,255,255,.07),transparent 68%)}.gtp2s2-logo img,.gtp2s2-logo .gt159-logo,.gtp2s2-logo .gt159-logo-fallback{width:78px!important;height:78px!important;max-width:78px!important;object-fit:contain;filter:drop-shadow(0 10px 18px rgba(0,0,0,.42))}
.gtp2s2-copy{min-width:0}.gtp2s2-copy strong{display:block;color:#fff;font-size:24px;line-height:1.03;font-weight:1000;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtp2s2-copy span{display:block;margin-top:6px;color:#9db3c3;font-size:11px;font-weight:800}.gtp2s2-copy em{display:inline-flex;margin-top:7px;padding:4px 9px;border:1px solid rgba(78,196,240,.30);border-radius:999px;background:rgba(21,103,145,.17);color:#71d8ff;font-style:normal;font-size:8px;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.gtp2s2-center{display:grid;gap:9px;text-align:center}.gtp2s2-total{padding:11px 14px;border:1px solid rgba(69,199,255,.58);border-radius:15px;background:linear-gradient(180deg,rgba(12,55,77,.96),rgba(5,24,36,.96));box-shadow:0 10px 24px rgba(0,0,0,.24)}.gtp2s2-total span{display:block;color:#a7c3d5;font-size:9px;font-weight:900;letter-spacing:.10em;text-transform:uppercase}.gtp2s2-total strong{display:block;margin-top:2px;color:#fff;font-size:31px;line-height:1;font-weight:1000}.gtp2s2-confidence{display:inline-flex;justify-content:center;align-items:center;gap:7px;padding:7px 11px;border:1px solid rgba(55,231,164,.54);border-radius:999px;background:rgba(13,113,76,.20);color:#63f0b4;font-size:9px;font-weight:950;letter-spacing:.03em}.gtp2s2-confidence:before{content:"▥";font-size:12px}
.gtp2s2-context{position:relative;z-index:1;display:grid;grid-template-columns:1.25fr 1fr 1fr;border-top:1px solid rgba(77,170,207,.22);background:rgba(3,13,22,.50)}.gtp2s2-context>div{min-width:0;padding:11px 14px;border-right:1px solid rgba(76,145,177,.15);text-align:center}.gtp2s2-context>div:last-child{border-right:0}.gtp2s2-context b{display:block;color:#f6f9fc;font-size:11px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtp2s2-context span{display:block;margin-top:3px;color:#819aab;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:760px){.gtp2s2-heading h2{font-size:25px}.gtp2s2-hero{border-radius:18px}.gtp2s2-stage{grid-template-columns:minmax(0,1fr) 120px minmax(0,1fr);gap:8px;padding:10px 10px 17px}.gtp2s2-team{gap:7px}.gtp2s2-logo{width:54px;height:54px;flex-basis:54px;border-radius:17px}.gtp2s2-logo img,.gtp2s2-logo .gt159-logo,.gtp2s2-logo .gt159-logo-fallback{width:50px!important;height:50px!important;max-width:50px!important}.gtp2s2-copy strong{font-size:15px}.gtp2s2-copy span{font-size:8px}.gtp2s2-copy em{font-size:7px;padding:3px 6px}.gtp2s2-total{padding:9px 8px}.gtp2s2-total strong{font-size:24px}.gtp2s2-confidence{font-size:7px;padding:5px 7px}.gtp2s2-context{grid-template-columns:1fr}.gtp2s2-context>div{border-right:0;border-bottom:1px solid rgba(76,145,177,.13)}.gtp2s2-context>div:last-child{border-bottom:0}}
@media(max-width:480px){.gtp2s2-stage{grid-template-columns:minmax(0,1fr) 88px minmax(0,1fr);padding-left:6px;padding-right:6px}.gtp2s2-logo{width:42px;height:42px;flex-basis:42px}.gtp2s2-logo img,.gtp2s2-logo .gt159-logo,.gtp2s2-logo .gt159-logo-fallback{width:39px!important;height:39px!important;max-width:39px!important}.gtp2s2-copy strong{font-size:13px}.gtp2s2-total strong{font-size:21px}.gtp2s2-meta{font-size:8px}}
</style>
"""


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _candidate(mapping: Mapping[str, Any] | None, *keys: str) -> str:
    source = mapping if isinstance(mapping, Mapping) else {}
    for key in keys:
        value = _clean(source.get(key))
        if value:
            return value
    return ""


def _team(identity: Mapping[str, Any], stats: Mapping[str, Any], side: str) -> tuple[str, str, str]:
    side_identity = identity.get(side) if isinstance(identity.get(side), Mapping) else {}
    name = _candidate(side_identity, "team", "display_name", "displayName", "name") or _candidate(stats, "team", "team_name", "name") or side.title()
    conference = _candidate(side_identity, "conference", "conference_name") or "NCAAF"
    record = _candidate(stats, "record", "overall_record") or "—"
    return name, conference, record


def _parse_kickoff(game: Mapping[str, Any], identity: Mapping[str, Any] | None = None) -> datetime | None:
    sources = [game, identity or {}]
    for source in sources:
        for key in ("kickoff_iso", "start_time_utc", "kickoff_utc", "start_time", "date"):
            raw = _candidate(source, key)
            if not raw or "T" not in raw:
                continue
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
            return parsed.astimezone(ZoneInfo(PHOENIX_TZ))

    day = _candidate(game, "game_date") or _candidate(identity or {}, "game_date")
    for source in sources:
        raw = _candidate(source, "kickoff", "kickoff_et")
        if not raw or not day:
            continue
        normalized = raw.upper().replace(" EST", " ET").replace(" EDT", " ET")
        if not normalized.endswith(" ET"):
            continue
        try:
            parsed = datetime.strptime(f"{day} {normalized[:-3].strip()}", "%Y-%m-%d %I:%M %p")
        except ValueError:
            continue
        parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
        return parsed.astimezone(ZoneInfo(PHOENIX_TZ))
    return None


def phoenix_kickoff_parts(game: Mapping[str, Any], identity: Mapping[str, Any] | None = None) -> tuple[str, str]:
    parsed = _parse_kickoff(game, identity)
    if parsed is None:
        return "Date pending", "Time pending"
    day_label = f"{parsed.strftime('%a')} • {parsed.strftime('%b')} {parsed.day}"
    time_label = parsed.strftime("%I:%M %p").lstrip("0") + " AZ"
    return day_label, time_label


def _line_text(value: Any) -> str:
    if value is None or _clean(value) == "":
        return "Line pending"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return _clean(value)


def build_page2_matchup_hero_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
    *,
    away_logo_html: str,
    home_logo_html: str,
    total_line: Any,
    confidence_label: str,
) -> str:
    """Build Page 2's dynamic selected-matchup hero from already-owned values."""
    away_name, away_conf, away_record = _team(identity, away, "away")
    home_name, home_conf, home_record = _team(identity, home, "home")
    day_label, time_label = phoenix_kickoff_parts(display_game, identity)
    venue = _candidate(identity, "venue") or _candidate(display_game, "venue") or "Venue pending"
    location = _candidate(display_game, "venue_location", "location", "city") or "Location pending"
    line_text = _line_text(total_line)
    confidence = _clean(confidence_label) or "Confidence pending"

    html = f"""
{PAGE2_STEP2_CSS}
<div class="gtp2s2-wrap" data-step2="{STEP2_MARKER}" data-timezone="{PHOENIX_TZ}">
  <header class="gtp2s2-heading">
    <h2>CFB Game Total</h2>
    <p>Game Breakdown &amp; Prediction &nbsp;•&nbsp; Page 2 of 2</p>
  </header>
  <section class="gtp2s2-hero" data-testid="gtp2s2-matchup-hero" aria-label="Page 2 selected college football matchup">
    <div class="gtp2s2-field"></div>
    <div class="gtp2s2-meta">{escape(day_label)} &nbsp;•&nbsp; {escape(time_label)} &nbsp;•&nbsp; America/Phoenix</div>
    <div class="gtp2s2-stage">
      <div class="gtp2s2-team away">
        <div class="gtp2s2-logo">{away_logo_html}</div>
        <div class="gtp2s2-copy"><strong>{escape(away_name)}</strong><span>{escape(away_record)}</span><em>{escape(away_conf)}</em></div>
      </div>
      <div class="gtp2s2-center">
        <div class="gtp2s2-total" data-testid="gtp2s2-total-line"><span>Game Total</span><strong>{escape(line_text)}</strong></div>
        <div class="gtp2s2-confidence" data-testid="gtp2s2-confidence">{escape(confidence)}</div>
      </div>
      <div class="gtp2s2-team home">
        <div class="gtp2s2-copy"><strong>{escape(home_name)}</strong><span>{escape(home_record)}</span><em>{escape(home_conf)}</em></div>
        <div class="gtp2s2-logo">{home_logo_html}</div>
      </div>
    </div>
    <div class="gtp2s2-context">
      <div><b>{escape(venue)}</b><span>{escape(location)}</span></div>
      <div><b>{escape(time_label)}</b><span>Phoenix kickoff time</span></div>
      <div><b>{escape(day_label)}</b><span>Selected matchup</span></div>
    </div>
  </section>
</div>
"""
    return html


__all__ = [
    "FREEZE_TOKEN",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STEP2_CSS",
    "PHOENIX_TZ",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_MARKER",
    "build_page2_matchup_hero_html",
    "phoenix_kickoff_parts",
]
