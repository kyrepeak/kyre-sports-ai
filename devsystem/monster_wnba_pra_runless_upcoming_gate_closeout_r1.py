"""MONSTER WNBA PRA Runless upcoming-only Step 2G production closeout.

Post-merge only. Discovers a FUTURE scheduled WNBA game through the official
WNBA schedule exposed by Kyre Sports API/Vercel, waits for the merged Runless
market-board schedule gate to become live, proves the canonical PickVault
WNBA/PRA route at 390x844, then CAS-writes and independently reads back the
MONSTER frozen-artifact registry. Live/final/historical games are never targets.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping
from urllib.parse import urlencode

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _body_has_forbidden_error, _find_app_frame
from devsystem.frozen_artifact_registry_v1 import validate_registry

API_BASE = "https://kyre-runless-proof.vercel.app"
PRODUCTION_URL = "https://pickvault.streamlit.app"
REPOSITORY = "kyrepeak/kyre-sports-ai"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
FREEZE_TOKEN = "MONSTER_WNBA_PRA_UPCOMING_ONLY_R2_FINAL_CARD_FROZEN"
SEARCH_DAYS = 14
ROLLOUT_SECONDS = 480
POLL_SECONDS = 15
TARGET_ARTIFACTS = (
    "wnba_pra_api_market_bridge_upcoming_only_r1.py",
    "wnba_pra_page1_ultra_stier_v3.py",
    "wnba_pra_hub_v3612.py",
    "runless_v2/wnba_pra_runless_upcoming_gate_r1.py",
    "runless_v2/__init__.py",
    "tests/test_monster_wnba_pra_runless_upcoming_gate_r1.py",
)


class CloseoutFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _team_key(value: Any) -> str:
    text = " ".join(str(value or "").casefold().replace(".", " ").split())
    aliases = {
        "golden state valkyries": "gsv", "gs valkyries": "gsv", "gsv": "gsv",
        "atlanta dream": "atl", "atl dream": "atl", "atl": "atl",
        "new york liberty": "nyl", "ny liberty": "nyl", "nyl": "nyl",
        "las vegas aces": "lva", "lva": "lva",
        "chicago sky": "chi", "chi": "chi", "seattle storm": "sea", "sea": "sea",
        "dallas wings": "dal", "dal": "dal", "phoenix mercury": "phx", "phx": "phx",
        "minnesota lynx": "min", "min": "min", "indiana fever": "ind", "ind": "ind",
        "los angeles sparks": "las", "la sparks": "las", "las": "las",
        "connecticut sun": "con", "con": "con", "washington mystics": "was", "was": "was",
        "portland fire": "por", "por": "por", "toronto tempo": "tor", "tor": "tor",
    }
    return aliases.get(text, text)


def _schedule(day: str) -> dict[str, Any]:
    response = requests.get(
        API_BASE + "/api/v1/wnba/games",
        params={"date": day, "season": 2026},
        headers={"accept": "application/json", "user-agent": "monster-wnba-runless-closeout/1"},
        timeout=25,
    )
    if response.status_code != 200:
        raise CloseoutFailure(f"schedule HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("source") != "WNBA Official Schedule":
        raise CloseoutFailure("official schedule identity mismatch")
    return payload


def discover_future_target() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date()
    for offset in range(SEARCH_DAYS + 1):
        day = (today + timedelta(days=offset)).isoformat()
        payload = _schedule(day)
        for raw in payload.get("games") or []:
            if not isinstance(raw, Mapping):
                continue
            status = raw.get("status") if isinstance(raw.get("status"), Mapping) else {}
            if str(status.get("category") or "").casefold() != "scheduled":
                continue
            start = _utc(raw.get("game_datetime_utc"))
            if start is None or start <= now:
                continue
            away = raw.get("away") if isinstance(raw.get("away"), Mapping) else {}
            home = raw.get("home") if isinstance(raw.get("home"), Mapping) else {}
            return {
                "date": day,
                "game_id": str(raw.get("game_id") or ""),
                "start_utc": start.isoformat(),
                "away": str(away.get("full_name") or away.get("team_tricode") or ""),
                "home": str(home.get("full_name") or home.get("team_tricode") or ""),
            }
    raise CloseoutFailure("no future scheduled WNBA target available; refusing live/final fallback")


def wait_for_production_gate(target: Mapping[str, Any]) -> dict[str, Any]:
    deadline = time.monotonic() + ROLLOUT_SECONDS
    last: Any = None
    pair = frozenset((_team_key(target["away"]), _team_key(target["home"])))
    while time.monotonic() < deadline:
        try:
            response = requests.get(
                API_BASE + "/api/v1/wnba/pra/market-board",
                params={"date": target["date"], "season": 2026},
                headers={"accept": "application/json", "user-agent": "monster-wnba-runless-closeout/1"},
                timeout=35,
            )
            if response.status_code == 200:
                body = response.json()
                last = body
                gate = body.get("pregame_gate") if isinstance(body, Mapping) else None
                if isinstance(gate, Mapping) and gate.get("authority") == "WNBA Official Schedule" and gate.get("rule") == "FUTURE_SCHEDULED_ONLY" and int(gate.get("eligible_games") or 0) >= 1:
                    for offer in body.get("offers") or []:
                        if not isinstance(offer, Mapping):
                            raise CloseoutFailure("production market board offer shape invalid")
                        offer_pair = frozenset((_team_key(offer.get("away_team")), _team_key(offer.get("home_team"))))
                        if offer_pair != pair:
                            raise CloseoutFailure(f"production leaked non-target matchup: {dict(offer)!r}")
                    return dict(body)
        except (requests.RequestException, ValueError):
            pass
        time.sleep(POLL_SECONDS)
    raise CloseoutFailure(f"merged production gate did not converge: last={last!r}")


def prove_streamlit(target: Mapping[str, Any], artifact_dir: Path) -> dict[str, Any]:
    route = PRODUCTION_URL.rstrip("/") + "/?" + urlencode({"sport": "wnba", "market": "pra", "date": target["date"]})
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        try:
            page.goto(route, wait_until="domcontentloaded", timeout=120000)
            frame, scans = _find_app_frame(page, timeout_seconds=120.0)
            deadline = time.monotonic() + 120.0
            body = ""
            while time.monotonic() < deadline:
                body = frame.locator("body").inner_text(timeout=5000)
                forbidden = _body_has_forbidden_error(body)
                if forbidden:
                    raise CloseoutFailure(f"PickVault runtime error marker: {forbidden}")
                folded = body.casefold()
                if "wnba" in folded and ("pra" in folded or "player discovery" in folded):
                    break
                page.wait_for_timeout(500)
                frame, scans = _find_app_frame(page, timeout_seconds=12.0)
            else:
                raise CloseoutFailure(f"PickVault canonical WNBA/PRA route not ready; body={body[:3000]!r}; scans={scans!r}")
            artifact_dir.mkdir(parents=True, exist_ok=True)
            screenshot = artifact_dir / "pickvault-wnba-pra-future-pregame.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {"route": route, "body_marker": "WNBA/PRA", "screenshot": str(screenshot)}
        finally:
            context.close()
            browser.close()


def _git_blob(path: str) -> str:
    completed = subprocess.run(["git", "rev-parse", f"HEAD:{path}"], text=True, capture_output=True, check=False)
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(value) != 40:
        raise CloseoutFailure(f"cannot resolve freeze artifact blob: {path}")
    return value


def _registry_headers(token: str) -> dict[str, str]:
    return {
        "accept": "application/vnd.github+json",
        "authorization": f"Bearer {token}",
        "x-github-api-version": "2022-11-28",
        "user-agent": "monster-wnba-runless-freeze/1",
    }


def _read_registry(token: str) -> tuple[dict[str, Any], str]:
    url = f"https://api.github.com/repos/{REPOSITORY}/contents/{REGISTRY_PATH}"
    response = requests.get(url, params={"ref": REGISTRY_BRANCH}, headers=_registry_headers(token), timeout=30)
    if response.status_code != 200:
        raise CloseoutFailure(f"registry read HTTP {response.status_code}")
    raw = response.json()
    if not isinstance(raw, Mapping) or raw.get("encoding") != "base64":
        raise CloseoutFailure("registry read shape invalid")
    payload = json.loads(base64.b64decode(str(raw["content"])).decode("utf-8"))
    validate_registry(payload)
    return payload, str(raw.get("sha") or "")


def freeze_and_read_back(*, token: str, merged_sha: str) -> dict[str, Any]:
    registry, content_sha = _read_registry(token)
    artifacts = {path: _git_blob(path) for path in TARGET_ARTIFACTS}
    thaw_paths = {path for grant in registry.get("active_thaws", []) for path in (grant.get("files") or {})}
    overlap = sorted(set(artifacts) & thaw_paths)
    if overlap:
        raise CloseoutFailure("freeze overlaps active thaw: " + ",".join(overlap))

    flattened: dict[str, str] = {}
    for entry in (registry.get("entries") or {}).values():
        if isinstance(entry, Mapping):
            flattened.update({str(k): str(v) for k, v in (entry.get("artifacts") or {}).items()})
    conflicts = sorted(path for path, blob in artifacts.items() if path in flattened and flattened[path] != blob)
    if conflicts:
        raise CloseoutFailure("frozen baseline conflict: " + ",".join(conflicts))

    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if existing:
        if dict(existing.get("artifacts") or {}) != artifacts:
            raise CloseoutFailure("freeze token already exists with different artifacts")
        registry_source_main_sha = str(existing.get("source_main_sha") or "")
        readback, _ = _read_registry(token)
        readback_entry = (readback.get("entries") or {}).get(FREEZE_TOKEN)
        if not isinstance(readback_entry, Mapping) or dict(readback_entry.get("artifacts") or {}) != artifacts or str(readback_entry.get("source_main_sha") or "") != registry_source_main_sha:
            raise CloseoutFailure("registry independent read-back mismatch")
        return {
            "revision": readback["revision"],
            "state_hash": readback["state_hash"],
            "frozen_token": FREEZE_TOKEN,
            "merged_sha": merged_sha,
            "registry_source_main_sha": registry_source_main_sha,
            "artifact_count": len(artifacts),
            "idempotent": True,
        }

    updated = deepcopy(registry)
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = merged_sha
    updated["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": merged_sha,
        "artifacts": artifacts,
    }
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    content = base64.b64encode((json.dumps(updated, indent=2, sort_keys=True) + "\n").encode("utf-8")).decode("ascii")
    url = f"https://api.github.com/repos/{REPOSITORY}/contents/{REGISTRY_PATH}"
    response = requests.put(
        url,
        headers=_registry_headers(token),
        json={
            "message": f"registry: freeze {FREEZE_TOKEN}",
            "content": content,
            "sha": content_sha,
            "branch": REGISTRY_BRANCH,
        },
        timeout=45,
    )
    if response.status_code not in {200, 201}:
        raise CloseoutFailure(f"registry CAS write HTTP {response.status_code}: {response.text[:500]}")

    readback, _ = _read_registry(token)
    entry = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    if not isinstance(entry, Mapping) or entry.get("source_main_sha") != merged_sha or dict(entry.get("artifacts") or {}) != artifacts or readback.get("state_hash") != updated["state_hash"]:
        raise CloseoutFailure("registry independent read-back mismatch")
    return {"revision": readback["revision"], "state_hash": readback["state_hash"], "frozen_token": FREEZE_TOKEN, "merged_sha": merged_sha, "artifact_count": len(artifacts), "idempotent": False}


def run(*, artifact_dir: Path) -> dict[str, Any]:
    merged_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip().lower()
    target = discover_future_target()
    market = wait_for_production_gate(target)
    streamlit = prove_streamlit(target, artifact_dir)
    token = str(os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        raise CloseoutFailure("GITHUB_TOKEN required for registry freeze")
    freeze = freeze_and_read_back(token=token, merged_sha=merged_sha)
    result = {
        "status": "GREEN_FROZEN",
        "authority": "MONSTER_ONLY",
        "merged_sha": merged_sha,
        "future_target": target,
        "market_gate": market.get("pregame_gate"),
        "offer_count": len(market.get("offers") or []),
        "streamlit": streamlit,
        "freeze": freeze,
        "api2_state_used": False,
        "live_final_historical_target_used": False,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("MONSTER_WNBA_PRA_RUNLESS_UPCOMING_GATE_GREEN_FROZEN=" + json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="artifacts/monster-wnba-pra-runless-upcoming-gate-r1")
    args = parser.parse_args()
    run(artifact_dir=Path(args.artifact_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
