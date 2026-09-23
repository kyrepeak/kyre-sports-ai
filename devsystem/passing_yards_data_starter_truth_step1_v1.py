"""Passing Yards Next Phase Step 1 — data completeness + starter availability truth.

Certification-first layer. It audits the existing Passing Yards identity path
against the current official ESPN slate, depth chart, current roster, league
injury feed, and exact-event injury feed.

This file does not change product/model behavior.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import time
from urllib.parse import urlencode

import pandas as pd

import nfl_game_day_availability_v1 as game_day
import nfl_hub_v19 as nfl
import nfl_passing_yards_full_slate_router_v1 as full_slate
import nfl_passing_yards_identity_v1 as identity

MODEL_VERSION = "PASSING YARDS DATA + STARTER TRUTH STEP 1 V1"


class StarterTruthFailure(RuntimeError):
    pass


def _safe(value, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _rank(value) -> int:
    parsed = pd.to_numeric(value, errors="coerce")
    return int(parsed) if pd.notna(parsed) else 99


def audit_team_context(ctx: dict) -> dict:
    """Fail closed if the displayed QB cannot be defended as current starter truth."""
    abbr = _safe(ctx.get("abbr")).upper()
    if not abbr:
        raise StarterTruthFailure("missing team abbreviation")
    if ctx.get("depth_state") != "VERIFIED":
        raise StarterTruthFailure(f"{abbr}: verified ESPN depth chart unavailable")
    if not ctx.get("current_roster_verified"):
        raise StarterTruthFailure(f"{abbr}: current ESPN roster not verified")
    if not ctx.get("identity_verified"):
        raise StarterTruthFailure(f"{abbr}: QB1 identity unresolved")

    selected = dict(ctx.get("qb1") or {})
    selected_id = _safe(selected.get("athlete_id"))
    selected_name = _safe(selected.get("name"))
    if not selected_id or not selected_name:
        raise StarterTruthFailure(f"{abbr}: selected QB missing exact athlete identity")
    if game_day.is_unavailable_status(selected.get("injury_status")):
        raise StarterTruthFailure(
            f"{abbr}: unavailable QB selected as starter: {selected_name} ({_safe(selected.get('injury_status'))})"
        )

    eligible_ids, eligible_names, roster_diag = game_day.current_prop_eligible_keys(abbr)
    if not roster_diag.get("ok"):
        raise StarterTruthFailure(f"{abbr}: current roster provider unhealthy")
    if selected_id not in eligible_ids and selected_name.lower() not in eligible_names:
        raise StarterTruthFailure(f"{abbr}: selected QB not on current active roster: {selected_name}")

    qbs = sorted(
        [dict(row) for row in (ctx.get("qbs") or []) if _safe(row.get("name"))],
        key=lambda row: (_rank(row.get("rank")), _safe(row.get("name"))),
    )
    if not qbs:
        raise StarterTruthFailure(f"{abbr}: verified QB depth room empty")

    depth_qb1 = qbs[0]
    depth_qb1_id = _safe(depth_qb1.get("athlete_id"))
    depth_qb1_name = _safe(depth_qb1.get("name"))
    replacement = bool(
        (depth_qb1_id and selected_id != depth_qb1_id)
        or (not depth_qb1_id and selected_name.lower() != depth_qb1_name.lower())
    )

    skipped_reason = ""
    if replacement:
        top_unavailable = game_day.is_unavailable_status(depth_qb1.get("injury_status"))
        top_roster_ineligible = bool(
            depth_qb1_id not in eligible_ids
            and depth_qb1_name.lower() not in eligible_names
        )
        if not (top_unavailable or top_roster_ineligible):
            raise StarterTruthFailure(
                f"{abbr}: replacement {selected_name} selected without a verified reason to skip depth QB1 {depth_qb1_name}"
            )
        skipped_reason = "unavailable" if top_unavailable else "not-current-active-roster"

    return {
        "team": abbr,
        "starter_athlete_id": selected_id,
        "starter_name": selected_name,
        "starter_injury_status": _safe(selected.get("injury_status"), "No listed injury"),
        "depth_qb1_name": depth_qb1_name,
        "starter_class": "VERIFIED_REPLACEMENT" if replacement else "EXPECTED_DEPTH_QB1",
        "replacement_reason": skipped_reason,
        "depth_source": _safe(ctx.get("depth_source")),
        "roster_http": roster_diag.get("http"),
    }


def audit_window(start_date: str, days: int) -> dict:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    if days < 1 or days > 14:
        raise StarterTruthFailure("days must be between 1 and 14")

    game_rows: list[dict] = []
    team_rows: list[dict] = []
    dates_checked: list[dict] = []

    for offset in range(days):
        day = start + timedelta(days=offset)
        day_str = day.isoformat()
        games, diag = full_slate.load_full_slate(
            day_str,
            primary_loader=nfl.load_nfl_slate,
        )
        expected = int(diag.get("expected_games") or 0)
        actual = int(len(games))
        if expected and actual < expected:
            raise StarterTruthFailure(
                f"{day_str}: incomplete official slate actual={actual} expected={expected}"
            )
        dates_checked.append({
            "date": day_str,
            "games": actual,
            "expected_games": expected,
            "provider": _safe(diag.get("provider")),
            "fallback_used": bool(diag.get("fallback_used")),
        })
        if games.empty:
            continue

        for _, series in games.iterrows():
            game = series.to_dict()
            game_id = _safe(game.get("game_id"))
            if not game_id.isdigit():
                raise StarterTruthFailure(f"{day_str}: invalid official game ID {game_id!r}")

            resolved = identity.resolve_matchup_identity(game, day.year)
            if not resolved.get("injury_feed_ok"):
                raise StarterTruthFailure(f"{game_id}: injury feeds unavailable")
            if not resolved.get("identity_ready"):
                raise StarterTruthFailure(
                    f"{game_id}: starter identity unresolved: {_safe(resolved.get('reason'))}"
                )

            away = audit_team_context(dict(resolved.get("away") or {}))
            home = audit_team_context(dict(resolved.get("home") or {}))
            team_rows.extend((away, home))
            game_rows.append({
                "date": day_str,
                "game_id": game_id,
                "matchup": f"{_safe(game.get('away_team'))} @ {_safe(game.get('home_team'))}",
                "away_abbr": _safe(game.get("away_abbr")).upper(),
                "home_abbr": _safe(game.get("home_abbr")).upper(),
                "away_starter": away["starter_name"],
                "home_starter": home["starter_name"],
                "availability_state": _safe(resolved.get("availability_state"), "UNVERIFIED"),
                "prop_availability_ready": bool(resolved.get("prop_availability_ready")),
            })

    if not game_rows:
        raise StarterTruthFailure(
            f"no NFL games found in {start_date} + {days - 1} day window"
        )

    replacements = [row for row in team_rows if row["starter_class"] == "VERIFIED_REPLACEMENT"]
    return {
        "model_version": MODEL_VERSION,
        "status": "GREEN",
        "start_date": start_date,
        "days": days,
        "dates_checked": dates_checked,
        "games_verified": len(game_rows),
        "team_starters_verified": len(team_rows),
        "verified_replacements": len(replacements),
        "replacements": replacements,
        "games": game_rows,
    }


def _body_text(page) -> str:
    chunks = []
    for frame in page.frames:
        try:
            chunks.append(frame.locator("body").inner_text(timeout=2500))
        except Exception:
            pass
    return "\n".join(chunks)


def _find_frame(page, selector: str, timeout: float = 180.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = _body_text(page)
        if "TypeError" in body or "Traceback" in body:
            raise StarterTruthFailure("public runtime contains TypeError/Traceback")
        for frame in page.frames:
            try:
                if frame.locator(selector).count() >= 1:
                    return frame
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise StarterTruthFailure(f"public selector not ready: {selector}")


def public_proof(base_url: str, audit: dict, artifact_dir: str | Path) -> dict:
    from playwright.sync_api import sync_playwright

    target = audit["games"][0]
    params = {
        "ks_jump_sport": "NFL",
        "ks_jump_market": "Passing Yards",
        "ks_py_date": target["date"],
        "ks_py_matchup": target["matchup"],
    }
    url = base_url.rstrip("/") + "/?" + urlencode(params)
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            frame = _find_frame(page, '[data-passing-yards-mobile-cleanup-runtime="v70"]')
            if frame.locator('[data-passing-yards-v221-runtime="mobile-cleanup-steps2-3"]').count() != 1:
                # Router marker can live in another Streamlit element/frame.
                _find_frame(page, '[data-passing-yards-v221-runtime="mobile-cleanup-steps2-3"]')
            picker_frame = _find_frame(page, '[data-passing-yards-selection-screen="v58"]')
            cards = picker_frame.locator("[data-qb-selection-card]")
            if cards.count() != 2:
                raise StarterTruthFailure(f"public QB picker expected 2 cards, got {cards.count()}")
            card_text = "\n".join(cards.nth(i).inner_text() for i in range(cards.count()))
            for qb in (target["away_starter"], target["home_starter"]):
                if qb not in card_text:
                    raise StarterTruthFailure(f"public QB picker missing verified starter {qb}")
            body = _body_text(page)
            if "TypeError" in body or "Traceback" in body:
                raise StarterTruthFailure("public runtime contains TypeError/Traceback")
            page.screenshot(path=str(artifacts / "passing_yards_step1_starter_truth_public.png"), full_page=True)
        finally:
            browser.close()

    return {
        "status": "GREEN",
        "public_url": base_url,
        "matchup": target["matchup"],
        "date": target["date"],
        "away_starter": target["away_starter"],
        "home_starter": target["home_starter"],
        "v70_marker": True,
        "v221_marker": True,
        "qb_cards": 2,
        "typeerror": False,
        "traceback": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json-out")
    parser.add_argument("--public-url")
    parser.add_argument("--artifact-dir", default="artifacts/passing-yards-starter-truth-step1")
    args = parser.parse_args()

    result = audit_window(args.start_date, args.days)
    if args.public_url:
        result["public_proof"] = public_proof(args.public_url, result, args.artifact_dir)

    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")
    print("PASSING_YARDS_DATA_STARTER_TRUTH_STEP1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
