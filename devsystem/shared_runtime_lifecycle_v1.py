"""System-neutral runtime lifecycle ordering for the shared production entrypoint."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

Hook = Callable[[], Any]
Renderer = Callable[[], Any]


def run_shared_runtime_lifecycle(
    *,
    render: Renderer,
    pre_render_hooks: Iterable[Hook] = (),
    post_render_hooks: Iterable[Hook] = (),
) -> Any:
    """Run shared pre-render hooks, the primary renderer, then post-render hooks."""
    for hook in tuple(pre_render_hooks):
        hook()

    result = render()

    for hook in tuple(post_render_hooks):
        hook()

    return result
