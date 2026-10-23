"""Universal Page Experience V3 — truthful determinate loading progress.

Forward-only presentation successor over frozen V2. Keeps the existing KYRE
loading takeover while adding a stage-gated 0-100 progress surface. No timer
advances progress; Runtime V4 is the only server authority for stages > 0.
"""
from __future__ import annotations

from html import escape
import json
from typing import Any

from universal_atomic_navigation_v2 import destination_page_name
from universal_page_experience_v2 import (
    page_experience_controller_markup_v2,
    page_experience_native_top_markup,
    page_experience_top_sentinel_markup,
)

PAGE_EXPERIENCE_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE V3 • LOADING PROGRESS"
PROGRESS_STAGES = (0, 15, 35, 70, 90, 100)
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_PROGRESS_KEY = "__KYRE_UNIVERSAL_LOADING_PROGRESS_V1__"
_SPEED_KEY = "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V2_SPEED_GUARD__"

_PROGRESS_GUARD = r'''
<script>
(() => {
  const host = window.parent;
  const doc = host.document;
  const KEY = "__KYRE_UNIVERSAL_LOADING_PROGRESS_V1__";
  const SPEED_KEY = "__KYRE_UNIVERSAL_PAGE_EXPERIENCE_V2_SPEED_GUARD__";
  let pageName = __INITIAL_PAGE__;
  const existing = host[KEY];
  if (existing && existing.version === "v1") {
    existing.refresh(pageName);
    return;
  }

  const styleId = "kyre-universal-loading-progress-v1-style";
  if (!doc.getElementById(styleId)) {
    const style = doc.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-kyre-universal-loading="upe-v1"] .kyre-upe-progress-value{margin-top:12px;color:#7dd3fc;font:950 1.42rem/1 system-ui,-apple-system,sans-serif;letter-spacing:.02em;font-variant-numeric:tabular-nums}
      [data-kyre-universal-loading="upe-v1"] .kyre-upe-track:after{display:none!important;animation:none!important}
      [data-kyre-universal-loading="upe-v1"] .kyre-upe-progress-fill{height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,#38bdf8,#7dd3fc);box-shadow:0 0 14px rgba(125,211,252,.45);transition:width .22s ease}
      @media(prefers-reduced-motion:reduce){[data-kyre-universal-loading="upe-v1"] .kyre-upe-progress-fill{transition:none!important}}
    `;
    doc.head.appendChild(style);
  }

  let overlay = null;
  let valueNode = null;
  let statusNode = null;
  let trackNode = null;
  let fillNode = null;
  let observer = null;
  let boundGeneration = -1;

  function currentGeneration() {
    const speed = host[SPEED_KEY];
    return speed && typeof speed.generation === "function" ? Number(speed.generation()) : 0;
  }

  function ensureNodes() {
    overlay = doc.querySelector('[data-kyre-universal-loading="upe-v1"]');
    if (!overlay) return false;
    const pageNode = overlay.querySelector(".kyre-upe-page");
    statusNode = overlay.querySelector(".kyre-upe-load");
    trackNode = overlay.querySelector(".kyre-upe-track");
    if (!pageNode || !statusNode || !trackNode) return false;
    valueNode = overlay.querySelector(".kyre-upe-progress-value");
    if (!valueNode) {
      valueNode = doc.createElement("div");
      valueNode.className = "kyre-upe-progress-value";
      valueNode.setAttribute("aria-live", "polite");
      pageNode.insertAdjacentElement("afterend", valueNode);
    }
    fillNode = trackNode.querySelector(".kyre-upe-progress-fill");
    if (!fillNode) {
      fillNode = doc.createElement("div");
      fillNode.className = "kyre-upe-progress-fill";
      trackNode.appendChild(fillNode);
    }
    trackNode.setAttribute("role", "progressbar");
    trackNode.setAttribute("aria-valuemin", "0");
    trackNode.setAttribute("aria-valuemax", "100");
    return true;
  }

  function setProgress(percent, status, page) {
    if (!ensureNodes()) return false;
    const safe = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    const generation = currentGeneration();
    if (safe <= 15) boundGeneration = generation;
    if (boundGeneration >= 0 && generation !== boundGeneration && safe > 15) return false;
    if (page) {
      pageName = String(page);
      const pageNode = overlay.querySelector(".kyre-upe-page");
      if (pageNode) pageNode.textContent = pageName;
    }
    valueNode.textContent = `${safe}%`;
    statusNode.textContent = String(status || "Loading intelligence");
    trackNode.setAttribute("aria-valuenow", String(safe));
    trackNode.setAttribute("aria-valuetext", `${safe}% ${statusNode.textContent}`);
    fillNode.style.width = `${safe}%`;
    overlay.setAttribute("data-kyre-progress", String(safe));
    return true;
  }

  function resetWhenShown() {
    if (!ensureNodes()) return;
    if (overlay.getAttribute("aria-hidden") === "false") setProgress(0, "Starting page", pageName);
  }

  function observeOverlay() {
    if (!ensureNodes()) return;
    if (observer) observer.disconnect();
    observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === "attributes" && record.attributeName === "aria-hidden") resetWhenShown();
      }
    });
    observer.observe(overlay, {attributes:true, attributeFilter:["aria-hidden"]});
  }

  observeOverlay();
  if (overlay && overlay.getAttribute("aria-hidden") === "false") setProgress(0, "Starting page", pageName);

  host[KEY] = {
    version: "v1",
    setProgress,
    refresh(initialPage) {
      if (initialPage) pageName = String(initialPage);
      observeOverlay();
    },
    destroy() {
      if (observer) observer.disconnect();
    }
  };
})();
</script>
'''


def _progress_percent(percent: int | float | str) -> int:
    try:
        return max(0, min(100, int(percent)))
    except (TypeError, ValueError):
        return 0


