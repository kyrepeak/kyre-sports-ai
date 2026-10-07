from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/3102133/gamelog"


def _first_event(value):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return {k: item.get(k) for k in ("id", "eventId", "date", "stats", "statistics") if k in item}
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            return _first_event(items)
        for key, item in value.items():
            if isinstance(item, dict):
                out = {k: item.get(k) for k in ("id", "eventId", "date", "stats", "statistics") if k in item}
                out.setdefault("map_key", key)
                return out
    return None


def _category_view(category):
    if not isinstance(category, dict):
        return None
    return {
        "name": category.get("name") or category.get("displayName") or category.get("type"),
        "labels": category.get("labels"),
        "names": category.get("names"),
        "first_event": _first_event(category.get("events")),
    }


def execute():
    req = Request(
        URL + "?" + urlencode({"season": 2026}),
        headers={"Accept": "application/json,text/plain,*/*", "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(req, timeout=10) as response:
        payload = json.loads(response.read().decode())
        status = int(getattr(response, "status", 200))
    view = {
        "status": status,
        "root_keys": sorted(payload.keys()),
        "root_labels": payload.get("labels"),
        "root_names": payload.get("names"),
        "root_first_event": _first_event(payload.get("events")),
        "root_categories": [_category_view(x) for x in (payload.get("categories") or [])[:3]],
        "season_types": [],
    }
    for season_type in (payload.get("seasonTypes") or [])[:3]:
        if not isinstance(season_type, dict):
            continue
        view["season_types"].append({
            "name": season_type.get("name") or season_type.get("displayName") or season_type.get("type"),
            "categories": [_category_view(x) for x in (season_type.get("categories") or [])[:3]],
        })
    return view


def install_startup(app):
    app.state.wnba_rebound_provider_diag = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_rebound_provider_diag = {"status": "GREEN", "evidence": execute()}
        except Exception as exc:
            app.state.wnba_rebound_provider_diag = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]}
        print("WNBA_REBOUND_PROVIDER_DIAG=" + json.dumps(app.state.wnba_rebound_provider_diag, sort_keys=True), flush=True)
    return app
