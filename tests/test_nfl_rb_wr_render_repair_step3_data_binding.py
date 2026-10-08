from __future__ import annotations

from pathlib import Path


CERT = Path("devsystem/nfl_rb_wr_render_repair_step3_data_binding_v1.py")


def test_step3_data_binding_cert_exists_before_runtime_is_touched() -> None:
    assert CERT.exists(), "Step 3 data-binding certification module is missing"
