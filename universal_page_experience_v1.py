"""Universal Page Experience V1 — shared TOP control + transition presentation."""
from __future__ import annotations

from html import escape
import json
from typing import Any

from universal_atomic_navigation_v2 import LOADER_DELAY_MS, destination_page_name

PAGE_EXPERIENCE_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE V1"
TOP_REVEAL_PX = 320
TOP_TARGET_ID = "kyre-universal-page-top"
SERVER_LOADER_DELAY_MS = 120

_TOP_SENTINEL = (
    '<span id="kyre-universal-page-top" data-kyre-page-top="v2" aria-hidden="true" '
    'style="display:block;height:0;width:0;overflow:hidden"></span>'
)

_NATIVE_TOP = r'''<style id="kyre-universal-top-native-v2-style">
a[data-kyre-universal-top="v2"]{position:fixed;right:max(18px,calc(env(safe-area-inset-right,0px) + 14px));bottom:max(22px,calc(env(safe-area-inset-bottom,0px) + 18px));z-index:2147483646;min-width:44px;min-height:44px;padding:0 14px;border:1px solid rgba(125,211,252,.5);border-radius:999px;background:rgba(6,11,19,.96);color:#7dd3fc;font:900 12px/44px system-ui,-apple-system,sans-serif;letter-spacing:.08em;text-align:center;text-decoration:none;box-sizing:border-box;box-shadow:0 10px 30px rgba(0,0,0,.38),0 0 20px rgba(125,211,252,.12);cursor:pointer;pointer-events:auto!important;touch-action:manipulation;-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent}
a[data-kyre-universal-top="v2"]:focus-visible{outline:2px solid #7dd3fc;outline-offset:3px}
@media (prefers-reduced-motion:reduce){a[data-kyre-universal-top="v2"]{scroll-behavior:auto}}
</style>
<a data-kyre-universal-top="v2" data-no-js-fallback-href="#" href="#kyre-universal-page-top" aria-label="Back to top">↑ TOP</a>'''

