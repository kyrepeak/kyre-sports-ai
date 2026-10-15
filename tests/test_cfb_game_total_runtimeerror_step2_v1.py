from datetime import date

import cfb_game_total_clean_page_v42 as subject


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
        downstream_results.extend(subject.games_owner._load_games(stale_downstream_day))
        return "rendered"

    monkeypatch.setattr(subject.prior, "_selected_day", lambda: selected_day)
    monkeypatch.setattr(subject.games_owner, "_load_games", original_loader)
    monkeypatch.setattr(subject.prior, "render_game_total_hub", downstream_render)

    result = subject.render_game_total_hub()

    assert result == "rendered"
    assert original_calls == [selected_day]
    assert downstream_results == snapshot
    assert subject.games_owner._load_games is original_loader


def test_step2_patch_remains_snapshot_only_and_does_not_expand_scope():
    source = subject.__file__
    text = open(source, encoding="utf-8").read()

    assert "snapshot = tuple(dict(game) for game in original_loader(selected_day))" in text
    assert "games_owner._load_games = snapshot_loader" in text
    assert "games_owner._load_games = original_loader" in text
    assert "NETWORK_CALLS_ADDED = 0" in text
    assert "NEW_PROVIDER_PATHS_ADDED = 0" in text
    assert "MAY_MODIFY_MODEL = False" in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "MAY_MODIFY_PROBABILITY = False" in text
    assert "MAY_MODIFY_PAGE2 = False" in text
