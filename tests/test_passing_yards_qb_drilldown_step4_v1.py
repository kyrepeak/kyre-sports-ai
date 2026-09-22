from pathlib import Path
import importlib.util
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
V61 = (ROOT / "nfl_passing_yards_hub_v61.py").read_text()
V60 = (ROOT / "nfl_passing_yards_hub_v60.py").read_text()
V59 = (ROOT / "nfl_passing_yards_hub_v59.py").read_text()
V58 = (ROOT / "nfl_passing_yards_hub_v58.py").read_text()
R212 = (ROOT / "streamlit_memory_lazy_router_v212.py").read_text()
R211 = (ROOT / "streamlit_memory_lazy_router_v211.py").read_text()
APP = (ROOT / "app.py").read_text()


def test_v61_is_additive_over_frozen_v60():
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v60"' in V61
    assert 'import nfl_passing_yards_hub_v60 as prior' in V61
    assert 'DRILLDOWN_STEP = 4' in V61
    assert 'return prior.render_nfl_passing_yards_hub()' in V61


def test_step4_has_durable_card_system_witness_and_targets_current_surfaces():
    assert 'data-passing-yards-step4-card-system="v61"' in V61
    for selector in [
        ".ks-py58-head",
        ".ks-py58-card",
        ".ks-py58-identity",
        ".ks-py58-cta",
        ".ks-py59-head",
        ".ks-py59-player",
        ".ks-py59-identity",
        ".ks-py59-section",
        ".ks-py59-support details",
        '.ks-py59-section[data-qb-analysis-section="market"]',
    ]:
        assert selector in V61


def test_step4_uses_universal_semantic_tokens_only_for_presentation():
    assert "from kyre_universal_semantic_tokens_v2 import build_semantic_tokens_css" in V61
    assert "return build_semantic_tokens_css() + _CARD_CSS" in V61
    for token in [
        "var(--kyre-sem-border-medium)",
        "var(--kyre-sem-radius-card)",
        "var(--kyre-sem-surface-panel-alt)",
        "var(--kyre-sem-shadow-card)",
        "var(--kyre-sem-shadow-glow)",
    ]:
        assert token in V61


def test_step4_responsive_card_stack():
    assert "@media(max-width:900px)" in V61
    assert "@media(max-width:680px)" in V61
    assert ".ks-py58-grid," in V61
    assert ".ks-py59-evidence," in V61
    assert ".ks-py59-support{grid-template-columns:1fr!important}" in V61


def test_step4_guardrails_keep_model_data_math_frozen():
    for token in [
        "PRESENTATION_ONLY = True",
        "DISPLAY_ONLY = True",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_WIDGET_KEYS = False",
        "MAY_MODIFY_DATA = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        "STAKE_SIZING_ENABLED = False",
    ]:
        assert token in V61
    forbidden = [
        "requests.get(",
        "fetch_odds(",
        "calculate_projection(",
        "probability_model(",
        "st.selectbox(",
        "st.button(",
        "st.date_input(",
    ]
    assert not any(token in V61 for token in forbidden)


def test_frozen_step1_step2_step3_visible_contracts_remain_owned_below_v61():
    assert 'data-passing-yards-selection-screen="v58"' in V58
    assert 'data-qb-selection-card' in V58
    assert 'data-passing-yards-qb-detail="v59"' in V59
    assert 'data-qb-analysis-slot' in V59
    assert 'data-passing-yards-step3-header="v60"' in V60
    assert 'data-passing-yards-step3-controls="true"' in V60


def test_router_v212_only_advances_passing_yards_to_v61():
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v211"' in R212
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v61"' in R212
    assert 'return prior.render_app()' in R212


def test_v211_stays_frozen_under_v212():
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v210"' in R211
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v60"' in R211


def test_app_boots_v212_and_preserves_v211_compatibility():
    assert "from streamlit_memory_lazy_router_v212 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen QB Drill-Down Step 3 V211 compatibility" in APP
    assert 'PASSING_YARDS_QB_DRILLDOWN_STEP4_CARDS_RUNTIME = "NFL_PASSING_YARDS_V61_CARDS_2026_09_22"' in APP


