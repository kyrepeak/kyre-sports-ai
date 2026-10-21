"""Safe sportsbook-name alias resolution layered onto the CBS roster loader."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping, Sequence

from . import nba_pra_cbs_v1 as _cbs


def _tokens(value: Any) -> list[str]:
    return [token for token in _cbs._clean(value).replace('.', '').split() if token]


def resolve_requested_player(
    requested_name: str,
    roster: Mapping[str, Mapping[str, Any]],
) -> tuple[str, Mapping[str, Any]] | None:
    requested_key = _cbs._norm(requested_name)
    exact_row = roster.get(requested_key)
    if exact_row is not None and _cbs._norm(exact_row.get('player_name')) == requested_key:
        return requested_key, exact_row

    requested = _tokens(requested_name)
    if len(requested) < 2 or not requested[0]:
        return None
    initial = requested[0][0].casefold()
    surname = _cbs._norm(requested[-1])
    matches: list[tuple[str, Mapping[str, Any]]] = []
    for key, row in roster.items():
        canonical = _tokens(row.get('player_name'))
        if len(canonical) < 2 or not canonical[0]:
            continue
        if canonical[0][0].casefold() != initial:
            continue
        if _cbs._norm(canonical[-1]) != surname:
            continue
        matches.append((key, row))
    return matches[0] if len(matches) == 1 else None


def load_cbs_profiles(
    slate_date,
    player_names: Sequence[str],
    *,
    team_codes: Sequence[str] | None = None,
    fetch_text=None,
    max_workers: int = 8,
):
    requested = {_cbs._norm(name): _cbs._clean(name) for name in player_names if _cbs._clean(name)}
    if not requested:
        return {}
    codes = list(dict.fromkeys(
        _cbs._clean(code).upper()
        for code in (team_codes or _cbs.TEAM_ROUTES)
        if _cbs._clean(code).upper() in _cbs.TEAM_ROUTES
    ))
    if not codes:
        return {}
    fetch = fetch_text or _cbs._default_fetch_text

    all_roster: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(codes)))) as pool:
        jobs = {pool.submit(fetch, 'roster', code, None): code for code in codes}
        for future in as_completed(jobs):
            code = jobs[future]
            try:
                parsed = _cbs.parse_cbs_roster(future.result(), team=code)
            except Exception:
                continue
            for key, row in parsed.items():
                all_roster.setdefault(key, row)

    resolved: dict[str, dict[str, Any]] = {}
    for requested_key, requested_name in requested.items():
        match = resolve_requested_player(requested_name, all_roster)
        if match is not None:
            _, row = match
            resolved[requested_key] = dict(row)
    if not resolved:
        return {}

    current_start_year = slate_date.year if slate_date.month >= 7 else slate_date.year - 1

    def load_season(player_id: str, slug: str, season: int):
        document = (
            _cbs._fetch_gamelog(player_id, slug, season)
            if fetch_text is None
            else fetch('gamelog', player_id, season)
        )
        return _cbs.parse_cbs_gamelog(document)

    def history_job(requested_key: str, row: Mapping[str, Any]):
        player_id = _cbs._clean((row.get('provider_ids') or {}).get('cbs_sports'))
        slug = _cbs._clean(row.get('provider_slug'))
        if not player_id or not slug:
            return requested_key, None
        try:
            current = load_season(player_id, slug, current_start_year)
        except Exception:
            current = []
        prior = []
        if len(current) < 8:
            try:
                prior = load_season(player_id, slug, current_start_year - 1)
            except Exception:
                prior = []
        # Long-absence players may legitimately have no immediately prior season.
        # Look back exactly one additional season, then stop.
        if not current and not prior:
            try:
                prior = load_season(player_id, slug, current_start_year - 2)
            except Exception:
                prior = []
        if not current and not prior:
            return requested_key, None
        profile = dict(row)
        profile.pop('provider_slug', None)
        profile['current_games'] = current
        profile['prior_games'] = prior
        profile['stats_source'] = 'CBS Sports'
        profile['data_state'] = 'VERIFIED'
        return requested_key, profile

    out: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(resolved)))) as pool:
        jobs = {pool.submit(history_job, key, row): key for key, row in resolved.items()}
        for future in as_completed(jobs):
            try:
                key, profile = future.result()
            except Exception:
                continue
            if profile:
                out[key] = profile
    return out


_cbs.resolve_requested_player = resolve_requested_player
_cbs.load_cbs_profiles = load_cbs_profiles
