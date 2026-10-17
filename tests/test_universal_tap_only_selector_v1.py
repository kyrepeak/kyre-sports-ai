import importlib
from contextlib import contextmanager

import pytest


class _Box:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


class FakeSt:
    def __init__(self, *, clicked=None):
        self.session_state = {}
        self.clicked = set(clicked or [])
        self.popovers = []
        self.buttons = []
        self.captions = []
        self.writes = []

    def popover(self, label, **kwargs):
        self.popovers.append((label, kwargs))
        return _Box()

    def button(self, label, key=None, **kwargs):
        self.buttons.append((label, key, kwargs))
        return key in self.clicked

    def caption(self, text):
        self.captions.append(text)

    def markdown(self, text, **kwargs):
        self.writes.append((text, kwargs))

    def selectbox(self, *args, **kwargs):
        raise AssertionError('native selectbox must not be used for ordinary finite choices')


def _module():
    return importlib.import_module('universal_tap_only_selector_v1')


def test_materialize_generator_exactly_once():
    mod = _module()
    seen = []
    def options():
        for value in ['A', 'B', 'C']:
            seen.append(value)
            yield value
    values = mod._materialize_options(options())
    assert values == ['A', 'B', 'C']
    assert seen == ['A', 'B', 'C']


def test_resolve_selection_supports_unhashable_and_invalid_stored_values():
    mod = _module()
    values = [{'id': 1}, {'id': 2}]
    assert mod._resolve_selection(values, stored={'id': 2}, index=0) == (1, {'id': 2})
    assert mod._resolve_selection(values, stored={'id': 9}, index=0) == (0, {'id': 1})
    assert mod._resolve_selection(values, stored={'id': 9}, index=None) == (None, None)


def test_short_list_renders_tap_only_and_returns_raw_value(monkeypatch):
    mod = _module()
    fake = FakeSt()
    fake.session_state['team'] = {'id': 2, 'name': 'JAX'}
    monkeypatch.setattr(mod, 'st', fake)
    options = [{'id': 1, 'name': 'HOU'}, {'id': 2, 'name': 'JAX'}]
    result = mod._tap_only_selectbox('Team', options, key='team', format_func=lambda x: x['name'])
    assert result is options[1]
    assert fake.popovers[0][0] == 'JAX'
    assert [b[0] for b in fake.buttons] == ['HOU', '✓ JAX']


def test_index_none_uses_placeholder_without_selecting(monkeypatch):
    mod = _module()
    fake = FakeSt()
    monkeypatch.setattr(mod, 'st', fake)
    result = mod._tap_only_selectbox('Player', ['A', 'B'], key='player', index=None, placeholder='Choose player')
    assert result is None
    assert fake.popovers[0][0] == 'Choose player'
    assert 'player' not in fake.session_state


def test_empty_options_return_none_and_render_disabled_trigger(monkeypatch):
    mod = _module()
    fake = FakeSt()
    monkeypatch.setattr(mod, 'st', fake)
    result = mod._tap_only_selectbox('Game', [], key='game', placeholder='No games')
    assert result is None
    label, kwargs = fake.popovers[0]
    assert label == 'No games'
    assert kwargs['disabled'] is True
    assert fake.buttons == []


def test_disabled_selector_cannot_change_state(monkeypatch):
    mod = _module()
    fake = FakeSt(clicked={'team__tap_only__0'})
    fake.session_state['team'] = 'B'
    monkeypatch.setattr(mod, 'st', fake)
    result = mod._tap_only_selectbox('Team', ['A', 'B'], key='team', disabled=True)
    assert result == 'B'
    assert fake.session_state['team'] == 'B'
    assert all(button[2]['disabled'] is True for button in fake.buttons)


