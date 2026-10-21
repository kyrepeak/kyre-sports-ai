"""Static certification for WNBA PRA Page 1 refresh handoff V1."""
from __future__ import annotations
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main() -> int:
    failures=[]
    hub=(ROOT/'wnba_pra_hub_v3618.py').read_text(encoding='utf-8')
    compat=(ROOT/'wnba_pra_hub_v3612.py').read_text(encoding='utf-8')
    router=(ROOT/'streamlit_memory_lazy_router_v1.py').read_text(encoding='utf-8')
    for token in ('sportsgameodds','sgo','espn bet','espn.com','render.com'):
        if token in hub.casefold(): failures.append(f'forbidden_source:{token}')
    for token in ('import requests','import httpx'):
        if token in hub: failures.append(f'new_network_client:{token}')
    for token in (
        '_CONVERGENCE_DELAYS_SECONDS = (0.0, 0.25, 0.75)',
        'import wnba_pra_hub_v3617 as previous',
        '_refresh(day, background=False)',
        '_fetch_until_converged(day)',
    ):
        if token not in hub: failures.append(f'missing_handoff_contract:{token}')
    if hub.count('_refresh(day, background=False)') != 1:
        failures.append('sync_refresh_not_exactly_once')
    for token in (
        'import wnba_pra_hub_v3617 as active',
        'active.render_page_snapshot = _page1_final_polish.render_page_snapshot',
        'import wnba_pra_hub_v3618 as refresh_handoff',
        'return refresh_handoff.render_wnba_pra_hub',
    ):
        if token not in compat: failures.append(f'compat_contract_missing:{token}')
    if '_import("wnba_pra_hub_v3612")' not in router:
        failures.append('historical_streamlit_route_changed')
    if failures:
        print('WNBA_PRA_PAGE1_REFRESH_HANDOFF_SOURCE_POLICY_V1_RED')
        for failure in failures: print(failure)
        return 1
    print('WNBA_PRA_PAGE1_REFRESH_HANDOFF_SOURCE_POLICY_V1_GREEN')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
