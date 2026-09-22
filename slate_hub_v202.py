"""V20.2 Slate safety wrapper.

Prevents placeholder API keys from being treated as connected credentials and
sanitizes sportsbook API failures so secret values are never echoed into the UI.
"""

import requests
import streamlit as st

import slate_hub_v201 as base

MODEL_VERSION = "V20.2"

_original_get_api_key = base.get_api_key
_original_slate_snapshots = base.slate_snapshots_for_games


def _clean_key(value):
    if value is None:
        return None
    key = str(value).strip()
    if not key:
        return None
    upper = key.upper()
    placeholders = (
        "PASTE_YOUR_KEY_HERE",
        "YOUR_API_KEY",
        "YOUR_KEY_HERE",
        "API_KEY_HERE",
    )
    if any(token in upper for token in placeholders):
        return None
    return key


def _safe_get_api_key():
    return _clean_key(_original_get_api_key())


def _safe_snapshots(games_df, api_key, bookmakers):
    try:
        return _original_slate_snapshots(games_df, api_key, bookmakers)
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (401, 403):
            raise RuntimeError(
                "Odds API rejected the saved key. Replace ODDS_API_IO_KEY in Streamlit Secrets with your real key, then save and refresh."
            ) from None
        if status == 429:
            raise RuntimeError(
                "Odds API quota is temporarily exhausted. Odds will resume after the provider resets the free-plan quota."
            ) from None
        raise RuntimeError(
            f"Odds API is temporarily unavailable (HTTP {status or 'error'})."
        ) from None
    except Exception:
        raise RuntimeError("Odds feed could not refresh right now. Your API key was not displayed.") from None


# Patch the V20.1 implementation at runtime. Its render function resolves these
# module globals each time it runs.
base.get_api_key = _safe_get_api_key
base.slate_snapshots_for_games = _safe_snapshots


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    raw = _original_get_api_key()
    key = _clean_key(raw)
    if raw and not key:
        st.error(
            "🔐 Your Streamlit secret still contains the placeholder text `PASTE_YOUR_KEY_HERE`. Open Manage app → Settings → Secrets and replace only that placeholder with your real Odds-API.io key."
        )
    return base.render_slate_hub(games_df, section_header, status_info, team_logo, h)
