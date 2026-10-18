from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nfl_active_slate_controller_v1 import resolve_active_slate

TOKENS = (
    "API2_NFL_ACTIVE_SLATE_RESOLVER_OK",
    "API2_NFL_ACTIVE_SLATE_ALL_FINAL_ROLLOVER_OK",
    "API2_NFL_ACTIVE_SLATE_CROSS_MARKET_DATE_OK",
    "API2_NFL_ACTIVE_SLATE_MANUAL_OVERRIDE_OK",
    "API2_NFL_ACTIVE_SLATE_LEGACY_AUTO_GUARDS_OK",
    "API2_NFL_ACTIVE_SLATE_NON_NFL_DELEGATION_OK",
    "API2_NFL_ACTIVE_SLATE_MODEL_FIREWALL_OK",
    "API2_NFL_ACTIVE_SLATE_UNIVERSAL_NAV_OK",
    "API2_NFL_ACTIVE_SLATE_V1_PASS",
)

NFL_MARKET_IDS = (
    "slate",
    "moneyline",
    "spread",
    "game-total",
    "passing-yards",
    "rushing-yards",
    "receiving-yards",
    "receptions",
    "passing-tds",
    "anytime-td",
    "daily-picks",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _assert_all_final_rollover() -> None:
    today = date(2026, 10, 18)
    next_day = date(2026, 10, 19)

    def loader(day_iso: str):
        if day_iso == today.isoformat():
            return pd.DataFrame([{"state": "post"}, {"state": "post"}]), {"request_ok": True}
        if day_iso == next_day.isoformat():
            return pd.DataFrame([{"state": "pre"}]), {"request_ok": True}
        return pd.DataFrame(), {"request_ok": True}

    result = resolve_active_slate(today, loader, lambda *_: [next_day])
    assert result["state"] == "FOUND"
    assert result["resolved_date"] == next_day
    assert result["advanced"] is True


def certify_source_contract() -> dict[str, Any]:
    controller = _read("nfl_active_slate_controller_v1.py")
    runtime = _read("nfl_active_slate_runtime_v1.py")
    spread = _read("nfl_spread_autodate_repair_v1.py")
    passing = _read("nfl_passing_yards_hub_v37.py")
    receiving = _read("nfl_receiving_yards_hub_v11.py")
    totals = _read("nfl_game_totals_hub_v8_1.py")
    router = _read("streamlit_memory_lazy_router_api2_nfl_active_slate_v1.py")
    app = _read("app.py")

    assert "def resolve_active_slate(" in controller
    assert '"pre"' in controller and '"in"' in controller and '"post"' in controller
    print(TOKENS[0])

    _assert_all_final_rollover()
    print(TOKENS[1])

    assert 'MODE_KEY = "nfl_active_slate_mode"' in runtime
    assert 'COMPAT_DATE_KEY = "nfl_v1_date"' in runtime
    assert "install_nfl_date_input_bridge" in runtime
    print(TOKENS[2])

    assert 'MANUAL_DATE_KEY = "nfl_manual_slate_date"' in runtime
    assert 'session[MODE_KEY] = "MANUAL"' in runtime
    print(TOKENS[3])

    for source in (spread, passing, receiving, totals):
        assert "is_manual_mode" in source
    print(TOKENS[4])

    assert 'FROZEN_PARENT = "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1"' in router
    assert "if not _is_nfl_route():" in router
    assert "return prior.render_app()" in router
    print(TOKENS[5])

    for marker in (
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        "STAKE_SIZING_ENABLED = False",
        "WAGER_ACTIONS_ENABLED = False",
    ):
        assert marker in router
    print(TOKENS[6])

    assert "streamlit_memory_lazy_router_api2_nfl_active_slate_v1" in app
    assert "streamlit_memory_lazy_router_universal_nav_v4" in app
    registry_path = ROOT / "universal_sports_nav_registry_v1.py"
    if registry_path.exists():
        registry = registry_path.read_text(encoding="utf-8")
        for market_id in NFL_MARKET_IDS:
            assert f'"{market_id}"' in registry
    print(TOKENS[7])

    print(TOKENS[8])
    return {"status": "PASS", "tokens": list(TOKENS), "nfl_markets": list(NFL_MARKET_IDS)}


def main() -> int:
    certify_source_contract()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
