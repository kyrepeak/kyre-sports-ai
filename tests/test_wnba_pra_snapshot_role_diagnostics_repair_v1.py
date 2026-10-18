from pathlib import Path


def test_pra_product_snapshot_uses_hardened_role_diagnostics_owner():
    source = Path("wnba_pra_product_snapshot_v1.py").read_text(encoding="utf-8")
    assert "import wnba_role_v282 as role" in source
    assert "import wnba_role_v28 as role" not in source
