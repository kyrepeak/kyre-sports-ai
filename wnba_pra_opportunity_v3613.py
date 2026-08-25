"""WNBA PRA V3.6.13 — Precision Step 1 inside each V2.8 Top-5 player card.

Read-only opportunity decomposition. This module patches the existing compact
"Projection Path" presentation helper, not the Top-5 selector/renderer. That
makes Step 1 live inside every player card while preserving the frozen V3.6.11
fail-safe renderer, player order, projections, market grading, Monte Carlo,
qualification and ranking.

Only data already available to the V2.8 role layer is reused. Missing official
tracking metrics remain explicitly unavailable instead of being estimated.
"""
from __future__ import annotations

import html
import math

import pandas as pd

import wnba_role_v28 as role
import wnba_pra_step5_layout_v369 as layout


STEP_VERSION = "PRA V3.6.13 • PRECISION STEP 1 • OPPORTUNITY DECOMPOSITION"
_ORIGINAL_ATTR = "_v3613_original_compact_path_box"
_CACHE = {}


def _esc(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value)
    if x is None:
        return "—"
    return f"{x:.{digits}f}{suffix}"


def _per36(stat, minutes):
    s, m = _num(stat), _num(minutes)
    if s is None or m is None or m <= 0:
        return None
    return 36.0 * s / m


def _norm_name(value) -> str:
    try:
        return role.availability._norm_name(value)
    except Exception:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _norm_team(value) -> str:
    return str(value or "").upper().strip()


