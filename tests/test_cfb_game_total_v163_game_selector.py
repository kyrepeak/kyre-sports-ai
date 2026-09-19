from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v14.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v159.py"
APP = ROOT / "app.py"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V163 file: {path.name}"
    return path.read_text(encoding="utf-8")


def test_v163_adds_visible_scrollable_game_selector_with_espn_event_query():
    source = _read(PAGE)
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in source
    assert 'data-testid="gt163-game-strip"' in source
    assert "overflow-x:auto" in source.replace(" ", "")
    assert "GAMES ON THIS DAY" in source
    assert "event_id" in source
    assert 'aria-current="true"' in source


def test_v163_selected_event_controls_frozen_matchup_index_and_survives_refresh():
    source = _read(PAGE)
    assert "_selected_game_index" in source
    assert "_set_query_event_id" in source
    assert "_query_event_id" in source
    assert "_game_id" in source
    assert 'MATCHUP_STATE_KEY_PREFIX = "cfb_v152_game_total_matchup_"' in source
    assert 'st.session_state[f"{MATCHUP_STATE_KEY_PREFIX}{selected_day}"] = selected_index' in source
    assert "return selected_index" in source


def test_v163_game_links_preserve_date_route_and_exact_event_identity():
    source = _read(PAGE)
    assert "DATE_QUERY_KEY" in source
    assert "ROUTE_QUERY_SPORT" in source
    assert "ROUTE_QUERY_MARKET" in source
    assert "EVENT_QUERY_KEY" in source
    assert 'return "?" + urlencode(params)' in source
    assert 'target="_self"' in source
    assert 'SELECTOR_SYNC_QUERY_KEY = "ks_cfb_game_total_selector_sync"' in source
    assert 'SELECTOR_SYNC_QUERY_KEY: event_id' in source
    assert 'del st.query_params[SELECTOR_SYNC_QUERY_KEY]' in source


def test_v163_router_activates_fresh_page_successor_and_preserves_frozen_heartbeats():
    source = _read(ROUTER)
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v14"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"' in source
    assert 'LEGACY_V162_HEARTBEAT = "CFB_GAME_TOTAL_V162_PRODUCTION_ACTIVE"' in source
    assert 'LEGACY_V161_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v158"' in source


def test_app_activates_router_v159_and_preserves_v158_source_contract():
    source = _read(APP)
    assert "streamlit_memory_lazy_router_v159" in source
    assert "from streamlit_memory_lazy_router_v158 import record_bootstrap_import_ms, render_app" in source


def test_v163_retries_official_identity_pipeline_once_when_first_slate_has_no_espn_ids(monkeypatch):
    """A transient official-ID miss must recover without using provider game_id."""
    from datetime import date

    import cfb_game_total_clean_page_v14 as page_v14

    class FakeSchedule:
        def __init__(self):
            self.loads = 0
            self.clears = 0

        def load_with_diagnostics(self, selected_day):
            self.loads += 1
            base = {
                "game_id": "provider-only-id",
                "away_team": "Alpha",
                "home_team": "Beta",
                "kickoff_iso": "2026-09-19T23:30:00Z",
            }
            if self.loads == 1:
                return [base], {"espn_matches": 0}
            return [{**base, "espn_event_id": "401547777"}], {"espn_matches": 1}

        def clear_schedule_cache(self):
            self.clears += 1

    schedule_owner = page_v14.v161.prior.frozen_page.frozen_v2.frozen_v1
    fake_schedule = FakeSchedule()
    monkeypatch.setattr(schedule_owner, "schedule", fake_schedule)

    games = page_v14._load_games(date(2026, 9, 19))

    assert fake_schedule.loads == 2
    assert fake_schedule.clears == 1
    assert page_v14._game_id(games[0]) == "401547777"
    assert page_v14._game_id({"game_id": "provider-only-id"}) == ""