_CONTROLLER = r'''<script>
(() => {
  const host = window.parent;
  const doc = host.document;
  const KEY = "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V1__";
  const INITIAL_PAGE = __INITIAL_PAGE__;
  const TOP_REVEAL_PX = 320;
  const DELAY_MS = 140;
  const PAGE_TRANSITION = "PAGE_TRANSITION";
  const LOCAL_INTERACTION = "LOCAL_INTERACTION";
  const existing = host[KEY];
  if (existing && existing.version === "v1") { existing.refresh(INITIAL_PAGE); return; }

  const styleId = "kyre-universal-page-experience-v1-style";
  if (!doc.getElementById(styleId)) {
    const style = doc.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-kyre-universal-top="v1"]{position:fixed;right:max(18px,calc(env(safe-area-inset-right,0px) + 14px));bottom:max(22px,calc(env(safe-area-inset-bottom,0px) + 18px));z-index:2147483646;min-width:44px;min-height:44px;padding:0 14px;border:1px solid rgba(125,211,252,.5);border-radius:999px;background:rgba(6,11,19,.96);color:#7dd3fc;font:900 12px/44px system-ui,-apple-system,sans-serif;letter-spacing:.08em;cursor:pointer;opacity:0;pointer-events:none;transform:translateY(8px);transition:opacity .16s ease,transform .16s ease}
      [data-kyre-universal-top="v1"][aria-hidden="false"]{opacity:1;pointer-events:auto;transform:translateY(0)}
      [data-kyre-universal-loading="upe-v1"]{position:fixed;inset:0;z-index:2147483647;background:radial-gradient(circle at 50% 38%,rgba(14,165,233,.17),transparent 34%),linear-gradient(180deg,#050a12 0%,#07111d 52%,#050910 100%);pointer-events:all;display:none;place-items:center;min-height:100vh;opacity:0}
      [data-kyre-universal-loading="upe-v1"][aria-hidden="false"]{display:grid;animation:kyre-upe-reveal .16s ease forwards;animation-delay:120ms}
      [data-kyre-universal-loading="upe-v1"]:before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(125,211,252,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(125,211,252,.035) 1px,transparent 1px);background-size:32px 32px}
      .kyre-upe-card{position:relative;width:min(520px,88vw);text-align:center;color:#f8fafc;padding:34px 24px 30px;border:1px solid rgba(125,211,252,.22);border-radius:26px;background:linear-gradient(145deg,rgba(7,17,31,.96),rgba(10,23,38,.96));box-shadow:0 26px 80px rgba(0,0,0,.54),0 0 55px rgba(14,165,233,.08)}
      .kyre-upe-orbit{position:relative;width:74px;height:74px;margin:0 auto 18px;border-radius:50%;border:1px solid rgba(125,211,252,.18);display:grid;place-items:center;box-shadow:inset 0 0 28px rgba(14,165,233,.08)}
      .kyre-upe-orbit:before{content:"";position:absolute;inset:-1px;border-radius:50%;border-top:2px solid #7dd3fc;border-right:2px solid transparent;animation:kyre-upe-spin .9s linear infinite}
      .kyre-upe-core{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,#0b2237,#07121f);border:1px solid rgba(125,211,252,.25);color:#7dd3fc;font:950 12px/1 system-ui,-apple-system,sans-serif;letter-spacing:.1em}
      .kyre-upe-brand{font-size:.72rem;font-weight:950;letter-spacing:.2em;color:#7dd3fc}.kyre-upe-page{margin-top:12px;font-size:1.28rem;font-weight:950;line-height:1.2}.kyre-upe-load{margin-top:9px;font-size:.86rem;font-weight:800;color:#b7c8d8}.kyre-upe-track{height:3px;margin:20px auto 0;max-width:230px;border-radius:999px;background:rgba(148,163,184,.12);overflow:hidden}.kyre-upe-track:after{content:"";display:block;width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,transparent,#7dd3fc,transparent);animation:kyre-upe-track 1.15s ease-in-out infinite}
      @keyframes kyre-upe-reveal{from{opacity:0}to{opacity:1}}@keyframes kyre-upe-spin{to{transform:rotate(360deg)}}@keyframes kyre-upe-track{from{transform:translateX(-120%)}to{transform:translateX(300%)}}
      @media(prefers-reduced-motion:reduce){[data-kyre-universal-loading="upe-v1"]{animation:none!important}.kyre-upe-orbit:before,.kyre-upe-track:after{animation:none!important}}`;
    doc.head.appendChild(style);
  }

  let topButton = doc.querySelector('[data-kyre-universal-top="v2"]') || doc.querySelector('[data-kyre-universal-top="v1"]');
  if (!topButton) {
    topButton = doc.createElement("button");
    topButton.type = "button";
    topButton.setAttribute("data-kyre-universal-top", "v1");
    topButton.setAttribute("aria-label", "Back to top");
    topButton.setAttribute("aria-hidden", "true");
    topButton.textContent = "↑ TOP";
    doc.body.appendChild(topButton);
  }

  let overlay = doc.querySelector('[data-kyre-universal-loading="upe-v1"]');
  if (!overlay) {
    overlay = doc.createElement("div");
    overlay.setAttribute("data-kyre-universal-loading", "upe-v1");
    overlay.setAttribute("aria-hidden", "true");
    overlay.setAttribute("aria-live", "polite");
    overlay.innerHTML = '<div class="kyre-upe-card"><div class="kyre-upe-orbit"><div class="kyre-upe-core">KS</div></div><div class="kyre-upe-brand">KYRE SPORTS AI</div><div class="kyre-upe-page"></div><div class="kyre-upe-load">Loading intelligence</div><div class="kyre-upe-track"></div></div>';
    doc.body.appendChild(overlay);
  }
  const pageNode = overlay.querySelector(".kyre-upe-page");

  let scrollOwner = null;
  let observer = null;
  let timer = null;
  let pendingName = INITIAL_PAGE;
  let pendingKind = LOCAL_INTERACTION;
  let pendingRoute = "";

  function resolveScrollOwner() {
    const appView = doc.querySelector('[data-testid="stAppViewContainer"]');
    if (appView && appView.scrollHeight > appView.clientHeight + 4) return appView;
    return doc.scrollingElement || document.scrollingElement || doc.documentElement || doc.body;
  }
  function scrollY() {
    const owner = scrollOwner || resolveScrollOwner();
    if (owner === doc.documentElement || owner === doc.body || owner === doc.scrollingElement || owner === document.scrollingElement) return host.scrollY || owner.scrollTop || 0;
    return owner.scrollTop || 0;
  }
  function syncTop() {
    if (topButton.getAttribute("data-kyre-universal-top") === "v2") {
      topButton.setAttribute("aria-hidden", "false");
      return;
    }
    topButton.setAttribute("aria-hidden", scrollY() >= TOP_REVEAL_PX ? "false" : "true");
  }
  function bindScroll() {
    const next = resolveScrollOwner();
    if (scrollOwner === next) { syncTop(); return; }
    if (scrollOwner && scrollOwner.removeEventListener) scrollOwner.removeEventListener("scroll", syncTop);
    host.removeEventListener("scroll", syncTop);
    scrollOwner = next;
    if (scrollOwner === doc.documentElement || scrollOwner === doc.body || scrollOwner === doc.scrollingElement || scrollOwner === document.scrollingElement) host.addEventListener("scroll", syncTop, {passive:true});
    else scrollOwner.addEventListener("scroll", syncTop, {passive:true});
    syncTop();
  }
  function goTop() {
    const owner = scrollOwner || resolveScrollOwner();
    const reduce = host.matchMedia && host.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior = reduce ? "auto" : "smooth";
    const target = doc.getElementById("kyre-universal-page-top");
    if (target && target.scrollIntoView) target.scrollIntoView({block:"start",behavior});
    if (owner && owner.scrollTo) owner.scrollTo({top:0,left:0,behavior});
    host.scrollTo({top:0,left:0,behavior});
  }
  function onTopClick(event) {
    if (event && event.preventDefault) event.preventDefault();
    goTop();
  }

  function routeSignature() {
    const p = new URLSearchParams(host.location.search || "");
    return [p.get("sport")||"",p.get("market")||"",p.get("game_id")||"",p.get("player_id")||"",p.get("prop")||p.get("market_key")||"",p.get("page")||""].join("|");
  }
  function scriptState() {
    const app = doc.querySelector('[data-testid="stApp"]');
    return String(app ? app.getAttribute("data-test-script-state") || "" : "").toUpperCase().replace(/[^A-Z]/g, "");
  }
  function cancelTimer() { if (timer !== null) { host.clearTimeout(timer); timer = null; } }
  function showOverlay() { if (pageNode) pageNode.textContent = pendingName || INITIAL_PAGE || "Sports"; overlay.setAttribute("aria-hidden", "false"); }
  function hideOverlay() { overlay.setAttribute("aria-hidden", "true"); }
  function armTransition(name) {
    pendingKind = PAGE_TRANSITION;
    pendingName = name || INITIAL_PAGE || "Sports";
    pendingRoute = routeSignature();
    cancelTimer();
    showOverlay();
  }
  function classify(node) {
    if (!node) return LOCAL_INTERACTION;
    if (node.closest('input,textarea,select,[role="slider"],[type="range"]')) return LOCAL_INTERACTION;
    if (node.closest('[data-testid="stToolbar"],header,[data-testid="stSidebar"]')) return LOCAL_INTERACTION;
    if (node.closest('.st-key-ks_universal_nav_shell')) return PAGE_TRANSITION;
    const text = String(node.innerText || node.textContent || "").replace(/\s+/g," ").trim();
    if (/\b(analy[sz]e|open|view|back)\b/i.test(text) || /←/.test(text)) return PAGE_TRANSITION;
    if (node.tagName === "A" && node.getAttribute("href")) return PAGE_TRANSITION;
    return LOCAL_INTERACTION;
  }
  function inferName(node) {
    const text = String(node && (node.innerText || node.textContent) || "").replace(/\s+/g," ").trim();
    if (/back/i.test(text)) return "Returning to previous page";
    if (/analy[sz]e/i.test(text)) return "Player Analysis";
    return text && text.length < 70 ? text : INITIAL_PAGE;
  }
  function onPointerDown(event) {
    const node = event.target && event.target.closest ? event.target.closest('button,a,[role="button"],input,textarea,select') : null;
    if (!node) return;
    if (node.matches && node.matches('[data-kyre-universal-top="v2"],[data-kyre-universal-top="v1"]')) return;
    const appView = doc.querySelector('[data-testid="stAppViewContainer"]');
    if (appView && !appView.contains(node)) return;
    const kind = classify(node);
    if (kind === PAGE_TRANSITION) armTransition(inferName(node));
    else { pendingKind = LOCAL_INTERACTION; cancelTimer(); hideOverlay(); }
  }
  function onStateChange() {
    if (scriptState() === "NOTRUNNING") {
      cancelTimer(); hideOverlay(); pendingKind = LOCAL_INTERACTION;
      pendingRoute = routeSignature(); bindScroll();
    }
  }
  function observeApp() {
    if (observer) observer.disconnect();
    const app = doc.querySelector('[data-testid="stApp"]');
    if (!app) return;
    observer = new MutationObserver(onStateChange);
    observer.observe(app,{attributes:true,attributeFilter:["data-test-script-state"]});
  }
  function onPopState() { armTransition(INITIAL_PAGE); }

  topButton.addEventListener("click", onTopClick);
  doc.addEventListener("pointerdown", onPointerDown, true);
  host.addEventListener("popstate", onPopState, true);
  bindScroll();
  observeApp();

  host[KEY] = {
    version:"v1",
    refresh(initialPage) { if (initialPage) pendingName = initialPage; bindScroll(); observeApp(); if (scriptState() === "NOTRUNNING") { cancelTimer(); hideOverlay(); } },
    destroy() {
      cancelTimer(); hideOverlay();
      if (observer) observer.disconnect();
      if (scrollOwner && scrollOwner.removeEventListener) scrollOwner.removeEventListener("scroll", syncTop);
      host.removeEventListener("scroll", syncTop);
      host.removeEventListener("popstate", onPopState, true);
      doc.removeEventListener("pointerdown", onPointerDown, true);
      topButton.removeEventListener("click", onTopClick);
    }
  };
})();
</script>'''


