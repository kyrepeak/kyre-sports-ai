from pathlib import Path

import nfl_passing_yards_compact_ui_v1 as ui


def _captured():
    identity = [
        '<article class="kpass29-card"><img class="kpass29-logo" src="ari.png" alt="ARI logo"><div>Kyler Murray</div></article>',
        '<article class="kpass29-card"><img class="kpass29-logo" src="lv.png" alt="LV logo"><div>Geno Smith</div></article>',
    ]
    projection = [
        '<section class="kpy-proj"><div class="kpy-projgrade green">GREEN</div><div class="kpy-projhero"><div><b>252.4</b><span>Baseline Pass Yards</span></div></div><div class="kpy-projmeta">deep model metadata</div></section>',
        '<section class="kpy-proj"><div class="kpy-projgrade watch">WATCH</div><div class="kpy-projhero"><div><b>238.8</b><span>Baseline Pass Yards</span></div></div><div class="kpy-projmeta">deep model metadata</div></section>',
    ]
    market = [
        '<section class="kpy10-card"><div class="kpy10-hero"><div><b>OVER</b><span>Final Lean</span></div><div><b>249.5</b><span>Market Line</span></div><div><b>HIGH</b><span>Model Confidence</span></div></div><div class="kpy10-metrics"><div>x</div><div>x</div><div>x</div><div>x</div><div><b>+6.2 pp / -6.2 pp</b>Model edge Over / Under</div></div></section>',
        '<section class="kpy10-card"><div class="kpy10-hero"><div><b>PASS</b><span>Final Lean</span></div><div><b>241.5</b><span>Market Line</span></div><div><b>MEDIUM</b><span>Model Confidence</span></div></div><div class="kpy10-metrics"><div>x</div><div>x</div><div>x</div><div>x</div><div><b>+1.1 pp / -1.1 pp</b>Model edge Over / Under</div></div></section>',
    ]
    return {
        "identity": identity,
        "profile": ['<section class="green">profile A</section>', '<section class="watch">profile B</section>'],
        "defense": ['<section>defense A</section>', '<section>defense B</section>'],
        "pressure": ['<section class="watch">pressure A</section>', '<section>pressure B</section>'],
        "personnel": ['<section>personnel A</section>', '<section class="red">personnel B</section>'],
        "environment": ['<section>weather neutral</section>'],
        "projection": projection,
        "context": ['<section>context A</section>', '<section>context B</section>'],
        "distribution": ['<section>distribution A</section>', '<section>distribution B</section>'],
        "market": market,
    }


def test_compact_dashboard_keeps_decision_metrics_above_the_fold():
    html = ui.compact_dashboard_html(_captured(), "ARI @ LV • 8:15 PM ET")
    for token in ("Kyler Murray", "Geno Smith", "252.4", "249.5", "OVER", "HIGH", "+6.2 pp"):
        assert token in html
    assert "ari.png" in html and "lv.png" in html
    assert "ARI @ LV • 8:15 PM ET" in html


def test_compact_dashboard_has_five_reason_signals_and_deep_evidence_groups():
    html = ui.compact_dashboard_html(_captured(), "ARI @ LV • 8:15 PM ET")
    for label in ("Volume", "Efficiency", "Pressure", "Personnel", "Weather"):
        assert f">{label}<" in html
    for label in (
        "Passing Profile",
        "Opponent Defense",
        "Pressure",
        "Weapons / Injuries",
        "Environment",
        "Projection Engine",
        "Distribution",
        "Market Math",
        "Methodology",
    ):
        assert f">{label}<" in html


def test_semantic_palette_and_mobile_stack_are_explicit():
    css = ui.COMPACT_DASHBOARD_CSS
    for semantic in ("--kpass-good", "--kpass-bad", "--kpass-warn", "--kpass-info", "--kpass-model", "--kpass-muted"):
        assert semantic in css
    assert "@media(max-width:900px)" in css
    assert ".kpass36-grid{grid-template-columns:1fr}" in css


def test_tone_mapping_uses_existing_rendered_evidence_only():
    assert ui._tone('<div class="green">ready</div>') == "good"
    assert ui._tone('<div class="red">tough</div>') == "bad"
    assert ui._tone('<div class="watch">uncertain</div>') == "warn"
    assert ui._tone('<div>verified context</div>') == "info"


def test_v36_and_v137_are_additive_frozen_wrappers():
    root = Path(__file__).resolve().parents[1]
    hub = (root / "nfl_passing_yards_hub_v36.py").read_text()
    router = (root / "streamlit_memory_lazy_router_v137.py").read_text()
    app = (root / "app.py").read_text()

    assert "import nfl_passing_yards_hub_v35 as prior" in hub
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in hub
    assert "STAKE_SIZING_ENABLED = False" in hub
    assert "prior.render_nfl_passing_yards_hub()" in hub
    assert "import streamlit_memory_lazy_router_v136 as prior" in router
    assert "import streamlit_memory_lazy_router_v128 as passing_route" in router
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v36"' in router
    assert "from streamlit_memory_lazy_router_v137 import record_bootstrap_import_ms, render_app" in app
    assert "STREAMLIT_MAIN_V137_NFL_PASSING_YARDS_COMPACT_DASHBOARD" in app
