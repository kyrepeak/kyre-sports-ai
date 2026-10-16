from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V87_PATH = ROOT / "nfl_passing_yards_hub_v87.py"
ROUTER_PATH = ROOT / "streamlit_memory_lazy_router_v239.py"


def _load_v87():
    assert V87_PATH.exists(), "V87 placeholder transport repair is not implemented yet"
    spec = importlib.util.spec_from_file_location("nfl_passing_yards_hub_v87_contract", V87_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _selected_body() -> str:
    return """
<section class="ks-py59" data-passing-yards-qb-detail="v59" data-passing-yards-detail-cleanup="v69">
  <article class="ks-py59-player" data-selected-qb-analysis="1">
    <div>QB HERO</div>
  </article>
  <section class="ks-py69-clean-detail" data-passing-yards-clean-detail="market">
    <div data-clean-field="lean"><b>PASS</b></div>
    <div data-clean-field="line"><b>256.5</b></div>
    <div data-clean-field="confidence"><b>MEDIUM</b></div>
    <div data-clean-field="model-probability"><b>53.1% / 46.9%</b></div>
    <div data-clean-field="edge"><b>+3.1 pp / -3.1 pp</b></div>
  </section>
  <section class="ks-py69-clean-detail" data-passing-yards-clean-detail="projection">
    <div data-clean-field="baseline-yards"><b>260.7</b></div>
  </section>
  <section class="ks-py69-clean-detail" data-passing-yards-clean-detail="distribution">
    <div data-clean-field="p10"><b>211</b></div>
    <div data-clean-field="p25"><b>235</b></div>
    <div data-clean-field="p50"><b>261</b></div>
    <div data-clean-field="p75"><b>286</b></div>
    <div data-clean-field="p90"><b>310</b></div>
  </section>
  <section class="ks-py67-deep" data-passing-yards-deep-evidence="v67">ADVANCED</section>
</section>
""".strip()


class _FakePlaceholder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple, dict]] = []
        self.identity = "placeholder"

    def markdown(self, body, *args, **kwargs):
        self.calls.append((body, args, kwargs))
        return "MARKDOWN_RESULT"

    def write(self, value):
        return ("WRITE", value)


def test_v87_exists_as_additive_transport_repair() -> None:
    v87 = _load_v87()
    assert v87.FROZEN_PRIOR == "nfl_passing_yards_hub_v86"
    assert v87.PRESENTATION_ONLY is True
    assert v87.TRANSPORT_ONLY is True
    assert v87.MAY_MODIFY_PROJECTION is False
    assert v87.MAY_MODIFY_CONTEXT_MATH is False
    assert v87.MAY_MODIFY_PROBABILITY is False
    assert v87.MAY_MODIFY_MARKET_MATH is False
    assert v87.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v87.MAY_MODIFY_WIDGET_KEYS is False
    assert v87.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v87.STAKE_SIZING_ENABLED is False


def test_v87_transforms_the_real_placeholder_markdown_seam() -> None:
    v87 = _load_v87()
    placeholder = _FakePlaceholder()
    wrapped = v87._PlaceholderProxy(placeholder, v87._transform_final_body)

    result = wrapped.markdown(_selected_body(), unsafe_allow_html=True)

    assert result == "MARKDOWN_RESULT"
    assert len(placeholder.calls) == 1
    body, args, kwargs = placeholder.calls[0]
    assert args == ()
    assert kwargs == {"unsafe_allow_html": True}
    assert 'data-passing-yards-page2-compact-ux="v86"' in body
    assert 'data-passing-yards-page2-compact-transport="v87"' in body
    assert 'data-passing-yards-page2-quick-read="v86"' in body
    assert 'data-passing-yards-page2-range="v86"' in body
    assert 'class="ks-py86-advanced"' in body
    assert wrapped.identity == "placeholder"
    assert wrapped.write("x") == ("WRITE", "x")


def test_v87_leaves_non_page2_placeholder_markdown_unchanged() -> None:
    v87 = _load_v87()
    placeholder = _FakePlaceholder()
    wrapped = v87._PlaceholderProxy(placeholder, v87._transform_final_body)
    ordinary = "<div>ordinary placeholder</div>"

    wrapped.markdown(ordinary, unsafe_allow_html=True)

    assert placeholder.calls[0][0] == ordinary


def test_v87_empty_bridge_wraps_only_returned_placeholder() -> None:
    v87 = _load_v87()
    placeholder = _FakePlaceholder()
    calls = []

    def empty_delegate(*args, **kwargs):
        calls.append((args, kwargs))
        return placeholder

    bridge = v87._make_empty_bridge(empty_delegate)
    wrapped = bridge("slot", key="value")

    assert calls == [(('slot',), {'key': 'value'})]
    assert isinstance(wrapped, v87._PlaceholderProxy)
    assert wrapped.identity == "placeholder"


def test_v239_advances_passing_yards_only_to_v87() -> None:
    router = ROUTER_PATH.read_text(encoding="utf-8")
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v87"' in router
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v238"' in router
    assert 'FROZEN_DIRECT_PROP_ROUTER = "streamlit_memory_lazy_router_v188"' in router
