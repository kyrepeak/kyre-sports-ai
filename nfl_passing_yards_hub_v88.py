"""NFL Passing Yards V88 — compact fast quarterback picker.

Presentation/performance-only successor to frozen V87. The unselected Passing
Yards route now stops after verified slate + exact quarterback identity and
renders two compact player cards. The expensive projection/context/probability/
market/evidence stack is deferred until an explicit quarterback slot is selected.

Selected-QB analysis remains owned entirely by frozen V87. No football values,
model math, probability, market math, sportsbook/provider behavior, widget
semantics, or stake behavior are modified.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import importlib
from typing import Any, Mapping
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

MODEL_VERSION = "NFL PASSING YARDS V88 • COMPACT FAST QB PICKER"
FROZEN_SELECTED_OWNER = "nfl_passing_yards_hub_v87"
PRESENTATION_ONLY = True
FAST_PICKER_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_QB_SLOT_PARAM = "ks_qb_slot"
_DATE_PARAM = "ks_py_date"
_MATCHUP_PARAM = "ks_py_matchup"
TOP_DATE_KEY = "nfl_passing_yards_v46_slate_date"
V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_MATCHUP_KEY = "nfl_passing_yards_v8_matchup"
VISIBLE_MATCHUP_KEY = "nfl_passing_yards_v42_visible_matchup"
PHOENIX = ZoneInfo("America/Phoenix")

_FAST_CSS = r"""
<style data-passing-yards-fast-picker="v88">
.ks-py88,.ks-py88 *{box-sizing:border-box}
.ks-py88{max-width:1120px;margin:.35rem auto 1rem;color:#edf7ff}
.ks-py88-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px;padding:14px 16px;border:1px solid rgba(78,190,255,.25);border-radius:16px;background:linear-gradient(145deg,#0b1b29,#07131e)}
.ks-py88-kicker{font-size:.62rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase;color:#67d7ff}
.ks-py88-title{margin:.24rem 0 0;font-size:clamp(1.35rem,3vw,1.9rem);font-weight:950;line-height:1.05}
.ks-py88-sub{margin:.34rem 0 0;color:#8fa7b8;font-size:.72rem;line-height:1.45}
.ks-py88-fast{white-space:nowrap;border:1px solid rgba(86,230,177,.35);border-radius:999px;padding:6px 9px;background:rgba(22,118,80,.16);color:#79efbc;font-size:.58rem;font-weight:950}
.ks-py88-controls{margin-bottom:12px;padding:12px;border:1px solid rgba(78,190,255,.18);border-radius:15px;background:#091722}
.ks-py88-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.ks-py88-link{display:block;color:inherit!important;text-decoration:none!important;min-width:0}
.ks-py88-card{display:grid;grid-template-columns:112px minmax(0,1fr) 56px;align-items:center;gap:14px;min-height:150px;padding:14px;border:1px solid rgba(88,201,255,.22);border-radius:18px;background:linear-gradient(150deg,#0b1b29,#07131e);box-shadow:0 12px 30px rgba(0,0,0,.18);overflow:hidden}
.ks-py88-link:focus-visible .ks-py88-card,.ks-py88-link:hover .ks-py88-card{border-color:rgba(87,225,180,.55);transform:translateY(-1px)}
.ks-py88-headshot{display:block;width:112px;height:112px;max-width:112px;max-height:112px;object-fit:cover;object-position:center top;border-radius:18px;border:1px solid rgba(88,201,255,.22);background:#07131e}
.ks-py88-headshot-fallback{width:112px;height:112px;display:grid;place-items:center;border-radius:18px;border:1px solid rgba(88,201,255,.18);background:#07131e;color:#7790a3;font-size:.65rem;font-weight:900}
.ks-py88-copy{min-width:0}
.ks-py88-name{font-size:1.08rem;font-weight:950;line-height:1.08;color:#f7fbff}
.ks-py88-meta{margin-top:5px;color:#91a8b8;font-size:.72rem;line-height:1.4}
.ks-py88-status{display:inline-flex;margin-top:9px;padding:5px 8px;border:1px solid rgba(86,230,177,.3);border-radius:999px;color:#79efbc;background:rgba(22,118,80,.12);font-size:.56rem;font-weight:950}
.ks-py88-cta{margin-top:10px;color:#6fdcff;font-size:.65rem;font-weight:950;letter-spacing:.03em}
.ks-py88-logo{display:block;width:56px;height:56px;max-width:56px;max-height:56px;object-fit:contain;padding:5px;border:1px solid rgba(88,201,255,.15);border-radius:14px;background:#07131e}
.ks-py88-note{margin-top:10px;color:#758d9f;font-size:.62rem;line-height:1.45}
@media(max-width:760px){
  .ks-py88-head{align-items:flex-start;flex-direction:column}
  .ks-py88-grid{grid-template-columns:1fr}
  .ks-py88-card{grid-template-columns:96px minmax(0,1fr) 44px;gap:11px;min-height:124px;padding:11px}
  .ks-py88-headshot,.ks-py88-headshot-fallback{width:96px;height:96px;max-width:96px;max-height:96px;border-radius:16px}
  .ks-py88-logo{width:44px;height:44px;max-width:44px;max-height:44px;padding:4px;border-radius:11px}
  .ks-py88-name{font-size:1rem}.ks-py88-meta{font-size:.68rem}
}
@media(max-width:430px){
  .ks-py88-card{grid-template-columns:84px minmax(0,1fr) 38px;gap:9px}
  .ks-py88-headshot,.ks-py88-headshot-fallback{width:84px;height:84px;max-width:84px;max-height:84px}
  .ks-py88-logo{width:38px;height:38px;max-width:38px;max-height:38px}
}
</style>
"""


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _param(params: Mapping[str, Any], key: str) -> str:
    try:
        raw = params.get(key)
    except Exception:
        return ""
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return _text(raw)


def _selected_qb_slot(params: Mapping[str, Any]) -> int | None:
    raw = _param(params, _QB_SLOT_PARAM)
    if raw not in {"1", "2"}:
        return None
    return int(raw)


def _coerce_day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(_text(value)[:10])
    except Exception:
        return None


def _selected_day(st: Any) -> date:
    query_day = _coerce_day(_param(st.query_params, _DATE_PARAM))
    session_day = _coerce_day(st.session_state.get(TOP_DATE_KEY)) or _coerce_day(st.session_state.get(V8_DATE_KEY))
    chosen = query_day or session_day or datetime.now(PHOENIX).date()

    rolling = importlib.import_module("nfl_passing_yards_hub_v41")
    try:
        resolved = rolling.resolve_next_play_date(chosen)
        if str(resolved.get("state") or "") == "FOUND":
            chosen = _coerce_day(resolved.get("resolved_date")) or chosen
    except Exception:
        pass

    st.session_state[V8_DATE_KEY] = chosen
    return chosen


def _load_verified_slate(day: date):
    base = importlib.import_module("nfl_hub_v1")
    full = importlib.import_module("nfl_passing_yards_full_slate_router_v1")
    return full.load_full_slate(day.isoformat(), primary_loader=base.load_nfl_slate)


def _label(row: Mapping[str, Any]) -> str:
    return (
        f"{_text(row.get('away_team'), 'Away')} @ "
        f"{_text(row.get('home_team'), 'Home')} • "
        f"{_text(row.get('tip_et'), 'TBD')}"
    )


def _headshot_url(ctx: Mapping[str, Any]) -> str:
    qb = dict(ctx.get("qb1") or {})
    athlete_id = _text(qb.get("athlete_id"))
    if not ctx.get("identity_verified") or not athlete_id.isdigit():
        return ""
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png"


def _team_logo_url(ctx: Mapping[str, Any]) -> str:
    abbr = _text(ctx.get("abbr")).upper()
    if not ctx.get("identity_verified") or not abbr or not abbr.isalpha() or len(abbr) > 4:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"


def _player_url(day: date, matchup: str, slot: int) -> str:
    return "?" + urlencode({
        "ks_jump_sport": "NFL",
        "ks_jump_market": "Passing Yards",
        _DATE_PARAM: day.isoformat(),
        _MATCHUP_PARAM: matchup,
        _QB_SLOT_PARAM: str(slot),
    })


def _compact_qb_card_html(ctx: Mapping[str, Any], venue: str, opponent: str, slot: int, href: str) -> str:
    qb = dict(ctx.get("qb1") or {})
    name = _text(qb.get("name"), f"Quarterback {slot}")
    team = _text(ctx.get("team"), _text(ctx.get("abbr"), "NFL"))
    abbr = _text(ctx.get("abbr"), "NFL").upper()
    injury = _text(qb.get("injury_status"), "No listed injury")
    headshot = _headshot_url(ctx)
    logo = _team_logo_url(ctx)
    head_html = (
        f'<img class="ks-py88-headshot" src="{escape(headshot, quote=True)}" alt="{escape(name, quote=True)}" '
        'width="112" height="112" loading="lazy" decoding="async" fetchpriority="low">'
        if headshot else '<div class="ks-py88-headshot-fallback">QB</div>'
    )
    logo_html = (
        f'<img class="ks-py88-logo" src="{escape(logo, quote=True)}" alt="{escape(abbr, quote=True)} logo" '
        'width="56" height="56" loading="lazy" decoding="async" fetchpriority="low">'
        if logo else '<span></span>'
    )
    matchup_text = f"{abbr} {venue} {opponent}" if venue in {"@", "vs"} and opponent else abbr
    verified = "QB ID VERIFIED" if ctx.get("identity_verified") else "QB ID CHECK"
    return (
        f'<a class="ks-py88-link" data-passing-yards-fast-card="{slot}" href="{escape(href, quote=True)}">'
        '<article class="ks-py88-card">'
        + head_html
        + '<div class="ks-py88-copy">'
        + f'<div class="ks-py88-name">{escape(name)}</div>'
        + f'<div class="ks-py88-meta">QB • {escape(matchup_text)} • {escape(team)}</div>'
        + f'<div class="ks-py88-status">{escape(verified)} • {escape(injury)}</div>'
        + '<div class="ks-py88-cta">VIEW PLAYER →</div>'
        + '</div>'
        + logo_html
        + '</article></a>'
    )


def _render_fast_picker(st: Any) -> None:
    st.markdown(_FAST_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="ks-py88" data-passing-yards-fast-picker-shell="v88" data-deep-analysis-deferred="true">'
        '<header class="ks-py88-head"><div><div class="ks-py88-kicker">NFL PLAYER PROPS • PASSING YARDS</div>'
        '<h2 class="ks-py88-title">Choose a quarterback</h2>'
        '<p class="ks-py88-sub">Fast identity-only picker. Projection, probability, market and evidence layers load only after you choose a player.</p>'
        '</div><div class="ks-py88-fast">⚡ FAST PICKER</div></header></section>',
        unsafe_allow_html=True,
    )

    chosen_day = _selected_day(st)
    if TOP_DATE_KEY not in st.session_state:
        st.session_state[TOP_DATE_KEY] = chosen_day

    with st.container():
        st.markdown('<div class="ks-py88-controls">', unsafe_allow_html=True)
        date_col, matchup_col = st.columns([0.82, 2.18], gap="small")
        with date_col:
            day = st.date_input("Slate date", key=TOP_DATE_KEY)
        day = _coerce_day(day) or chosen_day
        if day != chosen_day:
            st.session_state[V8_DATE_KEY] = day
            st.session_state.pop(V8_MATCHUP_KEY, None)
            st.session_state.pop(VISIBLE_MATCHUP_KEY, None)

        games, diag = _load_verified_slate(day)
        if not diag.get("request_ok") or getattr(games, "empty", True):
            st.warning("No verified NFL Passing Yards slate is available for this date.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        rows: dict[str, dict[str, Any]] = {}
        labels: list[str] = []
        for _, row in games.iterrows():
            payload = row.to_dict()
            label = _label(payload)
            labels.append(label)
            rows[label] = payload

        prior_value = _text(st.session_state.get(VISIBLE_MATCHUP_KEY)) or _text(st.session_state.get(V8_MATCHUP_KEY))
        if prior_value not in labels:
            st.session_state.pop(VISIBLE_MATCHUP_KEY, None)
        with matchup_col:
            chosen = st.selectbox(
                f"Matchup • {len(labels)} verified games",
                labels,
                key=VISIBLE_MATCHUP_KEY,
            )
        st.session_state[V8_DATE_KEY] = day
        st.session_state[V8_MATCHUP_KEY] = chosen
        st.markdown('</div>', unsafe_allow_html=True)

    game = rows[chosen]
    identity = importlib.import_module("nfl_passing_yards_identity_v1")
    eligibility = importlib.import_module("nfl_prop_app_eligibility_v1")
    resolved = identity.resolve_matchup_identity(game, int(day.year))
    resolved = eligibility.guard_passing_identity(game, resolved)
    away = dict(resolved.get("away") or {})
    home = dict(resolved.get("home") or {})
    away_abbr = _text(game.get("away_abbr")).upper()
    home_abbr = _text(game.get("home_abbr")).upper()

    cards = (
        _compact_qb_card_html(away, "@", home_abbr, 1, _player_url(day, chosen, 1))
        + _compact_qb_card_html(home, "vs", away_abbr, 2, _player_url(day, chosen, 2))
    )
    st.markdown(
        '<section class="ks-py88"><div class="ks-py88-grid">' + cards + '</div>'
        '<div class="ks-py88-note">⚡ Deep analysis is deferred until a quarterback is selected. Identity remains exact-ID verified and fail-closed.</div></section>',
        unsafe_allow_html=True,
    )


def _render_selected_qb() -> None:
    prior = importlib.import_module(FROZEN_SELECTED_OWNER)
    return prior.render_nfl_passing_yards_hub()


def render_nfl_passing_yards_hub() -> None:
    st = importlib.import_module("streamlit")
    slot = _selected_qb_slot(st.query_params)
    if slot in (1, 2):
        return _render_selected_qb()
    return _render_fast_picker(st)


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V88 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FAST_PICKER_ONLY",
    "FROZEN_SELECTED_OWNER",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_compact_qb_card_html",
    "_selected_qb_slot",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
