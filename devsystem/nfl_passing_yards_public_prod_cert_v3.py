"""Browser-hardened wrapper for the NFL Passing Yards public production cert.

V3 changes certification mechanics only. Production/runtime code is untouched.
It keeps V2's ESPN transport hardening while making the Playwright proof follow
the public page's actual behavior:

* accept the page's own automatic next-verified-slate selection only when the
  rendered ET SLATE label proves the exact ESPN calendar day;
* accept the page's own default matchup only when Step 1 already renders the
  exact official ESPN event ID discovered before browser navigation;
* otherwise use exact date/matchup controls with frame-safe fallbacks.

The cert remains read-only and still requires the exact ESPN event identity,
fresh Kyre Sports API / FanDuel Passing Yards line + two-way prices, 0.0%
sportsbook projection influence, no fuzzy/synthetic IDs, and stake sizing OFF.
"""
from __future__ import annotations

from datetime import datetime
import json
import re
import time
from typing import Any

import nfl_passing_yards_public_prod_cert_v1 as base
import nfl_passing_yards_public_prod_cert_v2 as transport


def _rendered_slate_is_exact(frame, target: str) -> bool:
    try:
        body = base._body(frame)
    except Exception:
        return False
    # The compact status block renders the selected day immediately above
    # "ET SLATE". Do not treat a date mentioned only in an informational message
    # as proof that the widget actually selected that day.
    return re.search(rf"(?m)(?:^|\n){re.escape(target)}\s*\nET SLATE(?:\n|$)", body) is not None


def _date_input(frame):
    candidates = [
        frame.locator('[data-testid="stDateInput"] input'),
        frame.locator('input[aria-label="NFL Passing Yards slate date"]'),
        frame.get_by_label("NFL Passing Yards slate date", exact=True),
        frame.locator('input[type="date"]'),
    ]
    for locator in candidates:
        try:
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue
    return None


