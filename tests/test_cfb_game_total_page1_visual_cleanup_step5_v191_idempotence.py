from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V191 = ROOT / "streamlit_memory_lazy_router_v191.py"


def test_v191_installs_public_repair_once_per_process() -> None:
    source = V191.read_text(encoding="utf-8")
    assert "_PUBLIC_REPAIR_INSTALLED = False" in source
    assert "def _ensure_public_repair_once()" in source
    assert "if _PUBLIC_REPAIR_INSTALLED:" in source
    assert source.count("install_public_repair()") == 1


def test_v191_installs_cfb_game_total_compat_once_per_process() -> None:
    source = V191.read_text(encoding="utf-8")
    assert "_CFB_GAME_TOTAL_COMPAT_INSTALLED = False" in source
    assert "def _should_theme_route_once(sport: str, market: str) -> bool:" in source
    assert "if _CFB_GAME_TOTAL_COMPAT_INSTALLED:" in source
    assert source.count("should_theme_route(sport, market)") == 1


def test_v191_preserves_frozen_cfb_game_total_theme_exclusion() -> None:
    source = V191.read_text(encoding="utf-8")
    assert '(sport, market) == ("CFB", "Game Total")' in source
    assert "return False" in source
    assert "prior.render_app()" in source
