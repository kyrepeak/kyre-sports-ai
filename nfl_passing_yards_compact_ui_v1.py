"""Pure presentation helpers for the NFL Passing Yards compact dashboard.

This module consumes already-rendered certified HTML fragments only. It never
imports or executes projection, probability, market, identity, or API logic.
"""
from __future__ import annotations

from html import escape
import re
from typing import Mapping, Sequence

COMPACT_DASHBOARD_CSS = r'''
<style>
:root{--kpass-good:#34d399;--kpass-bad:#f87171;--kpass-warn:#fbbf24;--kpass-info:#60a5fa;--kpass-model:#a78bfa;--kpass-muted:#94a3b8;--kpass-line:#273449;--kpass-panel:#0b111c;--kpass-panel2:#0f1724}
.kpass36-shell{margin:8px 0 16px;color:#e5edf7}.kpass36-matchup{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;border:1px solid #334155;background:linear-gradient(135deg,#0d1421,#111827);border-radius:18px;padding:10px 13px;margin:4px 0 11px;box-shadow:0 10px 28px rgba(0,0,0,.18)}
.kpass36-matchlogo{width:38px;height:38px;object-fit:contain;background:#0b1220;border:1px solid #334155;border-radius:11px;padding:4px;box-sizing:border-box}.kpass36-matchcenter{text-align:center;min-width:0}.kpass36-kicker{font-size:.43rem;letter-spacing:.11em;text-transform:uppercase;color:var(--kpass-model);font-weight:950}.kpass36-matchlabel{font-size:.83rem;color:#f8fafc;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.kpass36-matchsub{font-size:.45rem;color:var(--kpass-muted);margin-top:2px}
.kpass36-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-items:start}.kpass36-player{min-width:0;border:1px solid #334155;border-radius:18px;background:linear-gradient(150deg,#0b111c,#0d1522);padding:10px;box-shadow:0 12px 28px rgba(0,0,0,.16)}.kpass36-playerbar{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 1px 8px}.kpass36-playerbar strong{font-size:.52rem;text-transform:uppercase;letter-spacing:.075em;color:#e2e8f0}.kpass36-modelchip{border:1px solid rgba(167,139,250,.55);background:rgba(88,28,135,.22);color:#c4b5fd;border-radius:999px;padding:4px 7px;font-size:.39rem;font-weight:950;white-space:nowrap}
.kpass36-hero .kpass29-card{border:0!important;background:#0f1724!important;padding:9px!important;box-shadow:none!important}.kpass36-hero .kpass29-card:after{display:none!important}.kpass36-hero .kpass29-main,.kpass36-hero .kpass29-foot{display:none!important}.kpass36-hero .kpass29-badge{border-color:#475569!important;background:#111827!important;color:#cbd5e1!important}.kpass36-hero .kpass29-badge.blue{border-color:rgba(96,165,250,.5)!important;background:rgba(30,64,175,.18)!important;color:#93c5fd!important}.kpass36-hero .kpass29-badge.gold{border-color:rgba(251,191,36,.5)!important;background:rgba(120,53,15,.18)!important;color:#fcd34d!important}
.kpass36-quick{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.kpass36-quickblock{min-width:0;border-radius:13px;padding:7px;background:#0a1220}.kpass36-quicklabel{font-size:.38rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;margin:0 0 5px}.kpass36-model{border:1px solid rgba(167,139,250,.45)}.kpass36-model .kpass36-quicklabel{color:var(--kpass-model)}.kpass36-market{border:1px solid rgba(96,165,250,.42)}.kpass36-market .kpass36-quicklabel{color:var(--kpass-info)}
.kpass36-quick .kpy-proj,.kpass36-quick .kpy10-card{border:0!important;background:transparent!important;padding:0!important;margin:0!important;border-radius:0!important}.kpass36-quick .kpy-projtop,.kpass36-quick .kpy10-top{margin-bottom:5px!important}.kpass36-quick .kpy-projsub,.kpass36-quick .kpy10-sub{display:none!important}.kpass36-quick .kpy-projhero,.kpass36-quick .kpy10-hero{margin-bottom:0!important;gap:4px!important}.kpass36-quick .kpy-projhero>div,.kpass36-quick .kpy10-hero>div{padding:6px!important;border-color:#273449!important;background:#0b1320!important}.kpass36-quick .kpy-projhero b,.kpass36-quick .kpy10-hero b{font-size:.82rem!important}.kpass36-quick .kpy-projhero span,.kpass36-quick .kpy10-hero span{font-size:.34rem!important}.kpass36-quick .kpy-projmeta,.kpass36-quick .kpy-projctx,.kpass36-quick .kpy10-note{display:none!important}.kpass36-market .kpy10-metrics{display:grid!important;grid-template-columns:1fr!important;margin-top:5px}.kpass36-market .kpy10-metrics>div{display:none!important}.kpass36-market .kpy10-metrics>div:nth-child(5){display:block!important;border:1px solid #273449!important;background:#0b1320!important;padding:6px!important}.kpass36-market .kpy10-metrics>div:nth-child(5) b{font-size:.65rem!important}
.kpass36-why{margin-top:9px;border-top:1px solid #273449;padding-top:8px}.kpass36-whyhead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}.kpass36-whytitle{font-size:.5rem;text-transform:uppercase;letter-spacing:.07em;color:#dbe5f1;font-weight:950}.kpass36-whysub{font-size:.38rem;color:var(--kpass-muted)}.kpass36-signals{display:flex;gap:5px;flex-wrap:wrap}.kpass36-signal{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:4px 7px;font-size:.39rem;font-weight:900;border:1px solid #334155;background:#111827;color:#cbd5e1}.kpass36-signal:before{content:"";width:5px;height:5px;border-radius:50%;background:var(--kpass-info)}.kpass36-signal.good{border-color:rgba(52,211,153,.38);color:#86efac;background:rgba(6,78,59,.16)}.kpass36-signal.good:before{background:var(--kpass-good)}.kpass36-signal.bad{border-color:rgba(248,113,113,.38);color:#fca5a5;background:rgba(127,29,29,.15)}.kpass36-signal.bad:before{background:var(--kpass-bad)}.kpass36-signal.warn{border-color:rgba(251,191,36,.38);color:#fcd34d;background:rgba(120,53,15,.15)}.kpass36-signal.warn:before{background:var(--kpass-warn)}.kpass36-signal.info{border-color:rgba(96,165,250,.36);color:#93c5fd;background:rgba(30,64,175,.14)}.kpass36-signal.info:before{background:var(--kpass-info)}
.kpass36-evidence{display:grid;gap:5px;margin-top:9px}.kpass36-evidence details{border:1px solid #273449;border-radius:10px;background:#0a111c;overflow:hidden}.kpass36-evidence summary{cursor:pointer;list-style:none;padding:7px 9px;font-size:.43rem;font-weight:950;color:#cbd5e1;letter-spacing:.035em}.kpass36-evidence summary::-webkit-details-marker{display:none}.kpass36-evidence summary:after{content:"+";float:right;color:var(--kpass-muted);font-size:.65rem;line-height:.8}.kpass36-evidence details[open] summary:after{content:"–"}.kpass36-detail{border-top:1px solid #273449;padding:7px}.kpass36-detail .kpass30-profile,.kpass36-detail section.kpy-defense,.kpass36-detail section.kpy-pressure,.kpass36-detail section.kpy-personnel,.kpass36-detail section.kpy-env,.kpass36-detail section.kpy-proj,.kpass36-detail section.kpy8-card,.kpass36-detail section.kpy9-card,.kpass36-detail section.kpy10-card{margin:0!important;width:auto!important;box-sizing:border-box!important}.kpass36-method{font-size:.46rem;line-height:1.55;color:var(--kpass-muted);padding:2px}.kpass36-method b{color:#c4b5fd}
@media(max-width:900px){.kpass36-grid{grid-template-columns:1fr}.kpass36-player{padding:9px}.kpass36-quick{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.kpass36-matchup{grid-template-columns:30px 1fr 30px;gap:7px;padding:8px}.kpass36-matchlogo{width:30px;height:30px}.kpass36-matchlabel{font-size:.69rem}.kpass36-quick{grid-template-columns:1fr}.kpass36-signals{gap:4px}.kpass36-signal{font-size:.36rem;padding:4px 6px}}
</style>
'''

