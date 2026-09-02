"""OFF-only one-page diagnostic for official WNBA roster markup.

This probe fetches only the Washington Mystics' official roster page and emits a
small sanitized description of where player identity is present in the raw
server response. It never stores full HTML, headers, cookies, or response bodies.
The purpose is to certify the correct parser seam before changing Step 7G roster
normalization.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from typing import Any

import httpx

REPORT_PATH = Path("step7g-roster-markup-probe.json")
URL = "https://mystics.wnba.com/roster"
KNOWN_PLAYER_ID = "1642785"
KNOWN_PLAYER_NAME = "Sonia Citron"
MAX_SNIPPET = 700

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    enabled = {key: os.getenv(key) for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))}
    if enabled:
        raise RuntimeError(
            "Roster markup probe refuses to run while production switches are enabled: "
            + ", ".join(sorted(enabled))
        )


def _clip(text: str, needle: str) -> str | None:
    index = text.casefold().find(needle.casefold())
    if index < 0:
        return None
    radius = MAX_SNIPPET // 2
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    snippet = text[start:end]
    # Collapse whitespace and redact obvious opaque query values while keeping
    # HTML/data shape readable.
    snippet = re.sub(r"\s+", " ", snippet)
    snippet = re.sub(r"([?&](?:token|key|sig|signature|auth)=[^&\"' ]+)", r"[redacted-query]", snippet, flags=re.I)
    return snippet[:MAX_SNIPPET]


class _MarkupInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.player_anchor_attribute_sets: list[dict[str, str]] = []
        self.script_rows: list[dict[str, Any]] = []
        self._script_attrs: dict[str, str] | None = None
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key): str(value or "") for key, value in attrs}
        if tag.casefold() == "a" and "/player/" in values.get("href", ""):
            # Only retain safe structural attributes. Values are clipped.
            safe: dict[str, str] = {}
            for key, value in values.items():
                lowered = key.casefold()
                if lowered in {"href", "title", "aria-label"} or lowered.startswith("data-"):
                    safe[key] = value[:160]
            if len(self.player_anchor_attribute_sets) < 8:
                self.player_anchor_attribute_sets.append(safe)
        if tag.casefold() == "script":
            self._script_attrs = values
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._script_attrs is not None:
            self._script_parts.append(str(data))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "script" or self._script_attrs is None:
            return
        content = "".join(self._script_parts)
        if KNOWN_PLAYER_ID in content or KNOWN_PLAYER_NAME.casefold() in content.casefold():
            self.script_rows.append(
                {
                    "id": self._script_attrs.get("id") or None,
                    "type": self._script_attrs.get("type") or None,
                    "length": len(content),
                    "contains_known_player_id": KNOWN_PLAYER_ID in content,
                    "contains_known_player_name": KNOWN_PLAYER_NAME.casefold() in content.casefold(),
                    "known_player_id_snippet": _clip(content, KNOWN_PLAYER_ID),
                    "known_player_name_snippet": _clip(content, KNOWN_PLAYER_NAME),
                }
            )
        self._script_attrs = None
        self._script_parts = []


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (compatible; kyre-sports-api/step7g-roster-markup-probe)",
    }
    response = httpx.get(URL, headers=headers, timeout=20.0, follow_redirects=True)
    response.raise_for_status()
    html = response.text

    inspector = _MarkupInspector()
    inspector.feed(html)

    player_href_ids = re.findall(r"(?:https://www\.wnba\.com)?/player/(\d+)", html)
    unique_ids: list[str] = []
    for value in player_href_ids:
        if value not in unique_ids:
            unique_ids.append(value)

    report = {
        "data_type": "wnba_step7g_roster_markup_probe_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "http_status": response.status_code,
        "raw_html_length": len(html),
        "player_href_occurrence_count": len(player_href_ids),
        "unique_player_href_id_count": len(unique_ids),
        "known_player_id_present_raw": KNOWN_PLAYER_ID in html,
        "known_player_name_present_raw": KNOWN_PLAYER_NAME.casefold() in html.casefold(),
        "known_player_id_snippet": _clip(html, KNOWN_PLAYER_ID),
        "known_player_name_snippet": _clip(html, KNOWN_PLAYER_NAME),
        "player_anchor_structural_attributes": inspector.player_anchor_attribute_sets,
        "script_match_count": len(inspector.script_rows),
        "matching_scripts": inspector.script_rows[:8],
        "markers": {
            "next_data_present": "__NEXT_DATA__" in html,
            "next_f_present": "__next_f.push" in html,
            "json_ld_present": "application/ld+json" in html,
            "team_roster_text_present_raw": "Team Roster" in html,
            "ppg_token_present_raw": "PPG" in html,
            "coaching_staff_present_raw": "Coaching Staff" in html,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "full_html_persisted": False,
            "response_headers_persisted": False,
            "cookies_persisted": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
