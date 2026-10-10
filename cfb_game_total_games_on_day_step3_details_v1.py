"""CFB Game Total — Games on This Day Step 3 useful card details.

Presentation-only successor to frozen Steps 1-2. Step 3 reuses the already-loaded
schedule identity carried by each game to add status, numeric ranking when
available, and conference metadata. It does not fetch data, change event
identity, alter selection, or touch model/projection/probability behavior.
"""
from __future__ import annotations

from html import escape
import importlib
import re
from threading import RLock
from typing import Any, Mapping

MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 3 DETAILS V1"
DIRECT_NETWORK_ENDPOINTS_ADDED = 0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_INSTALL_ATTR = "_cfb_games_on_day_step3_details_installed"
_ORIGINAL_ATTR = "_cfb_games_on_day_step3_original"
_LOCK = RLock()

STEP3_CSS = r"""
<style data-kyre-cfb-games-on-day-step3-details="v1">
.gt3-status-chip{display:inline-flex;align-items:center;justify-content:center;min-width:48px;padding:3px 7px;border-radius:999px;font-size:8px;font-weight:1000;letter-spacing:.08em;border:1px solid rgba(159,223,255,.32);background:rgba(159,223,255,.08);color:#d8f2ff}
.gt3-status-live{border-color:rgba(69,240,173,.58);background:rgba(69,240,173,.14);color:#8ff7c9;box-shadow:0 0 14px rgba(69,240,173,.10)}
.gt3-status-upcoming{border-color:rgba(88,201,255,.50);background:rgba(88,201,255,.11);color:#a9e7ff}
.gt3-status-final{border-color:rgba(170,183,196,.35);background:rgba(170,183,196,.08);color:#c5d0da}
.gt3-team-copy{display:flex;flex-direction:column;min-width:0;gap:2px}
.gt3-team-meta{display:flex;align-items:center;gap:5px;min-height:11px;font-size:8px;font-weight:850;letter-spacing:.035em;color:#7f9bad;line-height:1}
.gt3-rank{color:#f3c86b;font-weight:1000}
.gt3-conference{color:#87bdd6;font-weight:900}
.gt3-meta-dot{opacity:.48}
.gt2-game-card.selected .gt3-team-meta{color:#9fc9bb}
.gt2-game-card.selected .gt3-conference{color:#a8ddca}
@media(max-width:760px){.gt3-status-chip{font-size:8px;padding:3px 6px}.gt3-team-meta{font-size:8px}}
</style>
"""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def status_label(game: Mapping[str, Any]) -> str:
    raw = ""
    for key in ("status", "game_status", "status_text", "state"):
        raw = _clean(game.get(key))
        if raw:
            break
    if not raw:
        return ""
    upper = raw.upper()
    if "FINAL" in upper:
        return "FINAL"
    if any(token in upper for token in ("IN PROGRESS", "LIVE", "HALFTIME", "END OF")):
        return "LIVE"
    if re.search(r"\b(?:1ST|2ND|3RD|4TH|OT|Q1|Q2|Q3|Q4)\b", upper):
        return "LIVE"
    if any(token in upper for token in ("SCHEDULED", "UPCOMING", "PRE-GAME", "PREGAME")):
        return "UPCOMING"
    return ""


def _rank_text(value: Any) -> str:
    text = _clean(value).lstrip("#")
    if not text.isdigit():
        return ""
    rank = int(text)
    return f"#{rank}" if 1 <= rank <= 25 else ""