def _calendar_value(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except Exception:
            pass
    return ""


def _set_slate_date_exact(page, frame, day: str) -> None:
    target = datetime.fromisoformat(day).date().isoformat()

    # The Passing Yards page deliberately auto-opens the next verified NFL slate
    # when today has no games. If it already landed on the exact ESPN day, that is
    # stronger production evidence than mutating the date widget again.
    if _rendered_slate_is_exact(frame, target):
        print("PUBLIC_CERT_DATE_GREEN " + json.dumps({"mode": "public-auto-slate", "target": target}, sort_keys=True))
        return

    date_input = _date_input(frame)
    if date_input is None:
        # Log the visible input surface so a future Streamlit DOM change is easy
        # to diagnose without weakening the exact-date requirement.
        diagnostics: list[dict[str, str]] = []
        try:
            for i in range(min(frame.locator("input").count(), 25)):
                item = frame.locator("input").nth(i)
                diagnostics.append(
                    {
                        "type": str(item.get_attribute("type") or ""),
                        "aria": str(item.get_attribute("aria-label") or ""),
                        "placeholder": str(item.get_attribute("placeholder") or ""),
                        "value": str(item.input_value() or ""),
                    }
                )
        except Exception:
            pass
        raise base.PublicProductionCertFailure(
            "NFL Passing Yards slate-date input was not found and rendered ET slate did not equal target; inputs="
            + json.dumps(diagnostics, sort_keys=True)
        )

    input_type = str(date_input.get_attribute("type") or "").strip().lower()
    placeholder = str(date_input.get_attribute("placeholder") or "").strip()
    before = str(date_input.input_value() or "").strip()
    print(
        "PUBLIC_CERT_DATE_INPUT "
        + json.dumps(
            {"type": input_type, "placeholder": placeholder, "before": before, "target": target},
            sort_keys=True,
        )
    )

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

    seen: set[str] = set()
    observations: list[dict[str, str]] = []
    for fill_value in attempts:
        if fill_value in seen:
            continue
        seen.add(fill_value)
        try:
            current = _date_input(frame)
            if current is None:
                continue
            current.fill(fill_value)
            current.press("Enter")
            page.keyboard.press("Tab")
        except Exception as exc:
            observations.append({"fill": fill_value, "error": f"{type(exc).__name__}: {exc}"[:220]})
            continue

        deadline = time.monotonic() + 7.0
        last_value = ""
        while time.monotonic() < deadline:
            page.wait_for_timeout(350)
            if _rendered_slate_is_exact(frame, target):
                print(
                    "PUBLIC_CERT_DATE_GREEN "
                    + json.dumps({"mode": "widget", "fill": fill_value, "target": target}, sort_keys=True)
                )
                return
            try:
                refreshed = _date_input(frame)
                if refreshed is not None:
                    last_value = str(refreshed.input_value() or "").strip()
            except Exception:
                pass
        observations.append({"fill": fill_value, "observed": last_value})

    raise base.PublicProductionCertFailure(
        "public slate-date control did not settle on exact ESPN date "
        + target
        + "; observations="
        + json.dumps(observations, sort_keys=True)
    )


def _visible_option_texts(page, frame) -> tuple[Any, list[str]]:
    """Return the option locator from the actual portal owner plus visible text."""
    deadline = time.monotonic() + 12.0
    last: list[str] = []
    while time.monotonic() < deadline:
        for owner in (frame, page):
            try:
                options = owner.get_by_role("option")
                texts = [text.strip() for text in options.all_inner_texts() if text.strip()]
                if texts:
                    return options, texts
                last = texts
            except Exception:
                pass
        page.wait_for_timeout(250)
    return frame.get_by_role("option"), last


def _exact_event_already_rendered(frame, event_id: str) -> bool:
    try:
        body = base._body(frame)
    except Exception:
        return False
    # Step 1's official identity banner is the authority, not team-name text.
    return re.search(rf"\bESPN event\s+{re.escape(str(event_id))}\b", body, flags=re.IGNORECASE) is not None


def _select_exact_matchup_frame_safe(page, frame, event: dict[str, Any]) -> str:
    event_id = str(event["event_id"])
    matchup = frame.get_by_role("combobox", name="Verified matchup", exact=True)
    matchup.wait_for(state="visible", timeout=120000)

    # Public production defaults to the first verified matchup on the selected
    # slate. If Step 1 already proves the exact official event, do not reopen the
    # selectbox merely for automation's sake.
    if _exact_event_already_rendered(frame, event_id):
        try:
            selected = str(matchup.input_value() or "").strip()
        except Exception:
            selected = ""
        chosen = selected or f"{(event.get('away') or {}).get('abbr', '')} @ {(event.get('home') or {}).get('abbr', '')}"
        print(
            "PUBLIC_CERT_MATCHUP_GREEN "
            + json.dumps({"mode": "public-default", "event_id": event_id, "option": chosen}, sort_keys=True)
        )
        return chosen

    matchup.click()
    options, texts = _visible_option_texts(page, frame)

    away = event["away"]
    home = event["home"]

    def norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()

    away_tokens = [norm(away.get("name", "")), norm(away.get("short_name", "")), norm(away.get("abbr", ""))]
    home_tokens = [norm(home.get("name", "")), norm(home.get("short_name", "")), norm(home.get("abbr", ""))]
    away_nickname = norm(away.get("name", "")).split(" ")[-1]
    home_nickname = norm(home.get("name", "")).split(" ")[-1]

    chosen_index = -1
    chosen = ""
    for index, text in enumerate(texts):
        candidate = norm(text)
        away_ok = any(token and token in candidate for token in away_tokens) or (away_nickname and away_nickname in candidate)
        home_ok = any(token and token in candidate for token in home_tokens) or (home_nickname and home_nickname in candidate)
        if away_ok and home_ok:
            chosen_index = index
            chosen = text
            break

    if chosen_index < 0:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        raise base.PublicProductionCertFailure(
            f"verified ESPN event {event_id} was not present in public matchup options; saw {texts}"
        )

    try:
        options.nth(chosen_index).click()
    except Exception:
        base._choose(page, matchup, chosen)
    print(
        "PUBLIC_CERT_MATCHUP_GREEN "
        + json.dumps({"mode": "selectbox", "event_id": event_id, "option": chosen}, sort_keys=True)
    )
    return chosen


def run_public_cert(**kwargs):
    original_date = base._set_slate_date
    original_matchup = base._select_exact_matchup
    original_discover = base.discover_certifiable_event

    def discover_with_diagnostic(api_url: str, *, days: int = base.MAX_DISCOVERY_DAYS):
        event = original_discover(api_url, days=days)
        print(
            "PUBLIC_CERT_EXACT_EVENT "
            + json.dumps(
                {
                    "event_id": event.get("event_id"),
                    "day": event.get("day"),
                    "away": (event.get("away") or {}).get("abbr"),
                    "home": (event.get("home") or {}).get("abbr"),
                },
                sort_keys=True,
            )
        )
        return event

    base._set_slate_date = _set_slate_date_exact
    base._select_exact_matchup = _select_exact_matchup_frame_safe
    base.discover_certifiable_event = discover_with_diagnostic
    try:
        return transport.run_public_cert(**kwargs)
    finally:
        base._set_slate_date = original_date
        base._select_exact_matchup = original_matchup
        base.discover_certifiable_event = original_discover


if __name__ == "__main__":
    args = base._parse_args()
    run_public_cert(
        production_url=args.production_url,
        api_url=args.api_url,
        artifact_dir=args.artifact_dir,
    )
