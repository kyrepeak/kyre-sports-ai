"""NFL Passing Yards V36 — compact dashboard presentation.

Additive display-only wrapper over production V35 and certified V34 composition.
V36 changes only how already-certified Passing Yards HTML is grouped and styled:
a compact matchup shell, quarterback hero cards, visible projection/market panels,
semantic reason chips, and collapsed deep-evidence sections.

Frozen:
- V35 Market API V2 transport + legacy-caption cleanup;
- V34 capture/composition contracts;
- V33/V28 analytical values and fail-closed rules;
- exact ESPN identity contracts;
- projection/probability/market calculations;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from html import escape
from typing import Any

import nfl_passing_yards_hub_v34 as composition
import nfl_passing_yards_hub_v35 as prior


MODEL_VERSION = "NFL PASSING YARDS V36 • COMPACT DASHBOARD"
FROZEN_PRIOR = "nfl_passing_yards_hub_v35"
FROZEN_COMPOSITION = "nfl_passing_yards_hub_v34"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
DISPLAY_ONLY = True
COMPACT_DASHBOARD_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


_COMPACT_DASHBOARD_CSS = r'''
<style>
:root{
  --k36-green:#4ade80;--k36-red:#fb7185;--k36-amber:#fbbf24;
  --k36-blue:#60a5fa;--k36-purple:#a78bfa;--k36-gray:#94a3b8;
  --k36-panel:#0b1018;--k36-panel2:#111827;--k36-line:#273244;--k36-text:#f8fafc;
}
.kpass36-dashboard{margin:8px 0 16px;color:var(--k36-text)}
.kpass36-matchup{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;margin:0 0 12px;border:1px solid #303a4f;border-radius:18px;background:linear-gradient(135deg,#111827 0%,#0b1020 58%,#17112a 100%);box-shadow:0 12px 34px rgba(0,0,0,.18)}
.kpass36-matchup h3{margin:0;color:#f8fafc;font-size:1rem;font-weight:950;letter-spacing:.01em}.kpass36-matchup p{margin:4px 0 0;color:#94a3b8;font-size:.68rem;line-height:1.45}.kpass36-matchupchips{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.kpass36-kickoff{font-size:.48rem;font-weight:950;letter-spacing:.025em}
.kpass36-prelude{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:4px 0 8px;color:#94a3b8;font-size:.48rem}.kpass36-prelude strong{color:#c4b5fd;letter-spacing:.055em;text-transform:uppercase}.kpass36-preludechips{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.kpass36-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start}
.kpass36-hero{min-width:0;overflow:hidden;border:1px solid #2c3649;border-radius:20px;background:linear-gradient(155deg,#0d1420 0%,#090e16 62%,#120e1b 100%);box-shadow:0 14px 34px rgba(0,0,0,.18)}
.kpass36-herotop{padding:12px 12px 10px;border-bottom:1px solid #222c3c;background:rgba(15,23,42,.58)}
.kpass36-herolabel{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 1px 8px}.kpass36-herolabel strong{font-size:.58rem;letter-spacing:.08em;text-transform:uppercase;color:#c4b5fd}.kpass36-herochips{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.kpass36-chip,.kpass36-reason{display:inline-flex;align-items:center;gap:5px;border:1px solid #334155;border-radius:999px;background:#111827;padding:4px 7px;color:#cbd5e1;font-size:.43rem;font-weight:900;letter-spacing:.035em;white-space:nowrap}
.kpass36-tone-green{border-color:rgba(74,222,128,.48)!important;background:rgba(22,101,52,.18)!important;color:#86efac!important}.kpass36-tone-red{border-color:rgba(251,113,133,.48)!important;background:rgba(159,18,57,.16)!important;color:#fda4af!important}.kpass36-tone-amber{border-color:rgba(251,191,36,.48)!important;background:rgba(146,64,14,.16)!important;color:#fde68a!important}.kpass36-tone-blue{border-color:rgba(96,165,250,.48)!important;background:rgba(30,64,175,.16)!important;color:#bfdbfe!important}.kpass36-tone-purple{border-color:rgba(167,139,250,.52)!important;background:rgba(91,33,182,.18)!important;color:#ddd6fe!important}.kpass36-tone-gray{border-color:#475569!important;background:#111827!important;color:#cbd5e1!important}
.kpass36-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px 12px 4px}.kpass36-metric{min-width:0;border:1px solid #2a3447;border-radius:14px;background:#0b111b;padding:8px}.kpass36-metrichead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 1px 6px}.kpass36-metrichead b{font-size:.52rem;letter-spacing:.05em;text-transform:uppercase}.kpass36-projection{border-color:rgba(167,139,250,.36)}.kpass36-projection .kpass36-metrichead b{color:#c4b5fd}.kpass36-market{border-color:rgba(96,165,250,.34)}.kpass36-market .kpass36-metrichead b{color:#93c5fd}
.kpass36-why{margin:8px 12px 10px;padding:10px;border:1px solid #293446;border-radius:14px;background:#0b1119}.kpass36-whytitle{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}.kpass36-whytitle b{color:#f8fafc;font-size:.62rem}.kpass36-whytitle span{color:#64748b;font-size:.42rem}.kpass36-reasons{display:flex;gap:6px;flex-wrap:wrap}.kpass36-reason{font-size:.42rem;padding:4px 7px}
.kpass36-evidence{padding:0 12px 12px}.kpass36-evidence>details{margin-top:7px;border:1px solid #273244;border-radius:12px;background:#0a1018;overflow:hidden}.kpass36-evidence>details[open]{border-color:#3a465c}.kpass36-evidence summary{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 10px;color:#cbd5e1;font-size:.5rem;font-weight:900;letter-spacing:.025em}.kpass36-evidence summary::-webkit-details-marker{display:none}.kpass36-evidence summary:after{content:'＋';color:#64748b;font-size:.72rem}.kpass36-evidence details[open] summary:after{content:'−';color:#c4b5fd}.kpass36-evidencebody{padding:0 8px 9px;border-top:1px solid #202938}.kpass36-evidencehint{color:#64748b;font-size:.4rem;font-weight:800}
.kpass36-missing{border:1px dashed #475569;border-radius:10px;background:#0b1118;padding:9px;color:#94a3b8;font-size:.46rem;line-height:1.45}
/* Neutralize V34's blanket green framing while preserving semantic colors inside certified cards. */
.kpass36-hero .kpass29-card,.kpass36-hero .kpass30-profile,.kpass36-hero section.kpy-defense,.kpass36-hero section.kpy-pressure,.kpass36-hero section.kpy-personnel,.kpass36-hero section.kpy-env,.kpass36-hero section.kpy-proj,.kpass36-hero section.kpy8-card,.kpass36-hero section.kpy9-card,.kpass36-hero section.kpy10-card{margin:0!important;width:auto!important;box-sizing:border-box!important;border-radius:12px!important;border-color:#334155!important;box-shadow:none!important}
.kpass36-projection section.kpy-proj{border-color:rgba(167,139,250,.55)!important}.kpass36-market section.kpy10-card{border-color:rgba(96,165,250,.52)!important}.kpass36-evidence section.kpy-pressure{border-color:rgba(251,191,36,.42)!important}.kpass36-evidence section.kpy-env{border-color:rgba(96,165,250,.38)!important}.kpass36-evidence .kpass30-profile{border-color:rgba(96,165,250,.38)!important}.kpass36-evidence section.kpy-personnel{border-color:#475569!important}
.kpass36-hero .kpy-envteams{grid-template-columns:1fr!important}.kpass36-hero .kpy9-q{grid-template-columns:repeat(3,minmax(0,1fr))!important}
@media(max-width:900px){.kpass36-grid{grid-template-columns:1fr}.kpass36-matchup{align-items:flex-start;flex-direction:column}.kpass36-matchupchips{justify-content:flex-start}.kpass36-prelude{align-items:flex-start;flex-direction:column}.kpass36-preludechips{justify-content:flex-start}.kpass36-hero{border-radius:17px}}
@media(max-width:640px){.kpass36-metrics{grid-template-columns:1fr}.kpass36-herotop,.kpass36-metrics,.kpass36-evidence{padding-left:9px;padding-right:9px}.kpass36-why{margin-left:9px;margin-right:9px}.kpass36-chip,.kpass36-reason{white-space:normal}.kpass36-hero .kpy9-q{grid-template-columns:1fr 1fr!important}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _dashboard_banner_v36() -> str:
    return (
        '<div class="kpass36-prelude">'
        '<strong>🏈 NFL Passing Yards • Compact Dashboard</strong>'
        '<div class="kpass36-preludechips">'
        '<span class="kpass36-chip kpass36-tone-purple">MONSTER MODEL</span>'
        '<span class="kpass36-chip kpass36-tone-blue">MARKET CONTEXT</span>'
        '<span class="kpass36-chip kpass36-tone-gray">V33 + V28 FROZEN</span>'
        '</div></div>'
    )


def _matchup_header(matchup: dict[str, str]) -> str:
    away = _safe(matchup.get("away_team"), "Away")
    home = _safe(matchup.get("home_team"), "Home")
    tip_et = _safe(matchup.get("tip_et"))
    venue = _safe(matchup.get("venue"))
    kickoff = f"Verified kickoff • {tip_et}" if tip_et else "Kickoff • TBD"
    context = " • ".join(value for value in (venue, "Verified ESPN matchup") if value)
    return (
        '<section class="kpass36-matchup" data-verified-matchup="true">'
        '<div>'
        f'<h3>{escape(away)} @ {escape(home)}</h3>'
        f'<p>{escape(context)}</p>'
        '</div>'
        '<div class="kpass36-matchupchips">'
        f'<span class="kpass36-chip kpass36-tone-blue kpass36-kickoff">🕒 {escape(kickoff)}</span>'
        '<span class="kpass36-chip kpass36-tone-purple">PASSING YARDS</span>'
        '</div></section>'
    )


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _fallback(label: str) -> str:
    return f'<div class="kpass36-missing">{escape(label)} is unavailable for this verified matchup.</div>'


def _evidence(label: str, hint: str, content: str, tone: str = "gray") -> str:
    body = content or _fallback(label)
    return (
        '<details class="kpass36-deep">'
        f'<summary><span>{escape(label)}</span><span class="kpass36-evidencehint kpass36-tone-{escape(tone)}">{escape(hint)}</span></summary>'
        f'<div class="kpass36-evidencebody">{body}</div>'
        '</details>'
    )


def _compact_player(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index) or _fallback("Quarterback identity")
    projection = _piece(captured, "projection", index) or _fallback("Monster projection")
    market = _piece(captured, "market", index) or _fallback("Market + edge")

    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)

    return "".join(
        [
            f'<article class="kpass36-hero" data-player-card-index="{index}" data-compact-dashboard="true">',
            '<div class="kpass36-herotop">',
            '<div class="kpass36-herolabel"><strong>Quarterback Hero</strong><div class="kpass36-herochips">',
            '<span class="kpass36-chip kpass36-tone-purple">MODEL</span>',
            '<span class="kpass36-chip kpass36-tone-blue">MARKET</span>',
            '</div></div>',
            identity,
            '</div>',
            '<div class="kpass36-metrics">',
            '<section class="kpass36-metric kpass36-projection"><div class="kpass36-metrichead"><b>Monster Projection</b><span class="kpass36-chip kpass36-tone-purple">MODEL</span></div>',
            projection,
            '</section>',
            '<section class="kpass36-metric kpass36-market"><div class="kpass36-metrichead"><b>Market + Edge</b><span class="kpass36-chip kpass36-tone-blue">MARKET CONTEXT</span></div>',
            market,
            '</section>',
            '</div>',
            '<section class="kpass36-why">',
            '<div class="kpass36-whytitle"><b>Why This Projection</b><span>scan first • open evidence when needed</span></div>',
            '<div class="kpass36-reasons">',
            '<span class="kpass36-reason kpass36-tone-blue">Volume</span>',
            '<span class="kpass36-reason kpass36-tone-green">Efficiency</span>',
            '<span class="kpass36-reason kpass36-tone-amber">Pressure</span>',
            '<span class="kpass36-reason kpass36-tone-gray">Personnel</span>',
            '<span class="kpass36-reason kpass36-tone-blue">Weather</span>',
            '</div></section>',
            '<section class="kpass36-evidence">',
            '<div class="kpass36-herolabel"><strong>Deep Evidence</strong><span class="kpass36-chip kpass36-tone-gray">COLLAPSED BY DEFAULT</span></div>',
            _evidence("Volume + Efficiency", "QB PROFILE", profile, "blue"),
            _evidence("Opponent Pass Defense", "MATCHUP", defense, "red"),
            _evidence("Pressure", "PROTECTION", pressure, "amber"),
            _evidence("Personnel", "WEAPONS + INJURIES", personnel, "gray"),
            _evidence("Weather + Game Environment", "CONTEXT", environment, "blue"),
            _evidence("Context + Uncertainty", "RANGE", context, "gray"),
            _evidence("Distribution + Probability", "PROBABILITY", distribution, "purple"),
            '</section>',
            '</article>',
        ]
    )


def _compact_dashboard_html(captured: dict[str, list[str]], matchup: dict[str, str] | None = None) -> str:
    matchup = matchup or {}
    return (
        '<section class="kpass36-dashboard">'
        + _matchup_header(matchup)
        + '<div class="kpass36-grid">'
        + _compact_player(captured, 0)
        + _compact_player(captured, 1)
        + '</div></section>'
    )


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V35 while swapping only V34 presentation factories."""
    original_css = composition._PLAYER_CARD_CSS
    original_banner = composition._visual_build_banner_v34
    original_combined = composition._combined_player_cards_html
    identity_module = composition.identity_visual_ui.step7_ui.identity
    original_identity_resolver = identity_module.resolve_matchup_identity
    matchup: dict[str, str] = {}

    def capture_verified_matchup(game: Any, *args: Any, **kwargs: Any):
        if isinstance(game, dict):
            matchup.clear()
            matchup.update(
                {
                    "away_team": _safe(game.get("away_team")),
                    "home_team": _safe(game.get("home_team")),
                    "tip_et": _safe(game.get("tip_et")),
                    "venue": _safe(game.get("venue")),
                }
            )
        return original_identity_resolver(game, *args, **kwargs)

    def compact_with_matchup(captured: dict[str, list[str]]) -> str:
        return _compact_dashboard_html(captured, matchup)

    composition._PLAYER_CARD_CSS = _COMPACT_DASHBOARD_CSS
    composition._visual_build_banner_v34 = _dashboard_banner_v36
    composition._combined_player_cards_html = compact_with_matchup
    identity_module.resolve_matchup_identity = capture_verified_matchup
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        identity_module.resolve_matchup_identity = original_identity_resolver
        composition._PLAYER_CARD_CSS = original_css
        composition._visual_build_banner_v34 = original_banner
        composition._combined_player_cards_html = original_combined


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V36 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "COMPACT_DASHBOARD_ONLY",
    "DISPLAY_ONLY",
    "FROZEN_COMPOSITION",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_COMPACT_DASHBOARD_CSS",
    "_compact_dashboard_html",
    "_compact_player",
    "_dashboard_banner_v36",
    "_matchup_header",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]