def _page_name(route: Any | None) -> str:
    return destination_page_name(route) if route is not None else "Sports Intelligence"


def page_experience_controller_markup_v3(route: Any | None = None) -> str:
    """Return V2 navigation controller plus determinate progress overlay upgrade."""
    initial = _page_name(route)
    return page_experience_controller_markup_v2(route) + "\n" + _PROGRESS_GUARD.replace(
        "__INITIAL_PAGE__", json.dumps(initial)
    )


def page_experience_progress_markup(route: Any | None, percent: int, status: str) -> str:
    """Return server-held determinate progress fallback using the existing visual language."""
    safe_percent = max(0, min(100, int(percent)))
    page = escape(_page_name(route))
    safe_status = escape(str(status or "Loading intelligence"))
    return f'''<style>
@keyframes kyre-upe-v3-reveal{{from{{opacity:0}}to{{opacity:1}}}}@keyframes kyre-upe-v3-spin{{to{{transform:rotate(360deg)}}}}
[data-kyre-universal-loading="upe-v3-server"]{{position:fixed;inset:0;z-index:2147483647;pointer-events:all;display:grid;place-items:center;min-height:100vh;opacity:0;background:radial-gradient(circle at 50% 38%,rgba(14,165,233,.18),transparent 34%),linear-gradient(180deg,#050a12 0%,#07111d 52%,#060b13 100%);animation:kyre-upe-v3-reveal .16s ease forwards;animation-delay:120ms}}
[data-kyre-universal-loading="upe-v3-server"]:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(125,211,252,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(125,211,252,.035) 1px,transparent 1px);background-size:32px 32px}}
.kyre-upe-server-card{{position:relative;width:min(520px,88vw);text-align:center;color:#f8fafc;padding:34px 24px 30px;border:1px solid rgba(125,211,252,.22);border-radius:26px;background:linear-gradient(145deg,rgba(7,17,31,.97),rgba(10,23,38,.97));box-shadow:0 26px 80px rgba(0,0,0,.54),0 0 55px rgba(14,165,233,.08)}}
.kyre-upe-orbit{{position:relative;width:76px;height:76px;margin:0 auto 18px;border-radius:50%;border:1px solid rgba(125,211,252,.18);display:grid;place-items:center;box-shadow:inset 0 0 28px rgba(14,165,233,.08)}}.kyre-upe-orbit:before{{content:"";position:absolute;inset:-1px;border-radius:50%;border-top:2px solid #7dd3fc;border-right:2px solid transparent;animation:kyre-upe-v3-spin .9s linear infinite}}.kyre-upe-core{{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,#0b2237,#07121f);border:1px solid rgba(125,211,252,.25);color:#7dd3fc;font:950 12px/1 system-ui,-apple-system,sans-serif;letter-spacing:.1em}}.kyre-upe-server-brand{{font:950 .72rem/1.2 system-ui,-apple-system,sans-serif;letter-spacing:.2em;color:#7dd3fc}}.kyre-upe-server-page{{margin-top:12px;font:950 1.28rem/1.2 system-ui,-apple-system,sans-serif}}.kyre-upe-progress-value{{margin-top:12px;color:#7dd3fc;font:950 1.42rem/1 system-ui,-apple-system,sans-serif;font-variant-numeric:tabular-nums}}.kyre-upe-server-load{{margin-top:8px;color:#b7c8d8;font:800 .86rem/1.3 system-ui,-apple-system,sans-serif}}.kyre-upe-server-track{{height:4px;margin:18px auto 0;max-width:230px;border-radius:999px;background:rgba(148,163,184,.12);overflow:hidden}}.kyre-upe-progress-fill{{height:100%;border-radius:inherit;background:linear-gradient(90deg,#38bdf8,#7dd3fc);box-shadow:0 0 14px rgba(125,211,252,.45);transition:width .22s ease}}
@media(prefers-reduced-motion:reduce){{[data-kyre-universal-loading="upe-v3-server"]{{animation:none;opacity:1}}.kyre-upe-orbit:before{{animation:none}}.kyre-upe-progress-fill{{transition:none}}}}
</style><div data-kyre-universal-loading="upe-v3-server" data-kyre-progress="{safe_percent}" aria-live="polite" aria-label="Loading {page}"><div class="kyre-upe-server-card"><div class="kyre-upe-orbit"><div class="kyre-upe-core">KS</div></div><div class="kyre-upe-server-brand">KYRE SPORTS AI</div><div class="kyre-upe-server-page">{page}</div><div class="kyre-upe-progress-value">{safe_percent}%</div><div class="kyre-upe-server-load">{safe_status}</div><div class="kyre-upe-server-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{safe_percent}" aria-valuetext="{safe_percent}% {safe_status}"><div class="kyre-upe-progress-fill" style="width:{safe_percent}%"></div></div></div></div>'''


def page_experience_progress_update_markup(route: Any | None, percent: int, status: str) -> str:
    """Return a zero-layout script that advances the mounted client overlay."""
    safe_percent = _progress_percent(percent)
    page = _page_name(route)
    return (
        "<script>(()=>{const h=window.parent;const api=h["
        + json.dumps(_PROGRESS_KEY)
        + "];if(api&&typeof api.setProgress==='function'){api.setProgress("
        + str(safe_percent)
        + ","
        + json.dumps(str(status or "Loading intelligence"))
        + ","
        + json.dumps(page)
        + ");}})();</script>"
    )


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "PAGE_EXPERIENCE_VERSION",
    "PROGRESS_STAGES",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "page_experience_controller_markup_v3",
    "page_experience_native_top_markup",
    "page_experience_progress_markup",
    "page_experience_progress_update_markup",
    "page_experience_top_sentinel_markup",
]