def page_experience_top_sentinel_markup() -> str:
    """Return the real fragment target used by the native TOP control."""
    return _TOP_SENTINEL


def page_experience_native_top_markup() -> str:
    """Return the always-visible, mobile-tappable no-JavaScript TOP control."""
    return _NATIVE_TOP.strip()


def page_experience_controller_markup(route: Any | None = None) -> str:
    initial = destination_page_name(route) if route is not None else "Sports"
    return _CONTROLLER.replace("__INITIAL_PAGE__", json.dumps(initial)).strip()


def page_experience_fallback_markup(route: Any | None) -> str:
    """Return a server-held branded full-screen transition takeover."""
    page = escape(destination_page_name(route) if route is not None else "Sports Intelligence")
    return f'''<style>
@keyframes kyre-upe-server-reveal{{from{{opacity:0}}to{{opacity:1}}}}@keyframes kyre-upe-server-spin{{to{{transform:rotate(360deg)}}}}@keyframes kyre-upe-server-track{{from{{transform:translateX(-120%)}}to{{transform:translateX(300%)}}}}
[data-kyre-universal-loading="upe-v2-server"]{{position:fixed;inset:0;z-index:2147483647;pointer-events:all;display:grid;place-items:center;min-height:100vh;opacity:0;background:radial-gradient(circle at 50% 38%,rgba(14,165,233,.18),transparent 34%),linear-gradient(180deg,#050a12 0%,#07111d 52%,#060b13 100%);animation:kyre-upe-server-reveal .16s ease forwards;animation-delay:120ms}}
[data-kyre-universal-loading="upe-v2-server"]:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(125,211,252,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(125,211,252,.035) 1px,transparent 1px);background-size:32px 32px}}
.kyre-upe-server-card{{position:relative;width:min(520px,88vw);text-align:center;color:#f8fafc;padding:34px 24px 30px;border:1px solid rgba(125,211,252,.22);border-radius:26px;background:linear-gradient(145deg,rgba(7,17,31,.97),rgba(10,23,38,.97));box-shadow:0 26px 80px rgba(0,0,0,.54),0 0 55px rgba(14,165,233,.08)}}
.kyre-upe-orbit{{position:relative;width:76px;height:76px;margin:0 auto 18px;border-radius:50%;border:1px solid rgba(125,211,252,.18);display:grid;place-items:center;box-shadow:inset 0 0 28px rgba(14,165,233,.08)}}.kyre-upe-orbit:before{{content:"";position:absolute;inset:-1px;border-radius:50%;border-top:2px solid #7dd3fc;border-right:2px solid transparent;animation:kyre-upe-server-spin .9s linear infinite}}.kyre-upe-core{{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,#0b2237,#07121f);border:1px solid rgba(125,211,252,.25);color:#7dd3fc;font:950 12px/1 system-ui,-apple-system,sans-serif;letter-spacing:.1em}}.kyre-upe-server-brand{{font:950 .72rem/1.2 system-ui,-apple-system,sans-serif;letter-spacing:.2em;color:#7dd3fc}}.kyre-upe-server-page{{margin-top:12px;font:950 1.28rem/1.2 system-ui,-apple-system,sans-serif}}.kyre-upe-server-load{{margin-top:9px;color:#b7c8d8;font:800 .86rem/1.3 system-ui,-apple-system,sans-serif}}.kyre-upe-server-track{{height:3px;margin:20px auto 0;max-width:230px;border-radius:999px;background:rgba(148,163,184,.12);overflow:hidden}}.kyre-upe-server-track:after{{content:"";display:block;width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,transparent,#7dd3fc,transparent);animation:kyre-upe-server-track 1.15s ease-in-out infinite}}
@media(prefers-reduced-motion:reduce){{[data-kyre-universal-loading="upe-v2-server"]{{animation:none;opacity:1}}.kyre-upe-orbit:before,.kyre-upe-server-track:after{{animation:none}}}}
</style><div data-kyre-universal-loading="upe-v2-server" aria-live="polite" aria-label="Loading {page}"><div class="kyre-upe-server-card"><div class="kyre-upe-orbit"><div class="kyre-upe-core">KS</div></div><div class="kyre-upe-server-brand">KYRE SPORTS AI</div><div class="kyre-upe-server-page">{page}</div><div class="kyre-upe-server-load">Loading intelligence</div><div class="kyre-upe-server-track"></div></div></div>'''


__all__ = [
    "LOADER_DELAY_MS",
    "PAGE_EXPERIENCE_VERSION",
    "SERVER_LOADER_DELAY_MS",
    "TOP_REVEAL_PX",
    "TOP_TARGET_ID",
    "page_experience_top_sentinel_markup",
    "page_experience_native_top_markup",
    "page_experience_controller_markup",
    "page_experience_fallback_markup",
]
