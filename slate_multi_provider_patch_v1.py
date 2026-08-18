"""Global MLB Slate sportsbook transport patch.

Installs SportsGameOdds-primary / Odds-API.io-fallback transport underneath the
existing Slate V20.8/V20.9 UI without changing any projection, no-vig, freshness,
ranking, or simulation math. This app-shell patch makes routing independent of
which V20.9 wrapper is imported by the inherited Streamlit shell.
"""
from __future__ import annotations

import requests

import slate_hub_v205 as base205
import slate_hub_v208 as base208
import sportsbook_multi_provider_v1 as multi_odds


def _safe_snapshots_multi(games_df, api_key=None, bookmakers=None):
    try:
        return multi_odds.snapshots_for_games_multi(games_df, fallback=True)
    except requests.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            raise RuntimeError(
                "Sportsbook provider rejected a saved API key. Check SPORTSGAMEODDS_API_KEY; Odds-API.io remains the fallback."
            ) from None
        if status == 429:
            raise RuntimeError(
                "Available sportsbook providers are temporarily rate-limited. Cached markets remain untouched; retry after the provider reset."
            ) from None
        raise RuntimeError(
            f"Sportsbook provider is temporarily unavailable (HTTP {status or 'error'})."
        ) from None
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError(
            "Sportsbook feed could not refresh right now. No API key or market line was exposed or fabricated."
        ) from None


def install():
    base205._safe_snapshots = _safe_snapshots_multi
    base208._raw_get_api_key = lambda: (
        multi_odds.get_sgo_api_key() or multi_odds.get_legacy_api_key()
    )
    base208.get_bookmakers = multi_odds.get_display_bookmakers
