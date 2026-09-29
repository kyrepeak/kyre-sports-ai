"""Fresh-session responsive browser cert for WNBA Navigation V2 Step 6."""
from __future__ import annotations
import argparse, time
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

VIEWPORTS=((390,844),(768,1024),(1440,1000))
PAGES=("slate","game","player")

def find_frame(page,selector,timeout=60):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        for frame in page.frames:
            try:
                loc=frame.locator(selector)
                if loc.count():
                    return frame,loc.first
            except Exception:
                pass
        page.wait_for_timeout(150)
    details=[]
    for frame in page.frames:
        try:
            body=frame.locator("body")
            if body.count():
                details.append(body.inner_text(timeout=2000)[:2500])
        except Exception:
            pass
    raise RuntimeError("WNBA_STEP6_SELECTOR_NOT_READY:"+selector+"\nBODY:\n"+"\n---FRAME---\n".join(details))


def wait_buttons(frame, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            buttons=frame.locator('div[data-testid="stButton"] button')
            if buttons.count()>=1:
                buttons.first.wait_for(state="visible",timeout=2000)
                return buttons
        except Exception:
            pass
        frame.page.wait_for_timeout(100)
    raise RuntimeError("WNBA_STEP6_BUTTONS_NOT_READY")

def certify(base):
    results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox"])
        for page_name in PAGES:
            for width,height in VIEWPORTS:
                # Monster Speed V3 rule: fresh context/page for every viewport.
                context=browser.new_context(viewport={"width":width,"height":height})
                page=context.new_page()
                url=base+"/?"+urlencode({"proof_page":page_name})
                page.goto(url,wait_until="domcontentloaded",timeout=90000)
                frame,marker=find_frame(
                    page,
                    f'[data-wnba-nav-v2-step6="responsive-integration"][data-wnba-nav-page="{page_name}"]',
                    60,
                )
                assert marker.get_attribute("data-wnba-nav-responsive-targets")=="390,768,1440"
                assert marker.get_attribute("data-wnba-nav-zero-overflow")=="required"
                find_frame(page,f'[data-wnba-step6-proof-page="{page_name}"]',60)
                body=frame.locator("body")
                dims=body.evaluate("""e=>({
                  bodyScroll:e.scrollWidth,
                  docScroll:document.documentElement.scrollWidth,
                  viewport:window.innerWidth
                })""")
                assert max(dims["bodyScroll"],dims["docScroll"])<=dims["viewport"]+2,(page_name,width,dims)
                buttons=wait_buttons(frame,30)
                for i in range(buttons.count()):
                    box=buttons.nth(i).bounding_box()
                    assert box and box["height"]>=43.5,(page_name,width,box)
                first=buttons.first
                first.focus()
                style=first.evaluate("""e=>{const s=getComputedStyle(e);return {o:s.outlineStyle,w:s.outlineWidth,sh:s.boxShadow}}""")
                visible=(style["o"]!="none" and float((style["w"] or "0px").replace("px","") or 0)>=1) or style["sh"] not in ("","none")
                assert visible,(page_name,width,style)
                text=body.inner_text().lower()
                assert "traceback" not in text and "uncaught app exception" not in text,(page_name,width)
                results.append((page_name,width,"GREEN"))
                print(f"WNBA_NAV_STEP6_{page_name.upper()}_{width}_GREEN")
                context.close()
        browser.close()
    assert len(results)==9
    print("WNBA_NAV_STEP6_FRESH_SESSION_GREEN")
    print("WNBA_NAV_STEP6_ZERO_HORIZONTAL_OVERFLOW_GREEN")
    print("WNBA_NAV_STEP6_RESPONSIVE_BROWSER_GREEN")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base-url",required=True)
    a=p.parse_args()
    certify(a.base_url.rstrip("/"))
if __name__=="__main__": main()
