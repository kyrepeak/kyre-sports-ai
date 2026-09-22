"""MLB H+R+RBI V1.0.5 — Step 3 official batter-vs-pitcher history.

Presentation/context-only wrapper around verified H+R+RBI V1.0.4. The Strongest
2+ cards retain Steps 1-2 (batter/team identity + fail-safe opposing starter) and
add official MLB batter-vs-current-probable-starter history.

The lookup mirrors the verified MLB 1+ Hit Step-3 path: MLB Stats API `vsPlayer`
using the exact batter and starter IDs already present in the modeled result. Career
history and selected-season history are shown when returned. Small samples are
explicitly labeled and missing/zero-sample history is never inferred.

No H/R/RBI component rate, candidate pool, lineup rule, finalist selection,
Monte Carlo simulation, threshold probability, ranking, confidence or fair-odds
math is changed. The Step-3 strip is fully fail-safe: if the optional display lookup
or renderer fails, the verified V1.0.4 card still renders unchanged.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import mlb_hrrbi_hub_v104 as prior

MODEL_VERSION = "H+R+RBI V1.0.5"
base = prior.base
core = prior.core
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "KyreSportsAI/1.0"}


def _safe_id(value):
    return prior._safe_id(value)


def _selected_season():
    return prior._selected_season()


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _first_stat(group):
    splits = (group or {}).get("splits") or []
    for split in splits:
        stat = (split or {}).get("stat") or {}
        if stat:
            return stat
    return {}


def _stat_line(stat):
    stat = stat or {}
    ab = _to_int(stat.get("atBats"))
    hits = _to_int(stat.get("hits"))
    avg = stat.get("avg")
    if (avg is None or str(avg).strip() in {"", "-", ".---"}) and ab > 0:
        avg = f"{hits / ab:.3f}"
    return {
        "games": _to_int(stat.get("gamesPlayed")),
        "pa": _to_int(stat.get("plateAppearances")),
        "ab": ab,
        "hits": hits,
        "avg": avg,
        "doubles": _to_int(stat.get("doubles")),
        "triples": _to_int(stat.get("triples")),
        "hr": _to_int(stat.get("homeRuns")),
        "rbi": _to_int(stat.get("rbi")),
        "bb": _to_int(stat.get("baseOnBalls")),
        "so": _to_int(stat.get("strikeOuts")),
    }


@st.cache_data(ttl=900, show_spinner=False)
def _official_bvp(batter_id, pitcher_id, season_year):
    """Official MLB batter-vs-pitcher history for display only."""
    bid = _safe_id(batter_id)
    pid = _safe_id(pitcher_id)
    if bid is None or pid is None:
        return {"season": {}, "career": {}, "source": "MLB Stats"}

    try:
        r = requests.get(
            f"{MLB_API}/people/{bid}/stats",
            params={
                "stats": "vsPlayer",
                "group": "hitting",
                "opposingPlayerId": pid,
                "season": int(season_year),
                "sportId": 1,
            },
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        groups = r.json().get("stats") or []

        season_stat = {}
        career_stat = {}
        fallback_stats = []
        for group in groups:
            stat = _first_stat(group)
            if not stat:
                continue
            fallback_stats.append(stat)
            type_name = str(((group.get("type") or {}).get("displayName") or "")).replace(" ", "").lower()
            if "vsplayertotal" in type_name or ("vsplayer" in type_name and "total" in type_name):
                career_stat = stat
            elif "vsplayer" in type_name:
                season_stat = stat

        # Preserve valid older MLB payload shapes without fabricating a split.
        if not season_stat and fallback_stats:
            season_stat = fallback_stats[0]
        if not career_stat and len(fallback_stats) > 1:
            career_stat = fallback_stats[-1]

        return {
            "season": _stat_line(season_stat),
            "career": _stat_line(career_stat),
            "source": "MLB Stats",
        }
    except Exception:
        return {"season": {}, "career": {}, "source": "MLB Stats"}


def _fmt_avg(value):
    try:
        x = float(value)
        return f"{x:.3f}".lstrip("0")
    except (TypeError, ValueError, OverflowError):
        text = str(value or "").strip()
        return text if text and text not in {"-", ".---"} else "—"


def _bvp_summary(label, row):
    row = row or {}
    ab = _to_int(row.get("ab"))
    if ab <= 0:
        return None
    hits = _to_int(row.get("hits"))
    pa = _to_int(row.get("pa"))
    hr = _to_int(row.get("hr"))
    rbi = _to_int(row.get("rbi"))
    bb = _to_int(row.get("bb"))
    so = _to_int(row.get("so"))

    pieces = [f"{label}: {hits}-for-{ab} ({_fmt_avg(row.get('avg'))})"]
    if pa and pa != ab:
        pieces.append(f"{pa} PA")
    if hr:
        pieces.append(f"{hr} HR")
    if rbi:
        pieces.append(f"{rbi} RBI")
    if bb:
        pieces.append(f"{bb} BB")
    if so:
        pieces.append(f"{so} K")
    return " • ".join(pieces)


def _bvp_strip(result):
    season_year = _selected_season()
    bvp = _official_bvp(result.get("player_id"), result.get("starter_id"), season_year)
    career = bvp.get("career") or {}
    season_row = bvp.get("season") or {}

    career_text = _bvp_summary("Career", career)
    season_text = _bvp_summary(str(season_year), season_row)

    if not career_text and not season_text:
        main = "No recorded MLB BvP at-bats"
        sub = "No prior batter-vs-current-starter sample is inferred."
        sample_class = " hrr105-empty"
    else:
        main = career_text or season_text
        secondary = season_text if career_text and season_text and season_text != career_text else None
        shown = career if career_text else season_row
        ab = _to_int(shown.get("ab"))
        if 0 < ab < 10:
            sample = "SMALL SAMPLE • descriptive only"
            sample_class = " hrr105-small"
        elif ab < 20:
            sample = "LIMITED SAMPLE • descriptive only"
            sample_class = " hrr105-small"
        else:
            sample = "RECORDED SAMPLE • context only"
            sample_class = ""
        sub_parts = []
        if secondary:
            sub_parts.append(secondary)
        sub_parts.append(sample)
        sub = " • ".join(sub_parts)

    return (
        f'<div class="hrr105-bvp{sample_class}">'
        '<div class="hrr105-bvp-head">STEP 3 • BATTER VS PITCHER • OFFICIAL MLB HISTORY</div>'
        f'<div class="hrr105-bvp-main">{escape(str(main))}</div>'
        f'<div class="hrr105-bvp-sub">{escape(str(sub))}</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hrr105-bvp{margin:7px 0 5px;padding:8px 9px;border:1px solid #1d4a48;background:linear-gradient(145deg,#071b1d,#081722);border-radius:12px}
.hrr105-bvp-head{font-size:.43rem;letter-spacing:.08em;color:#57d6c4;font-weight:950;text-transform:uppercase}
.hrr105-bvp-main{font-size:.61rem;color:#eefaf8;font-weight:900;line-height:1.45;margin-top:3px}
.hrr105-bvp-sub{font-size:.49rem;color:#8ba8a7;line-height:1.4;margin-top:2px}
.hrr105-small{border-color:#6e5b1c;background:linear-gradient(145deg,#1b1808,#081722)}.hrr105-small .hrr105-bvp-head{color:#e9c65a}.hrr105-small .hrr105-bvp-sub{color:#c7b977}
.hrr105-empty{border-color:#344753;background:#0a1720}.hrr105-empty .hrr105-bvp-head{color:#8397a5}.hrr105-empty .hrr105-bvp-main{color:#c6d2d9}
.hrr105-step-badge{display:inline-flex;align-items:center;gap:5px;border:1px solid #2a6078;background:#071d2b;color:#79dfff;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin:0 0 9px}
</style>
"""

if "hrr105-bvp" not in base.CSS:
    base.CSS = base.CSS + _EXTRA_CSS


def _card_v105(r, rank, threshold):
    """Verified Steps 1-2 card first; optional Step 3 can never crash it."""
    html = prior._card_v104(r, rank, threshold)
    try:
        strip = _bvp_strip(r)
        marker = '<div class="hrr-prob">'
        if marker in html and strip:
            return html.replace(marker, strip + marker, 1)
    except Exception:
        pass
    return html


# Card-render seam only. V1.0 candidate/model/simulation/ranking remain untouched.
base._card = _card_v105


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(
        '<div class="hrr105-step-badge">⚔️ H+R+RBI V1.0.5 • Steps 1–3 active • official MLB BvP context</div>',
        unsafe_allow_html=True,
    )
    return core.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
