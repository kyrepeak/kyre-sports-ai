"""CFB Game Total Page 1 visual cleanup Step 4 presentation helpers.

Presentation-only helpers for the Overview page. Step 4 removes the dense
Steps 1-12/final-summary/Top-5 wall from the main Overview surface, preserves
that evidence in the existing analysis controls, and adds a compact same-day
games section plus a professional source/update/calculation footer.

No model, projection, ranking, qualification, probability, API transport, or
sportsbook ownership is changed. Sportsbook context remains 0.0% of projection.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

MODEL_VERSION = "CFB GAME TOTAL PAGE1 VISUAL CLEANUP • STEP 4 FOOTER EVIDENCE V1"
PHOENIX_TZ = "America/Phoenix"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0

STEP4_CSS = r"""
<style data-kyre-cfb-gt-visual-cleanup-step4="v1">
.gtvc4-relocated{margin-top:10px;padding:11px 13px;border:1px solid rgba(88,201,255,.18);border-radius:14px;background:linear-gradient(145deg,#081925,#08131d);display:flex;align-items:center;justify-content:space-between;gap:12px}
.gtvc4-relocated b{display:block;color:#dff5ff;font-size:.47rem;letter-spacing:.08em}.gtvc4-relocated span{display:block;color:#829caf;font-size:.27rem;line-height:1.45;margin-top:3px}.gtvc4-relocated strong{flex:0 0 auto;padding:5px 9px;border:1px solid rgba(98,239,182,.32);border-radius:999px;background:rgba(25,113,78,.13);color:#72efbd;font-size:.24rem;letter-spacing:.04em}
.gtvc4-day{margin-top:11px;border:1px solid rgba(88,201,255,.18);border-radius:15px;background:linear-gradient(180deg,#081724,#07131e);padding:11px}.gtvc4-dayhead{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:8px}.gtvc4-dayhead b{color:#eef8ff;font-size:.48rem;letter-spacing:.06em}.gtvc4-dayhead span{color:#7893a8;font-size:.25rem}.gtvc4-daygrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.gtvc4-game{padding:9px 10px;border:1px solid rgba(88,201,255,.16);border-radius:11px;background:#0a1c29;min-width:0}.gtvc4-game-top{display:flex;align-items:center;justify-content:space-between;gap:8px}.gtvc4-matchup{color:#edf7ff;font-size:.39rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtvc4-time{color:#69d9ff;font-size:.26rem;font-weight:900;white-space:nowrap}.gtvc4-meta{margin-top:4px;color:#7894a9;font-size:.23rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gtvc4-footer{margin:11px 0 2px;border:1px solid rgba(88,201,255,.16);border-radius:14px;background:linear-gradient(145deg,#071620,#07111a);display:grid;grid-template-columns:1.25fr .8fr 1.25fr;overflow:hidden}.gtvc4-footcell{padding:10px 12px;border-right:1px solid rgba(88,201,255,.11);min-width:0}.gtvc4-footcell:last-child{border-right:0}.gtvc4-footcell b{display:block;color:#dff5ff;font-size:.31rem;letter-spacing:.07em}.gtvc4-footcell span{display:block;color:#829caf;font-size:.23rem;line-height:1.5;margin-top:4px}.gtvc4-footcell strong{color:#72efbd}
@media(max-width:760px){.gtvc4-relocated{align-items:flex-start;flex-direction:column}.gtvc4-daygrid{grid-template-columns:1fr}.gtvc4-footer{grid-template-columns:1fr}.gtvc4-footcell{border-right:0;border-bottom:1px solid rgba(88,201,255,.11)}.gtvc4-footcell:last-child{border-bottom:0}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _team_name(game: Mapping[str, Any], side: str) -> str:
    nested = game.get(side)
    if isinstance(nested, Mapping):
        for key in ("display_name", "displayName", "name", "team_name", "short_name"):
            value = _clean(nested.get(key))
            if value:
                return value
    elif isinstance(nested, str) and nested.strip():
        return nested.strip()
    for key in (
        f"{side}_team",
        f"{side}_name",
        f"{side}_team_name",
        f"{side}_display_name",
    ):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _event_id(game: Mapping[str, Any]) -> str:
    for key in ("espn_event_id", "event_id", "game_id", "id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _venue(game: Mapping[str, Any]) -> str:
    venue = game.get("venue")
    if isinstance(venue, Mapping):
        parts = [
            _clean(venue.get("name")),
            _clean(venue.get("city")),
            _clean(venue.get("state")),
        ]
        return " • ".join(part for part in parts if part)
    if _clean(venue):
        return _clean(venue)
    for key in ("stadium", "location"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _kickoff_value(game: Mapping[str, Any]) -> Any:
    for key in (
        "start_time",
        "start_datetime",
        "kickoff",
        "kickoff_time",
        "date",
        "start_date",
    ):
        value = game.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _phoenix_time(game: Mapping[str, Any]) -> str:
    parsed = _as_datetime(_kickoff_value(game))
    if parsed is None:
        return ""
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(PHOENIX_TZ))
    local = parsed.astimezone(ZoneInfo(PHOENIX_TZ))
    return local.strftime("%-I:%M %p PHX")


def build_relocated_analysis_html(*_args: Any, **_kwargs: Any) -> str:
    """Replace the dense legacy Overview evidence wall with one compact handoff."""
    return (
        '<div class="gtvc4-relocated" data-testid="gtvc4-analysis-relocated">'
        '<div><b>FULL ANALYSIS</b>'
        '<span>Deep model evidence and slate-scan controls stay preserved outside the clean Overview surface.</span></div>'
        '<strong>OVERVIEW CLEAN • MODEL PRESERVED</strong>'
        '</div>'
    )


def build_games_on_day_html(
    games: Sequence[Mapping[str, Any]] | None,
    selected_day: str,
    *,
    max_games: int = 12,
) -> str:
    """Build a compact same-day schedule from already-loaded game rows only."""
    rows: list[str] = []
    for game in list(games or [])[: max(1, int(max_games))]:
        if not isinstance(game, Mapping):
            continue
        away = _team_name(game, "away")
        home = _team_name(game, "home")
        if not away or not home:
            continue
        time_text = _phoenix_time(game)
        venue = _venue(game)
        event_id = _event_id(game)
        meta_parts = [part for part in (venue, f"ID {event_id}" if event_id else "") if part]
        rows.append(
            '<div class="gtvc4-game" data-event-id="%s">'
            '<div class="gtvc4-game-top"><span class="gtvc4-matchup">%s @ %s</span>%s</div>%s</div>'
            % (
                escape(event_id),
                escape(away),
                escape(home),
                f'<span class="gtvc4-time">{escape(time_text)}</span>' if time_text else "",
                f'<div class="gtvc4-meta">{escape(" • ".join(meta_parts))}</div>' if meta_parts else "",
            )
        )
    if not rows:
        return ""
    day = _clean(selected_day)
    return (
        '<div class="gtvc4-day" data-testid="gtvc4-games-on-day">'
        '<div class="gtvc4-dayhead"><b>🏈 GAMES ON THIS DAY</b>'
        f'<span>{escape(day)} • PHOENIX TIME</span></div>'
        f'<div class="gtvc4-daygrid">{"".join(rows)}</div></div>'
    )


def build_footer_html(*, now: datetime | None = None) -> str:
    """Build the Page-1 source/update/calculation footer in Phoenix time."""
    reference = now or datetime.now(ZoneInfo(PHOENIX_TZ))
    if reference.tzinfo is None or reference.utcoffset() is None:
        reference = reference.replace(tzinfo=ZoneInfo(PHOENIX_TZ))
    local = reference.astimezone(ZoneInfo(PHOENIX_TZ))
    updated = local.strftime("%-I:%M %p PHX • %b %-d, %Y")
    return (
        '<div class="gtvc4-footer" data-testid="gtvc4-data-footer">'
        '<div class="gtvc4-footcell"><b>DATA SOURCES</b>'
        '<span>Kyre Sports API • ESPN schedule/team identity • FanDuel verified market context</span></div>'
        '<div class="gtvc4-footcell"><b>UPDATED</b>'
        f'<span><strong>{escape(updated)}</strong></span></div>'
        '<div class="gtvc4-footcell"><b>HOW WE CALCULATE</b>'
        '<span>Frozen Game Total model inputs + verified team context. Sportsbook projection influence: <strong>0.0%</strong>.</span></div>'
        '</div>'
    )


__all__ = [
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PHOENIX_TZ",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_CSS",
    "build_footer_html",
    "build_games_on_day_html",
    "build_relocated_analysis_html",
]
