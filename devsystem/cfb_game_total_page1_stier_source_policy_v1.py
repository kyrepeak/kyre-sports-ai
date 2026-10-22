"""Static source-policy proof for CFB Game Total Page 1 S-tier V1."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_page1_stier_v1.py"
API = ROOT / "sports_api" / "api" / "cfb_game_total_page1_v1.py"
COLLECTOR = ROOT / "sports_api" / "collectors" / "cfb_game_total_market_v1.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py"
ENTRY = ROOT / "kyre_sports_api_vercel_v1.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    page = _text(PAGE)
    page_lower = page.casefold()
    api = _text(API)
    api_lower = api.casefold()
    collector_lower = _text(COLLECTOR).casefold()
    terminal = _text(TERMINAL)
    entry = _text(ENTRY)

    for token in (
        "actionnetwork", "action network", "site.api.espn", "espn bet",
        "sportsgameodds", "sports-game-odds", "cfb_fanduel_direct",
        "the-odds-api.com", "api.sportsbook.fanduel.com",
    ):
        if token in page_lower:
            failures.append(f"frontend forbidden direct provider token: {token}")

    for token in ("actionnetwork", "site.api.espn", "sportsgameodds", "sports-game-odds"):
        if token in api_lower or token in collector_lower:
            failures.append(f"backend forbidden provider path: {token}")

    required_page = (
        'PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"',
        'KYRE_SPORTS_API_BASE_URL = "KYRE_SPORTS_API_BASE_URL"',
        "MARKET COMMAND CENTER",
        "Line Integrity",
        "OPEN ANALYSIS",
    )
    for marker in required_page:
        if marker not in page:
            failures.append(f"missing page contract marker: {marker}")

    required_api = (
        '"application_gateway": "Kyre Sports API"',
        '"schedule_primary": "NCAA"',
        '"market_primary": "FanDuel"',
        '"consensus_averaging": False',
        '"null_to_zero": False',
        'FORBIDDEN_PROVIDERS = ["SGO", "ESPN", "ESPN BET"]',
    )
    for marker in required_api:
        if marker not in api:
            failures.append(f"missing API routing marker: {marker}")

    if 'route.sport_id == "cfb" and route.market_id == "game-total"' not in terminal:
        failures.append("terminal CFB Game Total route activation missing")
    if 'importlib.import_module("cfb_game_total_page2_market_completeness_r1")' not in terminal:
        failures.append("selected-game Page 2 preservation missing")
    if "sports_api.api.cfb_game_total_page1_v1" not in entry or "app.include_router(cfb_game_total_router)" not in entry:
        failures.append("dedicated Kyre Sports API route registration missing")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: CFB Game Total Page 1 S-tier source policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
