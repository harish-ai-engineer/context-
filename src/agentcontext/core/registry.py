"""A tiny, dependency-free plugin registry.

v0.1 ships one registry (parsers). The class is generic on purpose: chunkers,
embedders, retrievers and exporters get their own instances in later versions
without reworking the architecture.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str, obj: T | None = None) -> Callable[[T], T] | T:
        """Use directly ``reg.register("name", obj)`` or as a decorator."""
        if obj is not None:
            self._items[name] = obj
            return obj

        def deco(target: T) -> T:
            self._items[name] = target
            return target

        return deco

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(
                f"No {self.kind} named {name!r}. Available: {sorted(self._items)}"
            ) from None

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return name in self._items


# The one v0.1 registry.
parsers: Registry = Registry("parser")
