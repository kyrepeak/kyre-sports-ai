import traceback

import pandas as pd


def _run_boundary(name, fn):
    try:
        return fn()
    except Exception as exc:
        print(f"LIVE_PRA_BOUNDARY_FAILURE={name}")
        print(f"LIVE_PRA_EXCEPTION={type(exc).__name__}:{exc}")
        traceback.print_exc()
        raise


def test_slate_player_pool_fails_closed_when_team_id_is_missing():
    import wnba_availability_v27 as availability

    schedule = pd.DataFrame([{"away_team_id": 1, "home_team_id": 2}])
    stats = pd.DataFrame([{"PLAYER_NAME": "Missing Team Identity"}])

    pool = availability.slate_player_pool(schedule, stats)
    assert isinstance(pool, pd.DataFrame)
    assert pool.empty


def test_active_wnba_pra_snapshot_boundaries_do_not_raise_keyerror():
    import wnba_pra_hub_v3616 as hub
    import wnba_pra_product_snapshot_v1 as snapshot
    import wnba_pra_market_v29 as market
    import wnba_pra_matchup_v30 as matchup
    import wnba_pra_final_v32 as final
    import wnba_pra_hub_v27 as v27
    import wnba_role_v282 as role

    hub.api_market.install()
    day = _run_boundary("resolve_active_slate_date", hub.resolve_active_slate_date)
    print(f"LIVE_PRA_ACTIVE_DAY={day}")

    _run_boundary("market_projection_frame", lambda: market._projection_frame(day))
    _run_boundary("market_grade", lambda: market.grade_pra_markets(day))
    _run_boundary("matchup_grade", lambda: matchup.grade_matchup_pra(day))
    _run_boundary("stored_rows", lambda: final._stored_rows(day))
    _run_boundary("availability_diagnostics", lambda: v27.availability.availability_diagnostics(day))
    _run_boundary("role_diagnostics", lambda: role.role_diagnostics(day))
    product = _run_boundary("build_product_snapshot", lambda: snapshot.build_product_snapshot(day))
    assert product.day == str(day)


def test_public_streamlit_wnba_pra_route_has_no_keyerror():
    from playwright.sync_api import sync_playwright
    from devsystem.browser_qa_v1 import _find_app_frame

    route = "https://pickvault.streamlit.app/?ks_jump_sport=WNBA&ks_jump_market=PRA"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 1200, "height": 1100})
        page = context.new_page()
        try:
            page.goto(route, wait_until="domcontentloaded", timeout=90000)
            frame, _ = _find_app_frame(page, timeout_seconds=75.0)
            frame.get_by_text("WNBA", exact=False).first.wait_for(state="visible", timeout=30000)
            page.wait_for_timeout(4000)
            body = frame.locator("body").inner_text(timeout=15000)
            print("LIVE_PRA_PUBLIC_BODY_START")
            print(body[:5000])
            print("LIVE_PRA_PUBLIC_BODY_END")
            assert "KeyError" not in body, "LIVE_PRA_PUBLIC_KEYERROR_PRESENT"
            assert "WNBA PRA" in body, "LIVE_PRA_PUBLIC_PRODUCT_SURFACE_MISSING"
        finally:
            context.close()
            browser.close()