_LOGO_RE = re.compile(r'<img\s+class="kpass29-logo"\s+src="([^"]+)"\s+alt="([^"]+)\s+logo"', re.IGNORECASE)


def _piece(captured: Mapping[str, Sequence[str]], key: str, index: int) -> str:
    rows = list(captured.get(key) or [])
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _tone(fragment: str) -> str:
    """Map existing rendered status language to display tone; calculate nothing."""
    text = str(fragment or "").lower()
    if any(token in text for token in ('class="red', " negative", "tough", "unfavorable")):
        return "bad"
    if any(token in text for token in ('class="green', " favorable", "advantage", ">green<")):
        return "good"
    if any(token in text for token in ("watch", "check", "caution", "uncertain", "withheld", "missing")):
        return "warn"
    return "info"


def _status_word(tone: str) -> str:
    return {"good": "Favorable", "bad": "Negative", "warn": "Caution", "info": "Neutral"}.get(tone, "Neutral")


def _signal(label: str, fragment: str) -> str:
    tone = _tone(fragment)
    return f'<span class="kpass36-signal {tone}" title="{escape(_status_word(tone))}">{escape(label)}</span>'


def _detail(label: str, content: str, key: str) -> str:
    body = content or '<div class="kpass36-method">Certified evidence is unavailable for this selection.</div>'
    return (
        f'<details data-passing-section="{escape(key, quote=True)}">'
        f'<summary>{escape(label)}</summary>'
        f'<div class="kpass36-detail">{body}</div>'
        '</details>'
    )


