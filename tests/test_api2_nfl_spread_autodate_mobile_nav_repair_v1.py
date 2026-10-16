from __future__ import annotations

from datetime import date
from importlib import util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTODATE = ROOT / "nfl_spread_autodate_repair_v1.py"
HUB_V6 = ROOT / "nfl_spread_hub_v6.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"
APP = ROOT / "app.py"


def _load_module(path: Path, name: str):
    assert path.exists(), f"missing repair module: {path.name}"
    spec = util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_empty_widget_date_advances_even_if_v5_one_shot_flag_exists():
    mod = _load_module(AUTODATE, "nfl_spread_autodate_repair_v1_test_a")
    apply_repair = getattr(mod, "apply_spread_autodate", None)
    assert callable(apply_repair), "apply_spread_autodate must exist"

    session = {
        "nfl_v1_date": date(2026, 10, 16),
        "nfl_spread_v4_date_input": date(2026, 10, 16),
        "nfl_spread_v5_auto_resolved": True,
    }
    calls = []

    def resolver(selected: date):
        calls.append(selected)
        return {
            "state": "FOUND",
            "selected_date": selected,
            "resolved_date": date(2026, 10, 18),
            "advanced": True,
            "source": "schedule",
        }

    result = apply_repair(session, date(2026, 10, 16), resolver)

    assert result["resolved_date"] == date(2026, 10, 18)
    assert session["nfl_v1_date"] == date(2026, 10, 18)
    assert session["nfl_spread_v4_date_input"] == date(2026, 10, 18)
    assert calls == [date(2026, 10, 16)]


def test_manual_empty_date_is_rechecked_after_previous_good_date():
    mod = _load_module(AUTODATE, "nfl_spread_autodate_repair_v1_test_b")
    apply_repair = getattr(mod, "apply_spread_autodate", None)
    assert callable(apply_repair), "apply_spread_autodate must exist"

    session = {
        "nfl_v1_date": date(2026, 10, 18),
        "nfl_spread_v4_date_input": date(2026, 10, 18),
    }
    calls = []

    def resolver(selected: date):
        calls.append(selected)
        if selected == date(2026, 10, 18):
            return {
                "state": "FOUND",
                "selected_date": selected,
                "resolved_date": selected,
                "advanced": False,
                "source": "primary",
            }
        return {
            "state": "FOUND",
            "selected_date": selected,
            "resolved_date": date(2026, 10, 22),
            "advanced": True,
            "source": "schedule",
        }

    first = apply_repair(session, date(2026, 10, 18), resolver)
    assert first["resolved_date"] == date(2026, 10, 18)

    session["nfl_v1_date"] = date(2026, 10, 20)
    session["nfl_spread_v4_date_input"] = date(2026, 10, 20)
    second = apply_repair(session, date(2026, 10, 20), resolver)

    assert second["resolved_date"] == date(2026, 10, 22)
    assert session["nfl_v1_date"] == date(2026, 10, 22)
    assert session["nfl_spread_v4_date_input"] == date(2026, 10, 22)
    assert calls == [date(2026, 10, 18), date(2026, 10, 20)]


def test_same_verified_date_is_cached_to_preserve_fast_rerenders():
    mod = _load_module(AUTODATE, "nfl_spread_autodate_repair_v1_test_c")
    apply_repair = getattr(mod, "apply_spread_autodate", None)
    assert callable(apply_repair), "apply_spread_autodate must exist"

    session = {
        "nfl_v1_date": date(2026, 10, 18),
        "nfl_spread_v4_date_input": date(2026, 10, 18),
    }
    calls = []

    def resolver(selected: date):
        calls.append(selected)
        return {
            "state": "FOUND",
            "selected_date": selected,
            "resolved_date": selected,
            "advanced": False,
            "source": "primary",
        }

    apply_repair(session, date(2026, 10, 18), resolver)
    apply_repair(session, date(2026, 10, 18), resolver)

    assert calls == [date(2026, 10, 18)]


def test_additive_v6_hub_and_tap_only_overlay_exist():
    assert HUB_V6.exists(), "V6 must wrap the frozen Spread page instead of reopening V5"
    assert OVERLAY.exists(), "mobile repair overlay must be additive"


def test_mobile_nfl_market_control_is_tap_only_not_searchable():
    assert OVERLAY.exists(), "mobile repair overlay must exist"
    source = OVERLAY.read_text(encoding="utf-8")
    assert "_tap_only_nfl_market_picker" in source
    assert "st.popover" in source
    assert "st.button" in source
    assert "🎯 NFL Market" in source
    assert "st.text_input" not in source


def test_app_boots_new_additive_repair_overlay():
    source = APP.read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1 import "
        "record_bootstrap_import_ms, render_app"
    ) in source
