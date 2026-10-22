"""Kyre Sports API CFB Top Picks Page 1 S-tier V3.

V3 keeps Page 1 deliberately simple while the gateway performs the hard work:
- one Top 10 pool across moneyline, spread, and total selections,
- one separate Top 10 pool for player props,
- exact sportsbook observations only,
- primary-first, field-scoped fallback,
- incomplete candidates are rejected instead of patched with invented values.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Callable, Mapping, Sequence

from fastapi import APIRouter, HTTPException, Query

import cfb_over_under_model_v1 as total_model
import cfb_player_props_fanduel_bound_v2 as fanduel_props
import cfb_player_props_odds_api_v1 as odds_api_props
import sports_api.api.cfb_game_total_page1_v1 as game_market_api
import sports_api.api.cfb_moneyline_page1_v1 as moneyline_api
import sports_api.api.cfb_top_picks_page1_v1 as frozen_top_v1

router = APIRouter(prefix="/api/v3/cfb/top-picks", tags=["cfb"])
MODEL_VERSION = "CFB TOP PICKS PAGE1 API V3 • SIMPLE TOP 10 + PROP TOP 10"
SCHEMA_VERSION = "cfb_top_picks_page1_v3"
DEFAULT_LIMIT = 10
MAX_LIMIT = 10
SLATE_BACKFILL_SCAN_DAYS = 14
SPREAD_SIGMA = 14.0
APPROVED_PROP_BOOKS = {
    "fanduel",
    "draftkings",
    "betmgm",
    "caesars",
    "bet365",
    "fanatics sportsbook",
    "fanatics",
}
PROP_LABELS = {
    "passing_yards": "Passing Yards",
    "rushing_yards": "Rushing Yards",
    "receiving_yards": "Receiving Yards",
    "receiving_receptions": "Receptions",
    "passing_touchdowns": "Passing Touchdowns",
    "touchdowns": "Touchdowns",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _american(value: Any) -> int | None:
    number = _float(value)
    if number is None or number == 0:
        return None
    return int(round(number))


def american_implied_probability(value: Any) -> float | None:
    odds = _float(value)
    if odds is None or odds == 0:
        return None
    if odds < 0:
        return (-odds) / ((-odds) + 100.0)
    return 100.0 / (odds + 100.0)


def same_book_devig_probability(over: Mapping[str, Any], under: Mapping[str, Any]) -> float | None:
    """Return exact-pair fair P(over); cross-book or cross-line pairs fail closed."""
    if _clean(over.get("sportsbook")).casefold() != _clean(under.get("sportsbook")).casefold():
        return None
    over_line = _float(over.get("line"))
    under_line = _float(under.get("line"))
    if over_line is None or under_line is None or abs(over_line - under_line) > 1e-9:
        return None
    p_over = american_implied_probability(over.get("american_odds") if "american_odds" in over else over.get("price"))
    p_under = american_implied_probability(under.get("american_odds") if "american_odds" in under else under.get("price"))
    if p_over is None or p_under is None or p_over + p_under <= 0:
        return None
    return p_over / (p_over + p_under)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def _record_text(profile: Mapping[str, Any] | None) -> str | None:
    if not isinstance(profile, Mapping):
        return None
    direct = _clean(profile.get("record_text"))
    if direct and direct not in {"—", "N/A"}:
        return direct
    record = profile.get("record")
    if not isinstance(record, Mapping):
        return None
    try:
        games = int(record.get("games") or 0)
        wins = int(record.get("wins") or 0)
        losses = int(record.get("losses") or 0)
        ties = int(record.get("ties") or 0)
    except (TypeError, ValueError):
        return None
    if games <= 0:
        return None
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _game_id(game: Mapping[str, Any]) -> str:
    return _clean(game.get("game_id") or game.get("official_game_id") or game.get("event_id") or game.get("identity_key"))


def _canonical_id(game: Mapping[str, Any]) -> str:
    try:
        return _clean(frozen_top_v1._canonical_event_id(game))
    except Exception:
        return _game_id(game)


def _team_logo(game: Mapping[str, Any], side: str) -> str | None:
    for key in (
        f"{side}_logo",
        f"{side}_logo_url",
        f"{side}_image",
        f"{side}_team_logo",
    ):
        value = _clean(game.get(key))
        if value.startswith("https://"):
            return value
    return None


def _complete_game_candidate(row: Mapping[str, Any]) -> bool:
    required_text = (
        "candidate_id", "event_id", "market_type", "selection", "side",
        "sportsbook", "away_team", "home_team", "away_record", "home_record",
        "kickoff_iso", "market_timestamp",
    )
    if any(not _clean(row.get(key)) for key in required_text):
        return False
    if _american(row.get("american_odds")) is None:
        return False
    probability = _float(row.get("probability"))
    if probability is None or not (0.0 < probability < 1.0):
        return False
    market = _clean(row.get("market_type")).upper()
    if market in {"SPREAD", "TOTAL"} and _float(row.get("line")) is None:
        return False
    return market in {"MONEYLINE", "SPREAD", "TOTAL"}


def _complete_prop_candidate(row: Mapping[str, Any]) -> bool:
    required_text = (
        "candidate_id", "event_id", "player_name", "market_key", "market_label",
        "side", "sportsbook", "away_team", "home_team", "away_record",
        "home_record", "kickoff_iso", "market_timestamp", "probability_basis",
    )
    if any(not _clean(row.get(key)) for key in required_text):
        return False
    if _float(row.get("line")) is None or _american(row.get("american_odds")) is None:
        return False
    probability = _float(row.get("probability"))
    return probability is not None and 0.0 < probability < 1.0


def _price_sort(value: Any) -> int:
    odds = _american(value)
    return odds if odds is not None else -100000


def rank_game_candidates(candidates: Sequence[Mapping[str, Any]], *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Rank one mixed game-selection pool; there are deliberately no market quotas."""
    best_by_market: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in candidates:
        row = dict(raw)
        if not _complete_game_candidate(row):
            continue
        key = (_clean(row.get("event_id")), _clean(row.get("market_type")).upper())
        incumbent = best_by_market.get(key)
        score = (_float(row.get("probability")) or 0.0, _price_sort(row.get("american_odds")))
        old_score = (
            (_float(incumbent.get("probability")) or 0.0, _price_sort(incumbent.get("american_odds")))
            if incumbent is not None else (-1.0, -100000)
        )
        if incumbent is None or score > old_score:
            best_by_market[key] = row
    ranked = sorted(
        best_by_market.values(),
        key=lambda row: (
            -float(row.get("probability") or 0.0),
            -_price_sort(row.get("american_odds")),
            _clean(row.get("kickoff_iso")),
            _clean(row.get("event_id")),
            _clean(row.get("market_type")),
        ),
    )[: max(0, min(MAX_LIMIT, int(limit)))]
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def rank_player_props(candidates: Sequence[Mapping[str, Any]], *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str, float, str], dict[str, Any]] = {}
    for raw in candidates:
        row = dict(raw)
        if not _complete_prop_candidate(row):
            continue
        row["player_id"] = _clean(row.get("player_id")) or None
        row["player_id_display"] = row["player_id"] or "ID not reported"
        line = float(row["line"])
        key = (
            _clean(row.get("event_id")),
            _clean(row.get("player_name")).casefold(),
            _clean(row.get("market_key")),
            line,
            _clean(row.get("side")).upper(),
        )
        incumbent = best.get(key)
        source_priority = 1 if _clean(row.get("source_provider")) == "FanDuel" else 0
        score = (
            float(row.get("probability") or 0.0),
            source_priority,
            _price_sort(row.get("american_odds")),
        )
        old_score = (
            (
                float(incumbent.get("probability") or 0.0),
                1 if _clean(incumbent.get("source_provider")) == "FanDuel" else 0,
                _price_sort(incumbent.get("american_odds")),
            )
            if incumbent is not None else (-1.0, -1, -100000)
        )
        if incumbent is None or score > old_score:
            best[key] = row
    ranked = sorted(
        best.values(),
        key=lambda row: (
            -float(row.get("probability") or 0.0),
            -(1 if _clean(row.get("source_provider")) == "FanDuel" else 0),
            -_price_sort(row.get("american_odds")),
            _clean(row.get("kickoff_iso")),
            _clean(row.get("player_name")),
        ),
    )[: max(0, min(MAX_LIMIT, int(limit)))]
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def _analysis_profiles(
    games: list[dict[str, Any]], selected_day: str
) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, Any]]]:
    try:
        return frozen_top_v1._analyze_games(games, selected_day, moneyline_api._analysis)
    except Exception as exc:
        return {}, [{"error": type(exc).__name__}]


