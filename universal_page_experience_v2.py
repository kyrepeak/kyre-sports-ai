"""Universal Page Experience V2 — same-tab navigation + latest-tap browser guard.

V2 is a narrow forward-only successor over frozen Page Experience V1. It
preserves the existing TOP/loading presentation and adds one event-driven
browser guard that keeps internal links in the current document and makes
stale delayed navigation work lose to the newest user tap.
"""
from __future__ import annotations

import json
from typing import Any

from universal_page_experience_v1 import (
    page_experience_controller_markup,
    page_experience_fallback_markup,
    page_experience_native_top_markup,
    page_experience_top_sentinel_markup,
)
from universal_atomic_navigation_v2 import destination_page_name

PAGE_EXPERIENCE_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE V2"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_SPEED_GUARD = r'''
<script>
(() => {
  const host = window.parent;
  const doc = host.document;
  const KEY = "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V2_SPEED_GUARD__";
  const INITIAL_PAGE = __INITIAL_PAGE__;
  const existing = host[KEY];
  if (existing && existing.version === "v2") {
    existing.refresh(INITIAL_PAGE);
    return;
  }

  let navGeneration = 0;
  let observer = null;
  let latestPage = INITIAL_PAGE;

  function internalURL(anchor) {
    if (!anchor || !anchor.getAttribute) return null;
    if (anchor.hasAttribute("download")) return null;
    const raw = String(anchor.getAttribute("href") || "").trim();
    if (!raw || raw.startsWith("mailto:") || raw.startsWith("tel:") || raw.startsWith("javascript:")) return null;
    let url;
    try { url = new URL(raw, host.location.href); } catch (_) { return null; }
    if (url.origin !== host.location.origin) return null;
    return url;
  }

  function normalizeAnchor(anchor) {
    const url = internalURL(anchor);
    if (!url) return false;
    if (anchor.getAttribute("target") !== "_self") anchor.setAttribute("target", "_self");
    return true;
  }

  function normalizeTree(root) {
    if (!root) return;
    if (root.matches && root.matches("a[href]")) normalizeAnchor(root);
    if (root.querySelectorAll) root.querySelectorAll("a[href]").forEach(normalizeAnchor);
  }

  function isPageTransition(node) {
    if (!node) return false;
    if (node.closest && node.closest('[data-testid="stToolbar"],header,[data-testid="stSidebar"]')) return false;
    if (node.closest && node.closest('.st-key-ks_universal_nav_shell')) return true;
    const anchor = node.closest ? node.closest("a[href]") : null;
    if (anchor && internalURL(anchor)) return true;
    const text = String(node.innerText || node.textContent || "").replace(/\s+/g, " ").trim();
    return /\b(analy[sz]e|open|view|back)\b/i.test(text) || /←/.test(text);
  }

  function onPointerDown(event) {
    const node = event.target && event.target.closest ? event.target.closest('button,a,[role="button"]') : null;
    if (!node) return;
    const appView = doc.querySelector('[data-testid="stAppViewContainer"]');
    if (appView && !appView.contains(node)) return;
    const anchor = node.closest ? node.closest("a[href]") : null;
    if (anchor) normalizeAnchor(anchor);
    if (!isPageTransition(node)) return;

    const generation = ++navGeneration;
    const text = String(node.innerText || node.textContent || "").replace(/\s+/g, " ").trim();
    if (text) latestPage = text.slice(0, 96);

    host.requestAnimationFrame(() => {
      if (generation !== navGeneration) return;
      normalizeTree(doc.querySelector('[data-testid="stAppViewContainer"]') || doc.body);
    });
  }

  function onPopState() {
    const generation = ++navGeneration;
    host.requestAnimationFrame(() => {
      if (generation !== navGeneration) return;
      normalizeTree(doc.querySelector('[data-testid="stAppViewContainer"]') || doc.body);
    });
  }

  function observe() {
    if (observer) observer.disconnect();
    const root = doc.querySelector('[data-testid="stAppViewContainer"]') || doc.body;
    normalizeTree(root);
    observer = new MutationObserver((records) => {
      const generation = navGeneration;
      for (const record of records) {
        if (generation !== navGeneration) return;
        if (record.type === "attributes") normalizeAnchor(record.target);
        record.addedNodes && record.addedNodes.forEach(normalizeTree);
      }
    });
    observer.observe(root, {subtree:true, childList:true, attributes:true, attributeFilter:["href","target"]});
  }

  doc.addEventListener("pointerdown", onPointerDown, true);
  host.addEventListener("popstate", onPopState, true);
  observe();

  host[KEY] = {
    version: "v2",
    refresh(initialPage) {
      if (initialPage) latestPage = initialPage;
      observe();
    },
    generation() { return navGeneration; },
    destroy() {
      if (observer) observer.disconnect();
      doc.removeEventListener("pointerdown", onPointerDown, true);
      host.removeEventListener("popstate", onPopState, true);
    }
  };
})();
</script>
'''


def page_experience_controller_markup_v2(route: Any | None = None) -> str:
    """Return V1 presentation plus the singleton V2 same-tab/latest-tap guard."""
    initial = destination_page_name(route) if route is not None else "Sports"
    return page_experience_controller_markup(route) + "\n" + _SPEED_GUARD.replace(
        "__INITIAL_PAGE__", json.dumps(initial)
    )


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "PAGE_EXPERIENCE_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "page_experience_controller_markup_v2",
    "page_experience_fallback_markup",
    "page_experience_native_top_markup",
    "page_experience_top_sentinel_markup",
]
