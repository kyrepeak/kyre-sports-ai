from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("sports" + "gameodds", "esp" + "n bet", "esp" + "n.com", "import esp" + "n", "render.com")


def main() -> int:
    failures = []
    for rel in ("wnba_pra_page1_stier_v1.py", "wnba_pra_hub_v3617.py"):
        text = (ROOT / rel).read_text(encoding="utf-8").casefold()
        for token in FORBIDDEN:
            if token in text:
                failures.append(f"{rel}:{token}")
    renderer = (ROOT / "wnba_pra_page1_stier_v1.py").read_text(encoding="utf-8").casefold()
    for token in ("import requests", "import httpx", "curl_cffi"):
        if token in renderer:
            failures.append(f"renderer-network:{token}")
    hub = (ROOT / "wnba_pra_hub_v3617.py").read_text(encoding="utf-8")
    for token in ("fetch_page_snapshot", "refresh_if_claimed", "wnba_pra_page1_stier_v1"):
        if token not in hub:
            failures.append(f"hub-contract:{token}")
    market = (ROOT / "runless_v2/wnba_pra_market_v1.py").read_text(encoding="utf-8")
    for token in ("FanDuel", "DraftKings", "consensus_averaging", "projection_weight"):
        if token not in market:
            failures.append(f"market-contract:{token}")
    if failures:
        raise SystemExit("WNBA_PRA_PAGE1_STIER_SOURCE_POLICY_FAIL:" + ",".join(failures))
    print("WNBA_PRA_PAGE1_STIER_SOURCE_POLICY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
