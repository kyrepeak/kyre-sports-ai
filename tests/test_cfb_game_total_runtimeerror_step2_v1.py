from datetime import date
from pathlib import Path

import cfb_game_total_clean_page_v44 as subject

ROOT = Path(__file__).resolve().parents[1]
V42 = ROOT / "cfb_game_total_clean_page_v42.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def test_date_change_uses_pinned_selected_day_snapshot_without_runtimeerror(monkeypatch):
    """A stale downstream date must not crash after the user selects a new day."""
    selected_day = date(2026, 10, 17)
    stale_downstream_day = date(2026, 10, 10)
    snapshot = [
        {
            "event_id": "step2-game-1",
            "away_team": "Away",
            "home_team": "Home",
        }
    ]
    original_calls = []
    downstream_results = []

    def original_loader(requested_day):
        original_calls.append(requested_day)
        return [dict(game) for game in snapshot]

    def downstream_render(*_args, **_kwargs):
        downstream_results.extend(
            subject.snapshot_owner.games_owner._load_games(stale_downstream_day)
        )
        return "rendered"

    monkeypatch.setattr(subject.snapshot_owner.prior, "_selected_day", lambda: selected_day)
    monkeypatch.setattr(subject.snapshot_owner.games_owner, "_load_games", original_loader)
    monkeypatch.setattr(
        subject.snapshot_owner.prior,
        "render_game_total_hub",
        downstream_render,
    )

    original_v42_render = subject.snapshot_owner.render_game_total_hub
    result = subject.render_game_total_hub()

    assert result == "rendered"
    assert original_calls == [selected_day]
    assert downstream_results == snapshot
    assert subject.snapshot_owner.games_owner._load_games is original_loader
    assert subject.snapshot_owner.render_game_total_hub is original_v42_render


def test_step2_successor_preserves_frozen_v42_and_does_not_expand_scope():
    source = Path(subject.__file__).read_text()
    v42 = V42.read_text()

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v43"' in source
    assert "STALE_DOWNSTREAM_DAY_USES_PINNED_SNAPSHOT = True" in source
    assert "snapshot = tuple(dict(game) for game in original_loader(selected_day))" in source
    assert "snapshot_owner.games_owner._load_games = snapshot_loader" in source
    assert "snapshot_owner.games_owner._load_games = original_loader" in source
    assert "raise RuntimeError(" in v42
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "NEW_PROVIDER_PATHS_ADDED = 0" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_PAGE2 = False" in source


def test_step2_router_advances_only_page1_owner_to_v44():
    router = ROUTER.read_text()
    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v44"' in router
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in router
