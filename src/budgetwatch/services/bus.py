from __future__ import annotations

from collections.abc import Callable


class DataBus:
    """Application-wide change notifications. Qt-free so services stay testable."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)
        return callback

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        self._listeners = [fn for fn in self._listeners if fn is not callback]

    def emit(self) -> None:
        for callback in list(self._listeners):
            callback()
