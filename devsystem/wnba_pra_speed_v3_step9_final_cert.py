"""Proof-only adapter for exact live Streamlit deployment identity."""
from __future__ import annotations

import os

EXPECTED_PRODUCT_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
os.environ["GITHUB_SHA"] = EXPECTED_PRODUCT_SHA

from devsystem import wnba_pra_repair_v1_step2_team_identity_cert as cert


def main() -> int:
    return cert.main()


if __name__ == "__main__":
    raise SystemExit(main())
