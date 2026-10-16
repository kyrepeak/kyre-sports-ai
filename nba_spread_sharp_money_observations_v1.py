"""NBA Spread Step 3 — sharp-money observations derived from verified Step-2 betting data."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from nba_spread_public_betting_observations_v1 import load_verified_public_betting_observations

MODEL_VERSION = "NBA_SPREAD_SHARP_MONEY_OBSERVATIONS_STEP3_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_RANKING = False
MAY_ACTIVATE_SHARP_MONEY = True
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}


def _tricode(value: object) -> str | None:
    text = str(value or "").strip().upper()
    return text if len(text) == 3 and text.isalpha() else None


def _percent(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= 100 else None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _schedule_index(
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    index: dict[tuple[str, str], Mapping[str, object]] = {}
    for game in schedule_games:
        if str(game.get("status") or "").strip().upper() not in ELIGIBLE_STATES:
            continue
        away = _tricode(game.get("away_tricode"))
        home = _tricode(game.get("home_tricode"))
        if away and home:
            index[(away, home)] = game
    return index


def _base(source: object = "") -> dict[str, object]:
    return {
        "source": str(source or ""),
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def derive_verified_sharp_money_observations(
    public_betting_payload: Mapping[str, object],
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Derive read-only sharp-money evidence from verified Step-2 observations.

    A side is sharp only when its verified money percentage is greater than its
    verified public-bet percentage. No minimum gap or arbitrary volume threshold
    is invented. Exact positive observed bet count is required as context.
    """
    source = public_betting_payload.get("source")
    base = _base(source)
    if str(public_betting_payload.get("verification") or "").upper() != "VERIFIED":
        return {
            **base,
            "verification": "UNAVAILABLE",
            "diagnostic_state": "UPSTREAM_PUBLIC_BETTING_UNAVAILABLE",
            "upstream_diagnostic_state": str(
                public_betting_payload.get("diagnostic_state") or "UNKNOWN"
            ),
        }

    schedule = _schedule_index(schedule_games)
    matched_any = False
    output: list[dict[str, object]] = []

    raw_rows = public_betting_payload.get("observations") or []
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        return {
            **base,
            "verification": "UNAVAILABLE",
            "diagnostic_state": "INVALID_PUBLIC_BETTING_PAYLOAD",
        }

    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        away = _tricode(raw.get("away_tricode"))
        home = _tricode(raw.get("home_tricode"))
        if not away or not home:
            continue
        game = schedule.get((away, home))
        if game is None:
            continue
        matched_any = True

        away_bets = _percent(raw.get("away_bet_pct"))
        home_bets = _percent(raw.get("home_bet_pct"))
        away_money = _percent(raw.get("away_money_pct"))
        home_money = _percent(raw.get("home_money_pct"))
        if None in {away_bets, home_bets, away_money, home_money}:
            return {
                **base,
                "verification": "UNAVAILABLE",
                "diagnostic_state": "INVALID_BETTING_SPLITS",
            }
        assert away_bets is not None and home_bets is not None
        assert away_money is not None and home_money is not None
        if away_bets + home_bets != 100 or away_money + home_money != 100:
            return {
                **base,
                "verification": "UNAVAILABLE",
                "diagnostic_state": "INVALID_BETTING_SPLITS",
            }

        bet_count = _positive_int(raw.get("bet_count"))
        if bet_count is None:
            return {
                **base,
                "verification": "UNAVAILABLE",
                "diagnostic_state": "SHARP_VOLUME_UNVERIFIED",
            }

        away_gap = away_money - away_bets
        home_gap = home_money - home_bets
        if away_gap <= 0 and home_gap <= 0:
            continue

        if away_gap > home_gap:
            sharp_side = away
            public_bet_pct = away_bets
            money_pct = away_money
            gap = away_gap
            sharp_name = str(game.get("away_name") or away)
        else:
            sharp_side = home
            public_bet_pct = home_bets
            money_pct = home_money
            gap = home_gap
            sharp_name = str(game.get("home_name") or home)

        output.append(
            {
                "away_tricode": away,
                "home_tricode": home,
                "away_name": str(game.get("away_name") or away),
                "home_name": str(game.get("home_name") or home),
                "game_date_phoenix": str(game.get("game_date_phoenix") or ""),
                "tip_phoenix": str(game.get("tip_phoenix") or ""),
                "status": str(game.get("status") or "UPCOMING").strip().upper(),
                "sharp_side_tricode": sharp_side,
                "sharp_side_name": sharp_name,
                "public_bet_pct": public_bet_pct,
                "money_pct": money_pct,
                "sharp_gap_pct": gap,
                "bet_count": bet_count,
            }
        )

    if output:
        return {
            **base,
            "verification": "VERIFIED",
            "diagnostic_state": "OK",
            "observations": output,
        }

    return {
        **base,
        "verification": "UNAVAILABLE",
        "diagnostic_state": (
            "NO_POSITIVE_SHARP_MONEY_DIVERGENCE"
            if matched_any
            else "NO_VERIFIED_SCHEDULE_MATCH"
        ),
    }


def load_verified_sharp_money_observations(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    public_betting_loader: Callable[
        [Sequence[Mapping[str, object]]], Mapping[str, object]
    ] = load_verified_public_betting_observations,
) -> dict[str, object]:
    """Load Step-2 observations once, then derive fail-closed sharp-money evidence."""
    try:
        payload = public_betting_loader(schedule_games)
    except Exception as exc:
        return {
            **_base(),
            "verification": "UNAVAILABLE",
            "diagnostic_state": "UPSTREAM_PUBLIC_BETTING_UNAVAILABLE",
            "upstream_diagnostic_state": f"PUBLIC_BETTING_LOADER_ERROR:{type(exc).__name__}",
        }
    if not isinstance(payload, Mapping):
        return {
            **_base(),
            "verification": "UNAVAILABLE",
            "diagnostic_state": "UPSTREAM_PUBLIC_BETTING_UNAVAILABLE",
            "upstream_diagnostic_state": "INVALID_PUBLIC_BETTING_PAYLOAD",
        }
    return derive_verified_sharp_money_observations(payload, schedule_games)


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_RANKING",
    "MAY_ACTIVATE_SHARP_MONEY",
    "derive_verified_sharp_money_observations",
    "load_verified_sharp_money_observations",
]
