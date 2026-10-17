from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

from universal_sports_nav_controller_v1 import RouteState

ROOT = Path(__file__).resolve().parents[1]


def _ui():
    assert find_spec('universal_sports_nav_ui_v2') is not None, 'tap-first nav UI v2 must exist'
    return import_module('universal_sports_nav_ui_v2')


def _overlay():
    assert find_spec('streamlit_memory_lazy_router_universal_nav_v2') is not None, 'tap-first overlay v2 must exist'
    return import_module('streamlit_memory_lazy_router_universal_nav_v2')


def test_sport_callback_queues_authoritative_intent_before_rerun(monkeypatch):
    ui = _ui()
    session = {'sport-key': 'nfl'}
    monkeypatch.setattr(ui.st, 'session_state', session)
    ui._queue_sport_intent('sport-key')
    assert session[ui.PENDING_INTENT_KEY] == {'sport_id': 'nfl', 'market_id': None, 'source': 'tap'}


def test_rapid_sport_taps_use_latest_pending_intent(monkeypatch):
    ui = _ui()
    session = {'sport-key': 'nfl'}
    monkeypatch.setattr(ui.st, 'session_state', session)
    ui._queue_sport_intent('sport-key')
    session['sport-key'] = 'wnba'
    ui._queue_sport_intent('sport-key')
    assert session[ui.PENDING_INTENT_KEY]['sport_id'] == 'wnba'


def test_market_callback_queues_exact_current_sport(monkeypatch):
    ui = _ui()
    session = {'market-key': 'moneyline'}
    monkeypatch.setattr(ui.st, 'session_state', session)
    ui._queue_market_intent('market-key', 'nfl')
    assert session[ui.PENDING_INTENT_KEY] == {'sport_id': 'nfl', 'market_id': 'moneyline', 'source': 'tap'}


def test_renderer_builds_market_row_from_canonical_sport_and_uses_callbacks(monkeypatch):
    ui = _ui()
    state = RouteState('nfl', 'spread', 'tap', 12, {'nfl': 'spread', 'mlb': 'slate'})
    calls = []
    class DummyContainer:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(ui.st, 'container', lambda **kwargs: DummyContainer())
    monkeypatch.setattr(ui.st, 'markdown', lambda *args, **kwargs: None)
    def pills(label, options, **kwargs):
        calls.append((label, tuple(options), kwargs.get('on_change'), kwargs.get('args')))
        return kwargs.get('default')
    monkeypatch.setattr(ui.st, 'pills', pills)
    ui.render_universal_nav(state)
    sport_call, market_call = calls
    assert sport_call[0] == 'Sport' and callable(sport_call[2])
    assert market_call[0] == 'Market' and callable(market_call[2])
    assert 'spread' in market_call[1]
    assert 'passing-yards' in market_call[1]
    assert 'home-run' not in market_call[1]


def test_pending_sport_tap_wins_before_parent_and_clears_stale_route_context(monkeypatch):
    overlay = _overlay()
    captured = {}
    session = {
        overlay.PENDING_INTENT_KEY: {'sport_id': 'nfl', 'market_id': None, 'source': 'tap'},
        'ks_universal_sport': 'mlb',
        'ks_universal_market': 'slate',
        'ks_universal_epoch': 4,
        'ks_universal_last_market_by_sport': {'mlb': 'slate', 'nfl': 'spread'},
    }
    query = {
        'sport': 'mlb',
        'market': 'slate',
        'date': '2026-10-17',
        'ks_sport': 'MLB',
        'ks_mlb_market': 'Slate',
        'ks_cfb_game_total_event_id': 'stale-event',
        'ks_cfb_game_total_selector_sync': 'stale-event',
    }
    dummy_st = SimpleNamespace(
        session_state=session,
        query_params=query,
        selectbox=lambda label, options, *args, **kwargs: options[0],
        markdown=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(overlay, 'st', dummy_st)
    monkeypatch.setattr(overlay.nav_ui, 'render_universal_nav', lambda state: captured.setdefault('state', state))
    def parent_render():
        state = overlay.prior._resolve_initial_state(dummy_st.session_state, dummy_st.query_params)
        overlay.prior.nav_ui.render_universal_nav(state)
        return (
            dummy_st.session_state.get('ks_sport_touch'),
            dummy_st.session_state.get('ks_nfl_market_touch'),
            dict(dummy_st.query_params),
        )
    monkeypatch.setattr(overlay.prior, 'render_app', parent_render)
    result = overlay.render_app()
    assert captured['state'].sport_id == 'nfl'
    assert captured['state'].market_id == 'spread'
    assert result[0:2] == ('NFL', 'Spread')
    assert result[2]['sport'] == 'nfl' and result[2]['market'] == 'spread'
    assert 'date' not in result[2]
    assert not any(str(key).startswith('ks_') for key in result[2])
    assert overlay.PENDING_INTENT_KEY not in session


def test_pending_intent_is_one_shot():
    overlay = _overlay()
    session = {overlay.PENDING_INTENT_KEY: {'sport_id': 'nba', 'market_id': 'spread', 'source': 'tap'}}
    intent = overlay._consume_pending_intent(session)
    assert (intent.sport_id, intent.market_id, intent.source) == ('nba', 'spread', 'tap')
    assert overlay._consume_pending_intent(session) is None


def test_callbacks_do_not_force_a_second_manual_rerun():
    source = (ROOT / 'universal_sports_nav_ui_v2.py').read_text(encoding='utf-8')
    assert 'on_change=' in source
    assert 'st.rerun(' not in source


def test_production_entrypoint_boots_tap_first_overlay():
    source = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'from streamlit_memory_lazy_router_universal_nav_v2 import record_bootstrap_import_ms, render_app' in source
