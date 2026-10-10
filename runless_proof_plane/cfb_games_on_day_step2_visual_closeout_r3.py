from __future__ import annotations

import json
import subprocess
import sys

from . import cfb_games_on_day_step2_visual_closeout as base


class Step2VisualCloseoutR3Failure(RuntimeError):
    pass


def _public_mobile_proof_subprocess() -> dict:
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    if install.returncode != 0:
        raise Step2VisualCloseoutR3Failure("PLAYWRIGHT_CHROMIUM_INSTALL_FAILED:" + install.stdout[-1600:])

    route = (
        base.PRODUCTION_URL.rstrip("/")
        + "/?ks_sport=College+Football&ks_cfb_market=Game+Total"
        + f"&ks_cfb_game_total_date={base.PRODUCTION_DATE}"
    )
    script = r'''
import json, time
from playwright.sync_api import sync_playwright

route = __ROUTE__
observer = r"""
(() => {
  if (window.__kyreStep2ObserverInstalled) return;
  window.__kyreStep2ObserverInstalled = true;
  const probe = () => {
    try {
      const marker = document.querySelector('style[data-kyre-cfb-games-on-day-step2-visual="v1"]');
      const strip = document.querySelector('[data-testid="gt163-game-strip"][data-step2-visual="v1"]');
      const cards = Array.from(document.querySelectorAll('.gt2-game-card'));
      if (!marker || !strip || cards.length < 1) return;
      const selected = document.querySelectorAll('.gt2-game-card.selected[aria-current="true"]');
      const kickoffs = Array.from(document.querySelectorAll('.gt2-kickoff')).map(x => (x.textContent || '').trim());
      const logos = document.querySelectorAll('.gt2-team-logo');
      const fallbacks = document.querySelectorAll('.gt2-team-logo-fallback');
      let selectedVisuals = 0;
      if (selected.length === 1) selectedVisuals = selected[0].querySelectorAll('.gt2-team-logo,.gt2-team-logo-fallback').length;
      const payload = {
        marker_count: 1,
        card_count: cards.length,
        selected_card_count: selected.length,
        selected_visual_count: selectedVisuals,
        logo_count: logos.length,
        fallback_count: fallbacks.length,
        phoenix_time: kickoffs.some(x => x.includes('MST')),
        section_horizontal_overflow: strip.scrollWidth > strip.clientWidth + 3,
        document_horizontal_overflow: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) > document.documentElement.clientWidth + 3,
        kickoff_text: kickoffs.join(' | '),
        href: location.href,
        capture_phase: 'mutation-observer'
      };
      console.log('KYRE_STEP2_EVIDENCE=' + JSON.stringify(payload));
    } catch (e) {}
  };
  const arm = () => {
    probe();
    try {
      new MutationObserver(probe).observe(document.documentElement || document, {subtree:true, childList:true, attributes:true});
    } catch (e) {}
    setInterval(probe, 25);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arm, {once:true}); else arm();
})();
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--disable-dev-shm-usage','--no-sandbox'])
    context = browser.new_context(viewport={'width':390,'height':844})
    context.add_init_script(observer)
    page = context.new_page()
    evidence = []
    page.on('console', lambda msg: evidence.append(msg.text) if msg.text.startswith('KYRE_STEP2_EVIDENCE=') else None)
    try:
        page.goto(route, wait_until='commit', timeout=120000)
        deadline = time.monotonic() + 150.0
        while time.monotonic() < deadline:
            if evidence:
                raw = evidence[-1].split('=',1)[1]
                payload = json.loads(raw)
                if (
                    payload.get('marker_count') == 1
                    and payload.get('card_count',0) >= 1
                    and payload.get('selected_card_count') == 1
                    and payload.get('selected_visual_count',0) >= 2
                    and payload.get('logo_count',0) >= 2
                    and payload.get('phoenix_time') is True
                    and payload.get('section_horizontal_overflow') is False
                    and payload.get('document_horizontal_overflow') is False
                ):
                    payload.update({
                        'status':'GREEN',
                        'url':route,
                        'page_url':page.url,
                        'viewport':{'width':390,'height':844},
                        'runtime_error':'',
                    })
                    print('CFB_GAMES_ON_DAY_STEP2_PUBLIC_PROOF_R3=' + json.dumps(payload, sort_keys=True))
                    raise SystemExit(0)
            time.sleep(0.05)
        diag = {
            'evidence_count': len(evidence),
            'page_url': page.url,
            'frames': [f.url for f in page.frames],
            'last_evidence': evidence[-1][-2200:] if evidence else '',
        }
        raise RuntimeError('STEP2_PUBLIC_MOBILE_PROOF_R3_TIMEOUT:' + json.dumps(diag, sort_keys=True))
    finally:
        context.close()
        browser.close()
'''.replace("__ROUTE__", repr(route))

    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    marker = "CFB_GAMES_ON_DAY_STEP2_PUBLIC_PROOF_R3="
    line = next((row[len(marker):] for row in reversed(completed.stdout.splitlines()) if row.startswith(marker)), "")
    if completed.returncode != 0 or not line:
        raise Step2VisualCloseoutR3Failure("PUBLIC_PROOF_R3_SUBPROCESS_FAILED:" + completed.stdout[-3600:])
    payload = json.loads(line)
    if payload.get("status") != "GREEN":
        raise Step2VisualCloseoutR3Failure("PUBLIC_PROOF_R3_NOT_GREEN")
    return payload


def execute(app):
    base._public_mobile_proof_subprocess = _public_mobile_proof_subprocess
    return base.execute(app)


def install_startup(app):
    app.state.cfb_games_on_day_step2_visual_closeout_r3 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step2_visual_closeout_r3 = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step2_visual_closeout_r3 = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP2_VISUAL_CLOSEOUT_R3="
            + json.dumps(app.state.cfb_games_on_day_step2_visual_closeout_r3, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
