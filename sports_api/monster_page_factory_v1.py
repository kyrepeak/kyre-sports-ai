"""Monster Page Factory V1.

Declarative, sport-agnostic page assembly for Kyre Sports AI.

This module intentionally contains **no sports model logic**, no schedule/odds
fetching, no Streamlit import, and no router mutation. A sport-specific adapter
provides a payload; the factory validates that payload against a reusable page
specification and dispatches ready components to injected renderers.

That separation lets future pages reuse the same proven page bones without
rewriting projection math, market logic, or data collection.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

FACTORY_VERSION = "MONSTER_PAGE_FACTORY_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False


class ComponentKind(StrEnum):
    MATCHUP_HEADER = "matchup_header"
    PLAYER_HEADER = "player_header"
    TEAM_COMPARISON = "team_comparison"
    RECENT_FORM = "recent_form"
    INJURIES = "injuries"
    ENVIRONMENT = "environment"
    MARKET_CONTEXT = "market_context"
    PROJECTION = "projection"
    SIMULATION = "simulation"
    CONFIDENCE = "confidence"
    SOURCES = "sources"
    DIAGNOSTICS = "diagnostics"


class ComponentState(StrEnum):
    READY = "ready"
    MISSING_REQUIRED = "missing_required"
    SKIPPED_OPTIONAL = "skipped_optional"


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    """One reusable page block.

    ``data_key`` is the only payload contract. The component never knows how
    data was collected or modeled.
    """

    key: str
    title: str
    kind: ComponentKind
    data_key: str
    required: bool = False
    description: str = ""
    expanded: bool = True
    columns: int = 1
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("component key must be non-empty")
        if not self.data_key.strip():
            raise ValueError("component data_key must be non-empty")
        if int(self.columns) < 1:
            raise ValueError("component columns must be >= 1")

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "kind": self.kind.value,
            "data_key": self.data_key,
            "required": self.required,
            "description": self.description,
            "expanded": self.expanded,
            "columns": self.columns,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class PageSpec:
    page_id: str
    title: str
    sport: str
    market: str
    components: tuple[ComponentSpec, ...]
    factory_version: str = FACTORY_VERSION
    subtitle: str = ""

    def __post_init__(self) -> None:
        if not self.page_id.strip():
            raise ValueError("page_id must be non-empty")
        if not self.title.strip():
            raise ValueError("page title must be non-empty")
        if not self.sport.strip():
            raise ValueError("sport must be non-empty")
        if not self.market.strip():
            raise ValueError("market must be non-empty")
        keys = [component.key for component in self.components]
        if len(keys) != len(set(keys)):
            raise ValueError("component keys must be unique within a page")

    def as_dict(self) -> dict[str, Any]:
        return {
            "factory_version": self.factory_version,
            "page_id": self.page_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "sport": self.sport,
            "market": self.market,
            "components": [component.as_dict() for component in self.components],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        }


@dataclass(frozen=True, slots=True)
class ComponentPlan:
    spec: ComponentSpec
    state: ComponentState
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.spec.key,
            "title": self.spec.title,
            "kind": self.spec.kind.value,
            "data_key": self.spec.data_key,
            "required": self.spec.required,
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class PagePlan:
    spec: PageSpec
    components: tuple[ComponentPlan, ...]

    @property
    def ready(self) -> bool:
        return not any(
            component.state is ComponentState.MISSING_REQUIRED
            for component in self.components
        )

    @property
    def ready_keys(self) -> tuple[str, ...]:
        return tuple(
            component.spec.key
            for component in self.components
            if component.state is ComponentState.READY
        )

    @property
    def missing_required(self) -> tuple[str, ...]:
        return tuple(
            component.spec.data_key
            for component in self.components
            if component.state is ComponentState.MISSING_REQUIRED
        )

    @property
    def skipped_optional(self) -> tuple[str, ...]:
        return tuple(
            component.spec.data_key
            for component in self.components
            if component.state is ComponentState.SKIPPED_OPTIONAL
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "factory_version": self.spec.factory_version,
            "page_id": self.spec.page_id,
            "sport": self.spec.sport,
            "market": self.spec.market,
            "ready": self.ready,
            "ready_keys": list(self.ready_keys),
            "missing_required": list(self.missing_required),
            "skipped_optional": list(self.skipped_optional),
            "components": [component.as_dict() for component in self.components],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        }


@dataclass(frozen=True, slots=True)
class RenderContext:
    page: PageSpec
    payload: Mapping[str, Any]
    helpers: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RenderResult:
    page_id: str
    rendered: tuple[str, ...]
    skipped_optional: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "rendered": list(self.rendered),
            "skipped_optional": list(self.skipped_optional),
        }


class PageFactoryError(RuntimeError):
    pass


ComponentRenderer = Callable[[ComponentSpec, Any, RenderContext], None]


def _has_value(payload: Mapping[str, Any], key: str) -> bool:
    if key not in payload:
        return False
    value = payload[key]
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return bool(value)
    return True


def compile_page(spec: PageSpec, payload: Mapping[str, Any]) -> PagePlan:
    """Create a deterministic read-only plan for a page payload."""
    plans: list[ComponentPlan] = []
    for component in spec.components:
        if _has_value(payload, component.data_key):
            plans.append(
                ComponentPlan(
                    spec=component,
                    state=ComponentState.READY,
                    value=payload[component.data_key],
                )
            )
        elif component.required:
            plans.append(
                ComponentPlan(
                    spec=component,
                    state=ComponentState.MISSING_REQUIRED,
                )
            )
        else:
            plans.append(
                ComponentPlan(
                    spec=component,
                    state=ComponentState.SKIPPED_OPTIONAL,
                )
            )
    return PagePlan(spec=spec, components=tuple(plans))


def render_page(
    spec: PageSpec,
    payload: Mapping[str, Any],
    renderers: Mapping[ComponentKind | str, ComponentRenderer],
    *,
    helpers: Mapping[str, Any] | None = None,
) -> RenderResult:
    """Render only validated components through injected renderers.

    The function does not import Streamlit and does not mutate ``payload``.
    A Streamlit page can inject Streamlit-aware renderers; tests or other UIs
    can inject lightweight renderers instead.
    """
    plan = compile_page(spec, payload)
    if not plan.ready:
        missing = ", ".join(plan.missing_required)
        raise PageFactoryError(
            f"{spec.page_id} cannot render; missing required payload: {missing}"
        )

    context = RenderContext(page=spec, payload=payload, helpers=helpers or {})
    rendered: list[str] = []
    normalized_renderers = {
        (key.value if isinstance(key, ComponentKind) else str(key)): value
        for key, value in renderers.items()
    }

    for component in plan.components:
        if component.state is not ComponentState.READY:
            continue
        renderer = normalized_renderers.get(component.spec.kind.value)
        if renderer is None:
            raise PageFactoryError(
                f"no renderer registered for component kind {component.spec.kind.value!r}"
            )
        renderer(component.spec, component.value, context)
        rendered.append(component.spec.key)

    return RenderResult(
        page_id=spec.page_id,
        rendered=tuple(rendered),
        skipped_optional=plan.skipped_optional,
    )


def with_component(
    spec: PageSpec,
    component: ComponentSpec,
    *,
    after: str | None = None,
) -> PageSpec:
    """Return a new spec with one component added; never mutate the original."""
    if any(existing.key == component.key for existing in spec.components):
        raise ValueError(f"component key already exists: {component.key}")
    components = list(spec.components)
    if after is None:
        components.append(component)
    else:
        indexes = [idx for idx, item in enumerate(components) if item.key == after]
        if not indexes:
            raise ValueError(f"after component not found: {after}")
        components.insert(indexes[0] + 1, component)
    return replace(spec, components=tuple(components))


def _sport_label(sport: str) -> str:
    value = " ".join(str(sport or "").strip().split())
    if not value:
        raise ValueError("sport must be non-empty")
    common = {
        "cfb": "College Football",
        "nfl": "NFL",
        "mlb": "MLB",
        "nba": "NBA",
        "wnba": "WNBA",
        "nhl": "NHL",
    }
    return common.get(value.lower(), value)


def _slug(value: str) -> str:
    return "-".join(
        part for part in "".join(
            char.lower() if char.isalnum() else " " for char in value
        ).split()
        if part
    )


def _common_game_components(*, projection_title: str) -> tuple[ComponentSpec, ...]:
    return (
        ComponentSpec(
            "matchup",
            "Matchup",
            ComponentKind.MATCHUP_HEADER,
            "matchup",
            required=True,
        ),
        ComponentSpec(
            "team-comparison",
            "Team Comparison",
            ComponentKind.TEAM_COMPARISON,
            "team_comparison",
            required=True,
            columns=2,
        ),
        ComponentSpec(
            "injuries",
            "Injuries & Availability",
            ComponentKind.INJURIES,
            "injuries",
        ),
        ComponentSpec(
            "environment",
            "Game-Day Environment",
            ComponentKind.ENVIRONMENT,
            "environment",
        ),
        ComponentSpec(
            "market",
            "Market Context",
            ComponentKind.MARKET_CONTEXT,
            "market",
        ),
        ComponentSpec(
            "projection",
            projection_title,
            ComponentKind.PROJECTION,
            "projection",
            required=True,
        ),
        ComponentSpec(
            "simulation",
            "Simulation",
            ComponentKind.SIMULATION,
            "simulation",
        ),
        ComponentSpec(
            "confidence",
            "Confidence & Risk",
            ComponentKind.CONFIDENCE,
            "confidence",
        ),
        ComponentSpec(
            "sources",
            "Sources & Data Quality",
            ComponentKind.SOURCES,
            "sources",
        ),
        ComponentSpec(
            "diagnostics",
            "Monster Diagnostics",
            ComponentKind.DIAGNOSTICS,
            "diagnostics",
            expanded=False,
        ),
    )


def totals_page(sport: str, *, title: str | None = None) -> PageSpec:
    label = _sport_label(sport)
    return PageSpec(
        page_id=f"{_slug(label)}-game-total",
        title=title or f"{label} Over/Under",
        subtitle="Reusable Monster totals-page shell",
        sport=label,
        market="Game Total",
        components=_common_game_components(projection_title="Total Projection"),
    )


def moneyline_page(sport: str, *, title: str | None = None) -> PageSpec:
    label = _sport_label(sport)
    return PageSpec(
        page_id=f"{_slug(label)}-moneyline",
        title=title or f"{label} Moneyline",
        subtitle="Reusable Monster moneyline-page shell",
        sport=label,
        market="Moneyline",
        components=_common_game_components(projection_title="Win Projection"),
    )


def player_prop_page(
    sport: str,
    prop: str,
    *,
    title: str | None = None,
) -> PageSpec:
    label = _sport_label(sport)
    prop_label = " ".join(str(prop or "").strip().split())
    if not prop_label:
        raise ValueError("prop must be non-empty")
    return PageSpec(
        page_id=f"{_slug(label)}-{_slug(prop_label)}-prop",
        title=title or f"{label} {prop_label}",
        subtitle="Reusable Monster player-prop shell",
        sport=label,
        market=prop_label,
        components=(
            ComponentSpec(
                "player",
                "Player",
                ComponentKind.PLAYER_HEADER,
                "player",
                required=True,
            ),
            ComponentSpec(
                "recent-form",
                "Recent Form",
                ComponentKind.RECENT_FORM,
                "recent_form",
            ),
            ComponentSpec(
                "matchup",
                "Matchup",
                ComponentKind.MATCHUP_HEADER,
                "matchup",
                required=True,
            ),
            ComponentSpec(
                "injuries",
                "Injuries & Availability",
                ComponentKind.INJURIES,
                "injuries",
            ),
            ComponentSpec(
                "market",
                "Market Context",
                ComponentKind.MARKET_CONTEXT,
                "market",
            ),
            ComponentSpec(
                "projection",
                "Prop Projection",
                ComponentKind.PROJECTION,
                "projection",
                required=True,
            ),
            ComponentSpec(
                "simulation",
                "Simulation",
                ComponentKind.SIMULATION,
                "simulation",
            ),
            ComponentSpec(
                "confidence",
                "Confidence & Risk",
                ComponentKind.CONFIDENCE,
                "confidence",
            ),
            ComponentSpec(
                "sources",
                "Sources & Data Quality",
                ComponentKind.SOURCES,
                "sources",
            ),
        ),
    )


def page_from_preset(preset: str, sport: str, *, prop: str = "") -> PageSpec:
    normalized = str(preset or "").strip().lower().replace("_", "-")
    if normalized in {"totals", "total", "game-total", "over-under"}:
        return totals_page(sport)
    if normalized in {"moneyline", "ml"}:
        return moneyline_page(sport)
    if normalized in {"player-prop", "prop"}:
        return player_prop_page(sport, prop)
    raise ValueError(f"unknown page preset: {preset}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monster Page Factory V1")
    parser.add_argument("--preset", default="totals", choices=("totals", "moneyline", "player-prop"))
    parser.add_argument("--sport", default="NFL")
    parser.add_argument("--prop", default="Passing Yards")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    spec = page_from_preset(args.preset, args.sport, prop=args.prop)
    payload = spec.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{spec.title} • {len(spec.components)} reusable components • "
            f"factory={spec.factory_version}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "FACTORY_VERSION",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SOURCE_DATA",
    "PROJECTION_WEIGHT",
    "ComponentKind",
    "ComponentPlan",
    "ComponentSpec",
    "ComponentState",
    "PageFactoryError",
    "PagePlan",
    "PageSpec",
    "RenderContext",
    "RenderResult",
    "compile_page",
    "moneyline_page",
    "page_from_preset",
    "player_prop_page",
    "render_page",
    "totals_page",
    "with_component",
]
