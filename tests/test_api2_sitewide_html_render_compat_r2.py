from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "streamlit_html_compat_v1.py"


class FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple, dict]] = []

    def markdown(self, body, *args, **kwargs):
        self.calls.append(("markdown", str(body), args, dict(kwargs)))
        return "markdown-result"

    def html(self, body, **kwargs):
        self.calls.append(("html", str(body), (), dict(kwargs)))
        return "html-result"


def _compat():
    if not MODULE.exists():
        pytest.fail("streamlit_html_compat_v1.py is missing")
    spec = importlib.util.spec_from_file_location("streamlit_html_compat_v1_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pure_html_unsafe_markdown_routes_to_dedicated_html_renderer():
    compat = _compat()
    st = FakeStreamlit()
    compat.install_sitewide_html_compat(st)
    result = st.markdown('<article class="card">Visible card</article>', unsafe_allow_html=True)
    assert result == "html-result"
    assert st.calls == [("html", '<article class="card">Visible card</article>', (), {})]


def test_css_routes_to_html_but_script_and_normal_markdown_keep_original_path():
    compat = _compat()
    st = FakeStreamlit()
    compat.install_sitewide_html_compat(st)
    assert st.markdown('<style>.card{display:block}</style>', unsafe_allow_html=True) == "html-result"
    assert st.markdown('<script>window.x=1</script>', unsafe_allow_html=True) == "markdown-result"
    assert st.markdown('**native markdown**') == "markdown-result"
    assert [call[0] for call in st.calls] == ["html", "markdown", "markdown"]


def test_unsupported_markdown_kwargs_fall_back_without_semantic_change():
    compat = _compat()
    st = FakeStreamlit()
    compat.install_sitewide_html_compat(st)
    st.markdown('<div>helped</div>', unsafe_allow_html=True, help='tip')
    assert st.calls[-1][0] == "markdown"
    assert st.calls[-1][3]["help"] == "tip"


def test_install_is_idempotent_and_preserves_width_for_html():
    compat = _compat()
    st = FakeStreamlit()
    compat.install_sitewide_html_compat(st)
    first = st.markdown
    compat.install_sitewide_html_compat(st)
    assert st.markdown is first
    st.markdown('<section>wide</section>', unsafe_allow_html=True, width='stretch')
    assert st.calls[-1] == ("html", '<section>wide</section>', (), {"width": "stretch"})


def test_app_installs_compat_before_any_html_heartbeat_and_before_render_app():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    install = "install_sitewide_html_compat(st)"
    assert install in source
    assert source.index(install) < source.index("st.markdown(")
    assert source.index(install) < source.index("render_app()")


def test_moneyline_and_nba_pra_keep_existing_presentation_contracts():
    moneyline = (ROOT / "nfl_moneyline_hub_v20.py").read_text(encoding="utf-8")
    nba = (ROOT / "nba_pra_page1_v2.py").read_text(encoding="utf-8")
    assert "GAME TIME / VENUE" in moneyline
    assert "VIEW FULL ANALYSIS" in moneyline
    assert "NBA PRA Intelligence" in nba
    assert "ALL UPCOMING PRA PLAYERS" in nba
    assert "unsafe_allow_html=True" in moneyline
    assert "unsafe_allow_html=True" in nba
