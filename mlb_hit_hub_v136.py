"""MLB 1+ Hit UI V13.6 — Step 3 official batter-vs-pitcher history.

Presentation/context-only wrapper around the verified V13.5/V13.4/V13.3 Top-5
scanner. Hit Model V13 probability math, Monte Carlo, full-slate candidate pool,
lineup handling, ranking, calibration and persistence are unchanged.

Step 3 adds official MLB batter-vs-current-probable-starter history to each Top-5
card. The lookup uses MLB Stats API's vsPlayer stat type with the exact batter and
starter IDs already carried by the verified modeled result. Career-total history is
shown when MLB returns vsPlayerTotal; the selected-season split is shown when
available. Missing or zero-sample history is labeled explicitly and never invented.
"""
from __future__ import annotations

from html import escape

import requests
import streamlit as st

import mlb_hit_hub_v135 as prior

active = prior.active
core = prior.core
visual = prior.prior

UI_VERSION = "V13.6"
MLB_API = "https://statsapi.mlb.com/api/v1"
_HEADERS = {"User-Agent": "KyreSportsAI/1.0"}


def _safe_id(value):
    return prior._safe_id(value)


def _selected_season():
    return prior._selected_season()


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


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
        "bb": _to_int(stat.get("baseOnBalls")),
        "so": _to_int(stat.get("strikeOuts")),
        "rbi": _to_int(stat.get("rbi")),
    }


def _first_stat(group):
    splits = (group or {}).get("splits") or []
    for split in splits:
        stat = (split or {}).get("stat") or {}
        if stat:
            return stat
    return {}


@st.cache_data(ttl=900, show_spinner=False)
def _official_bvp(batter_id, pitcher_id, season_year):
    """Return MLB vsPlayer season + total history for display only."""
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

        # MLB commonly returns both vsPlayer and vsPlayerTotal. On older payload
        # shapes, preserve whatever valid stat line was returned rather than fail.
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
    except (TypeError, ValueError):
        text = str(value or "").strip()
        if not text or text in {"-", ".---"}:
            return "—"
        return text


def _bvp_summary(label, row):
    row = row or {}
    ab = _to_int(row.get("ab"))
    hits = _to_int(row.get("hits"))
    if ab <= 0:
        return None
    pieces = [f"{label}: {hits}-for-{ab} ({_fmt_avg(row.get('avg'))})"]
    hr = _to_int(row.get("hr"))
    so = _to_int(row.get("so"))
    bb = _to_int(row.get("bb"))
    if hr:
        pieces.append(f"{hr} HR")
    if so:
        pieces.append(f"{so} K")
    if bb:
        pieces.append(f"{bb} BB")
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
        sub = "No prior batter-vs-current-starter sample is being inferred."
        sample_class = " hit136-empty"
    else:
        main = career_text or season_text
        secondary = season_text if career_text and season_text and season_text != career_text else None
        shown = career if career_text else season_row
        ab = _to_int(shown.get("ab"))
        caution = "Small sample" if 0 < ab < 10 else "Recorded sample"
        sub_parts = []
        if secondary:
            sub_parts.append(secondary)
        sub_parts.append(caution)
        sub = " • ".join(sub_parts)
        sample_class = ""

    return (
        f'<div class="hit136-bvp{sample_class}">'
        '<div class="hit136-bvp-head">BATTER VS PITCHER • OFFICIAL MLB HISTORY</div>'
        f'<div class="hit136-bvp-main">{escape(str(main))}</div>'
        f'<div class="hit136-bvp-sub">{escape(str(sub))}</div>'
        '</div>'
    )


_EXTRA_CSS = r"""
<style>
.hit136-bvp{margin:6px 0 5px;padding:7px 9px;border:1px solid #1d4a48;background:linear-gradient(145deg,#071b1d,#081722);border-radius:11px}
.hit136-bvp-head{font-size:.43rem;letter-spacing:.08em;color:#57d6c4;font-weight:950;text-transform:uppercase}
.hit136-bvp-main{font-size:.61rem;color:#eefaf8;font-weight:900;line-height:1.45;margin-top:2px}
.hit136-bvp-sub{font-size:.49rem;color:#8ba8a7;line-height:1.4;margin-top:2px}.hit136-empty{border-color:#344753;background:#0a1720}.hit136-empty .hit136-bvp-head{color:#8397a5}.hit136-empty .hit136-bvp-main{color:#c6d2d9}
</style>
"""

if "hit136-bvp" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _pick_html_v136(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if result.get("lineup_confirmed") else "🕒 PROJECTED"
    player_name = result.get("player_name")
    team_name = result.get("team")

    player_img = visual._img(
        visual.mlb_player_headshot_url(result.get("player_id")),
        "hit134-photo",
        player_name,
    )
    team_img = visual._img(
        visual.mlb_team_logo_url(result.get("team_id")),
        "hit134-team-logo",
        team_name,
    )
    identity = (
        '<div class="hit134-identity">'
        f'{player_img}'
        '<div class="hit134-copy">'
        f'<div class="hit-pick-name">{core._e(player_name)}</div>'
        f'<div class="hit-pick-meta">{core._e(team_name)} vs {core._e(result.get("opponent"))}<br>'
        f'vs {core._e(result.get("starter_name"))} • Bat #{core._e(result.get("position"))} • {core._e(result.get("first_pitch"))}</div>'
        '<div class="hit134-source">MLB batter + team identity</div>'
        '</div>'
        f'{team_img}'
        '</div>'
    )

    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank} • {source}</div>'
        f'{identity}'
        f'{prior._pitcher_strip(result)}'
        f'{_bvp_strip(result)}'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}<br>'
        f'90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{core._e(result.get("confidence","—"))}</div>'
        '</div>'
    )


# Replace only the active V13.3 Top-5 HTML renderer. BvP is context-only and is
# intentionally not added to prescreen/deep_scan/ranking/calibration inputs.
active._pick_html = _pick_html_v136


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.caption(
        "⚔️ Hit UI V13.6 • Step 3 official batter-vs-pitcher history ACTIVE • "
        "presentation/context only • Hit Model V13 unchanged"
    )
    return active.render_hit_hub(games_df, section_header, status_info, team_logo, h)
