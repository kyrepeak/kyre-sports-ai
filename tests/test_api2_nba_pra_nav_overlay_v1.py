import importlib


def test_overlay_adds_only_nba_pra_and_is_idempotent():
    registry = importlib.import_module('universal_sports_nav_registry_v1')
    overlay = importlib.import_module('nba_pra_nav_overlay_v1')
    before = {s.id: tuple(m.id for m in s.markets) for s in registry.SPORTS}
    overlay.activate()
    after = {s.id: tuple(m.id for m in s.markets) for s in registry.SPORTS}
    assert after['nba'] == before['nba'] + ('pra',)
    assert registry.get_market('nba', 'pra').page_params == ('date','game_id','player_id')
    for sport_id in before:
        if sport_id != 'nba': assert after[sport_id] == before[sport_id]
    overlay.activate()
    assert tuple(m.id for m in registry.get_sport('nba').markets).count('pra') == 1
