from pathlib import Path

import universal_tap_only_selector_v1 as selector
from tests.test_universal_tap_only_selector_v1 import FakeSt

ROOT = Path(__file__).resolve().parents[1]


def test_ordinary_selector_surface_has_no_editable_input_path(monkeypatch):
    fake = FakeSt()
    monkeypatch.setattr(selector, 'st', fake)
    native = fake.selectbox
    with selector.install_universal_tap_only_selectboxes():
        value = fake.selectbox('Player', ['A', 'B'], key='player')
    assert value == 'A'
    assert fake.popovers
    assert fake.buttons
    assert fake.selectbox.__func__ is native.__func__
    source = (ROOT / 'universal_tap_only_selector_v1.py').read_text(encoding='utf-8')
    assert 'st.text_input(' not in source
    assert 'st.text_area(' not in source
    assert 'st.rerun(' not in source


def test_intentional_new_option_typing_delegates_to_native(monkeypatch):
    calls = []
    class TypingSt(FakeSt):
        def selectbox(self, *args, **kwargs):
            calls.append((args, kwargs))
            return 'typed-native'
    fake = TypingSt()
    monkeypatch.setattr(selector, 'st', fake)
    with selector.install_universal_tap_only_selectboxes():
        result = fake.selectbox('Custom', ['A'], accept_new_options=True, key='custom')
    assert result == 'typed-native'
    assert len(calls) == 1
    assert fake.popovers == []


def test_production_entrypoint_uses_universal_nav_v2_with_tap_only_context():
    app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
    nav_source = (ROOT / 'streamlit_memory_lazy_router_universal_nav_v2.py').read_text(encoding='utf-8')
    assert 'from streamlit_memory_lazy_router_universal_nav_v2 import record_bootstrap_import_ms, render_app' in app_source
    assert 'tap_selector.install_universal_tap_only_selectboxes()' in nav_source
