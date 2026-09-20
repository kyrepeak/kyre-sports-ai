"""Step 3 read-only production proof for the 2026-09-20 NFL Passing Yards slate.

Acceptance:
- public Passing Yards exposes all 14 verified games;
- every game can be selected;
- each rendered QB card matches the exact ESPN/current-roster identity resolver
  by both player name and athlete ID;
- Unresolved QB1 never renders.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import nfl_hub_v25 as nfl
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_public_prod_cert_v1 as public

DAY = "2026-09-20"
EXPECTED_GAMES = 14
PRODUCTION_URL = "https://kyre-sports-ai.streamlit.app"


class Step3Failure(RuntimeError):
    pass


def _expected_slate():
    games, diag = nfl.load_nfl_slate(DAY)
    if not diag.get("request_ok"):
        raise Step3Failure(f"ESPN slate request failed: {diag}")
    if len(games) != EXPECTED_GAMES:
        raise Step3Failure(f"expected {EXPECTED_GAMES} games for {DAY}; got {len(games)}")

    expected = []
    for _, row in games.iterrows():
        game = row.to_dict()
        resolved = identity.resolve_matchup_identity(game, 2026)
        away = resolved.get("away") or {}
        home = resolved.get("home") or {}
        if resolved.get("identity_ready") is not True:
            raise Step3Failure(
                f"exact QB identity unresolved before public proof for event {game.get('game_id')}: "
                f"{resolved.get('reason')}"
            )
        aqb = away.get("qb1") or {}
        hqb = home.get("qb1") or {}
        if not str(aqb.get("athlete_id") or "").isdigit() or not str(hqb.get("athlete_id") or "").isdigit():
            raise Step3Failure(f"missing exact athlete IDs for event {game.get('game_id')}")
        expected.append(
            {
                "event_id": str(game.get("game_id") or ""),
                "label_prefix": f"{game.get('away_team')} @ {game.get('home_team')} • ",
                "away": {
                    "name": str(aqb.get("name") or "").strip(),
                    "athlete_id": str(aqb.get("athlete_id") or "").strip(),
                },
                "home": {
                    "name": str(hqb.get("name") or "").strip(),
                    "athlete_id": str(hqb.get("athlete_id") or "").strip(),
                },
            }
        )
    return expected


def _visible_option_texts(page, frame):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        for owner in (page, frame):
            try:
                loc = owner.get_by_role("option")
                texts = [x.strip() for x in loc.all_inner_texts() if x.strip()]
                if texts:
                    return loc, texts
            except Exception:
                pass
        page.wait_for_timeout(250)
    raise Step3Failure("visible matchup options never appeared")


def _visible_matchup_combo(frame):
    combos = frame.get_by_role(
        "combobox",
        name=re.compile(r"^Choose matchup • \d+ verified game(?:s)?$"),
    )
    combos.first.wait_for(state="visible", timeout=120000)
    return combos.first


def _select_game(page, frame, label_prefix: str) -> str:
    combo = _visible_matchup_combo(frame)
    combo.click()
    options, texts = _visible_option_texts(page, frame)
    index = next((i for i, text in enumerate(texts) if text.startswith(label_prefix)), -1)
    if index < 0:
        page.keyboard.press("Escape")
        raise Step3Failure(f"matchup missing from production selector: {label_prefix!r}; saw={texts}")
    chosen = texts[index]
    options.nth(index).click()
    return chosen


def _wait_qb_cards(page, frame, away: dict, home: dict) -> dict:
    deadline = time.monotonic() + 180
    last = {}
    while time.monotonic() < deadline:
        try:
            cards = frame.locator(".kpass29-card")
            names = [
                cards.nth(i).locator(".kpass29-name").first.inner_text().strip()
                for i in range(min(cards.count(), 2))
            ]
            ids = [
                cards.nth(i).locator(".kpass29-metric b").first.inner_text().strip()
                for i in range(min(cards.count(), 2))
            ]
            body = public._body(frame)
            last = {"names": names, "ids": ids, "body_start": body[:1000]}
            if len(names) >= 2 and len(ids) >= 2:
                if any(name == "Unresolved QB1" for name in names) or "Unresolved QB1" in body:
                    raise Step3Failure(f"Unresolved QB1 rendered: {last}")
                if names[:2] == [away["name"], home["name"]] and ids[:2] == [
                    away["athlete_id"],
                    home["athlete_id"],
                ]:
                    return {"names": names[:2], "ids": ids[:2]}
        except Step3Failure:
            raise
        except Exception:
            pass
        page.wait_for_timeout(500)
    raise Step3Failure(
        "QB cards did not settle to exact expected identities: "
        + json.dumps({"away": away, "home": home, "last": last}, sort_keys=True)
    )


def run(production_url: str = PRODUCTION_URL, artifact_dir: str = "artifacts/nfl-passing-step3"):
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    expected = _expected_slate()
    health = public._wait_for_public_streamlit(production_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1600})
        results = []
        try:
            page.goto(production_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120000)
            frame, scan = public._find_app_frame(page)
            public._assert_no_runtime_error(public._body(frame), "initial public app")

            sport = frame.get_by_role("combobox").nth(0)
            public._choose(page, sport, "NFL")
            market = frame.get_by_role("combobox", name="🎯 NFL Market", exact=True)
            market.wait_for(state="visible", timeout=60000)
            public._choose(page, market, "Passing Yards")

            combo = _visible_matchup_combo(frame)
            combo.click()
            options, texts = _visible_option_texts(page, frame)
            page.keyboard.press("Escape")
            if len(texts) != EXPECTED_GAMES:
                raise Step3Failure(f"production selector expected {EXPECTED_GAMES} games; saw {len(texts)}: {texts}")
            for item in expected:
                if not any(text.startswith(item["label_prefix"]) for text in texts):
                    raise Step3Failure(f"production selector missing event {item['event_id']}: {item['label_prefix']}")

            for index, item in enumerate(expected, start=1):
                chosen = _select_game(page, frame, item["label_prefix"])
                qb = _wait_qb_cards(page, frame, item["away"], item["home"])
                results.append(
                    {
                        "event_id": item["event_id"],
                        "matchup": chosen,
                        "away_qb": {"name": qb["names"][0], "athlete_id": qb["ids"][0]},
                        "home_qb": {"name": qb["names"][1], "athlete_id": qb["ids"][1]},
                    }
                )
                print(
                    "STEP3_GAME_GREEN "
                    + json.dumps(
                        {"index": index, "total": EXPECTED_GAMES, **results[-1]},
                        sort_keys=True,
                    )
                )

            body = public._body(frame)
            public._assert_no_runtime_error(body, "NFL Passing Yards Step 3 production")
            if "Unresolved QB1" in body:
                raise Step3Failure("Unresolved QB1 remains in final public body")

            screenshot = artifacts / "nfl_passing_step3_production_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "day": DAY,
                "games_verified": len(results),
                "expected_games": EXPECTED_GAMES,
                "unresolved_qb1_count": 0,
                "production_url": production_url,
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "frame_scan_count": len(scan),
                "games": results,
                "screenshot": str(screenshot),
            }
            (artifacts / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            print("NFL_PASSING_STEP3_14_GAME_PRODUCTION_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(path=str(artifacts / "nfl_passing_step3_production_failure.png"), full_page=True)
                (artifacts / "failure_body.txt").write_text(public._body(frame), encoding="utf-8")
            except Exception:
                pass
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    run()
