"""CFB Game Total Page 1 visual cleanup Step 2 — premium top shell.

Presentation-only helper for the Step-1-approved summary-first hierarchy. It
uses only values already owned by the selected game and the frozen Phoenix-time
presentation helper. No model, projection, probability, market ownership, event
identity, API routing, or sportsbook input is changed here.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import cfb_game_total_page1_step3_presentation_v1 as prior_presentation

PHOENIX_TZ = prior_presentation.PHOENIX_TZ
OVERVIEW_LABEL = "Overview"
FULL_ANALYSIS_LABEL = "Full Analysis"
STEP1_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP1_TARGET_LOCK_FROZEN"
STEP2_MARKER = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_STEP2_TOP_SHELL_ACTIVE"
PRESERVE_DYNAMIC_SELECTED_GAME_DATA = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

STEP2_TOP_SHELL_CSS = r"""
<style>
.gtvc2-shell{max-width:1120px;margin:0 auto 18px;color:#f7fbff}
.gtvc2-hero{position:relative;overflow:hidden;border:1px solid rgba(91,211,255,.46);border-radius:24px;background:radial-gradient(circle at 50% 8%,rgba(52,177,255,.21),transparent 34%),radial-gradient(circle at 8% 12%,rgba(48,232,214,.12),transparent 30%),radial-gradient(circle at 92% 12%,rgba(137,103,255,.12),transparent 30%),linear-gradient(180deg,#071723 0%,#06111b 58%,#040a11 100%);box-shadow:0 18px 48px rgba(0,0,0,.34),0 0 34px rgba(74,194,255,.08)}
.gtvc2-field{position:absolute;inset:0;pointer-events:none;opacity:.23;background:linear-gradient(90deg,transparent 49.8%,rgba(113,203,236,.18) 50%,transparent 50.2%),repeating-linear-gradient(90deg,transparent 0 12.35%,rgba(88,181,216,.055) 12.45% 12.6%);mask-image:linear-gradient(to bottom,transparent 0,black 16%,black 74%,transparent 94%)}
.gtvc2-kicker{position:relative;z-index:1;padding:16px 20px 4px;text-align:center;color:#86a9bf;font-size:10px;font-weight:950;letter-spacing:.13em;text-transform:uppercase}
.gtvc2-matchup{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1fr) 76px minmax(0,1fr);align-items:center;gap:18px;min-height:160px;padding:12px 38px 24px}
.gtvc2-team{display:flex;align-items:center;gap:18px;min-width:0}.gtvc2-team.away{justify-content:flex-end;text-align:right}.gtvc2-team.home{text-align:left}
.gtvc2-logo{width:94px;height:94px;flex:0 0 94px;display:grid;place-items:center;border-radius:26px;background:radial-gradient(circle,rgba(255,255,255,.07),transparent 68%)}
.gtvc2-logo img,.gtvc2-logo .gt159-logo,.gtvc2-logo .gt159-logo-fallback{width:86px!important;height:86px!important;max-width:86px!important;object-fit:contain;filter:drop-shadow(0 10px 18px rgba(0,0,0,.40))}
.gtvc2-copy{min-width:0}.gtvc2-copy strong{display:block;color:#fff;font-size:26px;line-height:1.02;font-weight:1000;letter-spacing:-.025em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtvc2-copy span{display:block;margin-top:7px;color:#9ab1c1;font-size:12px;font-weight:800}.gtvc2-copy em{display:inline-flex;margin-top:8px;padding:4px 10px;border:1px solid rgba(74,199,241,.34);border-radius:999px;background:rgba(22,105,148,.17);color:#6dd9ff;font-style:normal;font-size:9px;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.gtvc2-vs{width:58px;height:58px;margin:auto;display:grid;place-items:center;border:1px solid rgba(91,203,241,.42);border-radius:50%;background:#092231;color:#c0d3df;font-size:10px;font-weight:1000;letter-spacing:.11em;box-shadow:0 0 0 7px rgba(4,15,23,.40),0 0 24px rgba(71,196,239,.13)}
.gtvc2-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:10px;border:1px solid rgba(77,170,207,.24);border-radius:18px;background:linear-gradient(135deg,rgba(7,24,35,.96),rgba(7,15,27,.96));overflow:hidden}
.gtvc2-context>div{min-width:0;display:grid;grid-template-columns:28px minmax(0,1fr);grid-template-rows:auto auto;column-gap:9px;align-content:center;min-height:74px;padding:12px 15px;border-right:1px solid rgba(76,145,177,.16)}.gtvc2-context>div:last-child{border-right:0}.gtvc2-context i{grid-row:1/span 2;align-self:center;color:#62ceff;font-style:normal;font-size:17px}.gtvc2-context b{color:#f5f9fc;font-size:11px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtvc2-context span{margin-top:4px;color:#829aac;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gtvc2-tabs{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:12px;padding:5px;border:1px solid rgba(77,171,210,.23);border-radius:15px;background:#07131d}.gtvc2-tab{display:grid;place-items:center;min-height:43px;border-radius:11px;color:#8ea6b8;font-size:11px;font-weight:950;letter-spacing:.04em}.gtvc2-tab.active{background:linear-gradient(135deg,#18bfd8,#2588ff);color:#fff;box-shadow:0 8px 22px rgba(37,142,255,.20)}.gtvc2-tab.pending{background:#091925;color:#6f8797}
@media(max-width:760px){.gtvc2-hero{border-radius:19px}.gtvc2-kicker{padding:12px 10px 3px;font-size:8px}.gtvc2-matchup{grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);gap:7px;min-height:116px;padding:9px 10px 17px}.gtvc2-team{gap:7px}.gtvc2-logo{width:56px;height:56px;flex-basis:56px;border-radius:18px}.gtvc2-logo img,.gtvc2-logo .gt159-logo,.gtvc2-logo .gt159-logo-fallback{width:51px!important;height:51px!important;max-width:51px!important}.gtvc2-copy strong{font-size:16px}.gtvc2-copy span{margin-top:4px;font-size:9px}.gtvc2-copy em{margin-top:5px;padding:3px 7px;font-size:7px}.gtvc2-vs{width:34px;height:34px;font-size:8px;box-shadow:0 0 0 4px rgba(4,15,23,.35)}.gtvc2-context{grid-template-columns:repeat(2,minmax(0,1fr));border-radius:14px}.gtvc2-context>div{min-height:60px;padding:9px 8px}.gtvc2-context>div:nth-child(2){border-right:0}.gtvc2-context>div:nth-child(-n+2){border-bottom:1px solid rgba(76,145,177,.16)}.gtvc2-tab{min-height:39px;font-size:10px}}
@media(max-width:480px){.gtvc2-matchup{grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);padding-left:6px;padding-right:6px}.gtvc2-logo{width:44px;height:44px;flex-basis:44px}.gtvc2-logo img,.gtvc2-logo .gt159-logo,.gtvc2-logo .gt159-logo-fallback{width:40px!important;height:40px!important;max-width:40px!important}.gtvc2-copy strong{font-size:14px}.gtvc2-copy span{font-size:8px}.gtvc2-copy em{font-size:7px}.gtvc2-vs{width:30px;height:30px}}
</style>
"""


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _team_name(identity: Mapping[str, Any], stats: Mapping[str, Any], fallback: str) -> str:
    return _clean(identity.get("team")) or _clean(stats.get("team")) or fallback


def _conference(identity: Mapping[str, Any]) -> str:
    return _clean(identity.get("conference")) or "NCAAF"


def _record(stats: Mapping[str, Any]) -> str:
    return _clean(stats.get("record")) or "—"


def _precipitation(display_game: Mapping[str, Any]) -> str:
    value = display_game.get("precipitation")
    if value is None:
        value = display_game.get("precipitation_pct")
    if value is None:
        value = display_game.get("precip")
    text = _clean(value)
    if not text:
        return ""
    return text if "%" in text else f"{text}% precipitation"


def build_top_shell_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
    *,
    away_logo_html: str,
    home_logo_html: str,
) -> str:
    """Build the Step-2 hero, context strip and view shell from owned game data."""
    away_id = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
    home_id = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}
    away_name = _team_name(away_id, away, "Away")
    home_name = _team_name(home_id, home, "Home")
    away_conf = _conference(away_id)
    home_conf = _conference(home_id)
    kickoff = prior_presentation.phoenix_kickoff_text(display_game, identity)
    day_text = prior_presentation.phoenix_day_text(display_game, identity)
    venue = _clean(identity.get("venue")) or _clean(display_game.get("venue")) or "Venue pending"
    location = _clean(
        display_game.get("venue_location")
        or display_game.get("location")
        or display_game.get("city")
    ) or "Location pending"
    temperature_raw = _clean(display_game.get("temperature"))
    temperature = f"{temperature_raw}°" if temperature_raw else "—"
    weather = _clean(display_game.get("weather") or display_game.get("forecast")) or "Forecast pending"
    precipitation = _precipitation(display_game)
    weather_detail = " • ".join(part for part in (precipitation, weather) if part)
    wind = _clean(display_game.get("wind") or display_game.get("wind_mph")) or "Wind pending"

    return f"""
<div class="gtvc2-shell" data-step2="{STEP2_MARKER}" data-timezone="{PHOENIX_TZ}">
  <section class="gtvc2-hero" data-testid="gtvc2-matchup-hero" aria-label="Selected college football matchup">
    <div class="gtvc2-field"></div>
    <div class="gtvc2-kicker">NCAA FBS • {escape(day_text)} • {escape(kickoff)}</div>
    <div class="gtvc2-matchup">
      <div class="gtvc2-team away">
        <div class="gtvc2-logo">{away_logo_html}</div>
        <div class="gtvc2-copy"><strong>{escape(away_name)}</strong><span>{escape(_record(away))} ({escape(away_conf)})</span><em>{escape(away_conf)}</em></div>
      </div>
      <div class="gtvc2-vs">VS</div>
      <div class="gtvc2-team home">
        <div class="gtvc2-copy"><strong>{escape(home_name)}</strong><span>{escape(_record(home))} ({escape(home_conf)})</span><em>{escape(home_conf)}</em></div>
        <div class="gtvc2-logo">{home_logo_html}</div>
      </div>
    </div>
  </section>
  <section class="gtvc2-context" data-testid="gtvc2-context-strip" aria-label="Game context">
    <div><i>▣</i><b>{escape(venue)}</b><span>{escape(location)}</span></div>
    <div><i>☀</i><b>{escape(temperature)}</b><span>{escape(weather_detail)}</span></div>
    <div><i>≋</i><b>{escape(wind)}</b><span>Wind</span></div>
    <div><i>◷</i><b>{escape(kickoff)}</b><span>{escape(day_text)} • PHX</span></div>
  </section>
  <nav class="gtvc2-tabs" data-testid="gtvc2-view-tabs" aria-label="Game Total views">
    <span class="gtvc2-tab active" aria-current="page">{OVERVIEW_LABEL}</span>
    <span class="gtvc2-tab pending" aria-disabled="true" title="Full Analysis remains secondary until the evidence-relocation step">{FULL_ANALYSIS_LABEL}</span>
  </nav>
</div>
"""


__all__ = [
    "FULL_ANALYSIS_LABEL",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_PROJECTION",
    "OVERVIEW_LABEL",
    "PHOENIX_TZ",
    "PRESERVE_DYNAMIC_SELECTED_GAME_DATA",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_FREEZE_TOKEN",
    "STEP2_MARKER",
    "STEP2_TOP_SHELL_CSS",
    "build_top_shell_html",
]
