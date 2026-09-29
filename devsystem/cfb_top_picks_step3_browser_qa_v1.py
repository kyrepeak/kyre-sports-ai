"""Browser proof for CFB Top Picks Step 3 live-ranked card rendering."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from devsystem.browser_qa_v1 import _find_app_frame


def run(base_url: str, artifact_dir: str | Path) -> dict:
    artifacts=Path(artifact_dir); artifacts.mkdir(parents=True,exist_ok=True)
    url=base_url.rstrip("/")+"/?ks_sport=College+Football&ks_cfb_market=Top+Picks"
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":1440,"height":1100})
            page.goto(url,wait_until="domcontentloaded",timeout=90000)
            frame,scans=_find_app_frame(page,timeout_seconds=90.0)
            body=frame.locator("body").inner_text(timeout=5000)
            for marker in ("Top Picks","10 Best Daily College Football Picks","LIVE MODEL BOARD","MARKET DATA HAS 0% PROJECTION WEIGHT"):
                if marker.casefold() not in body.casefold():
                    raise AssertionError(f"missing {marker!r}; body={body[:5000]!r}")
            cards=frame.locator('article[data-testid^="cfb-top-picks-card-"]')
            if cards.count()!=10:
                raise AssertionError(f"expected 10 live-ranked cards, found {cards.count()}")
            if cards.locator('[data-expanded="true"]').count()!=0:
                raise AssertionError("Step 3 cards must remain collapsed")
            for market in ("MONEYLINE","SPREAD","OVER/UNDER"):
                if market not in body:
                    raise AssertionError(f"missing market type {market}")
            if "LAYOUT PREVIEW" in body:
                raise AssertionError("Step 2 preview label leaked into Step 3")
            shot=artifacts/"cfb_top_picks_step3_live_ranking_green.png"
            page.screenshot(path=str(shot),full_page=True)
            result={"status":"GREEN","card_count":10,"route":"College Football -> Top Picks","fixture_mode":"CI only","markets":["MONEYLINE","SPREAD","OVER/UNDER"],"screenshot":str(shot),"frame_scan_count":len(scans)}
            (artifacts/"cfb_top_picks_step3_evidence.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
            print("CFB_TOP_PICKS_STEP3_BROWSER_GREEN")
            print(json.dumps(result,indent=2,sort_keys=True))
            return result
        finally:
            browser.close()


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--base-url",default="http://127.0.0.1:8501"); p.add_argument("--artifact-dir",default="artifacts/cfb-top-picks-step3")
    args=p.parse_args(); run(args.base_url,args.artifact_dir); return 0

if __name__=="__main__": raise SystemExit(main())