def _side_rows(game: Mapping[str, Any], side: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    row = game.get(side) if isinstance(game.get(side), Mapping) else {}
    team = row.get("team") if isinstance(row.get("team"), Mapping) else {}
    return row, team


def _team_name(game: Mapping[str, Any], side: str) -> str:
    row, team = _side_rows(game, side)
    for value in (
        game.get(f"{side}_team"),
        game.get(f"{side}_team_name"),
        game.get(f"{side}_name"),
        row.get("display_name"),
        row.get("displayName"),
        row.get("name"),
        team.get("displayName"),
        team.get("shortDisplayName"),
        team.get("name"),
        team.get("location"),
    ):
        text = _clean(value)
        if text:
            return text
    return side.title()


def _rank(game: Mapping[str, Any], side: str) -> str:
    row, team = _side_rows(game, side)
    for value in (
        game.get(f"{side}_rank"),
        game.get(f"{side}_ranking"),
        row.get("rank"),
        row.get("ranking"),
        row.get("teamRank"),
        team.get("rank"),
        team.get("ranking"),
        team.get("teamRank"),
    ):
        rank = _rank_text(value)
        if rank:
            return rank
    return ""


def _conference(game: Mapping[str, Any], side: str) -> str:
    row, team = _side_rows(game, side)
    for value in (
        game.get(f"{side}_conference"),
        row.get("conference"),
        row.get("conferenceName"),
        row.get("conferenceSeo"),
        team.get("conference"),
        team.get("conferenceName"),
        team.get("conferenceSeo"),
    ):
        text = _clean(value)
        if not text:
            continue
        if text.lower() in {"conference unavailable", "unknown", "n/a", "na", "none"}:
            continue
        return text
    return ""


def _team_meta_html(game: Mapping[str, Any], side: str) -> str:
    rank = _rank(game, side)
    conference = _conference(game, side)
    pieces: list[str] = []
    if rank:
        pieces.append(f'<span class="gt3-rank">{escape(rank)}</span>')
    if conference:
        if pieces:
            pieces.append('<span class="gt3-meta-dot">•</span>')
        pieces.append(f'<span class="gt3-conference">{escape(conference)}</span>')
    if not pieces:
        return ""
    return '<span class="gt3-team-meta">' + "".join(pieces) + "</span>"


def augment_game_card_html(base_html: str, game: Mapping[str, Any]) -> str:
    """Add Step-3 display evidence to a Step-2 card without changing its link/state."""
    html = str(base_html or "")
    if not html or 'data-step3-details="v1"' in html:
        return html

    html = re.sub(
        r"(<(?:a|span)\b)",
        r'\1 data-step3-details="v1"',
        html,
        count=1,
    )

    status = status_label(game)
    if status:
        status_class = status.lower()
        chip = f'<span class="gt3-status-chip gt3-status-{status_class}">{status}</span>'
        html = html.replace('<div class="gt2-card-top">', '<div class="gt2-card-top">' + chip, 1)

    for side in ("away", "home"):
        name = _team_name(game, side)
        escaped_name = escape(name)
        needle = f'<span class="gt2-team-name">{escaped_name}</span>'
        if needle not in html:
            continue
        meta = _team_meta_html(game, side)
        replacement = (
            '<span class="gt3-team-copy">'
            + needle
            + meta
            + '</span>'
        )
        html = html.replace(needle, replacement, 1)
    return html


def install_games_on_day_step3_details() -> bool:
    """Install one idempotent wrapper around frozen Step-2 card composition."""
    with _LOCK:
        step2 = importlib.import_module("cfb_game_total_games_on_day_step2_visual_v1")
        current = step2.build_game_card_html
        if getattr(current, _INSTALL_ATTR, False):
            if STEP3_CSS not in step2.STEP2_CSS:
                step2.STEP2_CSS += STEP3_CSS
            return True

        def build_game_card_with_details(game: Mapping[str, Any], *args: Any, **kwargs: Any) -> str:
            return augment_game_card_html(current(game, *args, **kwargs), game)

        setattr(build_game_card_with_details, _INSTALL_ATTR, True)
        setattr(build_game_card_with_details, _ORIGINAL_ATTR, current)
        step2.build_game_card_html = build_game_card_with_details
        if STEP3_CSS not in step2.STEP2_CSS:
            step2.STEP2_CSS += STEP3_CSS
        return True


__all__ = [
    "DIRECT_NETWORK_ENDPOINTS_ADDED",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_CSS",
    "augment_game_card_html",
    "install_games_on_day_step3_details",
    "status_label",
]
