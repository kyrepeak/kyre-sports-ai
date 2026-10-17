from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
R3 = ROOT / "cfb_game_total_page2_visual_cleanup_r3.py"


def test_public_activation_uses_real_dependency_hash_trigger() -> None:
    lines = [line.strip() for line in REQ.read_text(encoding="utf-8").splitlines()]
    assert lines.count("packaging>=20") == 1


def test_activation_preserves_r3_runtime_owner() -> None:
    assert R3.exists()
    router = ROUTER.read_text(encoding="utf-8")
    assert 'CFB_PAGE2_RUNTIME = "cfb_game_total_page2_visual_cleanup_r3"' in router


def test_activation_is_dependency_only_not_product_rewrite() -> None:
    r3 = R3.read_text(encoding="utf-8")
    assert 'MAY_MODIFY_PAGE1 = False' in r3
    assert 'MAY_MODIFY_MODEL = False' in r3
    assert 'MAY_MODIFY_PROJECTION = False' in r3
    assert 'MAY_MODIFY_PROBABILITY = False' in r3
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in r3
