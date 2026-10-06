from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class ForbiddenGitHubEndpoint(RuntimeError):
    pass


@dataclass
class GithubClient:
    """Narrow GitHub adapter for Runless with Actions blocked at the choke point."""

    request: Callable[..., Any]

    @staticmethod
    def _guard_path(path: str) -> str:
        normalized = "/" + path.lstrip("/")
        if "/actions/" in normalized.lower():
            raise ForbiddenGitHubEndpoint("RUNLESS_GITHUB_ACTIONS_ENDPOINT_FORBIDDEN")
        return normalized

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", self._guard_path(path), **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", self._guard_path(path), **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", self._guard_path(path), **kwargs)
