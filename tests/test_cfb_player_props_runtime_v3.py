from types import SimpleNamespace


def test_runtime_routes_exclusively_by_canonical_selection(monkeypatch):
    import cfb_player_props_runtime_v3 as runtime
    calls=[]
    monkeypatch.setattr(runtime, 'st', SimpleNamespace(session_state={}, query_params={}))
    monkeypatch.setattr(runtime.page1, 'render_cfb_player_props_page1', lambda: calls.append('p1'))
    monkeypatch.setattr(runtime.page2, 'render_cfb_player_props_page2', lambda: calls.append('p2'))
    monkeypatch.setattr(runtime.page3, 'render_cfb_player_props_page3', lambda: calls.append('p3'))

    runtime.render_cfb_player_props_runtime(); assert calls==['p1']
    calls.clear(); runtime.st.session_state={'game_id':'g1'}; runtime.render_cfb_player_props_runtime(); assert calls==['p2']
    calls.clear(); runtime.st.session_state={'game_id':'g1','player_id':'p1'}; runtime.render_cfb_player_props_runtime(); assert calls==['p2']
    calls.clear(); runtime.st.session_state={'game_id':'g1','player_id':'p1','prop':'passing_yards'}; runtime.render_cfb_player_props_runtime(); assert calls==['p3']


def test_runtime_query_identity_can_complete_page3(monkeypatch):
    import cfb_player_props_runtime_v3 as runtime
    calls=[]
    monkeypatch.setattr(runtime, 'st', SimpleNamespace(session_state={'game_id':'g1'}, query_params={'player_id':'p1','prop':'rushing_yards'}))
    monkeypatch.setattr(runtime.page1, 'render_cfb_player_props_page1', lambda: calls.append('p1'))
    monkeypatch.setattr(runtime.page2, 'render_cfb_player_props_page2', lambda: calls.append('p2'))
    monkeypatch.setattr(runtime.page3, 'render_cfb_player_props_page3', lambda: calls.append('p3'))
    runtime.render_cfb_player_props_runtime()
    assert calls==['p3']
