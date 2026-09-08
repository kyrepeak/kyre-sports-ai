"""Regression checks for CFB O/U multi-source logo resolver V2."""
from __future__ import annotations

import cfb_over_under_logo_resolver_v2 as logos


def test_wikipedia_candidate_scoring_handles_miami_fl_with_acc_context():
    page = {
        "title": "Miami Hurricanes football",
        "extract": "The Miami Hurricanes compete in the ACC.",
    }
    assert logos._candidate_score(page, "Miami (FL)", "ACC") >= 12.0


def test_best_official_url_prefers_football_athletics_link():
    page = {
        "extlinks": [
            {"url": "https://www.youtube.com/example"},
            {"url": "https://example.edu/"},
            {"url": "https://famuathletics.com/sports/football"},
        ]
    }
    assert logos._best_official_url(page) == "https://famuathletics.com/sports/football"


def test_official_html_parser_prefers_logo_image():
    parser = logos._LogoHtmlParser("Florida A&M")
    parser.feed(
        '''
        <html><head><meta property="og:image" content="https://example.com/hero.jpg"></head>
        <body>
          <img class="site-logo" alt="Florida A&M Logo" src="/images/famu-logo.png">
          <img alt="player photo" src="/images/player.jpg">
        </body></html>
        '''
    )
    assert parser.image_candidates
    score, src = sorted(parser.image_candidates, reverse=True)[0]
    assert score > 0
    assert src == "/images/famu-logo.png"


def test_resolve_team_logo_prefers_official_over_wikipedia(monkeypatch):
    page = {
        "pageid": 1,
        "title": "Florida A&M Rattlers football",
        "_logo_score": 20.0,
        "fullurl": "https://en.wikipedia.org/wiki/Florida_A%26M_Rattlers_football",
        "thumbnail": {"source": "https://upload.wikimedia.org/wiki-thumb.png"},
        "extlinks": [{"url": "https://famuathletics.com/sports/football"}],
    }
    monkeypatch.setattr(logos, "_wikipedia_candidates", lambda *a, **k: ([page], []))
    monkeypatch.setattr(
        logos,
        "_official_page_logo",
        lambda *a, **k: ("https://famuathletics.com/images/logo.png", []),
    )
    monkeypatch.setattr(logos, "_commons_logo", lambda *a, **k: ("", []))

    out = logos.resolve_team_logo.__wrapped__("Florida A&M", "florida-a-m", "SWAC")
    assert out["logo_provider"] == "official_athletics"
    assert out["logo"] == "https://famuathletics.com/images/logo.png"
    assert out["confidence"] == "HIGH"


def test_resolve_team_logo_uses_wikipedia_when_official_unavailable(monkeypatch):
    page = {
        "pageid": 2,
        "title": "Miami Hurricanes football",
        "_logo_score": 20.0,
        "fullurl": "https://en.wikipedia.org/wiki/Miami_Hurricanes_football",
        "original": {"source": "https://upload.wikimedia.org/miami.svg"},
        "extlinks": [{"url": "https://miamihurricanes.com/sports/football"}],
    }
    monkeypatch.setattr(logos, "_wikipedia_candidates", lambda *a, **k: ([page], []))
    monkeypatch.setattr(logos, "_official_page_logo", lambda *a, **k: ("", []))
    monkeypatch.setattr(logos, "_commons_logo", lambda *a, **k: ("", []))

    out = logos.resolve_team_logo.__wrapped__("Miami (FL)", "miami-fl", "ACC")
    assert out["logo_provider"] == "wikipedia_pageimage"
    assert out["logo"] == "https://upload.wikimedia.org/miami.svg"


def test_resolve_team_logo_uses_commons_as_last_fallback(monkeypatch):
    monkeypatch.setattr(logos, "_wikipedia_candidates", lambda *a, **k: ([], []))
    monkeypatch.setattr(
        logos,
        "_commons_logo",
        lambda *a, **k: ("https://upload.wikimedia.org/commons-logo.svg", []),
    )

    out = logos.resolve_team_logo.__wrapped__("Example State", "example-state", "ACC")
    assert out["logo_provider"] == "wikimedia_commons"
    assert out["logo"].endswith("commons-logo.svg")


def test_resolve_visuals_fills_only_missing_side(monkeypatch):
    monkeypatch.setattr(
        logos.espn,
        "resolve_visuals",
        lambda game: {
            "away": {
                "logo": "https://a.espncdn.com/away.png",
                "source": "ESPN College Football",
            },
            "home": {},
        },
    )

    calls = []

    def fallback(name, slug="", conference=""):
        calls.append((name, slug, conference))
        return {
            "logo": "https://upload.wikimedia.org/home.svg",
            "logo_provider": "wikipedia_pageimage",
            "source": "Wikipedia / Wikimedia",
        }

    monkeypatch.setattr(logos, "resolve_team_logo", fallback)

    out = logos.resolve_visuals(
        {
            "away_team": "Florida A&M",
            "away_team_slug": "florida-a-m",
            "away_conference": "SWAC",
            "home_team": "Miami (FL)",
            "home_team_slug": "miami-fl",
            "home_conference": "ACC",
        }
    )

    assert out["away"]["logo"] == "https://a.espncdn.com/away.png"
    assert out["away"]["logo_provider"] == "espn"
    assert out["home"]["logo"] == "https://upload.wikimedia.org/home.svg"
    assert calls == [("Miami (FL)", "miami-fl", "ACC")]


def test_resolve_visuals_can_fill_both_when_espn_is_empty(monkeypatch):
    monkeypatch.setattr(
        logos.espn,
        "resolve_visuals",
        lambda game: {"away": {}, "home": {}},
    )

    def fallback(name, slug="", conference=""):
        return {
            "logo": f"https://upload.wikimedia.org/{slug}.svg",
            "logo_provider": "wikimedia_commons",
            "source": "Wikimedia Commons",
        }

    monkeypatch.setattr(logos, "resolve_team_logo", fallback)

    out = logos.resolve_visuals(
        {
            "away_team": "Florida A&M",
            "away_team_slug": "florida-a-m",
            "away_conference": "SWAC",
            "home_team": "Miami (FL)",
            "home_team_slug": "miami-fl",
            "home_conference": "ACC",
        }
    )
    assert out["away"]["logo"].endswith("florida-a-m.svg")
    assert out["home"]["logo"].endswith("miami-fl.svg")
