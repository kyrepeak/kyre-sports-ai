"""CFB Over/Under Intelligence V2 — Upgrade Step 1 matchup presentation.

Additive presentation wrapper over the permanently frozen College Football
Over/Under Step-9 hub. This module changes presentation only:
- college team logos when ESPN scoreboard identity can be verified,
- a cleaner matchup header,
- kickoff / stadium / TV / status / site context in one compact card.

The frozen Step-8 projection model, Step-9 final selection/ranking logic,
manual analysis-line behavior, team data, and schedule identity are untouched.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_hub_v3 as frozen_v3
import cfb_schedule_v3 as schedule

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 1 MATCHUP UI"
FROZEN_OVER_UNDER_HUB = "cfb_over_under_hub_v3"
MARKET = "Over/Under"
VISUAL_SOURCE = "ESPN College Football scoreboard"

_CSS = r"""
<style>
.cfbou1-hero{margin-top:10px;border:1px solid rgba(91,196,255,.28);border-radius:18px;
background:linear-gradient(145deg,#071421,#0b1b28 55%,#071712);overflow:hidden;
box-shadow:0 12px 34px rgba(0,0,0,.18)}
.cfbou1-top{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 12px;
border-bottom:1px solid rgba(91,196,255,.13);background:rgba(4,12,20,.34)}
.cfbou1-kicker{color:#79dfff;font-size:.49rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}
.cfbou1-badges{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:5px}
.cfbou1-badge{border:1px solid #31566c;border-radius:999px;padding:4px 7px;color:#9ccde4;
background:#0a2130;font-size:.40rem;font-weight:900;white-space:nowrap}
.cfbou1-badge.good{border-color:#2d7659;color:#8ceabb;background:#0b2b21}
.cfbou1-match{display:grid;grid-template-columns:minmax(0,1fr) 54px minmax(0,1fr);align-items:stretch;gap:8px;padding:13px}
.cfbou1-team{display:grid;grid-template-columns:62px minmax(0,1fr);gap:10px;align-items:center;
border:1px solid rgba(150,190,215,.14);border-radius:14px;background:rgba(5,18,28,.60);padding:10px}
.cfbou1-team.home{text-align:right;grid-template-columns:minmax(0,1fr) 62px}
.cfbou1-team.home .cfbou1-logo{grid-column:2}.cfbou1-team.home .cfbou1-copy{grid-column:1;grid-row:1}
.cfbou1-logo{width:62px;height:62px;border-radius:13px;border:1px solid rgba(255,255,255,.10);
background:rgba(255,255,255,.04);display:flex;align-items:center;justify-content:center;overflow:hidden}
.cfbou1-logo img{width:52px;height:52px;object-fit:contain;display:block}
.cfbou1-monogram{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;
font-size:.95rem;font-weight:950;color:#dff7ff;background:#102b3d;border:1px solid #28516b}
.cfbou1-rank{color:#83dfff;font-size:.45rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.cfbou1-name{color:#f5fbff;font-size:1.02rem;font-weight:950;line-height:1.08;margin-top:3px}
.cfbou1-meta{color:#91a7b4;font-size:.48rem;font-weight:800;line-height:1.45;margin-top:5px}
.cfbou1-at{display:flex;flex-direction:column;align-items:center;justify-content:center;color:#6c8a99}
.cfbou1-at strong{color:#d5eaf4;font-size:1.05rem}.cfbou1-at span{font-size:.38rem;font-weight:900;text-transform:uppercase;margin-top:2px}
.cfbou1-context{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;border-top:1px solid rgba(91,196,255,.13);background:rgba(5,16,24,.52)}
.cfbou1-context div{padding:9px 10px;border-right:1px solid rgba(91,196,255,.09);min-width:0}
.cfbou1-context div:last-child{border-right:0}.cfbou1-context strong{display:block;color:#6fa5bd;font-size:.38rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase}
.cfbou1-context span{display:block;color:#d8e8ef;font-size:.48rem;font-weight:850;line-height:1.35;margin-top:3px;overflow-wrap:anywhere}
.cfbou1-source{padding:7px 11px;border-top:1px solid rgba(91,196,255,.09);color:#64808e;font-size:.38rem;line-height:1.4}
@media(max-width:760px){
  .cfbou1-match{grid-template-columns:1fr;gap:7px;padding:10px}.cfbou1-at{min-height:26px;flex-direction:row;gap:5px}
  .cfbou1-team,.cfbou1-team.home{grid-template-columns:54px minmax(0,1fr);text-align:left;padding:9px}
  .cfbou1-team.home .cfbou1-logo{grid-column:1}.cfbou1-team.home .cfbou1-copy{grid-column:2;grid-row:1}
  .cfbou1-logo{width:54px;height:54px}.cfbou1-logo img{width:46px;height:46px}
  .cfbou1-context{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbou1-context div{border-bottom:1px solid rgba(91,196,255,.08)}
  .cfbou1-context div:last-child{grid-column:1/-1}.cfbou1-name{font-size:.92rem}
}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _name_key(value: Any) -> str:
    text = re.sub(r"\([^)]*\)", " ", _clean(value).lower())
    return re.sub(r"[^a-z0-9]+", "", text)


def _record_summary(competitor: Mapping[str, Any]) -> str:
    records = competitor.get("records") or []
    for row in records:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("name")).lower() in {"overall", "total"}:
            summary = _clean(row.get("summary"))
            if summary:
                return summary
    for row in records:
        if isinstance(row, Mapping):
            summary = _clean(row.get("summary"))
            if summary:
                return summary
    return ""


def _rank_value(competitor: Mapping[str, Any]) -> int | None:
    try:
        value = int((competitor.get("curatedRank") or {}).get("current"))
    except Exception:
        return None
    return value if 0 < value < 99 else None


def _safe_logo_url(team: Mapping[str, Any]) -> str:
    candidates: list[str] = []
    if _clean(team.get("logo")):
        candidates.append(_clean(team.get("logo")))
    for row in team.get("logos") or []:
        if isinstance(row, Mapping) and _clean(row.get("href")):
            candidates.append(_clean(row.get("href")))
    for url in candidates:
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        if url.startswith("https://"):
            return url
    return ""


def _visual_from_competitor(competitor: Mapping[str, Any]) -> dict[str, Any]:
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        team = {}
    return {
        "team_id": _clean(team.get("id")),
        "name": _clean(
            team.get("location")
            or team.get("shortDisplayName")
            or team.get("displayName")
        ),
        "slug": _clean(team.get("slug")),
        "logo": _safe_logo_url(team),
        "record": _record_summary(competitor),
        "rank": _rank_value(competitor),
    }


def _event_sides(event: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    competitions = event.get("competitions") or []
    if not competitions or not isinstance(competitions[0], Mapping):
        return {}
    sides: dict[str, Mapping[str, Any]] = {}
    for competitor in competitions[0].get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _clean(competitor.get("homeAway")).lower()
        if side in {"away", "home"}:
            sides[side] = competitor
    return sides


def _event_matches_game(event: Mapping[str, Any], game: Mapping[str, Any]) -> bool:
    event_id = _clean(event.get("id"))
    game_event_id = _clean(game.get("espn_event_id"))
    if not game_event_id:
        identity = _clean(game.get("identity_key"))
        if identity.startswith("espn:"):
            game_event_id = identity.split(":", 1)[1]
    if game_event_id and event_id == game_event_id:
        return True

    sides = _event_sides(event)
    if not sides:
        return False
    away_visual = _visual_from_competitor(sides.get("away") or {})
    home_visual = _visual_from_competitor(sides.get("home") or {})
    away_keys = {
        _name_key(away_visual.get("name")),
        _name_key(away_visual.get("slug")),
    }
    home_keys = {
        _name_key(home_visual.get("name")),
        _name_key(home_visual.get("slug")),
    }
    return (
        _name_key(game.get("away_team")) in away_keys
        or _name_key(game.get("away_team_slug")) in away_keys
    ) and (
        _name_key(game.get("home_team")) in home_keys
        or _name_key(game.get("home_team_slug")) in home_keys
    )


def _extract_visuals(
    payload: Mapping[str, Any],
    game: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping) or not _event_matches_game(event, game):
            continue
        sides = _event_sides(event)
        return {
            "away": _visual_from_competitor(sides.get("away") or {}),
            "home": _visual_from_competitor(sides.get("home") or {}),
        }
    return {"away": {}, "home": {}}


def _visuals_for_game(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    day = _clean(game.get("game_date"))
    if not day:
        return {"away": {}, "home": {}}
    try:
        payload, _ = schedule.frozen._fetch_espn_fbs_payload(day)
    except Exception:
        return {"away": {}, "home": {}}
    if not isinstance(payload, Mapping):
        return {"away": {}, "home": {}}
    return _extract_visuals(payload, game)


def _monogram(team_name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", team_name)
    if not words:
        return "CFB"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _logo_html(team_name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    name = escape(team_name, quote=True)
    if url:
        return (
            '<div class="cfbou1-logo">'
            f'<img src="{escape(url, quote=True)}" alt="{name} logo" loading="lazy">'
            "</div>"
        )
    return (
        '<div class="cfbou1-logo">'
        f'<div class="cfbou1-monogram" aria-label="{name} logo unavailable">'
        f"{escape(_monogram(team_name))}</div></div>"
    )


def _display_record(profile: Mapping[str, Any], visual: Mapping[str, Any]) -> str:
    profile_record = _clean(profile.get("record_text"))
    if profile_record and profile_record not in {"0-0", "—"}:
        return profile_record
    return _clean(visual.get("record")) or profile_record or "Record unavailable"


def _team_block(
    side: str,
    game: Mapping[str, Any],
    profile: Mapping[str, Any],
    visual: Mapping[str, Any],
) -> str:
    team_name = _clean(profile.get("team") or game.get(f"{side}_team")) or side.title()
    conference = _clean(profile.get("conference") or game.get(f"{side}_conference")) or "Conference unavailable"
    record = _display_record(profile, visual)
    rank = frozen_v3.frozen_v2.frozen_v1._rank_text(profile)
    home_class = " home" if side == "home" else ""
    logo = _logo_html(team_name, visual)
    copy = f"""
<div class="cfbou1-copy">
  <div class="cfbou1-rank">{escape(rank)}</div>
  <div class="cfbou1-name">{escape(team_name)}</div>
  <div class="cfbou1-meta">{escape(conference)} • {escape(record)}</div>
</div>
"""
    if side == "home":
        return f'<div class="cfbou1-team{home_class}">{copy}{logo}</div>'
    return f'<div class="cfbou1-team{home_class}">{logo}{copy}</div>'


def _enhanced_hero(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    visuals = _visuals_for_game(game)
    away_visual = visuals.get("away") or {}
    home_visual = visuals.get("home") or {}
    verified = bool(game.get("identity_verified") and game.get("date_matches_query"))
    logo_count = int(bool(away_visual.get("logo"))) + int(bool(home_visual.get("logo")))
    logo_badge = "TEAM LOGOS VERIFIED" if logo_count == 2 else ("TEAM LOGOS PARTIAL" if logo_count else "LOGO FALLBACK ACTIVE")
    site = "Neutral site" if bool(game.get("neutral_site")) else "Home field"

    return f"""
<div class="cfbou1-hero">
  <div class="cfbou1-top">
    <div class="cfbou1-kicker">O/U INTELLIGENCE V2 • UPGRADE STEP 1 • MATCHUP HEADER</div>
    <div class="cfbou1-badges">
      <span class="cfbou1-badge {'good' if verified else ''}">{'IDENTITY VERIFIED' if verified else 'CHECK IDENTITY'}</span>
      <span class="cfbou1-badge {'good' if logo_count == 2 else ''}">{escape(logo_badge)}</span>
      <span class="cfbou1-badge good">FROZEN STEP-9 MODEL</span>
    </div>
  </div>
  <div class="cfbou1-match">
    {_team_block('away', game, away, away_visual)}
    <div class="cfbou1-at"><strong>@</strong><span>matchup</span></div>
    {_team_block('home', game, home, home_visual)}
  </div>
  <div class="cfbou1-context">
    <div><strong>Kickoff</strong><span>{escape(_clean(game.get('kickoff_et')) or 'TBD')}</span></div>
    <div><strong>Stadium</strong><span>{escape(_clean(game.get('venue')) or 'Venue unavailable')}</span></div>
    <div><strong>TV</strong><span>{escape(_clean(game.get('broadcast')) or 'Broadcast unavailable')}</span></div>
    <div><strong>Status</strong><span>{escape(_clean(game.get('status')) or 'Status unavailable')}</span></div>
    <div><strong>Site</strong><span>{escape(site)}</span></div>
  </div>
  <div class="cfbou1-source">
    Logos are presentation-only ESPN scoreboard metadata. Rankings/records/conferences remain the existing certified display evidence. No Step-8/9 projection or selection math is changed.
  </div>
</div>
"""


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render frozen Step 9 with only its matchup hero temporarily upgraded."""
    st.caption("🧩 CFB O/U INTELLIGENCE V2 • Upgrade Step 1 • team logos + matchup header")
    st.markdown(_CSS, unsafe_allow_html=True)

    original_hero = frozen_v3.frozen_v2.frozen_v1._hero
    frozen_v3.frozen_v2.frozen_v1._hero = _enhanced_hero
    try:
        return frozen_v3.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v3.frozen_v2.frozen_v1._hero = original_hero


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 1 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_OVER_UNDER_HUB",
    "MARKET",
    "MODEL_VERSION",
    "VISUAL_SOURCE",
    "_enhanced_hero",
    "_event_matches_game",
    "_extract_visuals",
    "_logo_html",
    "_visual_from_competitor",
    "render_cfb_hub",
    "render_over_under_hub",
]
