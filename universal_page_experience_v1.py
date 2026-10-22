"""Universal Page Experience V1 — shared TOP control + transition presentation."""
from __future__ import annotations

import json
from typing import Any

from universal_atomic_navigation_v2 import LOADER_DELAY_MS, destination_page_name, transition_markup

PAGE_EXPERIENCE_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE V1"
TOP_REVEAL_PX = 320

_NATIVE_TOP = r'''<style id="kyre-universal-top-native-v2-style">
a[data-kyre-universal-top="v2"]{position:fixed;right:max(18px,calc(env(safe-area-inset-right,0px) + 14px));bottom:max(22px,calc(env(safe-area-inset-bottom,0px) + 18px));z-index:2147483646;min-width:44px;min-height:44px;padding:0 14px;border:1px solid rgba(125,211,252,.5);border-radius:999px;background:rgba(6,11,19,.96);color:#7dd3fc;font:900 12px/44px system-ui,-apple-system,sans-serif;letter-spacing:.08em;text-align:center;text-decoration:none;box-sizing:border-box;box-shadow:0 10px 30px rgba(0,0,0,.38),0 0 20px rgba(125,211,252,.12);cursor:pointer;-webkit-tap-highlight-color:transparent}
a[data-kyre-universal-top="v2"]:focus-visible{outline:2px solid #7dd3fc;outline-offset:3px}
@media (prefers-reduced-motion:reduce){a[data-kyre-universal-top="v2"]{scroll-behavior:auto}}
</style>
<a data-kyre-universal-top="v2" href="#" aria-label="Back to top">↑ TOP</a>'''

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
      [data-kyre-universal-top="v1"]{position:fixed;right:max(18px,calc(env(safe-area-inset-right,0px) + 14px));bottom:max(22px,calc(env(safe-area-inset-bottom,0px) + 18px));z-index:2147483646;min-width:44px;min-height:44px;padding:0 14px;border:1px solid rgba(125,211,252,.5);border-radius:999px;background:rgba(6,11,19,.94);color:#7dd3fc;font:900 12px/1 system-ui,-apple-system,sans-serif;letter-spacing:.08em;box-shadow:0 10px 30px rgba(0,0,0,.38),0 0 20px rgba(125,211,252,.12);cursor:pointer;opacity:0;pointer-events:none;transform:translateY(8px);transition:opacity .16s ease,transform .16s ease}
      [data-kyre-universal-top="v1"][aria-hidden="false"]{opacity:1;pointer-events:auto;transform:translateY(0)}
      [data-kyre-universal-loading="upe-v1"]{position:fixed;inset:0;z-index:2147483647;background:#060b13;pointer-events:all;display:none;place-items:center;min-height:100vh;opacity:0;transition:opacity .08s ease}
      [data-kyre-universal-loading="upe-v1"][aria-hidden="false"]{display:grid;opacity:1}
      .kyre-upe-card{width:min(520px,88vw);text-align:center;color:#f8fafc;padding:30px 22px;border:1px solid rgba(125,211,252,.2);border-radius:24px;background:linear-gradient(145deg,#07111f,#0a1726);box-shadow:0 24px 70px rgba(0,0,0,.48)}
      .kyre-upe-brand{font-size:.72rem;font-weight:950;letter-spacing:.18em;color:#7dd3fc}.kyre-upe-page{margin-top:12px;font-size:1.25rem;font-weight:950;line-height:1.2}.kyre-upe-load{margin-top:9px;font-size:.86rem;font-weight:800;color:#b7c8d8}.kyre-upe-pulse{display:inline-block;width:7px;height:7px;margin-left:7px;border-radius:50%;background:#7dd3fc;animation:kyre-upe-pulse .8s ease-in-out infinite alternate}
      @keyframes kyre-upe-pulse{from{opacity:.22;transform:scale(.8)}to{opacity:1;transform:scale(1.12)}}
      @media (prefers-reduced-motion:reduce){[data-kyre-universal-top="v1"],[data-kyre-universal-loading="upe-v1"]{transition:none!important}.kyre-upe-pulse{animation:none!important}}`;
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
    overlay.innerHTML = '<div class="kyre-upe-card"><div class="kyre-upe-brand">KYRE SPORTS AI</div><div class="kyre-upe-page"></div><div class="kyre-upe-load">Preparing analytics<span class="kyre-upe-pulse"></span></div></div>';
    doc.body.appendChild(overlay);
  }
  const pageNode = overlay.querySelector(".kyre-upe-page");

  let scrollOwner = null;
  let timer = null;
  let observer = null;
  let pendingName = INITIAL_PAGE;
  let pendingKind = LOCAL_INTERACTION;
  let pendingRoute = "";

  function resolveScrollOwner() {
    const appView = doc.querySelector('[data-testid="stAppViewContainer"]');
    if (appView && appView.scrollHeight > appView.clientHeight + 4) return appView;
    return document.scrollingElement || doc.documentElement || doc.body;
  }
  function scrollY() {
    const owner = scrollOwner || resolveScrollOwner();
    if (owner === doc.documentElement || owner === doc.body || owner === document.scrollingElement) return host.scrollY || owner.scrollTop || 0;
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
    if (scrollOwner === doc.documentElement || scrollOwner === doc.body || scrollOwner === document.scrollingElement) host.addEventListener("scroll", syncTop, {passive:true});
    else scrollOwner.addEventListener("scroll", syncTop, {passive:true});
    syncTop();
  }
  function goTop() {
    const owner = scrollOwner || resolveScrollOwner();
    const reduce = host.matchMedia && host.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior = reduce ? "auto" : "smooth";
    if (owner === doc.documentElement || owner === doc.body || owner === document.scrollingElement) host.scrollTo({top:0,left:0,behavior});
    else owner.scrollTo({top:0,left:0,behavior});
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
  function hideOverlay() { overlay.setAttribute("aria-hidden", "true"); }
  function showOverlay() { if (pageNode) pageNode.textContent = pendingName || INITIAL_PAGE || "Sports"; overlay.setAttribute("aria-hidden", "false"); }
  function armTransition(name) {
    pendingKind = PAGE_TRANSITION;
    pendingName = name || INITIAL_PAGE || "Sports";
    pendingRoute = routeSignature();
    cancelTimer();
    timer = host.setTimeout(() => { timer = null; if (scriptState() !== "NOTRUNNING") showOverlay(); }, DELAY_MS);
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
      cancelTimer();
      hideOverlay();
      pendingKind = LOCAL_INTERACTION;
      pendingRoute = routeSignature();
      bindScroll();
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

  topButton.addEventListener("click", goTop);
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
      topButton.removeEventListener("click", goTop);
    }
  };
})();
</script>'''


def page_experience_native_top_markup() -> str:
    """Always-visible, no-JavaScript TOP fallback for live Streamlit pages."""
    return _NATIVE_TOP.strip()


def page_experience_controller_markup(route: Any | None = None) -> str:
    initial = destination_page_name(route) if route is not None else "Sports"
    return _CONTROLLER.replace("__INITIAL_PAGE__", json.dumps(initial)).strip()


def page_experience_fallback_markup(route: Any) -> str:
    return transition_markup(route)


__all__ = [
    "LOADER_DELAY_MS",
    "PAGE_EXPERIENCE_VERSION",
    "TOP_REVEAL_PX",
    "page_experience_native_top_markup",
    "page_experience_controller_markup",
    "page_experience_fallback_markup",
]
