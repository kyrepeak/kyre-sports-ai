"""Visual V2 Step 6 final interactive certification.

This verifier owns no product behavior. It certifies the already-frozen Visual V2
composition locally on a PR and against the deployed public app after merge.
"""
from __future__ import annotations

import argparse
import math
import re
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


VIEWPORTS = ((390, 900), (768, 1050), (1440, 1050))


def _find(page, selector: str, timeout: float = 240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                loc = frame.locator(selector)
                if loc.count():
                    return frame, loc.first
            except Exception:
                pass
        page.wait_for_timeout(250)
    raise RuntimeError("VISUAL_V2_STEP6_SELECTOR_NOT_READY:" + selector)


def _role(page, kind: str, name: str, timeout: float = 180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                loc = frame.get_by_role(kind, name=name, exact=True)
                if loc.count():
                    return frame, loc.first
            except Exception:
                pass
        page.wait_for_timeout(250)
    raise RuntimeError(f"VISUAL_V2_STEP6_ROLE_NOT_READY:{kind}:{name}")


def _attr_float(locator, name: str) -> float:
    raw = (locator.get_attribute(name) or "").strip()
    return float(raw)


def _wait_attr_change(page, selector: str, attr: str, before: str, timeout: float = 180) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _, loc = _find(page, selector, timeout=2)
            now = (loc.get_attribute(attr) or "").strip()
            if now and now != before:
                return now
        except Exception:
            pass
        page.wait_for_timeout(250)
    raise RuntimeError(f"VISUAL_V2_STEP6_ATTR_DID_NOT_CHANGE:{attr}:{before}")


def _choose_other_segment(page, container_selector: str, state_selector: str, state_attr: str) -> tuple[str, str]:
    _, state = _find(page, state_selector, 120)
    before = (state.get_attribute(state_attr) or "").strip()

    frame, container = _find(page, container_selector, 120)
    buttons = container.locator("button")
    count = buttons.count()
    assert count >= 2, (container_selector, count)

    chosen = None
    for i in range(count):
        button = buttons.nth(i)
        pressed = (button.get_attribute("aria-pressed") or "").lower()
        selected = (button.get_attribute("aria-selected") or "").lower()
        if pressed == "false" or selected == "false":
            chosen = button
            break
    if chosen is None:
        chosen = buttons.nth(count - 1)

    chosen.click(timeout=10000)
    after = _wait_attr_change(page, state_selector, state_attr, before, 180)
    return before, after


def _box(locator):
    box = locator.bounding_box()
    assert box is not None
    return box


def _zero_duration(value: str) -> bool:
    pieces = [piece.strip() for piece in value.split(",") if piece.strip()]
    if not pieces:
        return True
    for piece in pieces:
        if piece.endswith("ms"):
            if abs(float(piece[:-2])) > 1e-6:
                return False
        elif piece.endswith("s"):
            if abs(float(piece[:-1])) > 1e-6:
                return False
        else:
            return False
    return True


def certify(base: str, public: bool) -> None:
    mode = "PUBLIC" if public else "BRANCH"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1080, "height": 1400})
        page = context.new_page()

        landing = base + "/?" + urlencode(
            {"ks_jump_sport": "NFL", "ks_jump_market": "Prop Analytics"}
        )
        deadline = time.monotonic() + (300 if public else 150)
        while True:
            try:
                page.goto(landing, wait_until="domcontentloaded", timeout=120000)
                _, selection = _find(
                    page,
                    '[data-nfl-prop-analytics-step3-selection="v1"]'
                    '[data-prop-selection-state="selected"]'
                    '[data-prop-handoff-state="ready"]',
                    30,
                )
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                page.wait_for_timeout(1000)

        selected_game = (selection.get_attribute("data-prop-selected-game") or "").strip()
        assert selected_game

        page.goto(
            base
            + "/?"
            + urlencode(
                {
                    "ks_jump_sport": "NFL",
                    "ks_jump_market": "Prop Analytics",
                    "ks_pa_page": "matchup",
                    "ks_pa_game": selected_game,
                }
            ),
            wait_until="domcontentloaded",
            timeout=120000,
        )
        roster_frame, _ = _find(
            page,
            '[data-nfl-prop-analytics-page2-unified-roster="v1"]'
            '[data-prop-page2-unified-state="live"]',
            300 if public else 240,
        )
        qb = roster_frame.get_by_role("button", name=re.compile(r"^[A-Z]{2,3} • QB • ")).first
        assert qb.count() == 1
        qb.click(timeout=10000)

        _, open_prop = _role(page, "button", "Open prop page", 180)
        open_prop.click(timeout=10000)

        _, hero = _find(page, '[data-page3-visual-v2-step2="v1"]', 300 if public else 240)
        _, stats = _find(
            page,
            '[data-page3-visual-v2-step3="v1"][data-page3-visual-v2-step3-state="ready"]',
            300 if public else 240,
        )
        _, settings = _find(
            page,
            '[data-page3-visual-v2-step4="v1"][data-page3-visual-v2-step4-state="ready"]',
            300 if public else 240,
        )

        state_selector = '[data-prop-page3-step2-nav-state="ready"]'
        _choose_other_segment(
            page,
            ".st-key-nfl_prop_analytics_page3_step2_history_nav_v1",
            state_selector,
            "data-prop-page3-step2-active-history",
        )
        _choose_other_segment(
            page,
            ".st-key-nfl_prop_analytics_page3_step2_market_nav_v1",
            state_selector,
            "data-prop-page3-step2-active-market",
        )
        print(f"VISUAL_V2_STEP6_{mode}_CONTROLS_GREEN")

        _, hero = _find(page, '[data-page3-visual-v2-step2="v1"]', 180)
        _, stats = _find(
            page,
            '[data-page3-visual-v2-step3="v1"][data-page3-visual-v2-step3-state="ready"]',
            180,
        )
        _, settings = _find(page, '[data-page3-visual-v2-step4="v1"]', 180)
        line_frame, line = _find(
            page,
            '[data-page3-visual-v2-step5="v1"]'
            '[data-page3-visual-v2-step5-region="line-lab"]'
            '[data-page3-visual-v2-step5-state="ready"]',
            240,
        )
        _, live = _find(
            page,
            '[data-page3-visual-v2-step5="v1"]'
            '[data-page3-visual-v2-step5-region="live-recalculation"]'
            '[data-page3-visual-v2-step5-live-state="ready"]',
            240,
        )
        _, chart_marker = _find(
            page,
            '[data-page3-visual-v2-step5="v1"]'
            '[data-page3-visual-v2-step5-region="game-chart"]',
            240,
        )
        _, chart = _find(
            page,
            '.st-key-nfl_prop_visual_v2_step5_game_chart_v1 '
            '.ks-pa5-chart[data-prop-page3-step5-state="ready"]',
            240,
        )

        positions = [_box(x)["y"] for x in (hero, stats, settings, line, live, chart)]
        assert positions == sorted(positions), positions
        assert len({round(y, 1) for y in positions}) == 6, positions

        assert stats.locator('[data-v2-stat-card]').count() == 5
        assert live.locator('[data-v2-live-card]').count() == 4
        assert chart.locator('[data-prop-page3-step5-game]').count() > 0
        print(f"VISUAL_V2_STEP6_{mode}_FULL_COMPOSITION_GREEN")

        history_frame, history_container = _find(
            page, ".st-key-nfl_prop_analytics_page3_step2_history_nav_v1", 120
        )
        _, market_container = _find(
            page, ".st-key-nfl_prop_analytics_page3_step2_market_nav_v1", 120
        )
        for container in (history_container, market_container):
            buttons = container.locator("button")
            assert buttons.count() >= 2
            for i in range(buttons.count()):
                b = _box(buttons.nth(i))
                assert b["height"] >= 43.5, b

        line_container = line_frame.locator(
            ".st-key-nfl_prop_visual_v2_step5_line_lab_v1"
        ).first
        slider = line_container.get_by_role("slider").first
        assert slider.count() == 1
        slider_box = _box(slider)
        assert slider_box["height"] >= 43.5 and slider_box["width"] >= 43.5, slider_box
        print(f"VISUAL_V2_STEP6_{mode}_TOUCH_TARGETS_GREEN")

        focus_button = history_container.locator("button").first
        focus_button.focus()
        page.keyboard.press("Tab")
        focus_style = history_frame.evaluate(
            """() => {
              const e = document.activeElement;
              const s = getComputedStyle(e);
              return {
                tag: e ? e.tagName : "",
                outlineStyle: s.outlineStyle,
                outlineWidth: s.outlineWidth,
                boxShadow: s.boxShadow
              };
            }"""
        )
        assert focus_style["tag"] == "BUTTON", focus_style
        outline_visible = (
            focus_style["outlineStyle"] != "none"
            and float(focus_style["outlineWidth"].replace("px", "") or 0) >= 1
        )
        shadow_visible = focus_style["boxShadow"] not in ("none", "")
        assert outline_visible or shadow_visible, focus_style
        print(f"VISUAL_V2_STEP6_{mode}_KEYBOARD_FOCUS_GREEN")

        normal_transition = history_container.locator("button").first.evaluate(
            "e=>getComputedStyle(e).transitionDuration"
        )
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_timeout(150)
        reduced_transition = history_container.locator("button").first.evaluate(
            "e=>getComputedStyle(e).transitionDuration"
        )
        assert not _zero_duration(normal_transition), normal_transition
        assert _zero_duration(reduced_transition), reduced_transition
        for selector in (
            ".ks-v2-hero-player",
            ".ks-v2-stat-ribbon article",
            ".ks-v2-step5-live article",
        ):
            _, target = _find(page, selector, 60)
            timing = target.evaluate(
                "e=>({t:getComputedStyle(e).transitionDuration,a:getComputedStyle(e).animationDuration})"
            )
            assert _zero_duration(timing["t"]) and _zero_duration(timing["a"]), (selector, timing)
        print(f"VISUAL_V2_STEP6_{mode}_REDUCED_MOTION_GREEN")
        page.emulate_media(reduced_motion="no-preference")

        before_line = _attr_float(line, "data-page3-visual-v2-step5-line")
        minimum = _attr_float(line, "data-page3-visual-v2-step5-min")
        maximum = _attr_float(line, "data-page3-visual-v2-step5-max")
        key = "Home" if math.isclose(before_line, maximum, abs_tol=1e-9) else "End"
        expected = minimum if key == "Home" else maximum
        slider.press(key)

        deadline = time.monotonic() + 180
        changed = False
        while time.monotonic() < deadline:
            try:
                _, new_line = _find(
                    page,
                    '[data-page3-visual-v2-step5-region="line-lab"]'
                    '[data-page3-visual-v2-step5-state="ready"]',
                    3,
                )
                _, new_live = _find(
                    page,
                    '[data-page3-visual-v2-step5-region="live-recalculation"]'
                    '[data-page3-visual-v2-step5-live-state="ready"]',
                    3,
                )
                _, new_chart = _find(
                    page,
                    '.st-key-nfl_prop_visual_v2_step5_game_chart_v1 '
                    '.ks-pa5-chart[data-prop-page3-step5-state="ready"]',
                    3,
                )
                line_value = _attr_float(new_line, "data-page3-visual-v2-step5-line")
                live_value = _attr_float(new_live, "data-page3-visual-v2-step5-live-line")
                chart_value = _attr_float(new_chart, "data-prop-page3-step5-line")
                if (
                    math.isclose(line_value, expected, abs_tol=1e-6)
                    and math.isclose(live_value, expected, abs_tol=1e-6)
                    and math.isclose(chart_value, expected, abs_tol=1e-6)
                    and not math.isclose(line_value, before_line, abs_tol=1e-9)
                ):
                    changed = True
                    break
            except Exception:
                pass
            page.wait_for_timeout(300)
        assert changed, (before_line, expected)
        print(f"VISUAL_V2_STEP6_{mode}_DOWNSTREAM_RECALC_GREEN")

        for width, height in VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(300)
            frame, _ = _find(page, '[data-page3-visual-v2-step2="v1"]', 120)
            dims = frame.evaluate(
                "()=>({i:innerWidth,d:document.documentElement.scrollWidth,b:document.body.scrollWidth})"
            )
            assert max(dims["d"], dims["b"]) <= dims["i"] + 2, (width, dims)

            _, ribbon = _find(page, '[data-page3-visual-v2-step3="v1"]', 120)
            cards = ribbon.locator('[data-v2-stat-card]')
            assert cards.count() == 5
            widths = [_box(cards.nth(i))["width"] for i in range(5)]
            assert max(widths) - min(widths) <= 2.5, (width, widths)

            _, hbox = _find(
                page, ".st-key-nfl_prop_analytics_page3_step2_history_nav_v1", 120
            )
            _, mbox = _find(
                page, ".st-key-nfl_prop_analytics_page3_step2_market_nav_v1", 120
            )
            _, lbox = _find(
                page, ".st-key-nfl_prop_visual_v2_step5_line_lab_v1", 120
            )
            _, live_box = _find(
                page, '[data-page3-visual-v2-step5-region="live-recalculation"]', 120
            )
            _, chart_box = _find(
                page, ".st-key-nfl_prop_visual_v2_step5_game_chart_v1 .ks-pa5-chart", 120
            )

            if width >= 768:
                hb, mb = _box(hbox), _box(mbox)
                assert abs(hb["y"] - mb["y"]) <= 6, (width, hb, mb)
                assert hb["x"] + hb["width"] <= mb["x"] + 6, (width, hb, mb)

                line_value = lbox.locator(".ks-v2-step5-line-value").first
                real_slider = lbox.locator('[data-testid="stSlider"]').first
                lv, rs = _box(line_value), _box(real_slider)
                lv_center = lv["x"] + lv["width"] / 2
                rs_center = rs["x"] + rs["width"] / 2
                assert abs(lv_center - rs_center) <= 14, (width, lv, rs)

                lb, cb = _box(live_box), _box(chart_box)
                assert abs(lb["x"] - cb["x"]) <= 12, (width, lb, cb)
                assert abs(lb["width"] - cb["width"]) <= 18, (width, lb, cb)
                assert lb["y"] + lb["height"] <= cb["y"] + 3, (width, lb, cb)

            print(f"VISUAL_V2_STEP6_{mode}_{width}_GREEN")

        print(f"VISUAL_V2_STEP6_{mode}_ACCESSIBILITY_GREEN")
        print(f"VISUAL_V2_STEP6_{mode}_RESPONSIVE_GREEN")
        print(f"VISUAL_V2_STEP6_{mode}_GREEN")
        context.close()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    certify(args.base_url.rstrip("/"), args.public)


if __name__ == "__main__":
    main()
