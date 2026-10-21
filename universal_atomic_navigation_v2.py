"""Universal Atomic Navigation V2 — immediate delayed loading handoff helpers."""
from __future__ import annotations

from html import escape
import json
from typing import Any, Mapping

MODEL_VERSION = "MONSTER UNIVERSAL ATOMIC NAVIGATION V2"
LOADER_DELAY_MS = 140

_MARKET_LABELS = {
    "slate": "Slate",
    "moneyline": "Moneyline",
    "spread": "Spread",
    "game-total": "Game Total",
    "over-under": "Over/Under",
    "top-picks": "Top Picks",
    "player-props": "Player Props",
    "passing-yards": "Passing Yards",
    "rushing-yards": "Rushing Yards",
    "receiving-yards": "Receiving Yards",
    "receptions": "Receptions",
    "passing-tds": "Passing TDs",
    "anytime-td": "Anytime TD",
    "daily-picks": "Daily Picks",
    "points": "Points",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "rebounds-assists": "Rebounds + Assists",
    "pra": "PRA",
    "one-plus-hit": "1+ Hit",
    "home-run": "Home Run",
    "hits-runs-rbis": "Hits + Runs + RBIs",
    "pitcher-strikeouts": "Pitcher Strikeouts",
    "matchup-explorer": "Matchup Explorer",
    "daily-game-picks": "Daily Game Picks",
    "run-line": "Run Line",
    "live-game": "Live Game",
    "live-odds": "Live Odds",
}


def _parts(route: Any) -> tuple[str, str, Mapping[Any, Any]]:
    sport = str(getattr(route, "sport_id", "") or "").strip().lower()
    market = str(getattr(route, "market_id", "") or "").strip().lower()
    raw = getattr(route, "params", {}) or {}
    params = raw if isinstance(raw, Mapping) else {}
    return sport, market, params


def _market_label(market_id: str) -> str:
    market = str(market_id or "").strip().lower()
    return _MARKET_LABELS.get(market, market.replace("-", " ").title() or "Page")


def destination_page_name(route: Any) -> str:
    """Return a concise human destination label for the route/deep-page identity."""
    sport, market, params = _parts(route)
    sport_label = (sport or "Sports").upper()
    market_label = _market_label(market)
    game_id = str(params.get("game_id") or "").strip()
    player_id = str(params.get("player_id") or "").strip()
    prop = str(params.get("prop") or params.get("market_key") or "").strip()

    if sport == "cfb" and market == "player-props" and player_id and prop:
        return "CFB Player Prop Intelligence Lab"
    base = f"{sport_label} {market_label}".strip()
    if player_id:
        return f"{base} • Player"
    if game_id:
        return f"{base} • Game"
    return base


def transition_markup(route: Any) -> str:
    """Server fallback when client-side script injection is unavailable."""
    page = escape(destination_page_name(route))
    return f"""
<div data-kyre-universal-loading="v2" aria-live="polite" style="position:fixed;inset:0;z-index:2147483647;background:#060b13;pointer-events:all;display:grid;place-items:center;min-height:100vh;">
  <div style="text-align:center;padding:1.4rem;max-width:34rem;color:#f8fafc;">
    <div style="font-size:.76rem;font-weight:950;letter-spacing:.16em;color:#7dd3fc;">KYRE SPORTS AI</div>
    <div style="font-size:1.32rem;font-weight:950;margin-top:.72rem;">{page}</div>
    <div style="font-size:.9rem;font-weight:800;margin-top:.48rem;color:#cbd5e1;">Loading…</div>
  </div>
</div>
""".strip()


