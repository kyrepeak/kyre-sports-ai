from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
REPAIR = ROOT / "cfb_game_total_v5_date_slate_repair_v1.py"
LOADER = ROOT / "universal_runtime_v5_loader_v21.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_gt_v5.py"
APP = ROOT / "app.py"


def _assert_new_modules() -> None:
    assert REPAIR.exists(), "V5 Game Total repair module is missing"
    assert LOADER.exists(), "Runtime loader V21 is missing"
    assert TERMINAL.exists(), "Game Total V5 terminal overlay is missing"


def test_game_total_v5_repair_modules_exist() -> None:
    _assert_new_modules()


def test_repair_installs_certified_daily_slate_context_and_preserves_page2_boundary() -> None:
    _assert_new_modules()
    source = REPAIR.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as daily_router" in source
    assert "with daily_router.install_daily_slate_page1():" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_SELECTED_GAME_RUNTIME = False" in source


def test_view_game_link_carries_canonical_and_legacy_exact_identity() -> None:
    _assert_new_modules()
    import cfb_game_total_v5_date_slate_repair_v1 as repair

    href = repair.canonical_view_game_href({"event_id": "401871055"}, date(2026, 10, 20))
    query = parse_qs(urlparse(href).query)
    assert query["sport"] == ["cfb"]
    assert query["market"] == ["game-total"]
    assert query["date"] == ["2026-10-20"]
    assert query["game_id"] == ["401871055"]
    assert query["ks_sport"] == ["College Football"]
    assert query["ks_cfb_market"] == ["Game Total"]
    assert query["ks_cfb_game_total_date"] == ["2026-10-20"]
    assert query["ks_cfb_game_total_event_id"] == ["401871055"]
    assert query["ks_cfb_game_total_selector_sync"] == ["401871055"]


def test_selected_event_prefers_canonical_route_game_id() -> None:
    _assert_new_modules()
    import cfb_game_total_v5_date_slate_repair_v1 as repair

    route = SimpleNamespace(params={"game_id": "401871055"})
    assert repair.selected_event_id(route, query={}, session={}) == "401871055"


def test_selected_event_supports_legacy_event_query_for_frozen_page2() -> None:
    _assert_new_modules()
    import cfb_game_total_v5_date_slate_repair_v1 as repair

    route = SimpleNamespace(params={})
    query = {"ks_cfb_game_total_event_id": "401871092"}
    assert repair.selected_event_id(route, query=query, session={}) == "401871092"


def test_selected_event_syncs_canonical_identity_into_frozen_page2_keys() -> None:
    _assert_new_modules()
    import cfb_game_total_v5_date_slate_repair_v1 as repair

    route = SimpleNamespace(params={"date": "2026-10-20", "game_id": "401871055"})
    query: dict[str, str] = {}
    session: dict[str, str] = {}
    repair.sync_selected_event_id("401871055", route, query=query, session=session)
    assert query["game_id"] == "401871055"
    assert query["date"] == "2026-10-20"
    assert query["ks_cfb_game_total_event_id"] == "401871055"
    assert query["ks_cfb_game_total_selector_sync"] == "401871055"
    assert query["ks_cfb_game_total_date"] == "2026-10-20"
    assert session["ks_cfb_game_total_event_id"] == "401871055"
    assert session["ks_cfb_game_total_selector_sync"] == "401871055"


def test_page1_runtime_context_patches_links_only_while_installed(monkeypatch) -> None:
    _assert_new_modules()
    import cfb_game_total_v5_date_slate_repair_v1 as repair

    calls: list[str] = []

    @contextmanager
    def fake_daily_context():
        calls.append("enter")
        yield
        calls.append("exit")

    monkeypatch.setattr(repair.daily_router, "install_daily_slate_page1", fake_daily_context)
    original = lambda game, selected_day: "OLD"  # noqa: E731
    page1 = SimpleNamespace(view_game_href=original)

    with repair.install_page1_runtime(page1):
        assert calls == ["enter"]
        assert page1.view_game_href is repair.canonical_view_game_href
    assert calls == ["enter", "exit"]
    assert page1.view_game_href is original


def test_loader_v21_repairs_only_cfb_game_total_and_delegates_everything_else() -> None:
    _assert_new_modules()
    source = LOADER.read_text(encoding="utf-8")
    assert "import universal_runtime_v5_loader_v20 as prior" in source
    assert 'route.sport_id == "cfb" and route.market_id == "game-total"' in source
    assert 'importlib.import_module("cfb_game_total_v5_date_slate_repair_v1")' in source
    assert 'importlib.import_module("cfb_game_total_page1_daily_slate_v1")' in source
    assert 'importlib.import_module("cfb_game_total_page2_market_completeness_r1")' in source
    assert "with repair.install_page1_runtime(page1):" in source
    assert "event_id = repair.selected_event_id(route)" in source
    assert "repair.sync_selected_event_id(event_id, route)" in source
    assert "return page2.render_cfb_hub(\"Game Total\")" in source
    assert "return prior.resolve_destination(route)" in source


def test_terminal_v5_advances_only_loader_handoff_and_app_points_to_it() -> None:
    _assert_new_modules()
    source = TERMINAL.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_universal_runtime_v5 as prior" in source
    assert "from universal_runtime_v5_loader_v21 import choose_prefetch, load_destination, resolve_destination" in source
    assert "prior.choose_prefetch = choose_prefetch" in source
    assert "prior.load_destination = load_destination" in source
    assert "prior.resolve_destination = resolve_destination" in source
    assert "return prior.render_app()" in source
    app_source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_gt_v5" in app_source
