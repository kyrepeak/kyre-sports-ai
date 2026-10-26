"""Fail-closed source policy for MONSTER WNBA PRA Page 1 ultra S-tier V2."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SUCCESSOR = ROOT / "wnba_pra_page1_ultra_stier_v2.py"
COMPAT = ROOT / "wnba_pra_hub_v3612.py"
FORBIDDEN = ("sports" + "gameodds", "esp" + "n bet", "import esp" + "n", "render.com", "import requests", "import httpx", "curl_cffi")


def main() -> int:
    failures = []
    source = SUCCESSOR.read_text(encoding="utf-8")
    lowered = source.casefold()
    for token in FORBIDDEN:
        if token in lowered:
            failures.append(f"successor-forbidden:{token}")
    for token in (
        "WNBA <b>PRA</b>",
        "Top 3 Model Edges",
        "Player Discovery",
        "Market Movement",
        "Analyze Player",
        "CERTIFIED PRA PICK",
        "build_player_board_rows",
        "rank_top_edges",
        "_handoff",
    ):
        if token not in source:
            failures.append(f"ui-contract:{token}")
    compat = COMPAT.read_text(encoding="utf-8")
    preserved = "active.render_page_snapshot = _page1_final_polish.render_page_snapshot"
    install = "active.render_page_snapshot = _page1_ultra_stier_v2.render_page_snapshot"
    refresh = "import wnba_pra_hub_v3618 as refresh_handoff"
    if preserved not in compat or install not in compat or refresh not in compat:
        failures.append("compat:missing-install-chain")
    elif not (compat.index(preserved) < compat.index(install) < compat.index(refresh)):
        failures.append("compat:install-order")
    frozen = {
        "wnba_pra_page1_stier_v1.py": "8882b1034ee7e05ae3006eaedc0ccd91ab30f51f",
        "wnba_pra_page1_final_polish_v1.py": "f524cc7e8216372047690c0b61305dbb308640c9",
        "wnba_pra_page_model_artifact_final_polish_v1.py": "18a3b100228007aa19a63513cfaeedc98f337fbc",
        "runless_v2/wnba_pra_page1_final_polish_runtime_v1.py": "7973b326709bca3abd813e7a2e35849f51afd4a3",
    }
    for rel, expected in frozen.items():
        actual = subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()
        if actual != expected:
            failures.append(f"frozen-byte-drift:{rel}:{actual}")
    if failures:
        raise SystemExit("WNBA_PRA_PAGE1_ULTRA_STIER_V2_SOURCE_POLICY_FAIL:" + ",".join(failures))
    print("WNBA_PRA_PAGE1_ULTRA_STIER_V2_SOURCE_POLICY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
