"""CFB Game Total — Games on This Day Step 2 game-card visual upgrade.

Presentation-only successor to frozen Step 1. It preserves verified event links,
selection semantics and the Step-1 responsive layout while adding exact ESPN
team logos when certified IDs exist, schedule-provided team-color accents,
Phoenix-local kickoff time and a stronger selected-game state.

No model, projection, probability, ranking, schedule selection, sportsbook
influence or other-sport behavior is changed.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import importlib
import re
from threading import RLock
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 2 VISUAL V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
DIRECT_NETWORK_ENDPOINTS_ADDED = 0
TARGET_PAGE = "cfb_game_total_clean_page_v38"
PHOENIX_TZ = ZoneInfo("America/Phoenix")
EASTERN_TZ = ZoneInfo("America/New_York")
ESPN_LOGO_CDN_TEMPLATE = "https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"

_INSTALL_ATTR = "_cfb_games_on_day_step2_visual_installed"
_STEP2_ORIGINAL_ATTR = "_cfb_games_on_day_step2_original"
_STEP1_ORIGINAL_ATTR = "_cfb_games_on_day_step1_original"
_LOCK = RLock()
_HEX = re.compile(r"^#?[0-9a-fA-F]{6}$")

STEP2_CSS = r"""
<style data-kyre-cfb-games-on-day-step2-visual="v1">
.gt2-game-card{position:relative;display:block!important;padding:12px 13px 11px!important;border-color:rgba(88,201,255,.24)!important;background:linear-gradient(145deg,rgba(7,24,36,.98),rgba(5,15,27,.98))!important;box-shadow:0 8px 24px rgba(0,0,0,.18);overflow:hidden!important;isolation:isolate}
.gt2-game-card::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--away-color,#58c9ff),var(--home-color,#45f0ad));opacity:.92}
.gt2-card-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:1px 0 9px}
.gt2-kickoff{font-size:10px;font-weight:950;letter-spacing:.055em;color:#9fdfff}
.gt2-selected-pill{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border-radius:999px;border:1px solid rgba(69,240,173,.58);background:rgba(69,240,173,.12);color:#8ff7c9;font-size:8px;font-weight:1000;letter-spacing:.08em}
.gt2-team-row{display:flex;align-items:center;gap:10px;min-width:0;padding:2px 0}
.gt2-team-logo,.gt2-team-logo-fallback{width:30px;height:30px;flex:0 0 30px;border-radius:50%;object-fit:contain;background:rgba(255,255,255,.96);box-shadow:0 2px 10px rgba(0,0,0,.20)}
.gt2-team-logo{padding:3px;box-sizing:border-box}.gt2-team-logo-fallback{display:grid;place-items:center;background:#102331;color:#d9f2ff;font-size:9px;font-weight:1000}
.gt2-team-name{min-width:0;color:#edf8ff;font-size:12px;font-weight:950;line-height:1.18;white-space:normal;overflow-wrap:anywhere}.gt2-at{margin:1px 0 1px 40px;color:#6f899e;font-size:8px;font-weight:1000;letter-spacing:.12em}
.gt2-game-card:hover{transform:translateY(-1px);border-color:rgba(88,201,255,.58)!important;background:linear-gradient(145deg,rgba(10,35,50,.98),rgba(6,21,34,.98))!important}
.gt2-game-card.selected{border-color:rgba(69,240,173,.92)!important;background:linear-gradient(145deg,rgba(12,58,48,.96),rgba(5,25,34,.98))!important;box-shadow:0 0 0 1px rgba(69,240,173,.18),0 10px 28px rgba(0,0,0,.28),0 0 24px rgba(69,240,173,.08)!important}.gt2-game-card.selected .gt2-team-name{color:#fff}.gt2-game-disabled{opacity:.72}
@media(max-width:760px){.gt2-game-card{padding:12px 12px 11px!important;min-height:112px!important}.gt2-team-logo,.gt2-team-logo-fallback{width:32px;height:32px;flex-basis:32px}.gt2-team-name{font-size:12px}.gt2-kickoff{font-size:9px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _event_id(game: Mapping[str, Any]) -> str:
    for key in ("espn_event_id", "event_id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _side_rows(game: Mapping[str, Any], side: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    row = game.get(side) if isinstance(game.get(side), Mapping) else {}
    team = row.get("team") if isinstance(row.get("team"), Mapping) else {}
    return row, team


def _team_name(game: Mapping[str, Any], side: str) -> str:
    row, team = _side_rows(game, side)
    for value in (
        game.get(f"{side}_team"), game.get(f"{side}_team_name"), game.get(f"{side}_name"),
        row.get("display_name"), row.get("displayName"), row.get("name"), row.get("school"),
        team.get("display_name"), team.get("displayName"), team.get("shortDisplayName"),
        team.get("name"), team.get("location"),
    ):
        if isinstance(value, Mapping):
            text = _clean(value.get("displayName") or value.get("name") or value.get("location"))
        else:
            text = _clean(value)
        if text:
            return text
    return side.title()


def _team_id(game: Mapping[str, Any], side: str) -> str:
    row, team = _side_rows(game, side)
    for value in (
        game.get(f"{side}_espn_team_id"), game.get(f"{side}_team_id"),
        row.get("team_id"), row.get("id"), team.get("id"),
    ):
        text = _clean(value)
        if text.isdigit():
            return text
    return ""


def _team_color(game: Mapping[str, Any], side: str) -> str:
    row, team = _side_rows(game, side)
    for value in (
        game.get(f"{side}_color"), game.get(f"{side}_team_color"), game.get(f"{side}_primary_color"),
        row.get("color"), row.get("primary_color"), row.get("primaryColor"),
        team.get("color"), team.get("primaryColor"),
    ):
        text = _clean(value)
        if _HEX.fullmatch(text):
            return text if text.startswith("#") else "#" + text
    return "#58C9FF" if side == "away" else "#45F0AD"


def _phoenix_kickoff_text(game: Mapping[str, Any]) -> str:
    for key in ("kickoff_iso", "start_time_utc", "kickoff_utc", "start_time", "kickoff", "start_date", "date", "kickoff_et"):
        raw = _clean(game.get(key))
        if not raw or ("T" not in raw and ":" not in raw):
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw if len(raw) <= 24 else "TIME TBD"
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=EASTERN_TZ)
        return parsed.astimezone(PHOENIX_TZ).strftime("%I:%M %p MST").lstrip("0")
    return "TIME TBD"


def _initials(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    return "".join(word[0] for word in words[:2]).upper() if words else "CFB"


def _logo_markup(team_id: str, team_name: str, side: str) -> str:
    if team_id:
        src = ESPN_LOGO_CDN_TEMPLATE.format(team_id=escape(team_id, quote=True))
        return f'<img class="gt2-team-logo" data-side="{side}" src="{src}" alt="{escape(team_name, quote=True)} logo" loading="lazy" decoding="async">'
    return f'<span class="gt2-team-logo-fallback" data-side="{side}">{escape(_initials(team_name))}</span>'


def build_game_card_html(game: Mapping[str, Any], *, selected_day: date | str, selected: bool, href: str) -> str:
    del selected_day
    event_id = _event_id(game)
    away_name, home_name = _team_name(game, "away"), _team_name(game, "home")
    away_id, home_id = _team_id(game, "away"), _team_id(game, "home")
    away_color, home_color = _team_color(game, "away"), _team_color(game, "home")
    kickoff = _phoenix_kickoff_text(game)
    selected_class = " selected" if selected else ""
    aria = ' aria-current="true"' if selected else ""
    pill = '<span class="gt2-selected-pill">✓ SELECTED</span>' if selected else ""
    style = f"--away-color:{away_color};--home-color:{home_color}"
    label = f"{kickoff}: {away_name} at {home_name}"
    inner = (
        f'<div class="gt2-card-top"><span class="gt2-kickoff">{escape(kickoff)}</span>{pill}</div>'
        f'<div class="gt2-team-row">{_logo_markup(away_id, away_name, "away")}<span class="gt2-team-name">{escape(away_name)}</span></div>'
        '<div class="gt2-at">AT</div>'
        f'<div class="gt2-team-row">{_logo_markup(home_id, home_name, "home")}<span class="gt2-team-name">{escape(home_name)}</span></div>'
    )
    if event_id and href:
        return f'<a class="gt163-game-link gt2-game-card{selected_class}" data-event-id="{escape(event_id)}" href="{escape(href, quote=True)}" target="_self" aria-label="{escape(label, quote=True)}" style="{style}"{aria}>{inner}</a>'
    return f'<span class="gt163-game-disabled gt2-game-card gt2-game-disabled" style="{style}" aria-label="{escape(label, quote=True)}">{inner}</span>'


def _visual_identity_context(selected_day: date):
    try:
        v15 = importlib.import_module("cfb_game_total_clean_page_v15")
        identity = importlib.import_module("cfb_game_total_team_logo_identity_v1")
        return identity, v15._selector_payload_for_day(selected_day)
    except Exception:
        return None, None


def _enhanced_renderer(owner: Any):
    def enhanced_render_game_strip(selected_day: date, games: Sequence[Mapping[str, Any]], selected_index: int) -> None:
        st = importlib.import_module("streamlit")
        st.markdown(str(getattr(owner, "_V163_CSS", "")) + STEP2_CSS, unsafe_allow_html=True)
        if not games:
            return
        identity, payload = _visual_identity_context(selected_day)
        cards: list[str] = []
        for index, raw_game in enumerate(games):
            game = dict(raw_game)
            if identity is not None:
                try:
                    game = identity.enrich_exact_team_ids(game, payload)
                except Exception:
                    pass
            event_id = owner._game_id(game)
            href = owner._selector_href(game, selected_day) if event_id else ""
            cards.append(build_game_card_html(game, selected_day=selected_day, selected=index == selected_index, href=href))
        st.markdown(
            '<div class="gt163-game-wrap" data-testid="gt163-game-strip" data-step2-visual="v1">'
            '<div class="gt163-game-title"><b>🏟️ GAMES ON THIS DAY</b><span>Tap a matchup • Phoenix time</span></div>'
            f'<div class="gt163-game-scroller">{"".join(cards)}</div></div>',
            unsafe_allow_html=True,
        )
    return enhanced_render_game_strip


def _patch_owner(owner: Any) -> tuple[Any, Any] | None:
    current = getattr(owner, "_render_game_strip", None)
    if current is None:
        raise RuntimeError("CFB Game Total V163 selector renderer unavailable")
    if getattr(current, _INSTALL_ATTR, False):
        return None
    enhanced_render_game_strip = _enhanced_renderer(owner)
    setattr(enhanced_render_game_strip, _INSTALL_ATTR, True)
    setattr(enhanced_render_game_strip, _STEP2_ORIGINAL_ATTR, current)
    owner._render_game_strip = enhanced_render_game_strip
    return owner, current


def _render_chain_has_step2(current: Any) -> bool:
    """Detect Step 2 even when frozen Step 1 is the outer wrapper."""
    seen: set[int] = set()
    node = current
    while callable(node) and id(node) not in seen:
        seen.add(id(node))
        if getattr(node, _INSTALL_ATTR, False) or hasattr(node, _STEP2_ORIGINAL_ATTR):
            return True
        step1_original = getattr(node, _STEP1_ORIGINAL_ATTR, None)
        if callable(step1_original):
            node = step1_original
            continue
        return False
    return False


def install_games_on_day_step2_visual() -> bool:
    """Install Step 2 once and rebind it after the exact-route module purge."""
    with _LOCK:
        owner = importlib.import_module("cfb_game_total_clean_page_v14")
        _patch_owner(owner)

        root = importlib.import_module("streamlit_memory_lazy_router_v1")
        render_owner = importlib.import_module("streamlit_memory_lazy_router_v160")
        route_owner = importlib.import_module("streamlit_memory_lazy_router_v181")
        current = render_owner._render_exact_game_total_surface
        if _render_chain_has_step2(current):
            return True
        original = current

        def render_with_step2_visual(*args: Any, **kwargs: Any):
            if not route_owner._game_total_route_active():
                return original(*args, **kwargs)
            original_import = root._import
            restores: list[tuple[Any, Any]] = []

            def import_with_step2(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    fresh_owner = importlib.import_module("cfb_game_total_clean_page_v14")
                    original_strip = fresh_owner._render_game_strip
                    if not getattr(original_strip, _INSTALL_ATTR, False):
                        enhanced_render_game_strip = _enhanced_renderer(fresh_owner)
                        setattr(enhanced_render_game_strip, _INSTALL_ATTR, True)
                        setattr(enhanced_render_game_strip, _STEP2_ORIGINAL_ATTR, original_strip)
                        fresh_owner._render_game_strip = enhanced_render_game_strip
                        restores.append((fresh_owner, original_strip))
                return page

            root._import = import_with_step2
            try:
                return original(*args, **kwargs)
            finally:
                root._import = original_import
                for fresh_owner, original_strip in reversed(restores):
                    fresh_owner._render_game_strip = original_strip

        setattr(render_with_step2_visual, _INSTALL_ATTR, True)
        setattr(render_with_step2_visual, _STEP2_ORIGINAL_ATTR, original)
        render_owner._render_exact_game_total_surface = render_with_step2_visual
        return True


__all__ = [
    "DIRECT_NETWORK_ENDPOINTS_ADDED", "ESPN_LOGO_CDN_TEMPLATE", "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS", "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION", "PHOENIX_TZ", "SPORTSBOOK_PROJECTION_INFLUENCE", "STEP2_CSS",
    "TARGET_PAGE", "build_game_card_html", "install_games_on_day_step2_visual",
]
