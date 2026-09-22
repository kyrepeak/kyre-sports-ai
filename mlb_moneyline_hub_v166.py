"""MLB Moneyline V16.6 — Step 1 official game identity + verification.

Presentation/intelligence-only wrapper over frozen V16.5. Step 1 adds a verified
identity block to each Top-5 Moneyline card using the already selected MLB slate:
- official game/team IDs and schedule source,
- away/home team logos and matchup identity,
- Phoenix-local first pitch alongside ET,
- venue and game status,
- both posted probable starters,
- current official lineup-posted state.

No probability, simulation, H2H adjustment, candidate selection, ranking, fair
odds, sportsbook context, confidence or persistence math is changed.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import mlb_moneyline_hub_v165 as prior
import mlb_schedule_v32 as schedule

MODEL_VERSION = "V16.6 • MONEYLINE STEP 1 • OFFICIAL GAME IDENTITY + VERIFICATION"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v165"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN

_ET = ZoneInfo("America/New_York")
_PHOENIX = ZoneInfo("America/Phoenix")

_STEP1_CSS = r"""
<style>
.ks-pick-card{grid-template-areas:"rank rank" "main right" "identity identity"!important}
.ml166-step1{grid-area:identity;margin-top:2px;padding:10px 11px;border:1px solid rgba(64,164,210,.32);border-radius:13px;background:linear-gradient(145deg,rgba(6,24,38,.96),rgba(8,18,30,.96));box-shadow:inset 3px 0 #43c7f4}
.ml166-step1-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml166-step1-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#74dcff}
.ml166-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #47596a;background:#16212c;color:#c8d4de}
.ml166-grade.verified{border-color:#277353;background:#0a3024;color:#83e7b6}.ml166-grade.recovery{border-color:#77611c;background:#342b0d;color:#f5db73}.ml166-grade.check{border-color:#7a3838;background:#341515;color:#ffaaa5}
.ml166-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px;padding:8px 0;border-top:1px solid rgba(91,140,166,.22);border-bottom:1px solid rgba(91,140,166,.22)}
.ml166-team{display:flex;align-items:center;gap:8px;min-width:0}.ml166-team.home{justify-content:flex-end;text-align:right}.ml166-team img{width:34px!important;height:34px!important;max-width:34px!important;object-fit:contain}.ml166-team b{font-size:.72rem;color:#f4f9fc;line-height:1.15}.ml166-at{color:#718b9c;font-size:.65rem;font-weight:900}
.ml166-pills{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.ml166-pill{display:inline-flex;align-items:center;min-height:25px;border:1px solid rgba(91,140,166,.25);background:#0a1825;color:#b9cad6;border-radius:999px;padding:4px 7px;font-size:.51rem;font-weight:850;line-height:1.1}.ml166-pill.good{border-color:#276b50;background:#0a291f;color:#89deb3}.ml166-pill.pending{border-color:#77611c;background:#30280d;color:#f3d977}.ml166-pill.check{border-color:#773737;background:#311515;color:#f3a5a0}
.ml166-details{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}.ml166-detail{border:1px solid rgba(91,140,166,.18);border-radius:9px;background:rgba(5,16,26,.7);padding:7px 8px;color:#9eb1bf;font-size:.50rem;line-height:1.42}.ml166-detail strong{display:block;color:#dce8ef;font-size:.48rem;letter-spacing:.04em;text-transform:uppercase;margin-bottom:2px}.ml166-source{margin-top:6px;color:#708696;font-size:.44rem;line-height:1.4}
.ml166-page-badge{display:inline-flex;align-items:center;gap:6px;margin:0 0 10px;padding:6px 9px;border:1px solid #315a70;border-radius:999px;background:#0a1b28;color:#8edcff;font-size:.58rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
@media(max-width:640px){.ml166-step1{padding:9px}.ml166-matchup{gap:5px}.ml166-team{gap:5px}.ml166-team img{width:29px!important;height:29px!important;max-width:29px!important}.ml166-team b{font-size:.61rem}.ml166-details{grid-template-columns:1fr}.ml166-pill{font-size:.47rem}.ml166-step1-title{font-size:.52rem}}
</style>
"""


def _safe_int(value: Any) -> int | None:
    try:
        number = int(float(value))
        return number
    except (TypeError, ValueError, OverflowError):
        return None


def _row_map(games_df) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if games_df is None or getattr(games_df, "empty", True):
        return out
    try:
        for _, row in games_df.iterrows():
            data = row.to_dict()
            pk = _safe_int(data.get("game_pk"))
            if pk is not None:
                out[pk] = data
    except Exception:
        return {}
    return out


def _phoenix_time(game_date: Any, first_pitch_et: Any) -> str:
    text = str(first_pitch_et or "").strip()
    if not text or text.upper() == "TBD":
        return "TBD"
    day = str(game_date or "")[:10]
    try:
        naive = datetime.strptime(f"{day} {text}", "%Y-%m-%d %I:%M %p")
        local = naive.replace(tzinfo=_ET).astimezone(_PHOENIX)
        return local.strftime("%I:%M %p").lstrip("0") + " MST"
    except Exception:
        return "TBD"


def _lineup_counts(games_df) -> dict[int, dict[str, int]]:
    """Read current official batting-order counts only; no projected lineup inference."""
    rows = _row_map(games_df)
    pks = tuple(sorted(pk for pk in rows if pk > 0))
    if not pks:
        return {}
    try:
        import slate_lineup_v204 as official_lineups
        payload = official_lineups._fetch_lineups_bulk(pks) or {}
    except Exception:
        return {}
    out: dict[int, dict[str, int]] = {}
    for pk, item in payload.items():
        block = item or {}
        out[int(pk)] = {
            "away": len(block.get("away") or []),
            "home": len(block.get("home") or []),
        }
    return out


def _lineup_label(count: int) -> tuple[str, str]:
    if int(count or 0) >= 9:
        return "CONFIRMED", "good"
    if int(count or 0) > 0:
        return "PARTIAL", "pending"
    return "NOT POSTED", "pending"


def _starter_posted(name: Any) -> bool:
    text = str(name or "").strip().upper()
    return bool(text and text not in {"TBD", "UNKNOWN", "NONE", "N/A", "—"})


def _identity_context(result: Mapping[str, Any], rows: Mapping[int, Mapping[str, Any]], lineups: Mapping[int, Mapping[str, int]]) -> dict[str, Any]:
    pk = _safe_int(result.get("game_pk"))
    row = dict(rows.get(pk) or {}) if pk is not None else {}
    away_id = _safe_int(result.get("away_team_id"))
    home_id = _safe_int(result.get("home_team_id"))
    row_away = _safe_int(row.get("away_team_id"))
    row_home = _safe_int(row.get("home_team_id"))
    teams_match = bool(row and away_id is not None and home_id is not None and away_id == row_away and home_id == row_home)
    source = str(row.get("schedule_source") or "source unavailable")
    verified_flag = bool(row.get("verified"))
    official = bool(pk is not None and pk > 0 and teams_match and verified_flag and "MLB" in source.upper())
    recovery = bool(not official and teams_match and verified_flag)
    if official:
        grade, grade_cls = "VERIFIED", "verified"
    elif recovery:
        grade, grade_cls = "RECOVERY VERIFIED", "recovery"
    else:
        grade, grade_cls = "CHECK IDENTITY", "check"

    away_name = str(row.get("away_team") or result.get("away_name") or "Away")
    home_name = str(row.get("home_team") or result.get("home_name") or "Home")
    away_pitcher = str(row.get("away_pitcher") or result.get("away_pitcher") or "TBD")
    home_pitcher = str(row.get("home_pitcher") or result.get("home_pitcher") or "TBD")
    starter_count = int(_starter_posted(away_pitcher)) + int(_starter_posted(home_pitcher))
    starter_text = "BOTH STARTERS POSTED" if starter_count == 2 else "1 STARTER POSTED" if starter_count == 1 else "STARTERS TBD"
    starter_cls = "good" if starter_count == 2 else "pending"

    lineup = dict(lineups.get(pk) or {}) if pk is not None else {}
    away_lineup, away_lineup_cls = _lineup_label(int(lineup.get("away", 0) or 0))
    home_lineup, home_lineup_cls = _lineup_label(int(lineup.get("home", 0) or 0))
    if away_lineup == home_lineup == "CONFIRMED":
        lineup_text, lineup_cls = "BOTH LINEUPS CONFIRMED", "good"
    elif "CONFIRMED" in {away_lineup, home_lineup}:
        lineup_text, lineup_cls = "1/2 LINEUPS CONFIRMED", "pending"
    else:
        lineup_text, lineup_cls = "LINEUPS PENDING", "pending"

    game_date = row.get("game_date") or result.get("game_date")
    et = row.get("first_pitch_et") or result.get("first_pitch") or "TBD"
    return {
        "game_pk": pk,
        "grade": grade,
        "grade_cls": grade_cls,
        "away_id": row_away if row_away is not None else away_id,
        "home_id": row_home if row_home is not None else home_id,
        "away_name": away_name,
        "home_name": home_name,
        "venue": str(row.get("venue_name") or result.get("venue") or "Venue TBD"),
        "status": str(row.get("status") or result.get("status") or "Unknown"),
        "source": source,
        "first_pitch_et": str(et),
        "first_pitch_phoenix": _phoenix_time(game_date, et),
        "away_pitcher": away_pitcher,
        "home_pitcher": home_pitcher,
        "starter_text": starter_text,
        "starter_cls": starter_cls,
        "away_lineup": away_lineup,
        "away_lineup_cls": away_lineup_cls,
        "home_lineup": home_lineup,
        "home_lineup_cls": home_lineup_cls,
        "lineup_text": lineup_text,
        "lineup_cls": lineup_cls,
        "teams_match": teams_match,
    }


def _team_logo_html(team_logo, team_id: Any) -> str:
    try:
        return str(team_logo(team_id) or "")
    except Exception:
        return ""


def _step1_html(context: Mapping[str, Any], team_logo) -> str:
    away_logo = _team_logo_html(team_logo, context.get("away_id"))
    home_logo = _team_logo_html(team_logo, context.get("home_id"))
    pk_text = str(context.get("game_pk") or "—")
    return (
        '<div class="ml166-step1">'
        '<div class="ml166-step1-head">'
        '<span class="ml166-step1-title">STEP 1 • OFFICIAL GAME IDENTITY + VERIFICATION</span>'
        f'<span class="ml166-grade {escape(str(context.get("grade_cls") or "check"))}">{escape(str(context.get("grade") or "CHECK"))}</span>'
        '</div>'
        '<div class="ml166-matchup">'
        f'<div class="ml166-team">{away_logo}<b>{escape(str(context.get("away_name") or "Away"))}</b></div>'
        '<div class="ml166-at">@</div>'
        f'<div class="ml166-team home"><b>{escape(str(context.get("home_name") or "Home"))}</b>{home_logo}</div>'
        '</div>'
        '<div class="ml166-pills">'
        f'<span class="ml166-pill good">🌵 {escape(str(context.get("first_pitch_phoenix") or "TBD"))} • Phoenix</span>'
        f'<span class="ml166-pill">ET {escape(str(context.get("first_pitch_et") or "TBD"))}</span>'
        f'<span class="ml166-pill">MLB GAME {escape(pk_text)}</span>'
        f'<span class="ml166-pill {escape(str(context.get("starter_cls") or "pending"))}">{escape(str(context.get("starter_text") or "STARTERS TBD"))}</span>'
        f'<span class="ml166-pill {escape(str(context.get("lineup_cls") or "pending"))}">{escape(str(context.get("lineup_text") or "LINEUPS PENDING"))}</span>'
        '</div>'
        '<div class="ml166-details">'
        f'<div class="ml166-detail"><strong>Away probable starter</strong>{escape(str(context.get("away_pitcher") or "TBD"))} • Lineup {escape(str(context.get("away_lineup") or "NOT POSTED"))}</div>'
        f'<div class="ml166-detail"><strong>Home probable starter</strong>{escape(str(context.get("home_pitcher") or "TBD"))} • Lineup {escape(str(context.get("home_lineup") or "NOT POSTED"))}</div>'
        f'<div class="ml166-detail"><strong>Venue</strong>{escape(str(context.get("venue") or "Venue TBD"))}</div>'
        f'<div class="ml166-detail"><strong>Game status</strong>{escape(str(context.get("status") or "Unknown"))}</div>'
        '</div>'
        f'<div class="ml166-source">Source: {escape(str(context.get("source") or "unavailable"))} • identity/readiness only • no Moneyline probability adjustment.</div>'
        '</div>'
    )


def _inject_step1(card_html: str, step_html: str) -> str:
    text = str(card_html or "")
    if not step_html or "ks-pick-card" not in text or "ml166-step1" in text:
        return text
    head, sep, tail = text.rpartition("</div>")
    if not sep:
        return text + step_html
    return head + step_html + sep + tail


def _card_renderer_with_step1(original, rows, lineups):
    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        cursor = {"index": 0}
        original_markdown = st.markdown

        def markdown_capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["index"] < len(ordered):
                result = ordered[cursor["index"]]
                cursor["index"] += 1
                context = _identity_context(result, rows, lineups)
                text = _inject_step1(text, _step1_html(context, team_logo))
                body = text
            return original_markdown(body, *args, **kwargs)

        st.markdown = markdown_capture
        try:
            return original(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def _fresh_identity_slate(fallback_games):
    try:
        day = schedule.current_selected_date()
        fresh, _diag = schedule.load_with_diagnostics(day)
        if fresh is not None and not fresh.empty:
            return fresh
    except Exception:
        pass
    return fallback_games


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render frozen V16.5 plus Step 1 verified game identity/readiness blocks."""
    identity_games = _fresh_identity_slate(games_df)
    rows = _row_map(identity_games)
    lineups = _lineup_counts(identity_games)

    st.markdown(
        '<div class="ml166-page-badge">💰 Moneyline Intelligence • Step 1 active • Official game identity + verification</div>',
        unsafe_allow_html=True,
    )

    v163 = prior.prior
    v162 = v163.base
    v161 = v162.base
    original_cards = v161._render_cards_v161
    original_css = prior._CSS
    v161._render_cards_v161 = _card_renderer_with_step1(original_cards, rows, lineups)
    prior._CSS = original_css + _STEP1_CSS
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._CSS = original_css
        v161._render_cards_v161 = original_cards


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MODEL_VERSION",
    "_identity_context",
    "_inject_step1",
    "_phoenix_time",
    "_row_map",
    "_step1_html",
    "render_moneyline_hub",
]
