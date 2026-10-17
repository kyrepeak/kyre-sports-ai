import importlib
from pathlib import Path

import pytest

import universal_tap_only_selector_v1 as selector
from tests.test_universal_tap_only_selector_v1 import FakeSt

ROOT = Path(__file__).resolve().parents[1]


def _overlay():
    return importlib.import_module('streamlit_memory_lazy_router_universal_tap_only_v1')


def test_overlay_wraps_parent_and_restores_selectbox(monkeypatch):
    overlay = _overlay()
    fake = FakeSt()
    native = fake.selectbox
    monkeypatch.setattr(selector, 'st', fake)
    monkeypatch.setattr(overlay, 'selector', selector)
    seen = {}
    def parent_render():
        seen['during'] = fake.selectbox
        return fake.selectbox('NFL Game', ['HOU @ JAX', 'NYJ @ NE'], key='nfl_game')
    monkeypatch.setattr(overlay.prior, 'render_app', parent_render)
    result = overlay.render_app()
    assert result == 'HOU @ JAX'
    assert seen['during'] is not native
    assert fake.selectbox.__func__ is native.__func__


@pytest.mark.parametrize(
    ('sport', 'label', 'options', 'key'),
    [
        ('NFL', 'Matchup', ['HOU @ JAX', 'NYJ @ NE'], 'nfl_matchup'),
        ('CFB', '🏟️ Matchup', ['ASU @ Utah', 'LSU @ Alabama'], 'cfb_matchup'),
        ('NBA', 'Player', ['Booker', 'Durant'], 'nba_player'),
        ('MLB', "TODAY'S MATCHUPS", ['ARI @ LAD', 'NYY @ BOS'], 'mlb_game'),
        ('WNBA', 'Player', ['Wilson', 'Stewart'], 'wnba_player'),
    ],
)
def test_cross_sport_finite_selectors_are_intercepted(monkeypatch, sport, label, options, key):
    overlay = _overlay()
    fake = FakeSt()
    monkeypatch.setattr(selector, 'st', fake)
    monkeypatch.setattr(overlay, 'selector', selector)
    def parent_render():
        return selector.st.selectbox(label, options, key=key)
    monkeypatch.setattr(overlay.prior, 'render_app', parent_render)
    assert overlay.render_app() == options[0]
    assert fake.popovers
    assert [b[0].lstrip('✓ ') for b in fake.buttons] == options


def test_nested_nfl_style_bridge_does_not_recurse_and_restores(monkeypatch):
    overlay = _overlay()
    fake = FakeSt()
    native = fake.selectbox
    monkeypatch.setattr(selector, 'st', fake)
    monkeypatch.setattr(overlay, 'selector', selector)
    calls = []
    def parent_render():
        universal_bridge = fake.selectbox
        def nfl_bridge(label, options, *args, **kwargs):
            if label == '🎯 NFL Market':
                calls.append('nfl-local')
                return options[0]
            return universal_bridge(label, options, *args, **kwargs)
        fake.selectbox = nfl_bridge
        try:
            market = fake.selectbox('🎯 NFL Market', ['Spread', 'Moneyline'], key='market')
            player = fake.selectbox('Player', ['Stroud', 'Lawrence'], key='player')
            return market, player
        finally:
            fake.selectbox = universal_bridge
    monkeypatch.setattr(overlay.prior, 'render_app', parent_render)
    assert overlay.render_app() == ('Spread', 'Stroud')
    assert calls == ['nfl-local']
    assert len(fake.popovers) == 1
    assert fake.selectbox.__func__ is native.__func__


def test_overlay_delegates_bootstrap_timing(monkeypatch):
    overlay = _overlay()
    seen = []
    monkeypatch.setattr(overlay.prior, 'record_bootstrap_import_ms', lambda value: seen.append(value))
    overlay.record_bootstrap_import_ms(12.5)
    assert seen == [12.5]


def test_overlay_has_no_route_or_data_ownership():
    source = (ROOT / 'streamlit_memory_lazy_router_universal_tap_only_v1.py').read_text(encoding='utf-8')
    assert 'query_params' not in source
    assert 'requests.' not in source
    assert 'httpx' not in source
    assert 'MODEL_VERSION = "API2 UNIVERSAL TAP-ONLY SELECTOR V1"' in source