_CONTROLLER = r"""
<script>
(() => {
  const host = window.parent;
  const doc = host.document;
  const KEY = "__KYRE_UNIVERSAL_LOADING_V2__";
  const DELAY_MS = 140;
  const INITIAL_PAGE = __INITIAL_PAGE_JSON__;
  const MARKET_LABELS = __MARKET_LABELS_JSON__;
  const DEFAULT_MARKETS = {nfl:"Daily Picks",cfb:"Moneyline",nba:"Spread",mlb:"Slate",wnba:"PRA"};
  const SPORT_IDS = ["nfl","cfb","nba","mlb","wnba"];

  const existing = host[KEY];
  if (existing && existing.version === "v2") {
    existing.refresh(INITIAL_PAGE);
    return;
  }

  const styleId = "kyre-universal-loading-v2-style";
  if (!doc.getElementById(styleId)) {
    const style = doc.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-kyre-universal-loading="v2"]{position:fixed;inset:0;z-index:2147483647;background:#060b13;pointer-events:all;display:none;place-items:center;min-height:100vh;opacity:0;transition:opacity .08s ease}
      [data-kyre-universal-loading="v2"][aria-hidden="false"]{display:grid;opacity:1}
      .kyre-ulv2-wrap{width:min(520px,88vw);text-align:center;color:#f8fafc;padding:28px 22px;border:1px solid rgba(125,211,252,.18);border-radius:22px;background:linear-gradient(145deg,#07111f,#0a1726);box-shadow:0 24px 70px rgba(0,0,0,.42)}
      .kyre-ulv2-brand{font-size:.72rem;font-weight:950;letter-spacing:.17em;color:#7dd3fc}
      .kyre-ulv2-page{margin-top:12px;font-size:1.25rem;font-weight:950;line-height:1.2}
      .kyre-ulv2-loading{margin-top:8px;font-size:.86rem;font-weight:800;color:#b7c8d8}
      .kyre-ulv2-dot{display:inline-block;width:7px;height:7px;margin-left:6px;border-radius:50%;background:#7dd3fc;animation:kyre-ulv2-pulse .8s ease-in-out infinite alternate}
      @keyframes kyre-ulv2-pulse{from{opacity:.22;transform:scale(.8)}to{opacity:1;transform:scale(1.12)}}
    `;
    doc.head.appendChild(style);
  }

  let overlay = doc.querySelector('[data-kyre-universal-loading="v2"]');
  if (!overlay) {
    overlay = doc.createElement("div");
    overlay.setAttribute("data-kyre-universal-loading", "v2");
    overlay.setAttribute("aria-hidden", "true");
    overlay.setAttribute("aria-live", "polite");
    overlay.innerHTML = '<div class="kyre-ulv2-wrap"><div class="kyre-ulv2-brand">KYRE SPORTS AI</div><div class="kyre-ulv2-page"></div><div class="kyre-ulv2-loading">Loading<span class="kyre-ulv2-dot"></span></div></div>';
    doc.body.appendChild(overlay);
  }
  const pageNode = overlay.querySelector(".kyre-ulv2-page");

  let timer = null;
  let pendingName = INITIAL_PAGE;
  let lastPointerAt = 0;
  let observer = null;

  function routeFromLocation() {
    const params = new URLSearchParams(host.location.search || "");
    return {
      sport: (params.get("sport") || "").toLowerCase(),
      market: (params.get("market") || "").toLowerCase(),
      game: params.get("game_id") || "",
      player: params.get("player_id") || "",
      prop: params.get("prop") || params.get("market_key") || ""
    };
  }

  function marketLabel(value) {
    const id = String(value || "").toLowerCase();
    return MARKET_LABELS[id] || id.split("-").filter(Boolean).map(x => x.charAt(0).toUpperCase()+x.slice(1)).join(" ") || "Page";
  }

  function pageName(route) {
    const sport = (route.sport || "sports").toUpperCase();
    if (route.sport === "cfb" && route.market === "player-props" && route.player && route.prop) return "CFB Player Prop Intelligence Lab";
    const base = `${sport} ${marketLabel(route.market)}`.trim();
    if (route.player) return `${base} • Player`;
    if (route.game) return `${base} • Game`;
    return base;
  }

  function scriptState() {
    const app = doc.querySelector('[data-testid="stApp"]');
    return String(app ? app.getAttribute("data-test-script-state") || "" : "").toUpperCase();
  }

  function visible() { return overlay.getAttribute("aria-hidden") === "false"; }
  function setName(name) { if (pageNode) pageNode.textContent = name || pageName(routeFromLocation()) || INITIAL_PAGE; }
  function hide() { overlay.setAttribute("aria-hidden", "true"); }
  function cancelTimer() { if (timer !== null) { host.clearTimeout(timer); timer = null; } }

  function show() {
    setName(pendingName || pageName(routeFromLocation()));
    overlay.setAttribute("aria-hidden", "false");
    host.setTimeout(() => { if (visible()) setName(pageName(routeFromLocation()) || pendingName); }, 180);
  }

  function arm(name) {
    pendingName = name || pendingName || pageName(routeFromLocation());
    cancelTimer();
    timer = host.setTimeout(() => {
      timer = null;
      const state = scriptState();
      if (state && state !== "NOT_RUNNING") show();
    }, DELAY_MS);
  }

  function currentSport() {
    const route = routeFromLocation();
    return route.sport || String(INITIAL_PAGE || "").split(" ")[0].toLowerCase();
  }

  function inferClickName(node) {
    const text = String(node.innerText || node.textContent || "").replace(/\s+/g, " ").trim();
    const lower = text.toLowerCase();
    const route = routeFromLocation();
    const navShell = node.closest('.st-key-ks_universal_nav_shell');
    if (navShell) {
      for (const sport of SPORT_IDS) {
        if (lower === sport || lower.endsWith(` ${sport}`) || lower.includes(`${sport} `)) {
          return `${sport.toUpperCase()} ${DEFAULT_MARKETS[sport] || ""}`.trim();
        }
      }
      for (const [market, label] of Object.entries(MARKET_LABELS)) {
        if (lower === label.toLowerCase()) return `${currentSport().toUpperCase()} ${label}`;
      }
    }
    if (/^analy[sz]e$/i.test(text) && route.sport === "cfb" && route.market === "player-props") return "CFB Player Prop Intelligence Lab";
    const back = text.match(/back\s+to\s+(.+)/i);
    if (back) return `${(route.sport || currentSport()).toUpperCase()} ${back[1].replace(/^←\s*/, "").trim()}`;
    return pageName(route) || INITIAL_PAGE;
  }

  function onPointerDown(event) {
    const node = event.target && event.target.closest ? event.target.closest('button,a,[role="button"]') : null;
    if (!node) return;
    if (node.closest('[data-testid="stToolbar"],header,[data-testid="stSidebar"]')) return;
    const appView = doc.querySelector('[data-testid="stAppViewContainer"]');
    if (appView && !appView.contains(node)) return;
    lastPointerAt = Date.now();
    arm(inferClickName(node));
  }

  function onStateChange() {
    const state = scriptState();
    if (state === "NOT_RUNNING") {
      cancelTimer();
      hide();
      pendingName = pageName(routeFromLocation()) || INITIAL_PAGE;
      return;
    }
    if (state && Date.now() - lastPointerAt < 1800 && !visible() && timer === null) arm(pendingName);
    if (visible()) setName(pageName(routeFromLocation()) || pendingName);
  }

  function observeApp() {
    if (observer) observer.disconnect();
    const app = doc.querySelector('[data-testid="stApp"]');
    if (!app) return;
    observer = new MutationObserver(onStateChange);
    observer.observe(app, {attributes:true, attributeFilter:["data-test-script-state"]});
  }

  function onPopState() {
    lastPointerAt = Date.now();
    arm(pageName(routeFromLocation()));
  }

  doc.addEventListener("pointerdown", onPointerDown, true);
  host.addEventListener("popstate", onPopState, true);
  observeApp();

  host[KEY] = {
    version:"v2",
    refresh(initialPage) {
      if (initialPage) pendingName = initialPage;
      observeApp();
      if (scriptState() === "NOT_RUNNING") { cancelTimer(); hide(); }
    },
    destroy() {
      cancelTimer();
      if (observer) observer.disconnect();
      doc.removeEventListener("pointerdown", onPointerDown, true);
      host.removeEventListener("popstate", onPopState, true);
      hide();
    }
  };
})();
</script>
"""


def transition_controller_markup(route: Any | None = None) -> str:
    """Return the singleton browser controller installed before navigation begins."""
    initial = destination_page_name(route) if route is not None else "Sports"
    return (
        _CONTROLLER
        .replace("__INITIAL_PAGE_JSON__", json.dumps(initial))
        .replace("__MARKET_LABELS_JSON__", json.dumps(_MARKET_LABELS, sort_keys=True))
    ).strip()


__all__ = [
    "LOADER_DELAY_MS",
    "MODEL_VERSION",
    "destination_page_name",
    "transition_controller_markup",
    "transition_markup",
]