def _form_index(frame):
    by_pair, by_name = {}, {}
    if frame is None or getattr(frame, "empty", True):
        return by_pair, by_name
    for _, row in frame.iterrows():
        name = _norm_name(row.get("PLAYER_NAME"))
        if not name:
            continue
        team = _norm_team(row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME"))
        by_pair[(name, team)] = row
        by_name.setdefault(name, row)
    return by_pair, by_name


def _usage_index(frame):
    by_pair, by_name = {}, {}
    if frame is None or getattr(frame, "empty", True):
        return by_pair, by_name
    for _, row in frame.iterrows():
        name = _norm_name(row.get("PLAYER_NAME"))
        if not name:
            continue
        team = _norm_team(row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME"))
        by_pair[(name, team)] = row
        by_name.setdefault(name, row)
    return by_pair, by_name


def _indexes():
    """Build form/usage lookup at most once per Streamlit render."""
    if "indexes" in _CACHE:
        return _CACHE["indexes"]

    try:
        form = role.player_form_table()
    except Exception:
        form = pd.DataFrame()

    usage_source = "Official Advanced USG when available"
    try:
        usage_result = role.advanced_usage_table()
        if isinstance(usage_result, tuple):
            usage = usage_result[0]
            if len(usage_result) > 1 and usage_result[1]:
                usage_source = str(usage_result[1])
        else:
            usage = usage_result
    except Exception:
        usage = pd.DataFrame()
        usage_source = "Advanced USG unavailable"

    result = (*_form_index(form), *_usage_index(usage), usage_source)
    _CACHE["indexes"] = result
    return result


def _lookup(pair_index, name_index, player, team):
    n = _norm_name(player)
    t = _norm_team(team)
    if not n:
        return None
    row = pair_index.get((n, t))
    if row is not None:
        return row
    return name_index.get(n)


def _reliability(form_row):
    if form_row is None:
        return "LOW", "#ffb3b3", "#35171d", "#7d424a"

    gp = int(_num(form_row.get("GP")) or 0)
    l10_gp = int(_num(form_row.get("L10_GP")) or min(gp, 10))
    l5_gp = int(_num(form_row.get("L5_GP")) or min(gp, 5))

    if gp >= 15 and l10_gp >= 8 and l5_gp >= 4:
        return "HIGH", "#8ff1c2", "#0d2a22", "#2f6b58"
    if gp >= 8 and l5_gp >= 3:
        return "MEDIUM", "#ffe189", "#2a220e", "#756227"
    return "LOW", "#ffb3b3", "#35171d", "#7d424a"


def _metric(label, value, note=""):
    note_html = (
        f'<div style="color:#6f879f;font-size:.42rem;line-height:1.25;margin-top:2px">{_esc(note)}</div>'
        if note else ""
    )
    return (
        '<div style="border:1px solid #27445d;background:#071521;border-radius:8px;'
        'padding:6px 7px;min-width:0">'
        f'<div style="color:#7890a7;font-size:.40rem;font-weight:900;letter-spacing:.045em;'
        f'text-transform:uppercase">{_esc(label)}</div>'
        f'<div style="color:#f4f9ff;font-size:.67rem;font-weight:900;margin-top:2px;'
        f'overflow-wrap:anywhere">{_esc(value)}</div>'
        f'{note_html}</div>'
    )


def _share(value, total):
    v, t = _num(value), _num(total)
    if v is None or t is None or t <= 0:
        return "—"
    return f"{100.0 * v / t:.0f}%"


def _row_value(row, *keys):
    if row is None:
        return None
    for key in keys:
        try:
            value = row.get(key)
        except Exception:
            value = None
        if _num(value) is not None:
            return value
    return None


def _opportunity_html(pick) -> str:
    """Return compact Step-1 HTML designed to sit inside an existing Top-5 card."""
    try:
        form_pair, form_name, usage_pair, usage_name, usage_source = _indexes()
        name = str(pick.get("name") or "Player")
        team = str(pick.get("team") or "")
        form = _lookup(form_pair, form_name, name, team)
        usage = _lookup(usage_pair, usage_name, name, team)

        proj_min = _num(pick.get("min"))
        proj_pts = _num(pick.get("p"))
        proj_reb = _num(pick.get("r"))
        proj_ast = _num(pick.get("a"))
        proj_pra = _num(pick.get("pra"))
        if proj_pra is None:
            proj_pra = sum(x or 0.0 for x in (proj_pts, proj_reb, proj_ast))

        season_min = _row_value(form, "MIN")
        l10_min = _row_value(form, "L10_MIN")
        l5_min = _row_value(form, "L5_MIN")

        season_pts = _row_value(form, "PTS")
        season_reb = _row_value(form, "REB")
        season_ast = _row_value(form, "AST")
        l10_pts = _row_value(form, "L10_PTS")
        l10_reb = _row_value(form, "L10_REB")
        l10_ast = _row_value(form, "L10_AST")
        l5_pts = _row_value(form, "L5_PTS")
        l5_reb = _row_value(form, "L5_REB")
        l5_ast = _row_value(form, "L5_AST")

        season_usg = _row_value(usage, "USG_PCT", "USG")
        l10_usg = _row_value(usage, "L10_USG_PCT", "USG_PCT_L10")
        l5_usg = _row_value(usage, "L5_USG_PCT", "USG_PCT_L5")
        proj_usg = _num(pick.get("usg"))

        gp = int(_num(form.get("GP")) or 0) if form is not None else 0
        reliability, rel_color, rel_bg, rel_border = _reliability(form)

        min_delta = None
        if proj_min is not None and _num(season_min) is not None:
            min_delta = proj_min - float(season_min)

        role_label = "CONFIRMED STARTER" if bool(pick.get("starter")) else str(
            pick.get("status") or "ACTIVE / ROTATION"
        ).upper()

        season36 = (
            f'{_fmt(_per36(season_pts, season_min),1)} P • '
            f'{_fmt(_per36(season_reb, season_min),1)} R • '
            f'{_fmt(_per36(season_ast, season_min),1)} A'
        )
        l1036 = (
            f'{_fmt(_per36(l10_pts, l10_min),1)} P • '
            f'{_fmt(_per36(l10_reb, l10_min),1)} R • '
            f'{_fmt(_per36(l10_ast, l10_min),1)} A'
        )
        l536 = (
            f'{_fmt(_per36(l5_pts, l5_min),1)} P • '
            f'{_fmt(_per36(l5_reb, l5_min),1)} R • '
            f'{_fmt(_per36(l5_ast, l5_min),1)} A'
        )

        minute_note = f"{min_delta:+.1f} vs season" if min_delta is not None else "V2.8 projected"
        mix = (
            f'{_share(proj_pts, proj_pra)} P • '
            f'{_share(proj_reb, proj_pra)} R • '
            f'{_share(proj_ast, proj_pra)} A'
        )
        usage_line = (
            f'Proj {_fmt(proj_usg,1,"%")} • '
            f'Szn {_fmt(season_usg,1,"%")} • '
            f'L10 {_fmt(l10_usg,1,"%")} • '
            f'L5 {_fmt(l5_usg,1,"%")}'
        )

        metrics = "".join([
            _metric("Projected MIN", _fmt(proj_min,1), minute_note),
            _metric("Season / L10 / L5 MIN",
                    f'{_fmt(season_min,1)} / {_fmt(l10_min,1)} / {_fmt(l5_min,1)}',
                    f"{gp} verified season GP"),
            _metric("PRA component mix", mix, "projected P / R / A share"),
            _metric("Projected P / R / A",
                    f'{_fmt(proj_pts,1)} / {_fmt(proj_reb,1)} / {_fmt(proj_ast,1)}',
                    f'PRA {_fmt(proj_pra,1)}'),
            _metric("Season per 36", season36, "box-score opportunity rate"),
            _metric("L10 per 36", l1036, "recent opportunity rate"),
            _metric("L5 per 36", l536, "recent opportunity rate"),
            _metric("Usage", usage_line, usage_source),
        ])

        return (
            '<div style="border:1px solid #2e607d;background:linear-gradient(145deg,#071a2a,#06131f);'
            'border-radius:11px;padding:9px;margin-top:8px">'
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:7px;'
            'flex-wrap:wrap;margin-bottom:7px">'
            '<div style="color:#78dcff;font-size:.52rem;font-weight:1000;letter-spacing:.075em">'
            '🔬 STEP 1 • OPPORTUNITY DECOMPOSITION</div>'
            f'<div style="border:1px solid {rel_border};background:{rel_bg};color:{rel_color};'
            'border-radius:999px;padding:3px 7px;font-size:.42rem;font-weight:950;white-space:nowrap">'
            f'DATA • {reliability}</div></div>'
            f'<div style="color:#8ea6bd;font-size:.48rem;line-height:1.4;margin-bottom:7px">'
            f'{_esc(role_label)} • read-only precision audit</div>'
            '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px">'
            f'{metrics}</div>'
            '<div style="margin-top:7px;border-left:2px solid #d7ba55;background:#181709;'
            'border-radius:0 7px 7px 0;padding:6px 7px;color:#d7c878;font-size:.43rem;line-height:1.35">'
            '<b>Tracking:</b> potential assists and rebound chances/touches remain UNAVAILABLE '
            'until an official verified tracking feed exists. No proxy is invented.'
            '</div>'
            '</div>'
        )
    except Exception as exc:
        # Presentation must fail open: never break the frozen Top-5 card.
        return (
            '<div style="border:1px solid #725b26;background:#251f0d;border-radius:9px;'
            'padding:7px 8px;margin-top:8px;color:#ead27b;font-size:.48rem;line-height:1.35">'
            '🔬 STEP 1 • OPPORTUNITY DECOMPOSITION • DATA PENDING '
            f'<span style="opacity:.65">({_esc(type(exc).__name__)})</span>'
            '</div>'
        )


def _compact_path_with_step1(pick):
    original = getattr(layout, _ORIGINAL_ATTR)
    try:
        base_html = original(pick)
    except Exception:
        base_html = ""
    return str(base_html or "") + _opportunity_html(pick)


_compact_path_with_step1._pra_precision_step1_helper = True


def install():
    """Patch the stable card subcomponent, never the Top-5 renderer itself."""
    current = layout._compact_path_box

    # Save the frozen original exactly once. If an older v3613 helper is already
    # installed on a hot worker, recover its saved original instead of nesting.
    if not hasattr(layout, _ORIGINAL_ATTR):
        old_original = getattr(current, "_pra_precision_step1_original", None)
        setattr(layout, _ORIGINAL_ATTR, old_original or current)

    layout._compact_path_box = _compact_path_with_step1


def begin_render():
    """Fresh lightweight data cache + deterministic card-helper binding."""
    _CACHE.clear()
    install()


__all__ = ["STEP_VERSION", "install", "begin_render"]
