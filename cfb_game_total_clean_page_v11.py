"""CFB Game Total Clean Page V11 — V161 days + verified market context.

Additive successor to permanently frozen V160. V161 keeps the exact V160
Monster dashboard foundation and frozen V159 model/data owner while adding only:
(1) visible game-day navigation, (2) removal of the visible brand masthead, and
(3) identity-verified, freshness-gated sportsbook game-total context.

Projection, distribution, Step-12 qualification, Top-5 ranking, API/model
behavior, and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
import os
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests
import streamlit as st

import cfb_game_total_clean_page_v10 as prior_v160

prior = prior_v160.prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V11 • V161 DAYS + VERIFIED MARKET"
MARKET = prior_v160.MARKET
FROZEN_GAME_TOTAL_HUB = prior_v160.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v10"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V161 ACTIVE"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
ODDS_API_BASE_ENV = "KYRE_SPORTS_API_BASE_URL"
ODDS_API_BASE_DEFAULT = "https://kyre-sports-api.onrender.com"
ODDS_ENDPOINT = "/api/v1/cfb/odds"
ODDS_MATCH_METHOD = "official ESPN event_id only"
ODDS_PROVIDER = "FanDuel"
MAX_VERIFIED_FEED_AGE_SECONDS = 180.0
_ALLOWED_LINE_STATUSES = {"open", "active"}

V161_REQUIRED_MARKERS = (
    ACTIVE_MARKER,
    "GAME TOTAL ANALYSIS",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)

_V161_CSS = r"""
<style>
.gt160-masthead{display:none!important}
.gt161-day-wrap{max-width:900px;margin:0 auto 8px;padding:8px 10px 5px;border:1px solid rgba(65,157,194,.30);border-radius:13px;background:linear-gradient(120deg,rgba(5,24,35,.98),rgba(7,17,31,.98));box-sizing:border-box}
.gt161-day-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 2px 6px;color:#edf7ff}.gt161-day-title b{font-size:11px;letter-spacing:.10em}.gt161-day-title span{font-size:9px;color:#8099ad}
.gt161-selected-date{max-width:900px;margin:-3px auto 8px;text-align:center;color:#45f0ad;font-size:9px;font-weight:900;letter-spacing:.065em}
.gt161-market-proof{margin:-2px 14px 12px;padding:6px 9px;border:1px solid rgba(69,240,173,.27);border-radius:8px;background:rgba(11,54,45,.25);color:#9fc9b7;font-size:9px;line-height:1.35}
.gt161-market-proof strong{color:#45f0ad}.gt161-market-proof.unavailable{border-color:rgba(255,210,77,.25);background:rgba(78,60,19,.18);color:#b7ab82}.gt161-market-proof.unavailable strong{color:#ffd24d}
.gt161-identity{display:none!important}
div[data-testid="stHorizontalBlock"] button[kind="secondary"]{min-height:40px!important;padding:4px 2px!important;border:1px solid rgba(79,153,194,.34)!important;border-radius:9px!important;background:#071824!important;color:#b8c9d7!important;font-size:10px!important;font-weight:900!important}
div[data-testid="stHorizontalBlock"] button[kind="primary"]{min-height:40px!important;padding:4px 2px!important;border:1px solid rgba(69,240,173,.70)!important;border-radius:9px!important;background:linear-gradient(145deg,rgba(19,105,76,.70),rgba(7,35,40,.95))!important;color:#f7fbff!important;font-size:10px!important;font-weight:950!important;box-shadow:0 0 14px rgba(69,240,173,.12)!important}
@media(max-width:760px){.gt161-day-wrap{padding:7px 7px 4px;margin-bottom:6px}.gt161-day-title span{display:none}div[data-testid="stHorizontalBlock"]{gap:3px!important}div[data-testid="stHorizontalBlock"] button[kind="secondary"],div[data-testid="stHorizontalBlock"] button[kind="primary"]{min-height:36px!important;padding:3px 1px!important;font-size:8px!important;border-radius:7px!important}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_aware(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _game_date(display_game: Mapping[str, Any]) -> str:
    for key in ("game_date", "date", "start_date"):
        text = _clean(display_game.get(key))
        if text:
            return text[:10]
    return ""


def _game_id(display_game: Mapping[str, Any]) -> str:
    for key in ("event_id", "game_id", "id"):
        text = _clean(display_game.get(key))
        if text:
            return text
    return ""


def _team_id(display_game: Mapping[str, Any], side: str) -> str:
    nested = display_game.get(side)
    if isinstance(nested, Mapping):
        for key in ("team_id", "id", "espn_team_id"):
            text = _clean(nested.get(key))
            if text:
                return text
    for key in (f"{side}_team_id", f"{side}_id"):
        text = _clean(display_game.get(key))
        if text:
            return text
    return ""


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "verified": False,
        "total": None,
        "sportsbook": "",
        "captured_at_utc": "",
        "line_updated_at_utc": "",
        "feed_age_seconds": None,
        "projection_weight": 0.0,
        "reason": reason,
    }


def _verified_market_for_game(
    display_game: Mapping[str, Any],
    payload: Mapping[str, Any] | None,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Return one exact, fresh sportsbook total or fail closed."""
    if not isinstance(payload, Mapping):
        return _unavailable("market feed unavailable")

    semantics = payload.get("market_semantics")
    if not isinstance(semantics, Mapping) or semantics.get("projection_weight") != 0.0:
        return _unavailable("market semantics rejected")
    if semantics.get("may_modify_projection") not in (None, False):
        return _unavailable("market projection firewall rejected")

    event_id = _game_id(display_game)
    selected_date = _game_date(display_game)
    if not event_id or not selected_date:
        return _unavailable("official game identity unavailable")

    captured = _parse_aware(payload.get("captured_at_utc"))
    if captured is None:
        return _unavailable("market freshness unavailable")
    reference = now_utc or datetime.now(timezone.utc)
    if reference.tzinfo is None or reference.utcoffset() is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age = (reference.astimezone(timezone.utc) - captured).total_seconds()
    if age < -60 or age > MAX_VERIFIED_FEED_AGE_SECONDS:
        return _unavailable("market feed stale")

    away_id = _team_id(display_game, "away")
    home_id = _team_id(display_game, "home")
    matches: list[Mapping[str, Any]] = []
    for row in payload.get("games") or []:
        if not isinstance(row, Mapping) or row.get("identity_verified") is not True:
            continue
        if _clean(row.get("game_id")) != event_id:
            continue
        if _clean(row.get("game_date")) != selected_date:
            continue
        if away_id and _clean(row.get("away_team_id")) != away_id:
            continue
        if home_id and _clean(row.get("home_team_id")) != home_id:
            continue
        if _clean(row.get("line_status")).casefold() not in _ALLOWED_LINE_STATUSES:
            continue
        matches.append(row)

    if len(matches) != 1:
        return _unavailable("no unique identity-verified market row")
    row = matches[0]
    try:
        total = float(row.get("total"))
    except (TypeError, ValueError):
        return _unavailable("verified market total unavailable")
    if not 0 < total <= 200:
        return _unavailable("verified market total invalid")

    sportsbook = _clean(row.get("sportsbook"))
    if not sportsbook:
        return _unavailable("sportsbook identity unavailable")

    return {
        "verified": True,
        "total": total,
        "sportsbook": sportsbook,
        "captured_at_utc": captured.isoformat(),
        "line_updated_at_utc": _clean(row.get("line_updated_at_utc")),
        "feed_age_seconds": max(0.0, age),
        "projection_weight": 0.0,
        "reason": "",
    }


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_odds_payload(game_date: str) -> dict[str, Any] | None:
    base = _clean(os.environ.get(ODDS_API_BASE_ENV)) or ODDS_API_BASE_DEFAULT
    try:
        response = requests.get(
            f"{base.rstrip('/')}{ODDS_ENDPOINT}",
            params={"game_date": game_date, "sportsbook": ODDS_PROVIDER},
            timeout=5.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _market_for_display_game(display_game: Mapping[str, Any]) -> dict[str, Any]:
    game_date = _game_date(display_game)
    if not game_date:
        return _unavailable("official game date unavailable")
    return _verified_market_for_game(display_game, _fetch_odds_payload(game_date))


def _market_proof_html(result: Mapping[str, Any]) -> str:
    if result.get("verified") is True:
        age = result.get("feed_age_seconds")
        age_text = f"{int(round(float(age)))}s old" if age is not None else "fresh"
        updated = _clean(result.get("line_updated_at_utc"))
        updated_text = f" • line {escape(updated)}" if updated else ""
        return (
            '<div class="gt161-market-proof" data-testid="gt161-market-proof">'
            f'<strong>✓ {escape(_clean(result.get("sportsbook")))}</strong> • exact ESPN event verified • feed {escape(age_text)}'
            f'{updated_text} • projection influence 0.0%</div>'
        )
    return (
        '<div class="gt161-market-proof unavailable" data-testid="gt161-market-proof">'
        '<strong>Market total unavailable</strong> • no fresh exact-game sportsbook row passed verification • projection remains independent</div>'
    )


def _query_date() -> date:
    raw = _clean(st.query_params.get(DATE_QUERY_KEY))
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now(ZoneInfo("America/Phoenix")).date()


def _set_query_date(selected: date) -> None:
    st.query_params[DATE_QUERY_KEY] = selected.isoformat()


def _render_day_strip() -> date:
    selected = _query_date()
    st.markdown(
        '<div class="gt161-day-wrap" data-testid="gt161-day-strip"><div class="gt161-day-title"><b>📅 GAME DAY</b><span>Select a day to load that CFB slate</span></div></div>',
        unsafe_allow_html=True,
    )
    start = selected - timedelta(days=2)
    days = [start + timedelta(days=i) for i in range(7)]
    columns = st.columns(7, gap="small")
    for column, candidate in zip(columns, days):
        label = f"{candidate.strftime('%a • %b')} {candidate.day}"
        if candidate == selected:
            label = f"✓ {label}"
        with column:
            if st.button(
                label,
                key=f"gt161_day_{candidate.isoformat()}",
                type="primary" if candidate == selected else "secondary",
                use_container_width=True,
            ):
                _set_query_date(candidate)
                st.rerun()
    selected_label = f"{selected.strftime('%A, %B')} {selected.day}, {selected.year}".upper()
    st.markdown(
        f'<div class="gt161-selected-date">SELECTED • {escape(selected_label)}</div>',
        unsafe_allow_html=True,
    )
    return selected


def _render_v161_identity() -> None:
    st.markdown(
        '<div class="gt161-identity" data-testid="cfb-game-total-v161-active">'
        f'{ACTIVE_MARKER} • V160 foundation frozen • sportsbook 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(prior_v160._V160_CSS, unsafe_allow_html=True)
    st.markdown(_V161_CSS, unsafe_allow_html=True)
    selected_date = _render_day_strip()
    _render_v161_identity()

    captured: dict[str, Mapping[str, Any]] = {}
    original_date_input = prior.st.date_input
    original_selectbox = prior.st.selectbox
    original_expander = prior.st.expander
    original_matchup = prior._matchup_header_html
    original_team_evidence = prior._team_evidence_html
    original_hero = prior._game_total_hero_html
    diagnostic_owner = prior.frozen_page.frozen_v2.frozen_v1.identity_ui
    original_diagnostics = diagnostic_owner._diagnostic_badges

    def date_input_wrapper(*_args, **_kwargs):
        return selected_date

    def matchup_wrapper(identity, away, home, display_game):
        captured["identity"] = identity
        return prior_v160._target_matchup_header_html(identity, away, home, display_game)

    def team_evidence_wrapper(away, home):
        return prior_v160._target_team_evidence_html(captured.get("identity", {}), away, home)

    def hero_wrapper(raw, final, display_game, statuses, ready_count):
        market = _market_for_display_game(display_game)
        enriched = dict(display_game)
        if market.get("verified") is True:
            enriched["market_total"] = market["total"]
        else:
            for key in ("total", "market_total", "total_line", "over_under", "ou"):
                enriched.pop(key, None)
            enriched.pop("odds", None)
            enriched.pop("market", None)
        return original_hero(raw, final, enriched, statuses, ready_count) + _market_proof_html(market)

    prior.st.date_input = date_input_wrapper
    prior.st.selectbox = st.sidebar.selectbox
    prior.st.expander = st.sidebar.expander
    prior._matchup_header_html = matchup_wrapper
    prior._team_evidence_html = team_evidence_wrapper
    prior._game_total_hero_html = hero_wrapper
    diagnostic_owner._diagnostic_badges = lambda _diag: ""
    try:
        result = prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        prior.st.date_input = original_date_input
        prior.st.selectbox = original_selectbox
        prior.st.expander = original_expander
        prior._matchup_header_html = original_matchup
        prior._team_evidence_html = original_team_evidence
        prior._game_total_hero_html = original_hero
        diagnostic_owner._diagnostic_badges = original_diagnostics

    st.markdown(prior_v160._V160_CSS, unsafe_allow_html=True)
    st.markdown(_V161_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V161 Game Total V11 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "DATE_QUERY_KEY",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "ODDS_ENDPOINT",
    "ODDS_MATCH_METHOD",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "V161_REQUIRED_MARKERS",
    "_verified_market_for_game",
    "render_cfb_hub",
    "render_game_total_hub",
]