def test_v61_emits_card_css_before_frozen_v60(monkeypatch):
    calls = []
    streamlit_stub = types.ModuleType("streamlit")
    def markdown(body, *args, **kwargs):
        calls.append(("markdown", str(body), bool(kwargs.get("unsafe_allow_html"))))
    streamlit_stub.markdown = markdown
    streamlit_stub.success = lambda body, *args, **kwargs: calls.append(("success", str(body), False))
    streamlit_stub.warning = lambda body, *args, **kwargs: calls.append(("warning", str(body), False))
    streamlit_stub.info = lambda body, *args, **kwargs: calls.append(("info", str(body), False))
    streamlit_stub.caption = lambda body, *args, **kwargs: calls.append(("caption", str(body), False))

    prior_stub = types.ModuleType("nfl_passing_yards_hub_v60")
    def prior_render():
        calls.append(("prior", "", False))
    prior_stub.render_nfl_passing_yards_hub = prior_render

    tokens_stub = types.ModuleType("kyre_universal_semantic_tokens_v2")
    tokens_stub.build_semantic_tokens_css = lambda: '<style data-kyre-semantic-tokens="v2"></style>'

    monkeypatch.setitem(sys.modules, "streamlit", streamlit_stub)
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_hub_v60", prior_stub)
    monkeypatch.setitem(sys.modules, "kyre_universal_semantic_tokens_v2", tokens_stub)

    spec = importlib.util.spec_from_file_location(
        "nfl_passing_yards_hub_v61_runtime_probe",
        ROOT / "nfl_passing_yards_hub_v61.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    module.render_nfl_passing_yards_hub()

    assert [call[0] for call in calls] == ["markdown", "prior"]
    assert 'data-passing-yards-step4-card-system="v61"' in calls[0][1]
    assert ".ks-py58-card" in calls[0][1]
    assert ".ks-py59-player" in calls[0][1]
    assert calls[0][2] is True


def test_v61_suppresses_legacy_visible_wrappers_but_preserves_styles(monkeypatch):
    calls = []
    streamlit_stub = types.ModuleType("streamlit")

    def markdown(body, *args, **kwargs):
        calls.append(("markdown", str(body)))
    def success(body, *args, **kwargs):
        calls.append(("success", str(body)))
    def warning(body, *args, **kwargs):
        calls.append(("warning", str(body)))
    def info(body, *args, **kwargs):
        calls.append(("info", str(body)))
    def caption(body, *args, **kwargs):
        calls.append(("caption", str(body)))
    def html(body, *args, **kwargs):
        calls.append(("html", str(body)))

    streamlit_stub.markdown = markdown
    streamlit_stub.success = success
    streamlit_stub.warning = warning
    streamlit_stub.info = info
    streamlit_stub.caption = caption
    streamlit_stub.html = html

    prior_stub = types.ModuleType("nfl_passing_yards_hub_v60")
    def prior_render():
        streamlit_stub.markdown(
            '<style data-legacy-style="true">.x{display:block}</style>'
            '<section class="ks-v44-page">legacy universal page</section>',
            unsafe_allow_html=True,
        )
        streamlit_stub.markdown('<section class="kpy16-match">legacy matchup</section>', unsafe_allow_html=True)
        streamlit_stub.warning("⚠️ STEP 3 PASS DEFENSE CHECK")
        streamlit_stub.caption("🏈 PASSING YARDS CONTROL DECK")
        streamlit_stub.html('<section data-passing-yards-step3-header="v60">Passing Yards</section>')
    prior_stub.render_nfl_passing_yards_hub = prior_render

    tokens_stub = types.ModuleType("kyre_universal_semantic_tokens_v2")
    tokens_stub.build_semantic_tokens_css = lambda: '<style data-kyre-semantic-tokens="v2"></style>'

    monkeypatch.setitem(sys.modules, "streamlit", streamlit_stub)
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_hub_v60", prior_stub)
    monkeypatch.setitem(sys.modules, "kyre_universal_semantic_tokens_v2", tokens_stub)

    spec = importlib.util.spec_from_file_location(
        "nfl_passing_yards_hub_v61_visible_composition_probe",
        ROOT / "nfl_passing_yards_hub_v61.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    module.render_nfl_passing_yards_hub()

    joined = "\n".join(body for _, body in calls)
    assert 'data-passing-yards-step4-card-system="v61"' in joined
    assert 'data-legacy-style="true"' in joined
    assert "legacy universal page" not in joined
    assert "legacy matchup" not in joined
    assert "PASS DEFENSE CHECK" not in joined
    assert "PASSING YARDS CONTROL DECK" in joined
    assert 'data-passing-yards-step3-header="v60"' in joined


def test_v61_visible_composition_guard_is_step4_only():
    assert "st.markdown = styles_only_markdown" in V61
    assert "st.success = filtered_success" in V61
    assert "st.warning = filtered_warning" in V61
    assert "st.info = filtered_info" in V61
    assert "st.caption = filtered_caption" in V61
    assert "finally:" in V61
    assert "st.markdown = original_markdown" in V61
    assert "st.warning = original_warning" in V61


def test_step4_collapses_legacy_native_evidence_before_drilldown():
    for selector in [
        '[data-testid="stDataFrame"]',
        '[data-testid="stTable"]',
        '[data-testid="stMetric"]',
        '[data-testid="stExpander"]',
        'input[aria-label="Sportsbook / source"]',
    ]:
        assert selector in V61
    assert "display:none!important;" in V61
    assert "height:0!important;" in V61
