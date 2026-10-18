import traceback


def _run_boundary(name, fn):
    try:
        return fn()
    except Exception as exc:
        print(f"LIVE_PRA_BOUNDARY_FAILURE={name}")
        print(f"LIVE_PRA_EXCEPTION={type(exc).__name__}:{exc}")
        traceback.print_exc()
        raise


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
