"""API2 NFL RB/WR render repair Step 4 — public mobile + route verification.

Verification-only browser cert. It never mutates product/runtime state.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

MISSION_STEP = "4/5"
TASK_ID = "nfl-rb-wr-render-repair-step4-mobile-route"
WORKSTREAM = "nfl-rb-wr-render-repair-v1"
EXPECTED_PUBLIC_BASE_URL = "https://pickvault.streamlit.app"
MOBILE_VIEWPORT = (390, 844)
VIEWPORTS = (MOBILE_VIEWPORT, (768, 1024), (1440, 1000))

AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
GITHUB_ACTIONS_FALLBACK = False

ROUTES: dict[str, dict[str, Any]] = {
    "Rushing Yards": {
        "card_selector": ".krush4-card",
        "grid_selector": ".krush4-grid",
        "date_labels": ("📅 Choose NFL slate date",),
        "labels": (
            "Projected Rush Yards",
            "FanDuel Line",
            "Projection − Line",
            "Expected Carries",
            "Expected YPC",
            "Over Price",
        ),
    },
    "Receiving Yards": {
        "card_selector": ".krecv13-card",
        "grid_selector": ".krecv13-grid",
        "date_labels": ("📅 NFL slate date",),
        "labels": (
            "CERTIFIED PROJECTION",
            "Projected Rec Yds",
            "FanDuel Rec Yds",
            "projection influence 0.0%",
        ),
    },
}

_FATAL_MARKERS = (
    "Traceback (most recent call last)",
    "RecursionError:",
    "KeyError:",
    "TypeError:",
    "AttributeError:",
    "ModuleNotFoundError:",
    "This app has encountered an error",
    "Uncaught app exception",
)

_RAW_FALLBACK = re.compile(
    r"(?:^|[^0-9])[-+]?\d+(?:\.\d+)?(?:Projected Rush Yards|FanDuel Line|"
    r"Projected Rec Yds|FanDuel Rec Yds)(?:$|[^A-Za-z])"
)


def route_url(base_url: str, market: str) -> str:
    return base_url.rstrip("/") + "/?" + urlencode(
        {"ks_jump_sport": "NFL", "ks_jump_market": market}
    )


def _next_sunday(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()) % 7)


def _calendar_value(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except Exception:
            pass
    return ""


def _find_date_input(page, market: str):
    labels = tuple(ROUTES[market].get("date_labels") or ())
    for frame in page.frames:
        candidates = [frame.locator('[data-testid="stDateInput"] input')]
        for label in labels:
            candidates.extend(
                [
                    frame.locator(f'input[aria-label="{label}"]'),
                    frame.get_by_label(label, exact=True),
                ]
            )
        candidates.append(frame.locator('input[type="date"]'))
        for locator in candidates:
            try:
                if locator.count() > 0:
                    return locator.first
            except Exception:
                continue
    return None


def _set_cert_slate_date(page, market: str) -> str:
    target = _next_sunday(date.today()).isoformat()
    deadline = time.monotonic() + 20.0
    locator = None
    while time.monotonic() < deadline:
        locator = _find_date_input(page, market)
        if locator is not None:
            break
        page.wait_for_timeout(250)
    if locator is None:
        raise RuntimeError(f"CERT_SLATE_DATE_INPUT_NOT_FOUND:{market}:{target}")

    try:
        current_value = str(locator.input_value() or "").strip()
    except Exception:
        current_value = ""
    if _calendar_value(current_value) == target:
        return target

    try:
        input_type = str(locator.get_attribute("type") or "").strip().lower()
    except Exception:
        input_type = ""
    day_obj = datetime.fromisoformat(target).date()
    attempts = [target]
    if input_type != "date":
        attempts.extend(
            [
                day_obj.strftime("%m/%d/%Y"),
                day_obj.strftime("%Y/%m/%d"),
                day_obj.strftime("%m-%d-%Y"),
            ]
        )

    observations: list[str] = []
    seen: set[str] = set()
    for fill_value in attempts:
        if fill_value in seen:
            continue
        seen.add(fill_value)
        try:
            current = _find_date_input(page, market)
            if current is None:
                continue
            current.fill(fill_value)
            current.press("Enter")
            page.keyboard.press("Tab")
        except Exception as exc:
            observations.append(f"{fill_value}:{type(exc).__name__}")
            continue

        settle = time.monotonic() + 10.0
        last = ""
        while time.monotonic() < settle:
            page.wait_for_timeout(350)
            try:
                refreshed = _find_date_input(page, market)
                if refreshed is None:
                    continue
                last = str(refreshed.input_value() or "").strip()
                if _calendar_value(last) == target:
                    return target
            except Exception:
                pass
        observations.append(f"{fill_value}:{last}")

    raise RuntimeError(
        f"CERT_SLATE_DATE_NOT_SET:{market}:{target}:" + "|".join(observations[:6])
    )


def raw_text_fallback_detected(text: str) -> bool:
    return _RAW_FALLBACK.search(str(text or "")) is not None


def card_style_is_styled(style: dict[str, Any]) -> bool:
    if int(style.get("count") or 0) < 1:
        return False
    border_style = str(style.get("border_style") or "").lower()
    border_width = str(style.get("border_width") or "").strip().lower()
    radius = str(style.get("border_radius") or "").strip().lower()
    image = str(style.get("background_image") or "").strip().lower()
    color = str(style.get("background_color") or "").strip().lower()
    border_ok = border_style not in {"", "none", "hidden"} and border_width not in {"", "0", "0px"}
    radius_ok = radius not in {"", "0", "0px"}
    background_ok = image not in {"", "none"} or color not in {
        "", "transparent", "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)"
    }
    return border_ok and radius_ok and background_ok


def _production_base_url() -> str:
    payload = json.loads(Path("devsystem/production_targets_v1.json").read_text())
    streamlit = payload.get("streamlit") or {}
    url = str(streamlit.get("url") or "").rstrip("/")
    if url != EXPECTED_PUBLIC_BASE_URL:
        raise RuntimeError(
            f"PUBLIC_TARGET_DRIFT:expected={EXPECTED_PUBLIC_BASE_URL}:observed={url}"
        )
    return url


def _all_frame_text(page) -> str:
    chunks: list[str] = []
    for frame in page.frames:
        try:
            text = frame.locator("body").inner_text(timeout=1500)
        except Exception:
            continue
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _fatal_marker(text: str) -> str | None:
    for marker in _FATAL_MARKERS:
        if marker in text:
            return marker
    return None


def _streamlit_busy(page) -> bool:
    for frame in page.frames:
        try:
            stop = frame.get_by_role("button", name="Stop")
            if stop.count() > 0 and stop.first.is_visible():
                return True
        except Exception:
            pass
    return False


def _first_frame_with(page, selector: str):
    for frame in page.frames:
        try:
            if frame.locator(selector).count() > 0:
                return frame
        except Exception:
            pass
    return None


def _card_text(frame, selector: str) -> str:
    try:
        values = frame.locator(selector).all_inner_texts()
    except Exception:
        return ""
    return "\n".join(str(value or "") for value in values if str(value or "").strip())


def _root_overflow(page) -> tuple[bool, str]:
    worst = 0
    samples: list[str] = []
    for frame in page.frames:
        try:
            dims = frame.locator("html").evaluate(
                """e => ({
                    sw: document.documentElement.scrollWidth,
                    cw: document.documentElement.clientWidth,
                    bw: document.body ? document.body.scrollWidth : 0,
                    iw: window.innerWidth
                })"""
            )
        except Exception:
            continue
        sw = max(int(dims.get("sw") or 0), int(dims.get("bw") or 0))
        cw = max(int(dims.get("cw") or 0), int(dims.get("iw") or 0))
        worst = max(worst, sw - cw)
        samples.append(f"{sw}/{cw}")
    return worst > 8, f"worst_delta={worst};frames={','.join(samples[:4])}"


def _card_style(frame, selector: str) -> dict[str, Any]:
    loc = frame.locator(selector)
    count = loc.count()
    if count < 1:
        return {"count": 0}
    style = loc.first.evaluate(
        """e => {
            const s = getComputedStyle(e);
            return {
                border_style: s.borderTopStyle,
                border_width: s.borderTopWidth,
                border_radius: s.borderTopLeftRadius,
                background_image: s.backgroundImage,
                background_color: s.backgroundColor,
                display: s.display
            };
        }"""
    )
    style["count"] = count
    return style


def _grid_style(frame, selector: str) -> dict[str, Any]:
    loc = frame.locator(selector)
    count = loc.count()
    if count < 1:
        return {"count": 0}
    style = loc.first.evaluate(
        """e => {
            const s = getComputedStyle(e);
            return {
                display: s.display,
                grid_template_columns: s.gridTemplateColumns,
                column_gap: s.columnGap,
                row_gap: s.rowGap
            };
        }"""
    )
    style["count"] = count
    return style


def _wait_for_cards(page, market: str, timeout_seconds: float = 55.0):
    cfg = ROUTES[market]
    deadline = time.monotonic() + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        last = _all_frame_text(page)
        fatal = _fatal_marker(last)
        if fatal:
            raise RuntimeError(f"FATAL_RENDER:{market}:{fatal}")
        frame = _first_frame_with(page, cfg["card_selector"])
        if frame is not None and not _streamlit_busy(page):
            return frame, last
        time.sleep(0.35)
    sample = " ".join(last.split())[:900]
    raise RuntimeError(f"CARD_NOT_READY:{market}:{sample}")


def _verify_route_viewport(page, base_url: str, market: str, viewport: tuple[int, int]) -> dict[str, Any]:
    width, height = viewport
    cfg = ROUTES[market]
    page.set_viewport_size({"width": width, "height": height})
    page.goto(route_url(base_url, market), wait_until="domcontentloaded", timeout=120_000)
    cert_slate_date = _set_cert_slate_date(page, market)
    frame, _ = _wait_for_cards(page, market)
    page_text = _all_frame_text(page)
    text = _card_text(frame, cfg["card_selector"]) or page_text

    fatal = _fatal_marker(page_text)
    if fatal:
        raise RuntimeError(f"FATAL_RENDER:{market}:{width}:{fatal}")
    missing = [label for label in cfg["labels"] if label not in text]
    if missing:
        raise RuntimeError(f"LABELS_MISSING:{market}:{width}:{','.join(missing)}")
    if raw_text_fallback_detected(text):
        raise RuntimeError(f"RAW_TEXT_FALLBACK:{market}:{width}")

    card = _card_style(frame, cfg["card_selector"])
    if not card_style_is_styled(card):
        raise RuntimeError(f"CARD_UNSTYLED:{market}:{width}:{json.dumps(card, sort_keys=True)}")
    grid = _grid_style(frame, cfg["grid_selector"])
    if str(grid.get("display") or "") != "grid":
        raise RuntimeError(f"GRID_NOT_STYLED:{market}:{width}:{json.dumps(grid, sort_keys=True)}")

    overflow, detail = _root_overflow(page)
    if overflow:
        raise RuntimeError(f"ROOT_OVERFLOW:{market}:{width}:{detail}")

    columns = str(grid.get("grid_template_columns") or "").split()
    if width <= 760 and len(columns) != 1:
        raise RuntimeError(f"MOBILE_GRID_NOT_SINGLE_COLUMN:{market}:{grid.get('grid_template_columns')}")
    if width >= 1000 and len(columns) < 2:
        raise RuntimeError(f"DESKTOP_GRID_NOT_MULTI_COLUMN:{market}:{grid.get('grid_template_columns')}")

    return {
        "market": market,
        "viewport": [width, height],
        "cert_slate_date": cert_slate_date,
        "card_count": int(card["count"]),
        "card_style": card,
        "grid_style": grid,
        "raw_text_fallback": False,
        "root_overflow": False,
        "status": "GREEN",
    }


def run_public_cert(*, headless: bool = True) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    base_url = _production_base_url()
    results: list[dict[str, Any]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            for market in ("Rushing Yards", "Receiving Yards"):
                for viewport in VIEWPORTS:
                    width, height = viewport
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        ignore_https_errors=False,
                    )
                    try:
                        page = context.new_page()
                        page.set_default_timeout(5_000)
                        results.append(
                            _verify_route_viewport(page, base_url, market, viewport)
                        )
                    finally:
                        context.close()
        finally:
            browser.close()

    mobile = [row for row in results if tuple(row["viewport"]) == MOBILE_VIEWPORT]
    if len(mobile) != 2 or any(row["status"] != "GREEN" for row in mobile):
        raise RuntimeError("MOBILE_PROOF_INCOMPLETE")
    return {
        "status": "GREEN",
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "step": MISSION_STEP,
        "public_base_url": base_url,
        "route_count": 2,
        "viewport_count": len(VIEWPORTS),
        "fresh_browser_context_count": len(results),
        "mobile_routes_green": len(mobile),
        "results": results,
        "product_runtime_mutations": 0,
        "github_actions_fallback": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", action="store_true", help="Run live public Playwright proof")
    args = parser.parse_args(argv)
    if not args.public:
        print(json.dumps({
            "status": "GREEN",
            "task_id": TASK_ID,
            "step": MISSION_STEP,
            "mode": "STATIC_CONTRACT",
            "product_runtime_mutations": 0,
        }, sort_keys=True))
        return 0
    result = run_public_cert()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