def _spread_probability(projected_margin: float, spread: float, *, home_side: bool) -> float:
    mean = float(projected_margin) if home_side else -float(projected_margin)
    return _normal_cdf((mean + float(spread)) / SPREAD_SIGMA)


def _game_candidates(
    games: list[dict[str, Any]],
    analyses: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for game in games:
        event_id = _canonical_id(game)
        analysis = analyses.get(event_id)
        if not isinstance(analysis, Mapping):
            continue
        away = analysis.get("away") if isinstance(analysis.get("away"), Mapping) else {}
        home = analysis.get("home") if isinstance(analysis.get("home"), Mapping) else {}
        final = analysis.get("final") if isinstance(analysis.get("final"), Mapping) else {}
        away_record = _record_text(away)
        home_record = _record_text(home)
        if not away_record or not home_record:
            continue
        away_team = _clean(game.get("away_team"))
        home_team = _clean(game.get("home_team"))
        kickoff = _clean(game.get("kickoff_iso"))
        if not away_team or not home_team or not kickoff:
            continue

        quotes = [dict(row) for row in list(game.get("market_quotes") or []) if isinstance(row, Mapping)]
        for quote in quotes:
            sportsbook = _clean(quote.get("sportsbook"))
            stamp = _clean(quote.get("observed_at_utc"))
            if not sportsbook or not stamp:
                continue
            winner_side = _clean(final.get("winner_side")).lower()
            winner_probability = _float(final.get("winner_probability_final"))
            if winner_side in {"home", "away"} and winner_probability is not None:
                ml_price = _american(quote.get(f"{winner_side}_moneyline"))
                winner_team = home_team if winner_side == "home" else away_team
                if ml_price is not None:
                    out.append({
                        "candidate_id": f"{event_id}:moneyline:{winner_side}:{sportsbook}",
                        "event_id": event_id,
                        "market_type": "MONEYLINE",
                        "selection": f"{winner_team} ML",
                        "side": winner_side.upper(),
                        "line": None,
                        "american_odds": ml_price,
                        "sportsbook": sportsbook,
                        "probability": float(winner_probability),
                        "away_team": away_team,
                        "home_team": home_team,
                        "away_record": away_record,
                        "home_record": home_record,
                        "away_logo": _team_logo(game, "away"),
                        "home_logo": _team_logo(game, "home"),
                        "kickoff_iso": kickoff,
                        "market_timestamp": stamp,
                    })

            analysis_line = _float(quote.get("total_line"))
            if analysis_line is None:
                analysis_line = 50.0
            projection = total_model.project_matchup(game, away, home, analysis_line)
            if projection.get("ready") is not True:
                continue
            projected_home = _float(projection.get("projected_home_points"))
            projected_away = _float(projection.get("projected_away_points"))
            if projected_home is None or projected_away is None:
                continue
            projected_margin = projected_home - projected_away

            spread_rows: list[dict[str, Any]] = []
            for side, team, spread_key, price_key, is_home in (
                ("HOME", home_team, "home_spread", "home_spread_price", True),
                ("AWAY", away_team, "away_spread", "away_spread_price", False),
            ):
                spread = _float(quote.get(spread_key))
                price = _american(quote.get(price_key))
                if spread is None or price is None:
                    continue
                probability = _spread_probability(projected_margin, spread, home_side=is_home)
                spread_rows.append({
                    "candidate_id": f"{event_id}:spread:{side.casefold()}:{spread}:{sportsbook}",
                    "event_id": event_id,
                    "market_type": "SPREAD",
                    "selection": f"{team} {spread:+g}",
                    "side": side,
                    "line": spread,
                    "american_odds": price,
                    "sportsbook": sportsbook,
                    "probability": probability,
                    "away_team": away_team,
                    "home_team": home_team,
                    "away_record": away_record,
                    "home_record": home_record,
                    "away_logo": _team_logo(game, "away"),
                    "home_logo": _team_logo(game, "home"),
                    "kickoff_iso": kickoff,
                    "market_timestamp": stamp,
                })
            if spread_rows:
                out.append(max(spread_rows, key=lambda row: (row["probability"], _price_sort(row["american_odds"]))))

            total_line = _float(quote.get("total_line"))
            if total_line is not None:
                total_projection = total_model.project_matchup(game, away, home, total_line)
                if total_projection.get("ready") is True:
                    total_rows: list[dict[str, Any]] = []
                    for side, probability_key, price_key in (
                        ("OVER", "over_probability", "over_price"),
                        ("UNDER", "under_probability", "under_price"),
                    ):
                        probability = _float(total_projection.get(probability_key))
                        price = _american(quote.get(price_key))
                        if probability is None or price is None:
                            continue
                        total_rows.append({
                            "candidate_id": f"{event_id}:total:{side.casefold()}:{total_line}:{sportsbook}",
                            "event_id": event_id,
                            "market_type": "TOTAL",
                            "selection": f"{side.title()} {total_line:g}",
                            "side": side,
                            "line": total_line,
                            "american_odds": price,
                            "sportsbook": sportsbook,
                            "probability": probability,
                            "away_team": away_team,
                            "home_team": home_team,
                            "away_record": away_record,
                            "home_record": home_record,
                            "away_logo": _team_logo(game, "away"),
                            "home_logo": _team_logo(game, "home"),
                            "kickoff_iso": kickoff,
                            "market_timestamp": stamp,
                        })
                    if total_rows:
                        out.append(max(total_rows, key=lambda row: (row["probability"], _price_sort(row["american_odds"]))))
    return out


def _game_contexts(
    games: list[dict[str, Any]], analyses: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for game in games:
        canonical = _canonical_id(game)
        analysis = analyses.get(canonical) if isinstance(analyses.get(canonical), Mapping) else {}
        away = analysis.get("away") if isinstance(analysis.get("away"), Mapping) else {}
        home = analysis.get("home") if isinstance(analysis.get("home"), Mapping) else {}
        context = {
            "event_id": canonical,
            "away_team": _clean(game.get("away_team")),
            "home_team": _clean(game.get("home_team")),
            "away_record": _record_text(away),
            "home_record": _record_text(home),
            "away_logo": _team_logo(game, "away"),
            "home_logo": _team_logo(game, "home"),
            "kickoff_iso": _clean(game.get("kickoff_iso")),
        }
        for key in {_game_id(game), canonical, _clean(game.get("identity_key"))}:
            if key:
                contexts[key] = context
    return contexts


def _normalize_prop_rows(
    rows: Sequence[Mapping[str, Any]],
    contexts: Mapping[str, Mapping[str, Any]],
    *,
    source_provider: str,
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for raw in rows:
        sportsbook = _clean(raw.get("sportsbook"))
        if not sportsbook:
            continue
        if source_provider != "FanDuel" and sportsbook.casefold() not in APPROVED_PROP_BOOKS:
            continue
        context = contexts.get(_clean(raw.get("official_game_id")))
        if not isinstance(context, Mapping):
            continue
        side = _clean(raw.get("side")).upper()
        line = _float(raw.get("line"))
        price = _american(raw.get("price"))
        player = _clean(raw.get("player_name"))
        market_key = _clean(raw.get("stat_id"))
        if side not in {"OVER", "UNDER"} or line is None or price is None or not player or not market_key:
            continue
        prepared.append({
            "event_id": _clean(context.get("event_id")),
            "official_game_id": _clean(raw.get("official_game_id")),
            "player_id": _clean(raw.get("provider_player_id")) or None,
            "player_name": player,
            "market_key": market_key,
            "market_label": PROP_LABELS.get(market_key, market_key.replace("_", " ").title()),
            "side": side,
            "line": line,
            "american_odds": price,
            "sportsbook": sportsbook,
            "source_provider": source_provider,
            "market_timestamp": _clean(raw.get("observed_at_utc")),
            **dict(context),
        })
    return prepared


def _prop_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, float], dict[str, dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        key = (
            _clean(row.get("event_id")),
            _clean(row.get("sportsbook")).casefold(),
            _clean(row.get("player_name")).casefold(),
            _clean(row.get("market_key")),
            float(row.get("line")),
        )
        grouped.setdefault(key, {})[_clean(row.get("side")).upper()] = row

    out: list[dict[str, Any]] = []
    for sides in grouped.values():
        over = sides.get("OVER")
        under = sides.get("UNDER")
        if over is not None and under is not None:
            fair_over = same_book_devig_probability(over, under)
            if fair_over is None:
                continue
            choices = [(over, fair_over), (under, 1.0 - fair_over)]
            selected, probability = max(choices, key=lambda item: (item[1], _price_sort(item[0].get("american_odds"))))
            basis = "same_book_devig"
        else:
            selected = over or under
            if selected is None:
                continue
            probability = american_implied_probability(selected.get("american_odds"))
            if probability is None:
                continue
            basis = "single_book_implied"
        candidate = dict(selected)
        candidate["candidate_id"] = ":".join(
            [
                _clean(candidate.get("event_id")),
                _clean(candidate.get("player_name")).casefold().replace(" ", "-"),
                _clean(candidate.get("market_key")),
                str(candidate.get("line")),
                _clean(candidate.get("side")).casefold(),
                _clean(candidate.get("sportsbook")).casefold().replace(" ", "-"),
            ]
        )
        candidate["probability"] = float(probability)
        candidate["probability_basis"] = basis
        out.append(candidate)
    return out


def _collect_player_prop_candidates(
    games: list[dict[str, Any]],
    analyses: Mapping[str, Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    contexts = _game_contexts(games, analyses)
    providers = ["FanDuel"]
    try:
        primary_raw = fanduel_props.fetch_fanduel_cfb_player_props(games)
    except Exception:
        primary_raw = []
    primary = _prop_candidates(_normalize_prop_rows(primary_raw, contexts, source_provider="FanDuel"))
    ranked_primary = rank_player_props(primary, limit=limit)
    secondary_count = 0
    all_candidates = list(primary)
    if len(ranked_primary) < limit:
        providers.append("The Odds API")
        try:
            secondary_raw = odds_api_props.fetch_odds_api_cfb_player_props(games)
        except Exception:
            secondary_raw = []
        secondary = _prop_candidates(_normalize_prop_rows(secondary_raw, contexts, source_provider="The Odds API"))
        secondary_count = len(secondary)
        all_candidates.extend(secondary)
    ranked = rank_player_props(all_candidates, limit=limit)
    return ranked, providers, {
        "primary_prop_candidates": len(primary),
        "secondary_prop_candidates": secondary_count,
        "rankable_prop_candidates": len(all_candidates),
    }


def _ordered_unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = _clean(raw)
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def build_page1_payload(
    *,
    game_date: str | None = None,
    limit: int = DEFAULT_LIMIT,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    now = now_provider()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    requested_limit = max(1, min(MAX_LIMIT, int(limit)))
    try:
        first_payload = game_market_api.build_page1_payload(game_date=game_date, now_provider=lambda: now)
    except ValueError as exc:
        raise ValueError("game_date must be YYYY-MM-DD") from exc

    selected_day = _clean(first_payload.get("selected_date"))
    try:
        selected_date = date.fromisoformat(selected_day)
    except ValueError as exc:
        raise ValueError("resolved slate date must be YYYY-MM-DD") from exc

    game_candidates: list[dict[str, Any]] = []
    prop_candidates: list[dict[str, Any]] = []
    analysis_failures: list[dict[str, Any]] = []
    game_market_providers: list[str] = []
    player_prop_providers: list[str] = []
    slate_dates: list[str] = []
    total_games = 0
    total_analysis_ready = 0
    primary_prop_candidates = 0
    secondary_prop_candidates = 0
    rankable_prop_candidates = 0

    def consume_slate(payload: Mapping[str, Any], *, need_props: bool) -> None:
        nonlocal total_games, total_analysis_ready
        nonlocal primary_prop_candidates, secondary_prop_candidates, rankable_prop_candidates
        slate_day = _clean(payload.get("selected_date"))
        games = [dict(row) for row in list(payload.get("games") or []) if isinstance(row, Mapping)]
        if not slate_day or not games:
            return
        analyses, failures = _analysis_profiles(games, slate_day)
        slate_dates.append(slate_day)
        total_games += len(games)
        total_analysis_ready += len(analyses)
        for failure in failures:
            item = dict(failure)
            item.setdefault("slate_date", slate_day)
            analysis_failures.append(item)
        game_candidates.extend(_game_candidates(games, analyses))
        routing = payload.get("routing") if isinstance(payload.get("routing"), Mapping) else {}
        game_market_providers.extend(_clean(value) for value in list(routing.get("provider_calls") or []))
        if need_props:
            needed = max(1, requested_limit - len(rank_player_props(prop_candidates, limit=requested_limit)))
            slate_props, providers, diag = _collect_player_prop_candidates(games, analyses, limit=needed)
            prop_candidates.extend(slate_props)
            player_prop_providers.extend(providers)
            primary_prop_candidates += int(diag.get("primary_prop_candidates") or 0)
            secondary_prop_candidates += int(diag.get("secondary_prop_candidates") or 0)
            rankable_prop_candidates += int(diag.get("rankable_prop_candidates") or 0)

    consume_slate(first_payload, need_props=True)
    game_picks = rank_game_candidates(game_candidates, limit=requested_limit)
    player_props = rank_player_props(prop_candidates, limit=requested_limit)

    if len(game_picks) < requested_limit or len(player_props) < requested_limit:
        for offset in range(1, SLATE_BACKFILL_SCAN_DAYS + 1):
            scan_day = (selected_date + timedelta(days=offset)).isoformat()
            try:
                payload = game_market_api.build_page1_payload(game_date=scan_day, now_provider=lambda: now)
            except Exception:
                continue
            games = [row for row in list(payload.get("games") or []) if isinstance(row, Mapping)]
            if not games:
                continue
            consume_slate(payload, need_props=len(player_props) < requested_limit)
            game_picks = rank_game_candidates(game_candidates, limit=requested_limit)
            player_props = rank_player_props(prop_candidates, limit=requested_limit)
            if len(game_picks) >= requested_limit and len(player_props) >= requested_limit:
                break

    game_market_providers = _ordered_unique(game_market_providers)
    player_prop_providers = _ordered_unique(player_prop_providers)
    slate_dates = _ordered_unique(slate_dates)
    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_date": selected_day,
        "slate_dates": slate_dates,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "game_picks": game_picks,
        "player_props": player_props,
        "routing": {
            "application_gateway": "Kyre Sports API",
            "game_schedule_primary": "NCAA",
            "game_market_providers": game_market_providers,
            "player_prop_providers": player_prop_providers,
            "player_props_primary": "FanDuel",
            "player_props_secondary": "The Odds API" if "The Odds API" in player_prop_providers else None,
            "approved_secondary_only_when_needed": True,
            "sportsbook_projection_weight": 0.0,
            "consensus_averaging": False,
            "null_to_zero": False,
            "fabrication": False,
        },
        "diagnostics": {
            "slate_games": total_games,
            "slate_dates": slate_dates,
            "slate_backfill_used": len(slate_dates) > 1,
            "analysis_ready_games": total_analysis_ready,
            "analysis_failures": analysis_failures,
            "game_candidate_count": len(game_candidates),
            "game_pick_count": len(game_picks),
            "player_prop_count": len(player_props),
            "game_picks_10_of_10": len(game_picks) == requested_limit,
            "player_props_10_of_10": len(player_props) == requested_limit,
            "all_requested_slots_verified": len(game_picks) == requested_limit and len(player_props) == requested_limit,
            "unverified_slot_fill": False,
            "primary_prop_candidates": primary_prop_candidates,
            "secondary_prop_candidates": secondary_prop_candidates,
            "rankable_prop_candidates": rankable_prop_candidates,
        },
    }


@router.get("/page1")
def page1(
    game_date: str | None = Query(None, min_length=10, max_length=10),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "american_implied_probability",
    "build_page1_payload",
    "page1",
    "rank_game_candidates",
    "rank_player_props",
    "router",
    "same_book_devig_probability",
]
