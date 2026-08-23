'''Kyre Sports AI entrypoint — exact frozen MLB/WNBA baseline + isolated NFL V1.

Base production checkpoint:
    8c9cd1b468ae84be7abc92d54a04dc09d665f9e7

This entrypoint deliberately does NOT recreate, wrap or modify any MLB/WNBA
runtime function. It loads the exact frozen pre-NFL app and intercepts only nested
historical `git show <commit>:app.py` reads. When (and only when) the real
mobile/touch Sport + Market navigation source is encountered, it adds NFL as a
third sport and routes NFL to the isolated `nfl_hub_v1` foundation page.

NFL V1 enables schedule/date/team/game identity only. NFL projections,
sportsbook grading, Monte Carlo, rankings and recommendations remain OFF.
'''
from __future__ import annotations

import subprocess
import urllib.request


BASE_PRODUCTION_COMMIT = "8c9cd1b468ae84be7abc92d54a04dc09d665f9e7"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{BASE_PRODUCTION_COMMIT}/app.py"
)


NFL_MARKETS_SOURCE = '''    else:
        market = st.selectbox(
            "🏈 NFL Market",
            [
                "Slate",
                "Moneyline",
                "Spread",
                "Game Total",
                "Passing Yards",
                "Rushing Yards",
                "Receiving Yards",
                "Receptions",
                "Passing TDs",
                "Anytime TD",
                "Daily Picks",
            ],
            index=0,
            key="ks_nfl_market_touch",
        )
'''

NFL_ROUTE_SOURCE = '''if sport == "NFL":
    from nfl_hub_v1 import render_nfl_hub

    render_nfl_hub(market)
    st.stop()

'''


def _patch_nfl_touch_navigation(value):
    """Add NFL only to the verified historical touch-nav source.

    Every wrapper layer that does not contain the exact navigation markers is
    returned unchanged. The patch is idempotent. If the patched outer wrapper
    does not compile, the original source is returned so NFL can never take down
    the frozen MLB/WNBA app.
    """
    is_bytes = isinstance(value, (bytes, bytearray))
    text = value.decode("utf-8") if is_bytes else str(value)

    if 'key="ks_nfl_market_touch"' in text:
        return value

    sport_marker = '["MLB", "WNBA"],'
    wnba_start = '''    else:
        market = st.selectbox(
            "🎯 WNBA Market",'''
    wnba_end = '''            key="ks_wnba_market_touch",
        )

'''
    route_boundary = '''if sport == "WNBA" and market == "PRA":'''

    # Not the actual touch-navigation source yet: preserve this layer exactly.
    if (
        sport_marker not in text
        or wnba_start not in text
        or wnba_end not in text
        or route_boundary not in text
    ):
        return value

    original_text = text

    # 1) Sport selector: MLB / WNBA -> MLB / WNBA / NFL.
    text = text.replace(sport_marker, '["MLB", "WNBA", "NFL"],', 1)

    # 2) Turn the old catch-all WNBA branch into an explicit WNBA branch.
    text = text.replace(
        wnba_start,
        '''    elif sport == "WNBA":
        market = st.selectbox(
            "🎯 WNBA Market",''',
        1,
    )

    # 3) Add the NFL market dropdown directly after the WNBA selectbox.
    boundary_pos = text.find(route_boundary)
    if boundary_pos == -1:
        return value
    prefix = text[:boundary_pos]
    suffix = text[boundary_pos:]
    wnba_end_pos = prefix.rfind(wnba_end)
    if wnba_end_pos == -1:
        return value
    insertion_point = wnba_end_pos + len(wnba_end)
    prefix = (
        prefix[:insertion_point]
        + NFL_MARKETS_SOURCE
        + "\n"
        + prefix[insertion_point:]
    )

    # 4) NFL exits into its isolated page before any MLB/WNBA bootstrap executes.
    text = prefix + NFL_ROUTE_SOURCE + suffix

    # Hard safety rail: validate the outer historical wrapper before allowing the
    # patched source into the execution chain. A bad optional patch becomes a no-op,
    # never a production outage.
    try:
        compile(text, "<kyre_nfl_touch_nav_preflight>", "exec")
    except Exception:
        text = original_text

    if is_bytes:
        return text.encode("utf-8")
    return text


# The app is a chain of preserved wrapper entrypoints. Intercept nested app.py
# reads so the patch reaches the historical touch-nav source instead of assuming
# the immediate wrapper contains navigation code.
_ORIGINAL_CHECK_OUTPUT = subprocess.check_output


def _nfl_nested_app_check_output(*args, **kwargs):
    result = _ORIGINAL_CHECK_OUTPUT(*args, **kwargs)
    try:
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
            if (
                str(cmd[0]) == "git"
                and str(cmd[1]) == "show"
                and str(cmd[2]).endswith(":app.py")
            ):
                return _patch_nfl_touch_navigation(result)
    except Exception:
        # Never break the frozen app because the optional NFL navigation patch
        # could not inspect one nested read.
        return result
    return result


subprocess.check_output = _nfl_nested_app_check_output


def _load_frozen_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{BASE_PRODUCTION_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            # The immediate frozen wrapper is not the touch-nav source, so this is
            # normally a no-op. Kept for a safe fallback if repository shape moves.
            return _patch_nfl_touch_navigation(response.read().decode("utf-8"))


source = _load_frozen_app()
exec(
    compile(
        source,
        "kyre_sports_ai_frozen_8c9cd1b_plus_isolated_nfl_v1.py",
        "exec",
    ),
    globals(),
    globals(),
)
