from __future__ import annotations

import json
from urllib import parse, request

WNBA_STATS = "https://stats.wnba.com/stats/playergamelog"
BREF = "https://www.basketball-reference.com/wnba/players/s/stewabr01w.html"


def _probe(url: str, headers: dict[str, str]) -> dict:
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read(200000).decode("utf-8", "replace")
            return {
                "status": int(response.status),
                "length": len(body),
                "prefix": body[:180],
                "has_pts": '"PTS"' in body or ">PTS<" in body,
                "has_ast": '"AST"' in body or ">AST<" in body,
                "has_reb": '"REB"' in body or ">TRB<" in body,
                "has_2026": "2026" in body,
            }
    except Exception as exc:
        return {"error": type(exc).__name__, "detail": str(exc)[:400]}


def execute() -> dict:
    params = parse.urlencode({
        "DateFrom": "",
        "DateTo": "",
        "LeagueID": "10",
        "PlayerID": "1627668",
        "Season": "2026",
        "SeasonType": "Regular Season",
    })
    wnba_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.wnba.com",
        "Referer": "https://www.wnba.com/",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
    }
    bref_headers = {"User-Agent": "Mozilla/5.0"}
    return {
        "status": "COMPLETE",
        "wnba_stats_api": _probe(WNBA_STATS + "?" + params, wnba_headers),
        "basketball_reference": _probe(BREF, bref_headers),
    }


def install_startup(app):
    app.state.wnba_history_provider_probe = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        app.state.wnba_history_provider_probe = execute()
        print("WNBA_HISTORY_PROVIDER_PROBE=" + json.dumps(app.state.wnba_history_provider_probe, sort_keys=True), flush=True)

    return app
