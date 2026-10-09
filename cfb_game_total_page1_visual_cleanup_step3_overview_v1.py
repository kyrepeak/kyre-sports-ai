"""CFB Game Total Page 1 visual cleanup Step 3 — Overview + Team Snapshot.

Presentation-only helpers. Uses existing selected-game Team Evidence and Phoenix
clock ownership. No model, projection, probability, ranking, qualification,
market ownership, or sportsbook input is changed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

PHOENIX_TZ = "America/Phoenix"
STEP3_MARKER = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_STEP3_OVERVIEW_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False

STEP3_CSS = r"""
<style>
.gtvc3-edge{margin:12px auto 0}.gtvc3-edgehead,.gtvc3-snaphead{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:10px}.gtvc3-edgehead b,.gtvc3-snaphead b{color:#f7fbff;font-size:15px;letter-spacing:.035em}.gtvc3-edgehead span,.gtvc3-snaphead span{color:#7895aa;font-size:9px;text-align:right}.gtvc3-edgegrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.gtvc3-edgecard{min-width:0;padding:14px;border:1px solid rgba(82,171,211,.24);border-radius:15px;background:linear-gradient(150deg,#091c29,#081724);box-shadow:0 10px 24px rgba(0,0,0,.13)}.gtvc3-edgecard.favorable{border-color:rgba(69,240,173,.30)}.gtvc3-edgecard.key{border-color:rgba(83,199,255,.34)}.gtvc3-edgecard.tough{border-color:rgba(169,104,255,.32)}.gtvc3-edgelabel{color:#7f9bad;font-size:8px;font-weight:950;letter-spacing:.11em}.gtvc3-edgevalue{display:block;margin-top:7px;color:#f8fcff;font-size:18px;font-weight:1000;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtvc3-edgedetail{display:block;margin-top:5px;color:#8ca7ba;font-size:9px;line-height:1.35}.gtvc3-snapshot{margin:12px auto 0;padding:16px;border:1px solid rgba(81,177,217,.28);border-radius:19px;background:radial-gradient(circle at 10% 0%,rgba(38,204,224,.08),transparent 30%),radial-gradient(circle at 90% 0%,rgba(86,126,255,.09),transparent 30%),linear-gradient(145deg,#061724,#071522 65%,#081321)}.gtvc3-snapgrid{display:grid;grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);gap:10px;align-items:stretch}.gtvc3-team{min-width:0;padding:13px;border:1px solid rgba(84,160,201,.21);border-radius:15px;background:#091b28}.gtvc3-teamtop{display:flex;align-items:center;gap:10px}.gtvc3-logo{width:48px;height:48px;flex:0 0 48px;display:grid;place-items:center}.gtvc3-logo img,.gtvc3-logo [class*=logo]{max-width:46px!important;max-height:46px!important;object-fit:contain}.gtvc3-teamcopy{min-width:0}.gtvc3-teamcopy b{display:block;color:#f7fbff;font-size:14px;font-weight:1000;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gtvc3-teamcopy span{display:block;margin-top:3px;color:#819caf;font-size:8px}.gtvc3-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:10px}.gtvc3-metric{padding:9px;border:1px solid rgba(84,160,201,.14);border-radius:10px;background:#0a2230}.gtvc3-metric strong{display:block;color:#eefaff;font-size:15px}.gtvc3-metric span{display:block;margin-top:3px;color:#7692a6;font-size:7px;font-weight:900;text-transform:uppercase}.gtvc3-vs{align-self:center;width:34px;height:34px;display:grid;place-items:center;border:1px solid rgba(86,190,231,.26);border-radius:50%;background:#092231;color:#b8cfdd;font-size:8px;font-weight:1000}
@media(max-width:760px){.gtvc3-edgegrid{grid-template-columns:1fr}.gtvc3-snapgrid{grid-template-columns:1fr}.gtvc3-vs{justify-self:center;margin:-2px 0}.gtvc3-edgehead,.gtvc3-snaphead{align-items:flex-start}.gtvc3-snapshot{padding:12px}.gtvc3-edgevalue{font-size:16px}}
</style>
"""


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _team_name(identity: Mapping[str, Any], stats: Mapping[str, Any], fallback: str) -> str:
    return _clean(identity.get("team")) or _clean(stats.get("team")) or fallback


def phoenix_day_window_including_today(
    selected: date | str | None,
    *,
    now: datetime | None = None,
    count: int = 7,
) -> list[date]:
    """Always show Phoenix today through the next six days, regardless of selected day."""
    reference = now or datetime.now(ZoneInfo(PHOENIX_TZ))
    if reference.tzinfo is None or reference.utcoffset() is None:
        reference = reference.replace(tzinfo=ZoneInfo(PHOENIX_TZ))
    else:
        reference = reference.astimezone(ZoneInfo(PHOENIX_TZ))
    anchor = reference.date()
    return [anchor + timedelta(days=index) for index in range(max(1, int(count)))]


def _edge_cards(identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> list[tuple[str, str, str, str]]:
    away_id = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
    home_id = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}
    away_name = _team_name(away_id, away, "Away")
    home_name = _team_name(home_id, home, "Home")
    cards: list[tuple[str, str, str, str]] = []

    away_diff, home_diff = _number(away.get("point_diff_pg")), _number(home.get("point_diff_pg"))
    if away_diff is not None and home_diff is not None:
        favored = away_name if away_diff >= home_diff else home_name
        margin = abs(away_diff - home_diff)
        cards.append(("favorable", "FAVORABLE FOR", favored, f"Point differential edge: {margin:.1f} pts/game"))

    candidates: list[tuple[float, str, str]] = []
    away_ppg, home_ppg = _number(away.get("ppg")), _number(home.get("ppg"))
    if away_ppg is not None and home_ppg is not None:
        gap = away_ppg - home_ppg
        leader = away_name if gap >= 0 else home_name
        candidates.append((abs(gap), leader, f"Scoring edge: {abs(gap):.1f} PPG"))
    away_allowed, home_allowed = _number(away.get("allowed_pg")), _number(home.get("allowed_pg"))
    if away_allowed is not None and home_allowed is not None:
        gap = away_allowed - home_allowed
        leader = away_name if gap <= 0 else home_name
        candidates.append((abs(gap), leader, f"Defense edge: {abs(gap):.1f} fewer PPG allowed"))
    if away_diff is not None and home_diff is not None:
        gap = away_diff - home_diff
        leader = away_name if gap >= 0 else home_name
        candidates.append((abs(gap), leader, f"Point-differential edge: {abs(gap):.1f}"))
    if candidates:
        _, leader, detail = max(candidates, key=lambda row: row[0])
        cards.append(("key", "KEY EDGE", leader, detail))

    if away_allowed is not None and home_allowed is not None:
        if home_allowed < away_allowed:
            tough_for, defense_name, defense = away_name, home_name, home_allowed
        else:
            tough_for, defense_name, defense = home_name, away_name, away_allowed
        cards.append(("tough", "TOUGHNESS FOR", tough_for, f"Faces {defense_name} defense allowing {defense:.1f} PPG"))
    return cards


def build_overview_edge_html(identity: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    cards = _edge_cards(identity, away, home)
    if not cards:
        return ""
    body = "".join(
        f'<div class="gtvc3-edgecard {escape(kind)}"><span class="gtvc3-edgelabel">{escape(label)}</span>'
        f'<strong class="gtvc3-edgevalue">{escape(value)}</strong><span class="gtvc3-edgedetail">{escape(detail)}</span></div>'
        for kind, label, value, detail in cards
    )
    return STEP3_CSS + (
        f'<section class="gtvc3-edge" data-testid="gtvc3-overview-edge" data-step3="{STEP3_MARKER}">'
        '<div class="gtvc3-edgehead"><b>OVERVIEW EDGES</b><span>Existing verified team evidence • presentation only</span></div>'
        f'<div class="gtvc3-edgegrid">{body}</div></section>'
    )


def _metric(label: str, value: Any, *, signed: bool = False) -> str:
    numeric = _number(value)
    if numeric is not None:
        display = f"{numeric:+.1f}" if signed else f"{numeric:.1f}"
    else:
        text = _clean(value)
        if not text:
            return ""
        display = text
    return f'<div class="gtvc3-metric"><strong>{escape(display)}</strong><span>{escape(label)}</span></div>'


def build_team_snapshot_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    *,
    away_logo_html: str,
    home_logo_html: str,
) -> str:
    away_id = identity.get("away") if isinstance(identity.get("away"), Mapping) else {}
    home_id = identity.get("home") if isinstance(identity.get("home"), Mapping) else {}

    def card(team_id: Mapping[str, Any], stats: Mapping[str, Any], logo: str) -> str:
        name = _team_name(team_id, stats, "Team")
        conference = _clean(team_id.get("conference")) or "NCAAF"
        record = _clean(stats.get("record"))
        meta = " • ".join(part for part in (record, conference) if part)
        metrics = "".join(filter(None, [
            _metric("PPG", stats.get("ppg")),
            _metric("Allowed PPG", stats.get("allowed_pg")),
            _metric("Point Diff", stats.get("point_diff_pg"), signed=True),
            _metric("Recent Form", stats.get("recent_form")),
        ]))
        return (
            '<div class="gtvc3-team"><div class="gtvc3-teamtop">'
            f'<div class="gtvc3-logo">{logo}</div><div class="gtvc3-teamcopy"><b>{escape(name)}</b>'
            f'<span>{escape(meta)}</span></div></div><div class="gtvc3-metrics">{metrics}</div></div>'
        )

    return (
        '<section class="gtvc3-snapshot" data-testid="gtvc3-team-snapshot">'
        '<div class="gtvc3-snaphead"><b>TEAM SNAPSHOT</b><span>Scoring • prevention • differential • recent form</span></div>'
        '<div class="gtvc3-snapgrid">'
        f'{card(away_id, away, away_logo_html)}<div class="gtvc3-vs">VS</div>{card(home_id, home, home_logo_html)}'
        '</div></section>'
    )


__all__ = [
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "PHOENIX_TZ",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_CSS",
    "STEP3_MARKER",
    "build_overview_edge_html",
    "build_team_snapshot_html",
    "phoenix_day_window_including_today",
]
