"""CFB Over/Under Clean Page V38 — V149 Monster compact dashboard.

Additive presentation-only wrapper over certified Clean Page V37.

V149 changes only presentation:
- cleaner matchup hero using the certified exact ESPN team-ID logo resolver,
- Phoenix, Arizona kickoff time,
- compact Quick Read final output,
- compact Steps 5–10 status rows with full certified explanations preserved
  inside collapsed expanders.

V37/V35 schedule, market, runtime analysis, Steps 1–12 calculations,
uncertainty, qualification, ranking, and frozen projection math are unchanged.
Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from time import perf_counter
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v37 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_performance_profiler_v1 as profiler

MODEL_VERSION = "CFB O/U CLEAN PAGE V38 • V149 MONSTER COMPACT DASHBOARD"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v37"
ACTIVE_LOGO_RESOLVER = "cfb_over_under_logo_resolver_v3"
PHOENIX_TIMEZONE = "America/Phoenix"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = frozen_page.ACTIVE_ANALYSIS_PREWARM

_PHOENIX = ZoneInfo(PHOENIX_TIMEZONE)
_EASTERN = ZoneInfo("America/New_York")

_V38_MARKER = (
    "🟣 CFB O/U • CLEAN PAGE V38 ACTIVE • V149 MONSTER COMPACT DASHBOARD • "
    "PHOENIX TIME • EXACT ESPN-ID LOGOS • QUICK READ • COMPACT STEPS 5-10 • "
    "FULL EVIDENCE IN EXPANDERS • V37/V35 BACKEND PRESERVED • "
    "0.0% SPORTSBOOK PROJECTION INFLUENCE • FROZEN PROJECTION MATH PRESERVED"
)

_CSS_V38 = r"""
<style>
.v149-hero{border:1px solid rgba(139,105,255,.34);border-radius:18px;background:radial-gradient(circle at 88% 0%,rgba(124,58,237,.18),transparent 20rem),linear-gradient(145deg,#07111d,#0a1724 62%,#0b1220);padding:13px;margin:10px 0;overflow:hidden}
.v149-kicker{color:#b7a4ff;font-size:.42rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}
.v149-match{display:grid;grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr);gap:8px;align-items:center;margin-top:8px}
.v149-team{display:grid;grid-template-columns:58px minmax(0,1fr);gap:8px;align-items:center;border:1px solid rgba(148,163,184,.13);border-radius:13px;background:#0a1621;padding:8px;min-width:0}
.v149-team.home{grid-template-columns:minmax(0,1fr) 58px;text-align:right}.v149-team.home .v149-logo{grid-column:2}.v149-team.home .v149-copy{grid-column:1;grid-row:1}
.v149-logo{width:58px;height:58px;border:1px solid rgba(255,255,255,.10);border-radius:12px;background:#0e1b28;display:flex;align-items:center;justify-content:center;overflow:hidden}.v149-logo img{width:50px;height:50px;object-fit:contain}.v149-mono{color:#dce9f3;font-size:.84rem;font-weight:950}
.v149-team b{display:block;color:#f4f8fb;font-size:.88rem;line-height:1.1}.v149-team span{display:block;color:#8195a8;font-size:.36rem;margin-top:4px;line-height:1.4}.v149-at{text-align:center;color:#74899b;font-size:.30rem;font-weight:950}.v149-at strong{display:block;color:#edf5fa;font-size:1rem}
.v149-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:8px;border-top:1px solid rgba(124,157,184,.12)}.v149-context div{padding:7px 8px;border-right:1px solid rgba(124,157,184,.08)}.v149-context div:last-child{border-right:0}.v149-context small{display:block;color:#71879a;font-size:.27rem;font-weight:950;text-transform:uppercase}.v149-context strong{display:block;color:#dce8f0;font-size:.41rem;margin-top:3px;line-height:1.35}
.v149-step-row{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid rgba(126,151,173,.16);border-radius:11px;background:#09151f;padding:8px 10px;margin:6px 0 3px}.v149-step-copy{min-width:0}.v149-step-copy small{display:block;color:#768c9e;font-size:.28rem;font-weight:950}.v149-step-copy b{display:block;color:#edf3f7;font-size:.51rem;margin-top:2px}.v149-step-copy span{display:block;color:#8396a5;font-size:.30rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v149-chip{border-radius:999px;padding:4px 7px;font-size:.29rem;font-weight:950;white-space:nowrap}.v149-chip.ready{background:rgba(43,163,102,.18);border:1px solid rgba(75,220,143,.35);color:#98efbd}.v149-chip.limited{background:rgba(128,92,20,.20);border:1px solid rgba(240,190,71,.34);color:#f3d17b}.v149-chip.gated{background:rgba(118,42,47,.20);border:1px solid rgba(255,101,111,.32);color:#ffabb1}.v149-chip.check{background:rgba(44,89,119,.20);border:1px solid rgba(92,179,236,.29);color:#9bdcff}
.v149-quick{border:1px solid rgba(157,111,255,.36);border-radius:16px;background:linear-gradient(145deg,rgba(74,42,123,.28),#091722);padding:12px;margin-top:10px}.v149-quick small{display:block;color:#b7a4ff;font-size:.32rem;font-weight:950;text-transform:uppercase;letter-spacing:.08em}.v149-quick-main{display:flex;justify-content:space-between;gap:10px;align-items:end;margin-top:5px}.v149-quick h3{margin:0;color:#fbfaff;font-size:1.28rem}.v149-quick strong{color:#d4c5ff;font-size:1.12rem}.v149-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:8px}.v149-metric{border:1px solid rgba(140,158,177,.13);border-radius:9px;background:#0a1620;padding:7px}.v149-metric b{display:block;color:#e9f1f5;font-size:.53rem}.v149-metric span{display:block;color:#748797;font-size:.25rem;text-transform:uppercase;margin-top:2px}.v149-note{color:#8d9cad;font-size:.31rem;line-height:1.45;margin-top:7px}
@media(max-width:760px){.v149-match{grid-template-columns:1fr}.v149-at{min-height:20px}.v149-team,.v149-team.home{grid-template-columns:52px minmax(0,1fr);text-align:left}.v149-team.home .v149-logo{grid-column:1}.v149-team.home .v149-copy{grid-column:2;grid-row:1}.v149-logo{width:52px;height:52px}.v149-logo img{width:45px;height:45px}.v149-context,.v149-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""

_BASE_GLOBALS = frozen_page._RENDER_V37.__globals__
_BASE_PRESENTATION = _BASE_GLOBALS["frozen_page"]
_BASE_ST = _BASE_GLOBALS["st"]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _kickoff_datetime(game: Mapping[str, Any]) -> datetime | None:
    raw = _clean(game.get("kickoff_iso"))
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_EASTERN)
            return parsed.astimezone(_PHOENIX)
        except Exception:
            pass
    day = _clean(game.get("game_date"))
    text = _clean(game.get("kickoff_et"))
    if day and text:
        cleaned = text.replace(" ET", "").replace(" EST", "").replace(" EDT", "").strip()
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                parsed = datetime.strptime(f"{day} {cleaned}", f"%Y-%m-%d {fmt}").replace(tzinfo=_EASTERN)
                return parsed.astimezone(_PHOENIX)
            except Exception:
                pass
    return None


def _kickoff_phoenix(game: Mapping[str, Any]) -> str:
    parsed = _kickoff_datetime(game)
    return "TBD Phoenix" if parsed is None else parsed.strftime("%I:%M %p").lstrip("0") + " Phoenix"


def _monogram(name: str) -> str:
    tokens = [token for token in _clean(name).replace("&", " ").split() if token]
    return "".join(token[0].upper() for token in tokens[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    if url:
        return f'<div class="v149-logo"><img src="{escape(url)}" alt="{escape(name)} logo"></div>'
    return f'<div class="v149-logo"><span class="v149-mono">{escape(_monogram(name))}</span></div>'


def _team_html(side: str, profile: Mapping[str, Any], visual: Mapping[str, Any]) -> str:
    name = _clean(profile.get("team")) or side.title()
    rank = profile.get("ap_rank")
    try:
        rank_text = f"#{int(rank)} AP • " if rank is not None else ""
    except Exception:
        rank_text = ""
    record = _clean(profile.get("record_text")) or "—"
    conference = _clean(profile.get("conference")) or "Conference unavailable"
    copy = f'<div class="v149-copy"><b>{escape(name)}</b><span>{escape(rank_text + record)} • {escape(conference)}</span></div>'
    logo = _logo_html(name, visual)
    cls = "v149-team home" if side == "home" else "v149-team"
    return f'<div class="{cls}">{copy}{logo}</div>' if side == "home" else f'<div class="{cls}">{logo}{copy}</div>'


def _hero(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    try:
        visuals = logo_v3.resolve_visuals(game)
    except Exception:
        visuals = {"away": {}, "home": {}}
    venue = _clean(game.get("venue")) or "Venue unavailable"
    broadcast = _clean(game.get("broadcast")) or "Broadcast unavailable"
    status = _clean(game.get("status")) or "Scheduled"
    site = "Neutral site" if bool(game.get("neutral_site")) else "Home field"
    return f'''
<div class="v149-hero">
 <div class="v149-kicker">MONSTER MATCHUP • EXACT OFFICIAL-ID VISUALS</div>
 <div class="v149-match">
  {_team_html("away", away, visuals.get("away") or {})}
  <div class="v149-at"><strong>@</strong>CFB O/U</div>
  {_team_html("home", home, visuals.get("home") or {})}
 </div>
 <div class="v149-context">
  <div><small>Kickoff</small><strong>{escape(_kickoff_phoenix(game))}</strong></div>
  <div><small>Stadium</small><strong>{escape(venue)}</strong></div>
  <div><small>TV</small><strong>{escape(broadcast)}</strong></div>
  <div><small>Game</small><strong>{escape(status)} • {escape(site)}</strong></div>
 </div>
</div>'''


def _status(engine: Mapping[str, Any]) -> str:
    try:
        return str(_BASE_PRESENTATION._engine_ready(engine) or "CHECK").upper()
    except Exception:
        return "READY" if engine.get("model_ready") is True or engine.get("ready") is True else "CHECK"


def _summary_metrics(engine: Mapping[str, Any]) -> str:
    try:
        rows = list(_BASE_PRESENTATION._interesting(engine, limit=3))
    except Exception:
        rows = []
    return " • ".join(f"{label}: {value}" for label, value in rows) or (_clean(engine.get("reason")) or "Certified evidence available in details")


def _quick_read(result: Mapping[str, Any]) -> str:
    raw = result.get("raw") or {}
    final = result.get("final") or {}
    selection = _clean(final.get("selection") or final.get("pick") or raw.get("model_lean")) or "PASS"
    probability = final.get("selection_probability")
    if probability is None:
        probability = raw.get("under_probability") if selection.upper() == "UNDER" else raw.get("over_probability")
    return f'''
<div class="v149-quick">
 <small>Quick Read • frozen certified output</small>
 <div class="v149-quick-main"><h3>{escape(selection)}</h3><strong>{escape(_pct(probability))}</strong></div>
 <div class="v149-metrics">
  <div class="v149-metric"><b>{escape(_num(raw.get("projected_total"),1))}</b><span>Monster projection</span></div>
  <div class="v149-metric"><b>{escape(_num(result.get("analysis_line"),1))}</b><span>Analysis line</span></div>
  <div class="v149-metric"><b>{escape(_num(raw.get("structural_total_sigma"),2))}</b><span>Structural sigma</span></div>
 </div>
 <div class="v149-note">Sportsbook total is a comparison threshold only. It contributes 0.0% to the frozen projection.</div>
</div>'''


class _PresentationV38:
    def __init__(self, base: Any) -> None:
        self._base = base

    def __getattr__(self, name: str) -> Any:
        if name == "_CSS":
            return getattr(self._base, "_CSS") + _CSS_V38
        return getattr(self._base, name)

    def _step1(self, game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
        return profiler.timed_call("presentation.step1", _hero, game, away, home)

    def _model_step(self, step: int, title: str, engine: Mapping[str, Any]) -> str:
        if int(step) not in {5, 6, 7, 8, 9, 10}:
            return self._base._model_step(step, title, engine)
        status = _status(engine)
        status_class = status.lower() if status.lower() in {"ready", "limited", "gated", "check"} else "check"
        st.markdown(
            f'<div class="v149-step-row"><div class="v149-step-copy"><small>STEP {int(step)}</small><b>{escape(title)}</b><span>{escape(_summary_metrics(engine))}</span></div><span class="v149-chip {escape(status_class)}">{escape(status)}</span></div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"Step {int(step)} details • {title.title()}", expanded=False):
            st.markdown(self._base._model_step(step, title, engine), unsafe_allow_html=True)
        return ""

    def _final(self, result: Mapping[str, Any]) -> str:
        return _quick_read(result)


class _StreamlitV38Proxy:
    _MARKER_TOKENS = (
        "CFB O/U • CLEAN PAGE V18 ACTIVE",
        "CFB O/U • CLEAN PAGE V30 ACTIVE",
        "CFB O/U • CLEAN PAGE V35 ACTIVE",
        "CFB O/U • CLEAN PAGE V36 ACTIVE",
        "CFB O/U • CLEAN PAGE V37 ACTIVE",
        "READABLE STEP 12 FINAL CERTIFICATION ACTIVE",
    )

    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_ST, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if any(token in text for token in self._MARKER_TOKENS):
            return st.caption(_V38_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)


_PRESENTATION = _PresentationV38(_BASE_PRESENTATION)
_ST_PROXY = _StreamlitV38Proxy()
_RENDER_V38 = clone_tools._clone_function(
    frozen_page._RENDER_V37,
    {
        "frozen_page": _PRESENTATION,
        "st": _ST_PROXY,
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    slot = st.empty()
    started = perf_counter()
    try:
        result = _RENDER_V38(section_header, status_info, team_logo, h)
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {
                "version": profiler.MODEL_VERSION,
                "active_page": MODEL_VERSION,
                "active_runtime_slate": ACTIVE_RUNTIME_SLATE,
                "active_market_adapter": ACTIVE_MARKET_ADAPTER,
                "active_prewarm": ACTIVE_ANALYSIS_PREWARM,
                "active_logo_resolver": ACTIVE_LOGO_RESOLVER,
                "total_ms": trace.total_ms(),
                "stages": trace.aggregate(),
                "projection_weight": 0.0,
                "may_modify_projection": False,
            }
        except Exception:
            pass
        slot.caption(trace.compact_caption(limit=8))
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V38 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM",
    "ACTIVE_LOGO_RESOLVER",
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_PERFORMANCE_PROFILER",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PHOENIX_TIMEZONE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_over_under_hub",
]
