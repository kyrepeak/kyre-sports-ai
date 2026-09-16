from __future__ import annotations

import nfl_passing_yards_hub_v36 as compact


def _identity(name: str, team: str, opponent: str, venue: str, logo: str, headshot: str) -> str:
    return (
        '<article class="kpass29-card">'
        '<div class="kpass29-top">'
        f'<div class="kpass29-head"><img src="{headshot}" alt="{name} headshot"></div>'
        '<div class="kpass29-ident">'
        f'<div class="kpass29-name">{name}</div>'
        f'<div class="kpass29-meta">QB • {team} {venue} {opponent} • {team} Team</div>'
        '</div>'
        f'<img class="kpass29-logo" src="{logo}" alt="{team} logo">'
        '</div></article>'
    )


def _projection(name: str, projection: str, attempts: str, ypa: str) -> str:
    return (
        '<section class="kpy-proj">'
        f'<div class="kpy-projname">{name} • Baseline Projection</div>'
        '<div class="kpy-projhero">'
        f'<div><b>{projection}</b><span>Baseline Pass Yards</span></div>'
        f'<div><b>{attempts}</b><span>Expected Attempts</span></div>'
        f'<div><b>{ypa}</b><span>Expected YPA</span></div>'
        '</div>'
        '<div class="kpy-projmeta">'
        '<div><b>100%</b>Attempt-source coverage</div>'
        '<div><b>100%</b>Efficiency-source coverage</div>'
        '<div><b>READY</b>Pressure context • not numerically adjusted</div>'
        '<div><b>WATCH</b>Personnel context • not numerically adjusted</div>'
        '</div>'
        '<div class="kpy-projctx">Environment: <b>READY</b> • weather: <b>CLEAR</b></div>'
        '</section>'
    )


def _market(name: str, lean: str, line: str, confidence: str, edge: str, grade: str) -> str:
    return (
        '<section class="kpy10-card">'
        f'<div class="kpy10-name">{name} • Market Evaluation</div>'
        f'<div class="kpy10-grade {grade.lower()}">{grade} • VALUE</div>'
        '<div class="kpy10-hero">'
        f'<div><b>{lean}</b><span>Final Lean</span></div>'
        f'<div><b>{line}</b><span>Market Line</span></div>'
        f'<div><b>{confidence}</b><span>Model Confidence</span></div>'
        '</div>'
        '<div class="kpy10-metrics">'
        f'<div><b>{edge}</b>Model edge Over / Under</div>'
        '</div></section>'
    )


def _captured() -> dict[str, list[str]]:
    names = ("Away QB", "Home QB")
    return {
        "identity": [
            _identity(names[0], "AWY", "HME", "@", "https://img/awy.png", "https://img/away-qb.png"),
            _identity(names[1], "HME", "AWY", "vs", "https://img/hme.png", "https://img/home-qb.png"),
        ],
        "profile": [f'<section class="kpass30-profile">{name} passing profile evidence</section>' for name in names],
        "defense": [f'<section class="kpy-defense">{name} opponent defense evidence</section>' for name in names],
        "pressure": [f'<section class="kpy-pressure">{name} pressure evidence</section>' for name in names],
        "personnel": [f'<section class="kpy-personnel">{name} weapons and injury evidence</section>' for name in names],
        "environment": ['<section class="kpy-env">Weather CLEAR • wind 4 mph</section>'],
        "projection": [
            _projection(names[0], "271.4", "36.2", "7.50"),
            _projection(names[1], "248.8", "33.1", "7.52"),
        ],
        "context": [f'<section class="kpy8-card">{name} context and uncertainty</section>' for name in names],
        "distribution": [f'<section class="kpy9-card">{name} distribution evidence</section>' for name in names],
        "market": [
            _market(names[0], "OVER", "245.5", "HIGH", "+6.2 pp / -6.2 pp", "A"),
            _market(names[1], "PASS", "249.5", "MEDIUM", "+0.8 pp / -0.8 pp", "PASS"),
        ],
    }


def test_v36_is_display_only_and_keeps_sportsbook_influence_zero() -> None:
    assert compact.DISPLAY_ONLY is True
    assert compact.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert compact.FROZEN_PRIOR == "nfl_passing_yards_hub_v35"
    assert compact.FROZEN_PASSING_ENGINE == "nfl_passing_yards_hub_v28"


def test_compact_dashboard_surfaces_certified_hero_metrics_without_recomputing() -> None:
    html = compact._compact_dashboard_html(_captured(), matchup_label="AWY @ HME • 8:15 PM ET")

    assert 'data-passing-dashboard="compact-v36"' in html
    assert html.count('class="kpass36-player"') == 2
    assert "Away QB" in html and "Home QB" in html
    assert "271.4" in html and "248.8" in html
    assert "245.5" in html and "249.5" in html
    assert "+6.2 pp / -6.2 pp" in html
    assert "OVER" in html
    assert "HIGH" in html
    assert "Why This Projection" in html


def test_compact_dashboard_keeps_all_deep_evidence_collapsible() -> None:
    html = compact._compact_dashboard_html(_captured(), matchup_label="AWY @ HME • 8:15 PM ET")

    for label in (
        "Passing Profile",
        "Opponent Defense",
        "Pressure",
        "Weapons/Injuries",
        "Environment",
        "Projection Engine",
        "Distribution",
        "Market Math",
        "Methodology",
    ):
        assert f">{label}</summary>" in html

    assert html.count("<details") >= 18
    assert "sportsbook projection influence remains 0.0%" in html.lower()


def test_compact_css_is_mobile_first_and_not_green_border_everywhere() -> None:
    css = compact._COMPACT_DASHBOARD_CSS
    assert "@media(max-width:860px)" in css
    assert ".kpass36-grid{grid-template-columns:1fr}" in css
    assert "--monster:#a78bfa" in css
    assert "--info:#60a5fa" in css
    assert "--good:#4ade80" in css
    assert "--bad:#fb7185" in css
    assert "--warn:#fbbf24" in css
