"""WNBA PRA V3.4 — RotoWire same-day OUT/status supplement.

This module does not replace the official/ESPN availability stack. It adds a
short-lived same-day RotoWire daily-lineups check as a conservative supplement:
explicit OUT/OFS/DOUBTFUL/GTD labels may strengthen a player's status, but an
absence of a RotoWire label never proves that a player is available.

Expected lineups from RotoWire are never treated as confirmed starters.
"""
from __future__ import annotations

from datetime import datetime
import html as html_lib
import re
import unicodedata
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_availability_v33 as availability

ET = ZoneInfo("America/New_York")
ROTOWIRE_LINEUPS = "https://www.rotowire.com/wnba/lineups.php"

_STATUS_RANK = {
    "NO DESIGNATION": 0,
    "ACTIVE": 1,
    "AVAILABLE": 1,
    "PROBABLE": 2,
    "DAY-TO-DAY": 3,
    "QUESTIONABLE": 4,
    "DOUBTFUL": 5,
    "INACTIVE": 6,
    "OUT": 7,
    "STATUS UNVERIFIED": -1,
}


def _plain_text(raw: str) -> str:
    text = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", str(raw or ""))
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _ascii_words(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@st.cache_data(ttl=60, show_spinner=False)
def rotowire_today_snapshot():
    meta = {
        "ok": False,
        "date": "",
        "http": None,
        "text": "",
        "source": "RotoWire WNBA Daily Lineups",
        "error": "",
    }
    try:
        response = requests.get(
            ROTOWIRE_LINEUPS,
            headers={
                "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache",
            },
            timeout=8,
        )
        meta["http"] = int(response.status_code)
        response.raise_for_status()
        plain = _plain_text(response.text)
        match = re.search(
            r"Starting lineups for\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            plain,
            flags=re.I,
        )
        page_day = ""
        if match:
            page_day = pd.to_datetime(match.group(1), errors="coerce")
            page_day = "" if pd.isna(page_day) else page_day.strftime("%Y-%m-%d")
        meta.update({
            "ok": bool(page_day and plain),
            "date": page_day,
            "text": _ascii_words(plain),
        })
    except Exception as exc:
        meta["error"] = f"{type(exc).__name__}: {exc}"[:220]
    return meta


def _name_variants(name: str) -> list[str]:
    full = _ascii_words(name)
    tokens = full.split()
    if not tokens:
        return []
    variants = [full]
    if len(tokens) >= 2:
        variants.append(f"{tokens[0][0]} {' '.join(tokens[1:])}")
    return sorted(set(v for v in variants if v), key=len, reverse=True)


def _rotowire_status(page_text: str, player_name: str) -> str:
    text = str(page_text or "")
    if not text:
        return ""
    for variant in _name_variants(player_name):
        v = re.escape(variant)
        tests = [
            ("OUT", rf"\b{v}\b(?:\s+[a-z0-9]+)?\s+out\b"),
            ("OUT", rf"\b{v}\b(?:\s+[a-z0-9]+)?\s+ofs\b"),
            ("DOUBTFUL", rf"\b{v}\b(?:\s+[a-z0-9]+)?\s+doubtful\b"),
            ("QUESTIONABLE", rf"\b{v}\b(?:\s+[a-z0-9]+)?\s+(?:gtd|questionable)\b"),
        ]
        for status, pattern in tests:
            if re.search(pattern, text, flags=re.I):
                return status
    return ""


def install():
    """Patch V3.3 availability once; keep all existing sources and math."""
    if getattr(availability, "_v34_rotowire_installed", False):
        return

    original_game = availability.availability_for_game
    original_clear = availability.clear_availability_cache

    def availability_for_game_v34(row, stats=None):
        result = original_game(row, stats)
        frame = result.get("players")
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return result

        day_str = availability._day_str(row.get("game_date") or None)
        today_str = datetime.now(ET).strftime("%Y-%m-%d")
        snap = rotowire_today_snapshot() if day_str == today_str else {
            "ok": False, "date": "", "text": "", "source": "RotoWire WNBA Daily Lineups"
        }

        frame = frame.copy()
        matched = []
        if bool(snap.get("ok")) and str(snap.get("date")) == day_str:
            page_text = str(snap.get("text") or "")
            for idx, player in frame.iterrows():
                new_status = _rotowire_status(page_text, str(player.get("PLAYER_NAME") or ""))
                if not new_status:
                    continue
                old_status = str(player.get("DESIGNATION") or "NO DESIGNATION").upper()
                if _STATUS_RANK.get(new_status, 0) >= _STATUS_RANK.get(old_status, -1):
                    frame.at[idx, "DESIGNATION"] = new_status
                    frame.at[idx, "DETAIL"] = "RotoWire daily lineups same-day status"
                    frame.at[idx, "STATUS_SOURCE"] = "RotoWire WNBA Daily Lineups"
                    frame.at[idx, "AVAILABILITY_VERIFIED"] = True
                    frame.at[idx, "PROVIDER_COVERED"] = True
                    matched.append(str(player.get("PLAYER_NAME") or ""))

        result["players"] = frame
        result["rotowire_connected"] = bool(snap.get("ok")) and str(snap.get("date")) == day_str
        result["rotowire_date"] = str(snap.get("date") or "")
        result["rotowire_matches"] = matched
        if result["rotowire_connected"]:
            result["source"] = (
                str(result.get("source") or "WNBA availability")
                + " + RotoWire same-day OUT/status supplement"
            )
        return result

    def clear_availability_cache_v34():
        try:
            rotowire_today_snapshot.clear()
        except Exception:
            pass
        return original_clear()

    availability.availability_for_game = availability_for_game_v34
    availability.clear_availability_cache = clear_availability_cache_v34
    availability._v34_rotowire_installed = True


__all__ = ["install", "rotowire_today_snapshot", "ROTOWIRE_LINEUPS"]