def _methodology_detail() -> str:
    return _detail(
        "Methodology",
        '<div class="kpass36-method"><b>Display-only compact view.</b> All identity, projection, probability, distribution, edge, EV and market values are rendered by the frozen certified Passing Yards stack and only reorganized here. Sportsbook projection influence remains <b>0.0%</b>; stake sizing remains <b>OFF</b>.</div>',
        "methodology",
    )


def _logo(identity_html: str) -> tuple[str, str]:
    match = _LOGO_RE.search(str(identity_html or ""))
    return (match.group(1), match.group(2)) if match else ("", "")


def _matchup_header(captured: Mapping[str, Sequence[str]], matchup_label: str) -> str:
    identities = list(captured.get("identity") or [])
    left = _logo(identities[0] if identities else "")
    right = _logo(identities[1] if len(identities) > 1 else "")

    def logo_html(item: tuple[str, str]) -> str:
        src, abbr = item
        if not src:
            return '<div class="kpass36-matchlogo"></div>'
        return f'<img class="kpass36-matchlogo" src="{escape(src, quote=True)}" alt="{escape(abbr, quote=True)} logo">'

    label = str(matchup_label or "Verified NFL matchup").strip()
    return (
        '<section class="kpass36-matchup">'
        f'{logo_html(left)}'
        '<div class="kpass36-matchcenter"><div class="kpass36-kicker">NFL • Passing Yards</div>'
        f'<div class="kpass36-matchlabel">{escape(label)}</div>'
        '<div class="kpass36-matchsub">Certified model • compact decision view</div></div>'
        f'{logo_html(right)}'
        '</section>'
    )


def compact_player_card(captured: Mapping[str, Sequence[str]], index: int) -> str:
    identity = _piece(captured, "identity", index) or '<div class="kpass36-method">Verified quarterback identity unavailable.</div>'
    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)
    projection = _piece(captured, "projection", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)
    market = _piece(captured, "market", index)

    why = "".join((
        _signal("Volume", profile or projection),
        _signal("Efficiency", projection or profile),
        _signal("Pressure", pressure),
        _signal("Personnel", personnel),
        _signal("Weather", environment),
    ))
    projection_visible = projection or '<div class="kpass36-method">Monster projection unavailable.</div>'
    market_visible = market or '<div class="kpass36-method">Verified market not entered yet.</div>'
    projection_engine = projection + context

    evidence = "".join((
        _detail("Passing Profile", profile, "passing-profile"),
        _detail("Opponent Defense", defense, "opponent-defense"),
        _detail("Pressure", pressure, "pressure"),
        _detail("Weapons / Injuries", personnel, "weapons-injuries"),
        _detail("Environment", environment, "environment"),
        _detail("Projection Engine", projection_engine, "projection-engine"),
        _detail("Distribution", distribution, "distribution"),
        _detail("Market Math", market, "market-math"),
        _methodology_detail(),
    ))

    return (
        f'<article class="kpass36-player" data-player-card-index="{index}">'
        '<div class="kpass36-playerbar"><strong>Quarterback Decision Card</strong><span class="kpass36-modelchip">MONSTER MODEL • FROZEN</span></div>'
        f'<div class="kpass36-hero">{identity}</div>'
        '<div class="kpass36-quick">'
        f'<section class="kpass36-quickblock kpass36-model"><div class="kpass36-quicklabel">Monster Projection</div>{projection_visible}</section>'
        f'<section class="kpass36-quickblock kpass36-market"><div class="kpass36-quicklabel">Market Read</div>{market_visible}</section>'
        '</div>'
        '<section class="kpass36-why"><div class="kpass36-whyhead"><span class="kpass36-whytitle">Why This Projection</span><span class="kpass36-whysub">quick evidence read</span></div>'
        f'<div class="kpass36-signals">{why}</div></section>'
        f'<div class="kpass36-evidence">{evidence}</div>'
        '</article>'
    )


def compact_dashboard_html(captured: Mapping[str, Sequence[str]], matchup_label: str = "") -> str:
    """Recompose frozen rendered fragments into the approved compact dashboard."""
    return (
        '<div class="kpass36-shell" data-compact-dashboard="passing-yards">'
        f'{_matchup_header(captured, matchup_label)}'
        '<div class="kpass36-grid">'
        f'{compact_player_card(captured, 0)}{compact_player_card(captured, 1)}'
        '</div></div>'
    )


def compact_banner_html() -> str:
    return (
        '<section class="kpass29-build"><div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">👹 Passing Yards • Compact Dashboard</div>'
        '<div class="kpass29-buildsub">Decision-first view up top • certified deep evidence stays one tap away below.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip blue">COMPACT VIEW</span>'
        '<span class="kpass29-buildchip">MODEL FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div></section>'
    )


__all__ = [
    "COMPACT_DASHBOARD_CSS",
    "_tone",
    "compact_banner_html",
    "compact_dashboard_html",
    "compact_player_card",
]