def test_duplicate_formatted_labels_keep_position_identity(monkeypatch):
    mod = _module()
    fake = FakeSt()
    values = [('x', 1), ('x', 2)]
    fake.session_state['dup'] = values[1]
    monkeypatch.setattr(mod, 'st', fake)
    result = mod._tap_only_selectbox('Duplicate', values, key='dup', format_func=lambda _: 'Same')
    assert result == values[1]
    assert fake.buttons[0][1] != fake.buttons[1][1]


def test_explicit_key_state_falls_back_to_requested_index(monkeypatch):
    mod = _module()
    fake = FakeSt()
    fake.session_state['market'] = 'stale'
    monkeypatch.setattr(mod, 'st', fake)
    result = mod._tap_only_selectbox('Market', ['ML', 'Spread'], key='market', index=1)
    assert result == 'Spread'
    assert fake.session_state['market'] == 'Spread'


def test_page_for_index_contract():
    mod = _module()
    assert mod.PAGE_SIZE == 20
    assert mod._page_for_index(None, 99) == 0
    assert mod._page_for_index(0, 99) == 0
    assert mod._page_for_index(20, 99) == 1


def test_long_list_renders_only_one_page_and_next_does_not_change_selection(monkeypatch):
    mod = _module()
    values = [f'P{i}' for i in range(41)]
    fake = FakeSt(clicked={'players__tap_only__next'})
    fake.session_state['players'] = 'P0'
    monkeypatch.setattr(mod, 'st', fake)
    result = mod._tap_only_selectbox('Players', values, key='players')
    option_buttons = [b for b in fake.buttons if '__tap_only__option__' in str(b[1])]
    assert len(option_buttons) == 20
    assert result == 'P0'
    assert fake.session_state['players'] == 'P0'
    assert fake.session_state[mod._pagination_key('players')] == 1


def test_long_list_initial_page_contains_current_selection(monkeypatch):
    mod = _module()
    values = [f'P{i}' for i in range(41)]
    fake = FakeSt()
    fake.session_state['players'] = 'P25'
    monkeypatch.setattr(mod, 'st', fake)
    mod._tap_only_selectbox('Players', values, key='players')
    labels = [b[0] for b in fake.buttons if '__tap_only__option__' in str(b[1])]
    assert labels[0] == 'P20'
    assert '✓ P25' in labels
    assert fake.captions[-1] == 'items 21–40 of 41'


def test_41_options_page_boundaries(monkeypatch):
    mod = _module()
    values = [f'P{i}' for i in range(41)]
    fake = FakeSt()
    fake.session_state['players'] = 'P40'
    monkeypatch.setattr(mod, 'st', fake)
    mod._tap_only_selectbox('Players', values, key='players')
    labels = [b[0] for b in fake.buttons if '__tap_only__option__' in str(b[1])]
    assert labels == ['✓ P40']
    assert fake.captions[-1] == 'items 41–41 of 41'


def test_selection_callback_runs_once_and_can_mutate_same_key(monkeypatch):
    mod = _module()
    calls = []
    fake = FakeSt(clicked={'team__tap_only__option__1'})
    fake.session_state['team'] = 'A'
    monkeypatch.setattr(mod, 'st', fake)
    def callback(prefix, *, suffix):
        calls.append((prefix, suffix))
        fake.session_state['team'] = 'CALLBACK'
    mod._tap_only_selectbox('Team', ['A', 'B'], key='team', on_change=callback, args=('x',), kwargs={'suffix': 'y'})
    assert calls == [('x', 'y')]
    assert fake.session_state['team'] == 'CALLBACK'


def test_no_key_selector_identity_is_stable_per_callsite_and_distinct_between_callsites():
    mod = _module()
    frame = object()
    first = mod._selector_identity('Player', None, frame=('page.py', 10))
    again = mod._selector_identity('Player', None, frame=('page.py', 10))
    second = mod._selector_identity('Player', None, frame=('page.py', 11))
    assert first == again
    assert first != second
    assert first.startswith('__tap_only_selectbox__')


def test_pagination_key_is_namespaced():
    mod = _module()
    assert mod._pagination_key('team') == '__tap_only_page__team'
