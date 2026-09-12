"""Read-only public production certification for NFL Passing Yards V20.

This certification intentionally targets the deployed Streamlit Community Cloud
application, not a branch-local server. It first discovers an upcoming official
ESPN NFL event for which the deployed Kyre Sports API currently exposes at least
one certified FanDuel Passing Yards prop. It then drives the public Streamlit UI
with Playwright and proves that the same exact event renders Step 10 with the
live line + Over price + Under price auto-filled from the API.

This file never writes to production and never weakens fail-closed behavior.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import time
from typing import Any
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

PRODUCTION_URL = "https://kyre-sports-ai.streamlit.app"
KYRE_API_URL = "https://kyre-sports-api.onrender.com"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ET = ZoneInfo("America/New_York")
USER_AGENT = "KyreSportsAI-NFL-Passing-Yards-Public-Cert/1.0"
MAX_DISCOVERY_DAYS = 8
FORBIDDEN_MARKERS = (
    "Traceback (most recent call last)",
    "RecursionError",
    "TypeError:",
    "ModuleNotFoundError",
    "ImportError:",
    "SyntaxError:",
    "NameError:",
    "This app has encountered an error",
)


class PublicProductionCertFailure(RuntimeError):
    pass


def _artifact_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _get(url: str, *, params: dict[str, Any] | None = None, timeout: float = 20.0) -> requests.Response:
    return requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})


def _wait_for_public_streamlit(base_url: str, timeout_seconds: float = 180.0) -> dict[str, int]:
    deadline = time.monotonic() + timeout_seconds
    last: str = ""
    while time.monotonic() < deadline:
        try:
            health = _get(base_url.rstrip("/") + "/_stcore/health", timeout=10)
            root = _get(base_url.rstrip("/") + "/", timeout=20)
            if health.status_code == 200 and root.status_code == 200 and "streamlit" in root.text.casefold():
                return {"health_http": health.status_code, "root_http": root.status_code}
            last = f"health={health.status_code} root={root.status_code}"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(4)
    raise PublicProductionCertFailure(f"public Streamlit did not become healthy: {last}")


def _official_event(event: dict[str, Any], day: str) -> dict[str, Any] | None:
    event_id = str(event.get("id") or "").strip()
    competitions = event.get("competitions") or []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    status = ((comp.get("status") or {}).get("type") or {}) if isinstance(comp, dict) else {}
    if not event_id.isdigit() or str(status.get("state") or "").lower() != "pre":
        return None
    sides: dict[str, dict[str, str]] = {}
    for row in comp.get("competitors") or []:
        if not isinstance(row, dict):
            continue
        side = str(row.get("homeAway") or "").lower()
        team = row.get("team") or {}
        if side in {"away", "home"}:
            sides[side] = {
                "team_id": str(team.get("id") or "").strip(),
                "name": str(team.get("displayName") or team.get("name") or "").strip(),
                "short_name": str(team.get("shortDisplayName") or team.get("name") or "").strip(),
                "abbr": str(team.get("abbreviation") or "").strip().upper(),
            }
    if set(sides) != {"away", "home"}:
        return None
    kickoff = str(comp.get("date") or event.get("date") or "").strip()
    try:
        stamp = datetime.fromisoformat(kickoff.replace("Z", "+00:00")).astimezone(ET)
        et_day = stamp.date().isoformat()
    except Exception:
        et_day = day
    return {
        "event_id": event_id,
        "day": et_day,
        "away": sides["away"],
        "home": sides["home"],
    }


def _api_contract_green(payload: Any, event_id: str) -> bool:
    if not isinstance(payload, dict):
        return False
    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    return bool(
        payload.get("schema_version") == "nfl_passing_yards_market_v1"
        and str(payload.get("official_event_id") or "") == event_id
        and payload.get("sportsbook") == "FanDuel"
        and payload.get("market_available") is True
        and isinstance(payload.get("props"), list)
        and len(payload.get("props") or []) >= 1
        and semantics.get("projection_weight") == 0.0
        and semantics.get("market_context_only") is True
        and semantics.get("may_modify_projection") is False
        and semantics.get("stake_sizing_enabled") is False
        and identity.get("fuzzy_matching") is False
        and identity.get("player_name_matching") is False
        and identity.get("synthetic_event_ids") is False
        and identity.get("synthetic_player_ids") is False
    )


def discover_certifiable_event(api_url: str, *, days: int = MAX_DISCOVERY_DAYS) -> dict[str, Any]:
    start = datetime.now(ET).date()
    diagnostics: list[dict[str, Any]] = []
    for offset in range(days):
        day_obj = start + timedelta(days=offset)
        day = day_obj.isoformat()
        scoreboard = _get(ESPN_SCOREBOARD, params={"dates": day_obj.strftime("%Y%m%d")})
        if scoreboard.status_code != 200:
            diagnostics.append({"day": day, "scoreboard_http": scoreboard.status_code})
            continue
        try:
            events = scoreboard.json().get("events") or []
        except Exception:
            events = []
        for raw in events:
            if not isinstance(raw, dict):
                continue
            event = _official_event(raw, day)
            if not event:
                continue
            event_id = event["event_id"]
            response = _get(api_url.rstrip("/") + "/api/v1/nfl/passing-yards", params={"event_id": event_id}, timeout=30)
            record: dict[str, Any] = {"day": event["day"], "event_id": event_id, "api_http": response.status_code}
            if response.status_code != 200:
                diagnostics.append(record)
                continue
            try:
                payload = response.json()
            except Exception:
                diagnostics.append({**record, "invalid_json": True})
                continue
            record["props"] = len(payload.get("props") or []) if isinstance(payload, dict) else 0
            diagnostics.append(record)
            if not _api_contract_green(payload, event_id):
                continue
            event["api_payload"] = payload
            event["discovery_diagnostics"] = diagnostics
            return event
    raise PublicProductionCertFailure(
        "no upcoming exact-ID ESPN event currently has a certifiable deployed Kyre Sports API Passing Yards market: "
        + json.dumps(diagnostics[-20:], sort_keys=True)
    )


def _find_app_frame(page, timeout_seconds: float = 120.0):
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            try:
                combos = frame.get_by_role("combobox").count()
            except Exception:
                combos = 0
            scans.append({"index": index, "url": frame.url, "comboboxes": combos, "body_start": body[:400]})
            if "get this app back up" in body.casefold():
                wake = frame.get_by_text("Yes, get this app back up!", exact=False)
                if wake.count() > 0:
                    wake.click()
                    page.wait_for_timeout(7000)
                    continue
            if combos >= 1 and ("KYRE SPORTS AI" in body or "Sport" in body):
                return frame, scans
        last_scan = scans
        page.wait_for_timeout(2500)
    raise PublicProductionCertFailure("could not locate rendered public Streamlit frame: " + json.dumps(last_scan))


def _choose(page, combo, value: str) -> None:
    combo.click()
    page.keyboard.type(value)
    page.keyboard.press("Enter")


def _body(frame) -> str:
    return frame.locator("body").inner_text(timeout=10000)


def _assert_no_runtime_error(body: str, phase: str) -> None:
    for marker in FORBIDDEN_MARKERS:
        if marker.casefold() in body.casefold():
            raise PublicProductionCertFailure(f"{phase} contains runtime error marker {marker!r}")


def _wait_text(frame, text: str, timeout_ms: int = 120000) -> None:
    try:
        frame.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout_ms)
    except Exception as exc:
        body = _body(frame)
        raise PublicProductionCertFailure(f"timed out waiting for {text!r}; body start={body[:5000]!r}") from exc


def _set_slate_date(page, frame, day: str) -> None:
    day_obj = datetime.fromisoformat(day).date()
    candidates = [
        frame.locator('input[aria-label="NFL Passing Yards slate date"]'),
        frame.get_by_label("NFL Passing Yards slate date", exact=True),
    ]
    date_input = None
    for locator in candidates:
        try:
            if locator.count() > 0:
                date_input = locator.first
                break
        except Exception:
            continue
    if date_input is None:
        raise PublicProductionCertFailure("NFL Passing Yards slate-date input was not found")
    # Streamlit's date widget is a locale-formatted text control in the browser.
    date_input.click()
    page.keyboard.press("Control+A")
    page.keyboard.type(day_obj.strftime("%m/%d/%Y"))
    page.keyboard.press("Enter")


def _select_exact_matchup(page, frame, event: dict[str, Any]) -> str:
    matchup = frame.get_by_role("combobox", name="Verified matchup", exact=True)
    matchup.wait_for(state="visible", timeout=120000)
    matchup.click()
    options = page.get_by_role("option")
    options.first.wait_for(state="visible", timeout=10000)
    texts = [x.strip() for x in options.all_inner_texts() if x.strip()]
    away = event["away"]
    home = event["home"]

    def norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

    away_tokens = [norm(away.get("name", "")), norm(away.get("short_name", "")), norm(away.get("abbr", ""))]
    home_tokens = [norm(home.get("name", "")), norm(home.get("short_name", "")), norm(home.get("abbr", ""))]
    away_nickname = norm(away.get("name", "")).split(" ")[-1]
    home_nickname = norm(home.get("name", "")).split(" ")[-1]

    chosen = ""
    for text in texts:
        n = norm(text)
        away_ok = any(token and token in n for token in away_tokens) or (away_nickname and away_nickname in n)
        home_ok = any(token and token in n for token in home_tokens) or (home_nickname and home_nickname in n)
        if away_ok and home_ok:
            chosen = text
            break
    page.keyboard.press("Escape")
    if not chosen:
        raise PublicProductionCertFailure(
            f"verified ESPN event {event['event_id']} was not present in public matchup options; saw {texts}"
        )
    _choose(page, matchup, chosen)
    return chosen


def _input_values(frame, label: str) -> list[str]:
    locator = frame.get_by_role("textbox", name=label, exact=True)
    return [locator.nth(i).input_value() for i in range(locator.count())]


def _assert_market_triplets(frame, api_payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _input_values(frame, "Sportsbook / source")
    lines = _input_values(frame, "Passing yards line")
    overs = _input_values(frame, "Over American odds")
    unders = _input_values(frame, "Under American odds")
    timestamps = _input_values(frame, "Price timestamp / note")
    count = min(len(sources), len(lines), len(overs), len(unders), len(timestamps))
    observed = [
        {"source": sources[i], "line": lines[i], "over": overs[i], "under": unders[i], "timestamp": timestamps[i]}
        for i in range(count)
    ]
    if not observed:
        raise PublicProductionCertFailure("Step 10 rendered no market input rows")

    def line_text(value: Any) -> str:
        return f"{float(value):g}"

    for prop in api_payload.get("props") or []:
        expected = (line_text(prop.get("line")), str(int(float(prop.get("over_odds")))), str(int(float(prop.get("under_odds")))))
        matches = [
            row for row in observed
            if row["line"] == expected[0]
            and row["over"] == expected[1]
            and row["under"] == expected[2]
            and "kyre sports api" in row["source"].casefold()
            and "fanduel" in row["source"].casefold()
            and row["timestamp"].strip()
        ]
        if not matches:
            raise PublicProductionCertFailure(
                f"public Step 10 did not render deployed API triplet for athlete {prop.get('official_athlete_id')}: expected={expected} observed={observed}"
            )
    return observed


def run_public_cert(
    *,
    production_url: str = PRODUCTION_URL,
    api_url: str = KYRE_API_URL,
    artifact_dir: str | Path = "artifacts/nfl-passing-yards-public-prod",
) -> dict[str, Any]:
    artifacts = _artifact_dir(artifact_dir)
    health = _wait_for_public_streamlit(production_url)
    event = discover_certifiable_event(api_url)
    api_payload = event["api_payload"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1600})
        try:
            page.goto(production_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120000)
            frame, scan = _find_app_frame(page)
            _assert_no_runtime_error(_body(frame), "initial public app")

            sport = frame.get_by_role("combobox").nth(0)
            _choose(page, sport, "NFL")
            nfl_market = frame.get_by_role("combobox", name="🎯 NFL Market", exact=True)
            nfl_market.wait_for(state="visible", timeout=60000)
            _choose(page, nfl_market, "Passing Yards")

            _wait_text(frame, "KYRE SPORTS API BRIDGE — STEP 10 AUTO MARKET", 120000)
            _set_slate_date(page, frame, event["day"])
            _wait_text(frame, "Verified matchup", 120000)
            chosen_matchup = _select_exact_matchup(page, frame, event)

            _wait_text(frame, "Step 10 — Market Edge + Final Grade", 180000)
            _wait_text(frame, "KYRE SPORTS API MARKET GREEN", 180000)
            body = _body(frame)
            _assert_no_runtime_error(body, "NFL Passing Yards public route")
            if event["event_id"] not in body:
                raise PublicProductionCertFailure(
                    f"public UI did not prove official ESPN event {event['event_id']} after matchup selection"
                )
            if "sportsbook projection influence 0.0%" not in body.casefold() and "sportsbook projection influence: 0.0%" not in body.casefold():
                raise PublicProductionCertFailure("public UI is missing the 0.0% sportsbook projection-influence proof")

            observed = _assert_market_triplets(frame, api_payload)
            screenshot = artifacts / "nfl_passing_yards_public_prod_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "production_url": production_url,
                "api_url": api_url,
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "official_event_id": event["event_id"],
                "slate_day_et": event["day"],
                "matchup": chosen_matchup,
                "api_prop_count": len(api_payload.get("props") or []),
                "observed_step10_rows": observed,
                "projection_weight": 0.0,
                "fuzzy_matching": False,
                "synthetic_ids": False,
                "stake_sizing_enabled": False,
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
                "discovery_diagnostics": event.get("discovery_diagnostics") or [],
            }
            (artifacts / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            print("NFL_PASSING_YARDS_PUBLIC_PRODUCTION_CERT_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(path=str(artifacts / "nfl_passing_yards_public_prod_failure.png"), full_page=True)
                (artifacts / "failure_body.txt").write_text(_body(frame) if "frame" in locals() else "frame unavailable", encoding="utf-8")
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PRODUCTION_URL)
    parser.add_argument("--api-url", default=KYRE_API_URL)
    parser.add_argument("--artifact-dir", default="artifacts/nfl-passing-yards-public-prod")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_public_cert(production_url=args.production_url, api_url=args.api_url, artifact_dir=args.artifact_dir)
